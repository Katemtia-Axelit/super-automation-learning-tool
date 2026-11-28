#!/usr/bin/env node
// .cursor/infra-tests/redline-guard/consistency_probe.js
//
// Proves that the LOCAL content-class rules (.cursor/hooks/redline-guard.js)
// and the REMOTE scan regex (.github/workflows/ci.yml :: PROTECTED_RE)
// classify a corpus of paths IDENTICALLY.
//
// Why this exists (2026-11-28):
//   There are two redline gates:
//
//     1. .cursor/hooks/redline-guard.js   -> local, BEFORE the write
//     2. .github/workflows/ci.yml          -> remote, AFTER the push
//
//   On 2026-11-28 the two disagreed badly: the hook only knew three exact
//   paths, while CI knew whole content classes. The hook therefore allowed
//   18 of 21 real leak shapes. A local gate that is looser than the remote
//   gate is not a defence — it is a false sense of security.
//
//   This probe makes the disagreement detectable. It reads PROTECTED_RE
//   straight out of ci.yml (no duplicated copy to drift), compiles it, and
//   compares its verdict against the hook's verdict for every corpus path.
//
//   Exit code:
//     0 = the two gates agree on every corpus path
//     1 = at least one disagreement (details printed)
//     2 = the probe itself failed (ci.yml unreadable, regex invalid, ...)
//
// Read-only: it never mutates the repository and never touches a redline.

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const HERE = __dirname;
const PROJECT_ROOT = path.resolve(HERE, '..', '..', '..');
const HOOK = path.resolve(HERE, '..', '..', 'hooks', 'redline-guard.js');
const CI_YML = path.resolve(PROJECT_ROOT, '.github', 'workflows', 'ci.yml');

// ---------------------------------------------------------------------------
// Corpus. Each entry is a path relative to the project root.
//
// `expect` is what BOTH gates must decide. It is derived from the project's
// documented redline policy (canonical redlines + content classes), not
// from either implementation — so the probe is a real cross-check, not a
// tautology.
// ---------------------------------------------------------------------------
const CORPUS = [
    // --- canonical redlines: must DENY ---
    { path: 'src/notes/vault/a.md', expect: 'deny' },
    { path: 'src/notes/vault/deep/nested/b.md', expect: 'deny' },
    { path: 'data/task_publisher.db', expect: 'deny' },
    { path: 'data/task_publisher.db-wal', expect: 'deny' },
    { path: 'data/task_publisher.db-shm', expect: 'deny' },
    { path: 'config/config.json', expect: 'deny' },

    // --- content class: data/ tree: must DENY ---
    { path: 'data/imports/course.md', expect: 'deny' },
    { path: 'data/backup/notes.zip', expect: 'deny' },
    { path: 'data/nested/deep/file.txt', expect: 'deny' },

    // --- content class: any .db / .zip: must DENY ---
    { path: 'archive.zip', expect: 'deny' },
    { path: 'sub/dir/archive.zip', expect: 'deny' },
    { path: 'root.db', expect: 'deny' },
    { path: 'root.db-wal', expect: 'deny' },
    { path: 'root.db-shm', expect: 'deny' },
    { path: '_archive/03_x/task.db', expect: 'deny' },

    // --- content class: vault-bearing directory names: must DENY ---
    { path: 'notes_backup/a.md', expect: 'deny' },
    { path: 'src/notes_backup/a.md', expect: 'deny' },
    { path: 'x/notes_backup/deep/a.md', expect: 'deny' },
    { path: '笔记备份/a.md', expect: 'deny' },
    { path: 'x/笔记_backup/a.md', expect: 'deny' },
    { path: 'x/备份/a.md', expect: 'deny' },
    { path: 'x/vault/a.md', expect: 'deny' },
    { path: '笔记处理系统/归档/a.zip', expect: 'deny' },
    { path: 'x/笔记处理系统/笔记/a.md', expect: 'deny' },
    { path: 'x/笔记处理系统/已分类/a.md', expect: 'deny' },

    // --- ordinary project files: must ALLOW ---
    { path: 'static/app.js', expect: 'allow' },
    { path: 'README.md', expect: 'allow' },
    { path: 'docs/CURRENT_PROJECT_STATE.md', expect: 'allow' },
    { path: 'server/backend_api.py', expect: 'allow' },
    { path: 'config/config.example.json', expect: 'allow' },
    { path: 'tests/e2e-manual.js', expect: 'allow' }
];

function readProtectedRe() {
    if (!fs.existsSync(CI_YML)) {
        console.error('consistency: missing ' + CI_YML);
        process.exit(2);
    }
    const raw = fs.readFileSync(CI_YML, 'utf8');
    // PROTECTED_RE: '<regex>'   (single-quoted YAML scalar)
    const m = /^([ \t]*)PROTECTED_RE:[ \t]*'((?:[^']|'')*)'[ \t]*$/m.exec(raw);
    if (!m) {
        console.error('consistency: could not find a single-quoted PROTECTED_RE in ci.yml');
        process.exit(2);
    }
    return m[2].replace(/''/g, "'");
}

function hookVerdict(relPath) {
    const envelope = JSON.stringify({
        tool_name: 'Write',
        tool_input: { file_path: relPath },
        cwd: PROJECT_ROOT
    });
    const res = spawnSync(process.execPath, [HOOK], {
        input: envelope,
        encoding: 'utf8',
        maxBuffer: 4 * 1024 * 1024
    });
    try {
        return JSON.parse(res.stdout).permission;
    } catch (_) {
        return 'ERROR';
    }
}

function main() {
    const protectedRe = readProtectedRe();
    let ciRe;
    try {
        ciRe = new RegExp(protectedRe);
    } catch (err) {
        console.error('consistency: PROTECTED_RE is not a valid regex: ' + err.message);
        process.exit(2);
    }

    console.log('PROTECTED_RE = ' + protectedRe);
    console.log('');

    let mismatches = 0;
    let policyViolations = 0;

    for (const item of CORPUS) {
        const ciVerdict = ciRe.test(item.path) ? 'deny' : 'allow';
        const hookV = hookVerdict(item.path);
        const agree = ciVerdict === hookV;
        const policyOk = ciVerdict === item.expect && hookV === item.expect;
        if (!agree) mismatches++;
        if (!policyOk) policyViolations++;

        const status = (agree && policyOk) ? 'OK  ' : 'BAD ';
        const note = agree ? '' : '  <-- GATES DISAGREE';
        const policyNote = policyOk ? '' : '  <-- POLICY VIOLATION';
        console.log(
            `${status} ${item.path.padEnd(46)} expect=${item.expect.padEnd(5)} ` +
            `ci=${ciVerdict.padEnd(5)} hook=${hookV.padEnd(5)}${note}${policyNote}`
        );
    }

    console.log('');
    console.log(`corpus=${CORPUS.length} gate-disagreements=${mismatches} policy-violations=${policyViolations}`);
    if (mismatches > 0 || policyViolations > 0) {
        console.log('consistency: FAILED — the two redline gates are not equivalent');
        process.exit(1);
    }
    console.log('consistency: PASSED — local hook and remote CI regex agree on every corpus path');
    process.exit(0);
}

main();
