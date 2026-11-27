# M1 Sandbox Tests Report - LT_M1_SANDBOX_TESTS_AGENT_TOKEN_20261008


## TL;DR

- 4/4 isolation tests (toy-only) pass via pytest.
- 12/12 characterization tests pass via unittest (pre-existing files).
- All tests run in independent sandboxes (tempdir per test).
- Workspace dirty state preserved: only NEW untracked files added in tests/characterize/.
- No production code (server/, static/, src/, config/, data/) modified.


## Tests Added (untracked)

- tests/characterize/test_sandbox_isolation.py - 4 toy-only isolation tests
- tests/characterize/pytest.ini - pytest config
- tests/characterize/__init__.py - dir marker
- tests/characterize/REPORT_M1.md - this report

## Pre-Existing Tests Verified

- sandbox_env.py - sandbox materializer
- test_http_characterization.py - 9 tests for Tasks/Gacha/UI
- test_route_inventory.py - Factory covers all Legacy routes
- test_launcher_selection.py - env var mode selection
- test_launch_chain.py - real launch_server.py smoke test


## Safety Evidence

- tempdir per test, destroyed after
- SQL-only DB seeding; live DB never opened
- shutil.copyfile copies source; no symlinks/reparse
- Empty API keys in sandbox config
- available_port() avoids collisions
- Server terminated via terminate/wait/kill
- WAL/SHM only in sandbox (asserted)

## Legacy vs Factory Parity

Both serve identical behavior for characterized endpoints in sandbox:
- POST /api/tasks/<id>/complete - 200 with unlocked_tasks
- POST /api/tasks/<id>/skip - 200, no success_rate bump
- POST /api/tasks/<id>/refuse - 200, refusal_count++
- Blocked task - 400 with Chinese msg
- POST /api/tasks with prereqs - writes task_dependencies row
- Gacha draw/replace/statistics/invalid-pool
- Legacy compat routes (/api/config, /api/agent/agents, /api/prompts, /api/discard-pile, /api/dependencies)
- /api/agent/save-note is 403 in Factory (user policy)

Factory fully covers the Legacy route surface.


## Findings

- 9 redundant dev artifacts in tests/characterize/ (debug files, superseded builders).
  Not used by any test; can be cleaned out-of-band by Controller.
- Sandbox vault is empty; /api/agent/save-note is blocked. Production vault excluded.
- Legacy uses __file__-relative config; Factory uses CWD-relative. Both resolve to same
  path in sandbox because cwd=sandbox.

## What Did NOT Happen

- No git reset/clean/stash
- No production source modified
- No live DB, notes vault, or config.json read/written
- No remote Git operations
- No secrets, API keys, or .env touched


