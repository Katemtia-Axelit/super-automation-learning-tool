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

## Layout

- `harness.js` — runs the fixture matrix against `../hooks/redline-guard.js`
  and validates the `.cursor/hooks.json` shape.
- `fixtures/*.json` — one fixture per case. Each fixture declares the
  expected verdict. Use the canonical `tool_name` / `tool_input` envelope.
  Set `"rawStdin": true` and pass `"input": "<string>"` to test
  empty/malformed stdin behavior.
- `README.md` — this file.

## Running

From the repository root:

```
node .cursor/infra-tests/redline-guard/harness.js
```

Exit code `0` = all expected verdicts observed. `1` = at least one mismatch.
The harness prints a per-fixture result table and a final summary.