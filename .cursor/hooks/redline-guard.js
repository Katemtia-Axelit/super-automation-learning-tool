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

// caseFold for Windows-style comparison
function caseFold(s) {
    return isWindows() ? String(s).toLowerCase() : String(s);
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