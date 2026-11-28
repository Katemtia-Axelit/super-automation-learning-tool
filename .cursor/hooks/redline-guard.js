#!/usr/bin/env node
// .cursor/hooks/redline-guard.js
//
// INFRA V2 Phase 5B1R - Project-local hard redline enforcement.
//
// Reads ONE JSON object from stdin describing a Cursor preToolUse invocation,
// writes EXACTLY ONE JSON object to stdout describing the verdict.
//
// Contract (REAL Cursor preToolUse envelope):
//   stdin:
//     { "tool_name": "<name>",
//       "tool_input": { ... tool-specific payload ... },
//       "tool_use_id": "<uuid>",
//       "cwd": "<project root>",
//       ... }
//
//   stdout:
//     { "permission": "allow" | "deny",
//       "user_message"?: string,
//       "agent_message"?: string }
//
// Project-local scope (mutation-only registration):
//   - Hard-denies mutation of src/notes/** (Obsidian vault red line).
//   - Hard-denies mutation of data/task_publisher.db and its WAL/SHM siblings.
//   - Hard-denies mutation of config/config.json.
//   - Hard-denies shell mutations targeting the same set
//     (git add, git add -f, git mv, Remove-Item / rm / del, redirections).
//   - For broad git commands (git add ., git add -A, git commit -a), runs
//     read-only preconditions: git ls-files + git diff --cached. If a
//     protected path is tracked or staged, deny. Otherwise allow.
//   - Allows every other intent. Generic danger (rm -rf /, force-push, etc.)
//     is owned by the user-global layer and is NOT handled here.
//
// Failure policy (mutation-only registration -> fail-closed):
//   - stdin read failure              -> DENY
//   - empty stdin                     -> DENY
//   - JSON parse failure              -> DENY
//   - schema mismatch (not an object) -> DENY
//   - missing tool_name              -> DENY
//   - missing required input fields  -> DENY
//   - any unexpected internal error  -> DENY
//
// CONTRACT: This file is the source of truth for project redline enforcement.
// Cursor cannot self-authorize. There is no in-Cursor bypass. Authorized
// out-of-band mutation is applied by the Controller/user.

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

// ---------------------------------------------------------------- constants

const HOOK_DIR = __dirname;                              // .../.cursor/hooks
const PROJECT_ROOT = path.resolve(HOOK_DIR, '..', '..'); // <repo> root

// Directory-prefix deny (any path under this prefix)
const NOTES_DIR_PREFIX = ['src', 'notes'];

// Exact-file deny (Windows-style; case-insensitive on Windows)
const EXACT_FILE_DENIES = [
    ['data', 'task_publisher.db'],
    ['data', 'task_publisher.db-wal'],
    ['data', 'task_publisher.db-shm'],
    ['config', 'config.json']
];

// ------------------------------------------------------------------
// Content-class deny (2026-11-28)
//
// 为什么需要这一层：
//   上面三条 canonical 红线只覆盖**精确路径**。但 2026-11-27 的实测证明，
//   真实泄露是以「同一类内容的不同落点」发生的：
//     * `data/backup/笔记(2).zip`      —— 笔记打包成 zip
//     * `_archive/03_数据库备份/*.db`  —— 生产库副本藏在归档目录
//     * `data/*.txt` / `data/*.md`     —— 课程题库
//     * `src/notes_backup/`、`笔记处理系统/归档/` —— vault 的其它落点
//
//   本地 hook 若只认精确路径，这些落点**全部放行**（实测 21 个泄露形态
//   只有 3 个被拦）。而 CI 的 `redline-scan` 已经按内容类别拦截 ——
//   两道防线口径不一致，hook 就成了绕过 CI 的后门。
//
// 因此本节的规则集与 `.github/workflows/ci.yml` 的 `PROTECTED_RE`
// **逐条对应**。CI 拦得住的，hook 也必须拦得住。
//
// 判定方式：把相对路径转成 POSIX 形态后逐条正则匹配。路径分段已做
// case-insensitive 比较（见 caseFold 注释），但这里的正则额外做
// 小写归一，以覆盖 `Notes.ZIP` 这类「扩展名大小写变体」。
// ------------------------------------------------------------------

// 目录前缀（相对项目根，POSIX 形态）。命中即 deny 整棵子树。
// 注意：前缀按**路径分段**匹配，不按字符串前缀。`src/notes_backup`
// 必须能被 `notes_backup` 规则命中，因此关键词走「任意层级」判定。
const PROTECTED_DIR_PREFIXES = [
    'src/notes',            // canonical：Obsidian vault
    'data'                  // 生产数据树（库、备份、导入、题库）
];

// 目录名关键词。命中路径中任意一段（或相邻多段）即 deny，不限位置、不限层级。
// 这是 CI 的 `(^|/)备份(/|$)` 与 `(^|/)vault(/|$)` 的等价物。
// `notes_backup` 放在这里而非 PROTECTED_DIR_PREFIXES，正是为了覆盖
// `src/notes_backup/` 这种「任意层级」落点。
const PROTECTED_DIR_SEGMENT_KEYWORDS = [
    '备份',
    'vault',
    'notes_backup',
    '笔记_backup',
    '笔记备份',
    '笔记处理系统/笔记',
    '笔记处理系统/归档',
    '笔记处理系统/已分类'
];

// 文件扩展名。命中即 deny —— 这是 CI 的 `\.db(-wal|-shm)?$` 与 `\.zip$` 的等价物。
// 注意 `\.db$` 不带 `$` 锚定前文，因此 `task_publisher.db-wal` 也会命中
// `\.db` 之后紧跟 `-wal` 的分支。
const PROTECTED_FILE_EXTENSIONS = [
    '.db',
    '.db-wal',
    '.db-shm',
    '.zip'
];

// 精确文件名（相对项目根）。命中即 deny。
const PROTECTED_EXACT_FILES = [
    'config/config.json'
];

// 归一化：转 POSIX、转小写、去掉末尾斜杠。
function normaliseRelPath(relPosix) {
    let s = String(relPosix).replace(/\\/g, '/');
    s = s.replace(/^\.\//, '');
    s = s.replace(/\/+$/, '');
    return s.toLowerCase();
}

// 判断一个（相对项目根的）POSIX 路径是否属于受保护内容类别。
// 返回 { kind, target } 或 null。
function classifyContentClass(relPosix) {
    const s = normaliseRelPath(relPosix);
    if (s === '') return null;

    // 1) 精确文件名
    for (const f of PROTECTED_EXACT_FILES) {
        if (s === f) return { kind: 'exact', target: f };
    }

    // 2) 目录前缀（目录本身或其子树）
    for (const d of PROTECTED_DIR_PREFIXES) {
        const dl = d.toLowerCase();
        if (s === dl || s.startsWith(dl + '/')) {
            return { kind: 'prefix', target: d };
        }
    }

    // 3) 目录名关键词（任意层级）
    const segs = s.split('/');
    for (const kw of PROTECTED_DIR_SEGMENT_KEYWORDS) {
        const kwParts = kw.toLowerCase().split('/');
        // 多段关键词（如 笔记处理系统/归档）要求相邻段匹配
        for (let i = 0; i + kwParts.length <= segs.length; i++) {
            let hit = true;
            for (let j = 0; j < kwParts.length; j++) {
                if (segs[i + j] !== kwParts[j]) { hit = false; break; }
            }
            if (hit) return { kind: 'keyword-dir', target: kw };
        }
    }

    // 4) 文件扩展名
    const base = segs[segs.length - 1];
    for (const ext of PROTECTED_FILE_EXTENSIONS) {
        if (base.endsWith(ext)) {
            return { kind: 'extension', target: ext };
        }
    }

    return null;
}

// Tools that mutate project files via a path-bearing field, using the REAL
// Cursor preToolUse envelope (tool_name -> tool_input[field]).
const PATH_FIELDS = {
    // Real Cursor mutation tools use tool_input.file_path. Keep path as a
    // compatibility fallback for older/synthetic envelopes.
    Write: ['file_path', 'path'],
    StrReplace: ['file_path', 'path'],
    Edit: ['file_path', 'path'],
    EditNotebook: ['file_path', 'path'],
    Delete: ['file_path', 'path'],
    'mcp__fs__write_file': ['path'],
    'mcp__fs__edit_file': ['path'],
    'mcp__fs__delete_file': ['path'],
    'mcp__filesystem__write_file': ['path'],
    'mcp__filesystem__edit_file': ['path'],
    'mcp__filesystem__delete_file': ['path']
};

// Tools this project hook never owns. The matcher restricts the hook to
// mutation tools, but the script also defends in depth: anything not in
// PATH_FIELDS and not a shell tool is also pass-through here, since the
// matcher prevents it from getting this far in real Cursor traffic.
const READ_ONLY_TOOLS = new Set([
    'Read', 'Grep', 'Glob', 'LS', 'List', 'Search', 'WebFetch', 'WebSearch'
]);

// Names that indicate a shell-equivalent mutation tool.
const SHELL_TOOLS = new Set(['Shell', 'Bash', 'bash', 'shell']);

// ---------------------------------------------------------------- utilities

function isWindows() {
    return process.platform === 'win32';
}

function normaliseSlashes(p) {
    return String(p).replace(/[\\/]+/g, '/');
}

// Split a path into segments, regardless of separator, and strip any
// ".."/"." segments, but keep the prefix. Returns an array of segments.
function splitSegments(p) {
    const n = normaliseSlashes(p).replace(/^\/+/, '').replace(/\/+$/, '');
    if (n.length === 0) return [];
    return n.split('/').filter((s) => s.length > 0);
}

// caseFold for path-segment comparison.
//
// A redline is a *content class*. If the guard only folds case on Windows,
// then the exact same bypass (`SRC\NOTES\Foo.md`) is allowed on Linux/macOS
// CI runners — the guard would be platform-dependent, i.e. weaker exactly
// where it is least visible. The 2026-11-28 CI run proved this: the
// `write-notes-case-insensitive` fixture expected `deny` and got `allow`
// on ubuntu-latest.
//
// Folding is therefore unconditional. This is *stricter* than the real
// filesystem on case-sensitive platforms, which is the correct direction
// for a guard: a false deny on Linux costs a user one workaround, while a
// false allow lets private data through.
function caseFold(s) {
    return String(s).toLowerCase();
}

function pathEqualSegments(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (caseFold(a[i]) !== caseFold(b[i])) return false;
    }
    return true;
}

function pathStartsWithSegments(segments, prefix) {
    if (segments.length < prefix.length) return false;
    for (let i = 0; i < prefix.length; i++) {
        if (caseFold(segments[i]) !== caseFold(prefix[i])) return false;
    }
    return true;
}

// Resolve a possibly-relative path to segments relative to the project root.
// Absolute paths are rebased onto the project root if they fall inside it,
// otherwise kept absolute (which is still inspectable as segments).
function resolveAgainstProject(p, cwd) {
    if (typeof p !== 'string' || p.length === 0) return null;
    let raw = p;
    let abs = false;
    if (/^[a-zA-Z]:[\\/]/.test(raw) || raw.startsWith('/') || raw.startsWith('\\')) {
        abs = true;
    }
    let resolved;
    if (abs) {
        // Treat as path.resolve but without requiring existence
        // Use posix-style normalisation for segment comparison
        const norm = path.posix.normalize(raw.replace(/\\/g, '/'));
        resolved = norm;
    } else {
        const base = (cwd && typeof cwd === 'string') ? cwd : PROJECT_ROOT;
        const joined = path.posix.join(base.replace(/\\/g, '/'), raw.replace(/\\/g, '/'));
        resolved = path.posix.normalize(joined);
    }
    return splitSegments(resolved);
}

// Compare a segment array against the project root segments, returning the
// segments relative to the project root if the path lives under it.
function relToProject(segments) {
    const rootSegs = splitSegments(PROJECT_ROOT);
    if (segments.length < rootSegs.length) return null;
    for (let i = 0; i < rootSegs.length; i++) {
        if (caseFold(segments[i]) !== caseFold(rootSegs[i])) return null;
    }
    return segments.slice(rootSegs.length);
}

// Decide if a given path segments array is a redline target.
function classifyBySegments(segments) {
    const rel = relToProject(segments);
    if (rel === null) {
        // Outside the project root, but still a candidate if it happens to
        // look like an exact protected file. We compare the full segments
        // against EXACT_FILE_DENIES too.
        for (const deny of EXACT_FILE_DENIES) {
            if (pathEqualSegments(segments, deny)) {
                return { kind: 'exact', target: deny.join('/') };
            }
        }
        return null;
    }
    // Directory-prefix match
    if (pathStartsWithSegments(rel, NOTES_DIR_PREFIX)) {
        return { kind: 'prefix', target: NOTES_DIR_PREFIX.join('/') };
    }
    // Exact-file match
    for (const deny of EXACT_FILE_DENIES) {
        if (pathEqualSegments(rel, deny)) {
            return { kind: 'exact', target: deny.join('/') };
        }
    }
    // Content-class match (2026-11-28) —— 与 CI 的 PROTECTED_RE 口径对齐。
    // 只在项目根之内判定；项目根之外的内容类别不在本 hook 的管辖范围
    // （例如用户主动写 ~/Downloads/x.zip 不属于本仓库红线）。
    const relPosix = rel.join('/');
    const cc = classifyContentClass(relPosix);
    if (cc) return cc;
    return null;
}

function classifyPath(p, cwd) {
    if (typeof p !== 'string' || p.length === 0) return null;
    const segs = resolveAgainstProject(p, cwd);
    if (!segs) return null;
    return classifyBySegments(segs);
}

// ---------------------------------------------------------------- shell parsing

// Tokenise a shell command line, respecting common quoting. The goal is
// to extract file arguments from likely mutation commands, not to be a
// full POSIX shell parser.
function tokenise(cmd) {
    const out = [];
    let cur = '';
    let quote = null; // '"', "'" or null
    for (let i = 0; i < cmd.length; i++) {
        const c = cmd[i];
        if (quote) {
            if (c === quote) { quote = null; continue; }
            cur += c;
            continue;
        }
        if (c === '"' || c === "'") { quote = c; continue; }
        if (c === '\\' && i + 1 < cmd.length) {
            cur += cmd[++i];
            continue;
        }
        if (c === ' ' || c === '\t' || c === '\n' || c === '\r') {
            if (cur.length > 0) { out.push(cur); cur = ''; }
            continue;
        }
        cur += c;
    }
    if (cur.length > 0) out.push(cur);
    return out;
}

// Find redirection targets in a command (>, >>, >&  and bare pipe). Returns
// the file path appearing on the right-hand side.
function findRedirectionTarget(cmd) {
    // Look for > (but not >>) and >> (append). The simplest pattern.
    const re = /(?:>>|>)\s*([^|&;\n]+)/g;
    const m = [];
    let mm;
    while ((mm = re.exec(cmd)) !== null) {
        m.push(mm[1].trim());
    }
    return m;
}

// Decide if a shell command is a mutation that targets a redline.
function classifyShell(cmd) {
    if (typeof cmd !== 'string' || cmd.length === 0) return null;
    const toks = tokenise(cmd);
    if (toks.length === 0) return null;
    const head = toks[0].toLowerCase();
    const headBase = head.split(/[\\/]/).pop();

    if (headBase === 'git') {
        const sub = (toks[1] || '').toLowerCase();
        // git add <path>  |  git add -f <path>  |  git add -A  |  git add .
        if (sub === 'add') {
            // Collect args after options. Options start with -.
            const paths = toks.slice(2).filter((t) => !t.startsWith('-'));
            if (paths.length === 0) {
                // No explicit paths => broad add; we must run precondition
                return { kind: 'broad-git-add' };
            }
            // `git add .` / `git add ./` / `git add ..` etc. are broad adds
            // expressed as a path, not as an explicit file list. Treating
            // "." as an explicit path would resolve to the project root and
            // miss every file underneath it — including protected ones.
            const isDotPath = paths.every((p) => p === '.' || p === './' || p === '..');
            if (isDotPath) {
                return { kind: 'broad-git-add' };
            }
            for (const p of paths) {
                const c = classifyPath(p, PROJECT_ROOT);
                if (c) return { kind: 'shell-path', target: c.target, source: p };
            }
            return null;
        }
        // git mv <src> <dst>
        if (sub === 'mv') {
            const paths = toks.slice(2);
            for (const p of paths) {
                const c = classifyPath(p, PROJECT_ROOT);
                if (c) return { kind: 'shell-path', target: c.target, source: p };
            }
            return null;
        }
        // git commit -a / --all
        if (sub === 'commit') {
            const hasAll = toks.slice(2).some((t) => t === '-a' || t === '--all');
            if (hasAll) return { kind: 'broad-git-commit' };
            return null;
        }
        // Any other git subcommand: no project-hook ownership
        return null;
    }

    if (headBase === 'rm' || headBase === 'del' || headBase === 'remove-item' ||
        headBase === 'ri' || headBase === 'erase' || headBase === 'unlink') {
        for (const t of toks.slice(1)) {
            if (t.startsWith('-')) continue;
            const c = classifyPath(t, PROJECT_ROOT);
            if (c) return { kind: 'shell-path', target: c.target, source: t };
        }
        return null;
    }

    // Copy / move / archive tools (2026-11-28).
    //
    // 为什么加这一组：真实泄露不只发生在 `git add`。
    // `cp data/backup/笔记(2).zip .` 会把受保护内容复制成普通文件；
    // `tar cf notes.zip src/notes` 会把 vault 打包。这些命令的共同点是
    // **命令行里出现了受保护路径**，因此对「所有参数」逐个判定即可。
    //
    // `cp` 的最后一个参数是**目标目录**，前面的参数是**源文件**。
    // 源与目标都要判定：`cp notes.zip archive/` 的目标是目录（`archive/`
    // 不是受保护类别），但源 `notes.zip` 是 —— 仍必须拦。
    const COPY_MOVE_TOOLS = new Set([
        'cp', 'copy', 'xcopy', 'robocopy', 'mv', 'move',
        'tar', 'zip', '7z', '7za', 'gzip', 'gunzip', 'rar'
    ]);
    if (COPY_MOVE_TOOLS.has(headBase)) {
        for (const t of toks.slice(1)) {
            // 选项与「选项=值」形式跳过
            if (t.startsWith('-')) continue;
            // `tar cf notes.zip src` —— `cf` 是 tar 的模式参数，不是路径。
            // 判定方式：若该 token 不含路径分隔符、且不是绝对路径、且
            // 不含扩展名，则它是子命令而非路径。含扩展名的（如 `notes.zip`）
            // 一律按路径判定。
            if (headBase === 'tar' && !t.includes('/') && !t.includes('\\') &&
                !/^\.[a-z0-9]+$/i.test(t) && !t.includes('.')) {
                continue;
            }
            const c = classifyPath(t, PROJECT_ROOT);
            if (c) return { kind: 'shell-path', target: c.target, source: t };
        }
        // tar/zip 的源目录可能不带扩展名（如 `tar cf out.tgz src/notes`）
        // —— 已由上面的路径判定覆盖（src/notes 命中前缀规则）。
        return null;
    }

    // Redirections anywhere in the command
    const reds = findRedirectionTarget(cmd);
    for (const r of reds) {
        // Skip the case where the RHS is not a path (e.g. >&2, /dev/null)
        if (r === '' || r === '&1' || r === '&2') continue;
        if (/^&?\d$/.test(r)) continue;
        if (r === '/dev/null' || r === 'NUL') continue;
        const c = classifyPath(r, PROJECT_ROOT);
        if (c) return { kind: 'shell-path', target: c.target, source: r };
    }

    return null;
}

// ---------------------------------------------------------------- preconditions

// Run a read-only git query and return stdout (or empty). Never mutates.
function gitQuery(args) {
    const proc = spawnSync('git', args, {
        cwd: PROJECT_ROOT,
        encoding: 'utf8',
        maxBuffer: 8 * 1024 * 1024
    });
    if (proc.status !== 0) return '';
    return (proc.stdout || '').toString();
}

function listTrackedOrStagedProtected() {
    // Tracked
    const tracked = gitQuery(['-c', 'core.quotepath=false', 'ls-files']);
    const staged = gitQuery(['-c', 'core.quotepath=false', 'diff', '--cached', '--name-only']);
    const lines = (tracked + '\n' + staged).split(/\r?\n/);
    const hits = [];
    for (const line of lines) {
        const c = classifyPath(line, PROJECT_ROOT);
        if (c) hits.push({ line, target: c.target });
    }
    return hits;
}

// List files that a broad `git add .` / `git add -A` would pick up:
// untracked, not-ignored, working-tree files.
//
// Why this is needed (2026-11-28):
//   The previous precondition only inspected `git ls-files` (already
//   tracked) and `git diff --cached` (already staged). That misses the
//   exact case that matters most:
//
//       $ cp ~/Downloads/notes.zip .        # untracked, not ignored
//       $ git add .                          # <- would stage it
//
//   An untracked-but-not-ignored file is invisible to both previous
//   queries, so the broad-add precondition passed and the protected
//   content was staged. `git ls-files --others --exclude-standard`
//   enumerates precisely that set.
//
//   `--exclude-standard` honours .gitignore, so legitimately ignored
//   working files (the whole vault, data/, ...) do NOT produce false
//   denials — they can never be staged by `git add .` anyway.
function listUntrackedNotIgnoredProtected() {
    const out = gitQuery([
        '-c', 'core.quotepath=false',
        'ls-files', '--others', '--exclude-standard'
    ]);
    const hits = [];
    for (const line of out.split(/\r?\n/)) {
        if (!line) continue;
        const c = classifyPath(line, PROJECT_ROOT);
        if (c) hits.push({ line, target: c.target });
    }
    return hits;
}

// ---------------------------------------------------------------- verdict helpers

function deny(redlineTarget, sourcePath) {
    const u = 'Project redline violation: the requested mutation targets "' +
        redlineTarget + '". This path is project-protected; ' +
        'Cursor cannot self-authorize a mutation on it. ' +
        'If this is intentional, apply the change out of band and request ' +
        'a Controller review.';
    const a = 'DENY (project redline "' + redlineTarget + '"). ' +
        'Do not attempt bypass; there is no in-Cursor escape hatch. ' +
        'If authorized, the Controller/user applies the change out of band. ' +
        'Attempted source: ' + JSON.stringify(sourcePath);
    return { permission: 'deny', user_message: u, agent_message: a };
}

function denyFailClosed(reason) {
    const u = 'Project redline guard could not validate this mutation request; ' +
        'blocked conservatively.';
    const a = 'FAIL-CLOSED. Do not retry with bypass. Report to Controller. ' +
        'Reason: ' + reason;
    return { permission: 'deny', user_message: u, agent_message: a };
}

function allow() {
    return { permission: 'allow' };
}

// ---------------------------------------------------------------- main

function readStdinSync() {
    if (process.stdin.isTTY) return '';
    const chunks = [];
    let total = 0;
    const MAX = 1024 * 1024;
    const buf = Buffer.alloc(4096);
    while (true) {
        const n = fs.readSync(0, buf, 0, buf.length);
        if (n <= 0) break;
        total += n;
        if (total > MAX) {
            chunks.push(Buffer.from(buf.subarray(0, n)));
            break;
        }
        chunks.push(Buffer.from(buf.subarray(0, n)));
    }
    return Buffer.concat(chunks).toString('utf8');
}

function emit(decision) {
    process.stdout.write(JSON.stringify(decision));
}

function parseRealEnvelope(raw) {
    // The REAL Cursor preToolUse envelope. Per the platform spec:
    //   { tool_name, tool_input, tool_use_id, cwd, ... }
    // Defensive: tolerate whitespace / BOM (some shells prepend \uFEFF).
    if (typeof raw !== 'string') return null;
    let s = raw;
    if (s.length > 0 && s.charCodeAt(0) === 0xFEFF) s = s.slice(1);
    s = s.trim();
    if (s.length === 0) return null;
    let input;
    try {
        input = JSON.parse(s);
    } catch (err) {
        return { __parseError: err.message };
    }
    if (input === null || typeof input !== 'object' || Array.isArray(input)) {
        return { __schemaError: 'envelope is not a JSON object' };
    }
    return input;
}

function main() {
    // --- 1) Read stdin. Failure here -> DENY (mutation-only registration).
    let raw = '';
    try {
        raw = readStdinSync();
    } catch (err) {
        emit(denyFailClosed('stdin read failure'));
        return;
    }

    // --- 2) Empty stdin on a mutation-only hook is unvalidated intent.
    if (!raw || raw.length === 0) {
        emit(denyFailClosed('empty stdin'));
        return;
    }

    // --- 3) Parse the REAL Cursor envelope. Failure -> DENY.
    const parsed = parseRealEnvelope(raw);
    if (parsed && parsed.__parseError) {
        emit(denyFailClosed('JSON parse failure'));
        return;
    }
    if (parsed && parsed.__schemaError) {
        emit(denyFailClosed('schema mismatch'));
        return;
    }
    if (!parsed) {
        emit(denyFailClosed('empty envelope'));
        return;
    }

    // --- 4) Extract canonical fields. Missing tool_name on a mutation-only
    //       hook is unvalidated intent -> DENY.
    const toolName = (typeof parsed.tool_name === 'string') ? parsed.tool_name : '';
    if (!toolName) {
        emit(denyFailClosed('missing tool_name'));
        return;
    }

    const toolInput = (parsed.tool_input && typeof parsed.tool_input === 'object' &&
                       !Array.isArray(parsed.tool_input))
        ? parsed.tool_input
        : {};
    const cwd = (typeof parsed.cwd === 'string') ? parsed.cwd : PROJECT_ROOT;

    // --- 5) Read-only tools would not match the preToolUse matcher in the
    //       registration, but if one ever does arrive, pass it through.
    if (READ_ONLY_TOOLS.has(toolName)) {
        emit(allow());
        return;
    }

    // --- 6) Path-bearing direct mutation tools.
    const fields = PATH_FIELDS[toolName];
    if (fields) {
        // For path-bearing mutation tools, every matched event MUST carry
        // a usable path. Missing path on a registered mutation tool is
        // unvalidated intent -> DENY.
        let sawAnyPath = false;
        for (const f of fields) {
            const v = toolInput[f];
            if (typeof v === 'string' && v.length > 0) {
                sawAnyPath = true;
                const c = classifyPath(v, cwd);
                if (c) {
                    emit(deny(c.target, v));
                    return;
                }
            }
        }
        if (!sawAnyPath) {
            emit(denyFailClosed('mutation tool missing required input'));
            return;
        }
        emit(allow());
        return;
    }

    // --- 7) Shell tool: parse the command from tool_input.command.
    if (SHELL_TOOLS.has(toolName)) {
        const cmd = (typeof toolInput.command === 'string') ? toolInput.command : '';
        // For shell mutation events, missing/empty command on a registered
        // mutation tool is unvalidated intent -> DENY.
        if (cmd.length === 0) {
            emit(denyFailClosed('shell mutation tool missing required input'));
            return;
        }
        const c = classifyShell(cmd);
        if (!c) {
            emit(allow());
            return;
        }
        if (c.kind === 'shell-path') {
            emit(deny(c.target, c.source));
            return;
        }
        if (c.kind === 'broad-git-add' || c.kind === 'broad-git-commit') {
            const hits = listTrackedOrStagedProtected();
            if (hits.length > 0) {
                emit(deny(hits[0].target, 'broad git command detected protected path: ' + hits[0].line));
                return;
            }
            // Also check untracked-but-not-ignored files: a broad add would
            // stage them, and they are invisible to ls-files / diff --cached.
            //
            // Only for broad ADD. `git commit -a` stages modifications to
            // ALREADY-TRACKED files only — it never stages untracked files.
            // Checking untracked for a commit would be a false positive.
            if (c.kind === 'broad-git-add') {
                const untracked = listUntrackedNotIgnoredProtected();
                if (untracked.length > 0) {
                    emit(deny(untracked[0].target,
                        'broad git command would stage an untracked, non-ignored protected path: ' +
                        untracked[0].line));
                    return;
                }
            }
            emit(allow());
            return;
        }
        emit(allow());
        return;
    }

    // --- 8) Unknown tool name on a mutation-only registration is
    //       unvalidated intent -> DENY. The matcher restricts traffic, so
    //       reaching this branch is unexpected; default closed.
    emit(denyFailClosed('unknown tool_name: ' + JSON.stringify(toolName)));
}

try {
    main();
} catch (err) {
    // Fail-CLOSED for any unexpected internal error. This hook is the
    // mutation-side of the redline; a hook crash must not silently allow.
    try { emit(denyFailClosed('internal error: ' + (err && err.message ? err.message : String(err)))); } catch (_) { /* swallow */ }
}