# INFRA V2 Phase 5B1R — Redline Guard Test Harness

This directory contains the project-local hard-enforcement test harness for
`.cursor/hooks/redline-guard.js`.

## Contract

- The hook is invoked as a Node.js script.
- It receives ONE JSON object on stdin: `{ "tool_name": "<name>", "tool_input": <object>, "cwd": "<path>", ... }`. **This is the real Cursor preToolUse envelope.**
- It must write EXACTLY ONE JSON object to stdout: `{ "permission": "allow" | "deny", "user_message"?: string, "agent_message"?: string }`.
- Exit code is ignored by the harness; only the stdout JSON is consumed.
- The harness NEVER performs a real mutation on a redline. The hook must enforce
  denials purely based on the JSON intent.

## Structural check

`harness.js` also validates that `.cursor/hooks.json` matches the **real Cursor
project-hook contract**:

```
{
  "version": 1,
  "hooks": {
    "<event>": [
      { "command": "...", "matcher": "..." }
    ]
  }
}
```

Phase 5B1 used a flat-array shape with per-entry `id` / `event` /
`permission` / `description` fields, which is **not** a supported Cursor
contract. The harness fails until that shape is corrected.

## Why project-local

- The project hook handles project-specific mutation intent only
  (e.g. writes/edits/deletes inside `src/notes/`, the DB family, or
  `config/config.json`; broad `git add .`-style commands that could capture
  them).
- Generic danger (rm -rf /, force-push, format, etc.) is owned by the
  user-global layer and is OUT OF SCOPE here.

## Content classes (2026-11-28)

The hook originally knew only **three exact paths**. The 2026-11-27 audit
proved that real leaks arrive as the *same kind of content at a different
path*:

| Shape | Example |
|---|---|
| note archive packed as zip | `data/backup/笔记(2).zip` |
| production DB copy hidden in an archive dir | `_archive/03_数据库备份/*.db` |
| course question bank | `data/*.txt`, `data/*.md` |
| vault at a historical landing spot | `src/notes_backup/`, `笔记处理系统/归档/` |

Measured with a 21-shape probe: **only 3 were denied**. The hook now also
enforces content classes, mirroring the CI's `PROTECTED_RE`:

- whole `data/` tree
- any `*.db` / `*.db-wal` / `*.db-shm`
- any `*.zip`
- vault-bearing directory names, at any depth
- `config/config.json`

## Two gates, one policy

| Gate | When | Enforces |
|---|---|---|
| `.cursor/hooks/redline-guard.js` | local, **before** the write | the above |
| `.github/workflows/ci.yml` (`redline-scan`) | remote, **after** the push | `PROTECTED_RE` |

A local gate looser than the remote one is not a defence — it is a false
sense of security. `consistency_probe.js` makes drift **detectable**: it
reads `PROTECTED_RE` straight out of `ci.yml` (no duplicated copy to rot)
and compares it against the hook's verdict for a 31-path corpus.

```
node .cursor/infra-tests/redline-guard/consistency_probe.js
```

Exit `0` = the two gates agree on every corpus path. This runs in CI on
every push.

## Layout

- `harness.js` — runs the fixture matrix against `../hooks/redline-guard.js`
  and validates the `.cursor/hooks.json` shape.
- `consistency_probe.js` — cross-checks the hook against CI's `PROTECTED_RE`.
- `fixtures/*.json` — one fixture per case. Each fixture declares the
  expected verdict. Use the canonical `tool_name` / `tool_input` envelope.
  Set `"rawStdin": true` and pass `"input": "<string>"` to test
  empty/malformed stdin behavior.
  A fixture may declare `"setupFiles": [{ "path": "...", "content": "..." }]`
  to materialise files on disk before the hook call (used by the broad-`git
  add` scenario, which inspects the real working tree). The harness removes
  them in a `finally` block, so it never leaves state behind.
- `README.md` — this file.

## Running

From the repository root:

```
node .cursor/infra-tests/redline-guard/harness.js
node .cursor/infra-tests/redline-guard/consistency_probe.js
```

Exit code `0` = all expected verdicts observed. `1` = at least one mismatch.
The harness prints a per-fixture result table and a final summary.