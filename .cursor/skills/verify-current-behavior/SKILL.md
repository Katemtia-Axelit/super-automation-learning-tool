---
name: verify-current-behavior
description: Common verification SOPs (alwaysApply: false, explicit Controller request only)
disable-model-invocation: true
---

# verify-current-behavior Skill

**SKILL_CONTRACT_ID: LT_VERIFY_BEHAVIOR_V1**

## Verification Coverage

### Legacy E2E (`node tests/e2e-manual.js`)
- Requires the default legacy service to be running; uses playwright-core with the pinned chromium path.
- Treat it as an integration run with possible application-state side effects; snapshot/restore relevant state when the Task Contract requires it.

### P0 Verifier (`scripts/verify_p0_cleanup.py`)
- Treat its stored `ALL ASSERTIONS PASSED` line as the durable verdict; do not
  hardcode an assertion count in this Skill.
- Before rerunning it, classify its actual filesystem/runtime side effects for
  the current version instead of assuming it is zero-write.

### Gacha Golden (`scripts/phase2_gacha_golden.py`)
- Proves algorithm weight correctness only.
- Does NOT prove HTTP route parity.
- Do NOT hardcode PASS count.

## Zero-Write Verification Rules

- Prefer: `python -B`, in-memory compile, read-only stat
- Avoid: commands that write `.pyc`, cache, bytecode
