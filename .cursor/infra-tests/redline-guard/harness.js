#!/usr/bin/env node
// .cursor/infra-tests/redline-guard/harness.js
//
// INFRA V2 Phase 5B1R - Project redline guard test harness (REAL Cursor envelope).
//
// Runs the fixture matrix against .cursor/hooks/redline-guard.js and asserts
// that every fixture's expected verdict is produced.
//
// Contract (REAL Cursor preToolUse envelope):
//   stdin:
//     { "tool_name": "<name>",
//       "tool_input": { ... tool-specific payload ... },
//       "cwd": "<project root>",
//       "tool_use_id": "<uuid>",
//       ... }
//
//   stdout:
//     { "permission": "allow" | "deny",
//       "user_message"?: string,
//       "agent_message"?: string }
//
// Exit code:
//   0 = all expected verdicts observed
//   1 = at least one mismatch (details printed to stderr)
//   2 = harness itself failed (hook missing, bad JSON, etc.)
//
// The harness NEVER performs a real mutation on a redline. It only feeds
// synthetic hook-input JSON to the hook and reads back its decision.
//
// Fixture schema:
//   {
//     "name": "<id>",
//     "description": "...",
//     "input": <object-to-serialize-as-stdin>  OR  <string-raw-stdin>,
//     "expect": "allow" | "deny",
//     "rawStdin": <bool, optional, default false>
//   }
//
// When `rawStdin` is true, `input` is sent as-is (string); used to test
// empty/malformed stdin behavior.

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const HERE = __dirname;
const HOOK = path.resolve(HERE, '..', '..', 'hooks', 'redline-guard.js');
const FIXTURES_DIR = path.join(HERE, 'fixtures');
const HOOKS_JSON = path.resolve(HERE, '..', '..', 'hooks.json');

function listFixtures() {
    if (!fs.existsSync(FIXTURES_DIR)) {
        console.error('harness: missing fixtures directory: ' + FIXTURES_DIR);
        process.exit(2);
    }
    return fs.readdirSync(FIXTURES_DIR)
        .filter((f) => f.endsWith('.json'))
        .sort()
        .map((f) => path.join(FIXTURES_DIR, f));
}

function loadFixture(file) {
    const raw = fs.readFileSync(file, 'utf8');
    let parsed;
    try {
        parsed = JSON.parse(raw);
    } catch (err) {
        console.error('harness: bad JSON in ' + file + ': ' + err.message);
        process.exit(2);
    }
    if (!parsed.name || parsed.expect === undefined) {
        console.error('harness: fixture missing required fields: ' + file);
        process.exit(2);
    }
    if (parsed.expect !== 'allow' && parsed.expect !== 'deny') {
        console.error('harness: fixture expect must be "allow" or "deny": ' + file);
        process.exit(2);
    }
    return parsed;
}

// Substitute the directory's <PROJECT_ROOT> placeholders in string fields.
function expandInput(input, projectRoot) {
    if (typeof input === 'string') {
        return substituteProjectRoot(input, projectRoot);
    }
    if (input === null || typeof input !== 'object') return input;
    const clone = JSON.parse(JSON.stringify(input));
    if (typeof clone.cwd === 'string') {
        clone.cwd = substituteProjectRoot(clone.cwd, projectRoot);
    }
    if (clone.tool_input && typeof clone.tool_input === 'object') {
        for (const k of Object.keys(clone.tool_input)) {
            if (typeof clone.tool_input[k] === 'string') {
                clone.tool_input[k] = substituteProjectRoot(clone.tool_input[k], projectRoot);
            }
        }
    }
    return clone;
}

function substituteProjectRoot(s, projectRoot) {
    if (typeof s !== 'string') return s;
    return s.replace(/<PROJECT_ROOT>/g, projectRoot);
}

// Run the hook with the given stdin payload and capture the JSON decision.
function callHook(hookPath, stdinPayload) {
    if (!fs.existsSync(hookPath)) {
        return { ok: false, reason: 'HOOK_MISSING', path: hookPath };
    }
    const proc = spawnSync(process.execPath, [hookPath], {
        input: stdinPayload,
        encoding: 'utf8',
        timeout: 30000,
        maxBuffer: 1024 * 1024
    });
    if (proc.error) {
        return { ok: false, reason: 'SPAWN_ERROR', error: String(proc.error) };
    }
    if (proc.status !== 0) {
        return {
            ok: false,
            reason: 'NONZERO_EXIT',
            status: proc.status,
            stderr: (proc.stderr || '').trim()
        };
    }
    let out;
    try {
        out = JSON.parse(proc.stdout);
    } catch (err) {
        return {
            ok: false,
            reason: 'BAD_HOOK_OUTPUT',
            stdout: (proc.stdout || '').slice(0, 500),
            error: err.message
        };
    }
    if (out.permission !== 'allow' && out.permission !== 'deny') {
        return {
            ok: false,
            reason: 'INVALID_PERMISSION',
            permission: out.permission
        };
    }
    return { ok: true, decision: out };
}

// Validate the structure of .cursor/hooks.json against the REAL Cursor
// project-hook contract.
//
// Required:
//   { "version": 1,
//     "hooks": { "<event>": [ { "command": "...", "matcher": "..." }, ... ],
//                ... } }
function checkHooksJsonStructure() {
    if (!fs.existsSync(HOOKS_JSON)) {
        return { ok: false, reason: 'HOOKS_JSON_MISSING', path: HOOKS_JSON };
    }
    let parsed;
    try {
        parsed = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    } catch (err) {
        return { ok: false, reason: 'HOOKS_JSON_BAD_JSON', error: err.message };
    }
    if (!parsed || typeof parsed !== 'object') {
        return { ok: false, reason: 'HOOKS_JSON_NOT_OBJECT' };
    }
    if (parsed.version !== 1) {
        return { ok: false, reason: 'HOOKS_JSON_BAD_VERSION', got: parsed.version };
    }
    const hooks = parsed.hooks;
    if (!hooks || typeof hooks !== 'object' || Array.isArray(hooks)) {
        return {
            ok: false,
            reason: 'HOOKS_JSON_HOOKS_NOT_OBJECT_MAP',
            got: Array.isArray(hooks) ? 'array' : typeof hooks
        };
    }
    // Validate each event's array of entries
    for (const evt of Object.keys(hooks)) {
        const arr = hooks[evt];
        if (!Array.isArray(arr)) {
            return {
                ok: false,
                reason: 'HOOKS_JSON_EVENT_NOT_ARRAY',
                event: evt
            };
        }
        for (let i = 0; i < arr.length; i++) {
            const entry = arr[i];
            if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
                return {
                    ok: false,
                    reason: 'HOOKS_JSON_ENTRY_NOT_OBJECT',
                    event: evt,
                    index: i
                };
            }
            if (typeof entry.command !== 'string' || entry.command.length === 0) {
                return {
                    ok: false,
                    reason: 'HOOKS_JSON_ENTRY_MISSING_COMMAND',
                    event: evt,
                    index: i
                };
            }
            // matcher may be undefined for session lifecycle hooks but is
            // required for tool-mutation hooks
            if (evt === 'preToolUse' || evt === 'postToolUse') {
                if (typeof entry.matcher !== 'string') {
                    return {
                        ok: false,
                        reason: 'HOOKS_JSON_ENTRY_MISSING_MATCHER',
                        event: evt,
                        index: i
                    };
                }
            }
            // Reject invented fields that are NOT part of the real Cursor
            // contract: id, event (per-entry), permission, description
            const banned = ['id', 'event', 'permission', 'description'];
            for (const k of banned) {
                if (Object.prototype.hasOwnProperty.call(entry, k)) {
                    return {
                        ok: false,
                        reason: 'HOOKS_JSON_ENTRY_HAS_INVENTED_FIELD',
                        event: evt,
                        index: i,
                        field: k
                    };
                }
            }
        }
    }
    return { ok: true, config: parsed };
}

function main() {
    const fixtures = listFixtures();
    if (fixtures.length === 0) {
        console.error('harness: no fixtures found');
        process.exit(2);
    }

    const projectRoot = path.resolve(HERE, '..', '..', '..');

    // Step A: structural check of .cursor/hooks.json. This is the
    // DEFECT-A RED: must FAIL until hooks.json is rewritten to the real
    // event-map shape.
    const hooksCheck = checkHooksJsonStructure();

    const rows = [];
    let pass = 0;
    let fail = 0;
    let error = 0;

    // First row: structural config check. Use a synthetic fixture name so
    // it shows up in the same table.
    rows.push({
        name: 'config-shape-event-map',
        expected: 'ok (real hooks.json shape)',
        got: hooksCheck.ok
            ? 'ok (real hooks.json shape)'
            : ('ERROR(' + hooksCheck.reason + ')'),
        pass: hooksCheck.ok,
        error: !hooksCheck.ok
    });
    if (hooksCheck.ok) pass++; else error++;

    for (const file of fixtures) {
        const fx = loadFixture(file);
        // Skip the explicit 90- config-shape fixture; it is covered by the
        // structural check above.
        if (fx.name === 'config-shape-current-must-RED') continue;

        // Optional on-disk setup: some scenarios (e.g. "a broad `git add .`
        // would stage an untracked protected file") cannot be expressed as a
        // pure envelope, because the hook inspects the real working tree.
        //
        // `setupFiles` is an array of { path, content }. Paths are relative
        // to the project root. Files are created before the hook call and
        // removed afterwards, in a finally block, so the harness never
        // leaves state behind.
        const created = [];
        if (Array.isArray(fx.setupFiles)) {
            for (const sf of fx.setupFiles) {
                const abs = path.resolve(projectRoot, sf.path);
                if (!abs.startsWith(projectRoot)) {
                    console.error('harness: setupFiles path escapes project root: ' + sf.path);
                    process.exit(2);
                }
                try {
                    fs.mkdirSync(path.dirname(abs), { recursive: true });
                    fs.writeFileSync(abs, typeof sf.content === 'string' ? sf.content : '');
                    created.push(abs);
                } catch (err) {
                    console.error('harness: cannot create setupFiles entry ' + sf.path + ': ' + err.message);
                    for (const c of created) { try { fs.unlinkSync(c); } catch (_) { /* ignore */ } }
                    process.exit(2);
                }
            }
        }

        try {
            const expanded = expandInput(fx.input, projectRoot);
            const stdinPayload = fx.rawStdin === true
                ? (typeof expanded === 'string' ? expanded : JSON.stringify(expanded))
                : JSON.stringify(expanded);

            const result = callHook(HOOK, stdinPayload);
            if (!result.ok) {
                rows.push({
                    name: fx.name,
                    expected: fx.expect,
                    got: 'ERROR(' + result.reason + ')',
                    pass: false,
                    error: true
                });
                error++;
                continue;
            }
            const got = result.decision.permission;
            const ok = (got === fx.expect);
            rows.push({
                name: fx.name,
                expected: fx.expect,
                got: got,
                pass: ok,
                error: false
            });
            if (ok) pass++; else fail++;
        } finally {
            // Remove in reverse creation order, then prune the directories
            // that setupFiles created (but only those that are now empty —
            // never a directory that existed before).
            for (let i = created.length - 1; i >= 0; i--) {
                const p = created[i];
                try { fs.unlinkSync(p); } catch (_) { /* ignore */ }
                // Prune empty parent dirs up to (but not including) root.
                let dir = path.dirname(p);
                while (dir.startsWith(projectRoot) && dir !== projectRoot) {
                    let entries;
                    try { entries = fs.readdirSync(dir); } catch (_) { break; }
                    if (entries.length > 0) break;
                    try { fs.rmdirSync(dir); } catch (_) { break; }
                    dir = path.dirname(dir);
                }
            }
        }
    }

    // Pretty-print
    const w = (s, n) => String(s).padEnd(n);
    console.log('');
    console.log(w('FIXTURE', 56) + w('EXPECT', 32) + w('GOT', 12) + 'STATUS');
    console.log('-'.repeat(112));
    for (const r of rows) {
        const status = r.error
            ? 'ERR'
            : (r.pass ? 'OK' : 'FAIL');
        console.log(w(r.name, 56) + w(r.expected, 32) + w(r.got, 12) + status);
    }
    console.log('-'.repeat(112));
    console.log('Total: ' + rows.length + '  Pass: ' + pass + '  Fail: ' + fail + '  Error: ' + error);

    if (fail > 0 || error > 0) {
        process.exit(1);
    }
    process.exit(0);
}

main();