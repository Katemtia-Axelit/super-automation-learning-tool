---
name: inspect-project-state
description: Inspect current project state (alwaysApply: false, explicit Controller request only)
disable-model-invocation: true
---

# inspect-project-state Skill

**SKILL_CONTRACT_ID: LT_INSPECT_STATE_V1**

## SOP

1. Read `docs/CURRENT_PROJECT_STATE.md`
2. Read `docs/ARCHITECTURE.md`
3. Distinguish runtime vs factory verification entry points
4. Dynamic counts (test counts, etc.) are NOT written to skill; consult source
5. Conflict: verify against implementation code

## Usage

Invoked explicitly by Controller. Not auto-triggered.
