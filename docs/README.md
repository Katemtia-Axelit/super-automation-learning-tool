# docs/ Navigation

> **2026-11-27 增量（仓库治理梳理 S1–S5）**：本仓库已成为**公开事实源**。
> 默认分支 = `main`；`master`（2026-06 Tauri/Rust 形态）保留原名供追溯，不合并不删除。
> 新增公开骨架：`.github/`（CI + 4 类 Issue 模板 + PR 模板 + CODEOWNERS + CONTRIBUTING + SECURITY）、
> `docs/ROUNDTABLE_PROTOCOL.md`（圆桌规范权威）、`docs/external-write-log.md`（外部写操作审计台账）。
> **README 已重写为七段式，只做指针、不复制动态计数**。
> 当前门禁**并非全绿**（4 个 RED）——缺口清单与失败签名见 `CURRENT_PROJECT_STATE.md` 顶部 2026-11-27 节。

> **2026-11-23 增量（AR03-P5 收尾）**：P5 已完成 —— Legacy 最终收敛、Schema 一致性门禁、目录治理、架构文档重写与最终交付。
> 入口文档：**`ARCHITECTURE.md`**（当前架构权威，已按当前代码重写，含 5 张 Mermaid）、**`P5_FINAL_DELIVERY_REPORT_20261122.md`**（交付证据）、**`ARCHIVE_INDEX.md`**（归档批次索引）。
> 旧的 2026-10-04 架构快照已归档到 `architecture/2026-10-04_snapshot.md`，仅供追溯，**不得**作为事实引用。

> **2026-11-15 增量：实现状态/架构仍以 CURRENT_PROJECT_STATE.md 与 ARCHITECTURE.md 为入口；RPG_PROGRESSION_PRODUCT_SPEC_V1.0.md 是该模块冻结的产品设计权威；RPG_PROGRESSION_INTEGRATION_ROADMAP.md 是已登记但暂缓启动的工程路线图，不代表实现事实或开工授权。旧架构快照仍须按日期阅读。Controller 的继任运行手册入口仍见 C:\Users\wn\.cursor\controller-loop\START_HERE_CONTROLLER.md。**

Current source-of-truth entry points:

1. `CURRENT_PROJECT_STATE.md` — **唯一现状权威**：current implementation status, verified baselines, known gaps, and next sequence. **The topmost dated section is the live one; older dated sections are historical snapshots.**
2. `ARCHITECTURE.md` — the running system's implementation architecture (claims remain date-stamped and must be checked against current code).
3. `RPG_PROGRESSION_PRODUCT_SPEC_V1.0.md` — the frozen product-design authority for the RPG Progression module; it defines intended product behavior, not proof of implementation.
4. `RPG_PROGRESSION_INTEGRATION_ROADMAP.md` — the parked engineering backlog and proposed phase gates; not an implementation specification or authorization to start.
5. `ROUNDTABLE_PROTOCOL.md` — the roundtable protocol authority: seat identities, fixed comment header, idempotency-key definition, audit requirements.
6. `external-write-log.md` — the audit ledger for every write to GitHub (issues, PRs, repo settings, labels, pushes).

AR03-P5 deliverables (2026-11-23):

5. `P5_FINAL_DELIVERY_REPORT_20261122.md` — the P5 delivery report: todo-by-todo status, schema-gate conclusions, health contract, legacy-convergence dual-form evidence, reduced-motion evidence, acceptance evidence, known limits, red-line statement.
6. `P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md` — directory governance before/after, archive-batch inventory, `.run/baseline_verification_backup/` disposition, root-artifact cleanup record, restore guidance.
7. `ARCHIVE_INDEX.md` — index of every `_archive/` batch (01–11 + `src_tasks_legacy/`) with content classification and restore paths.
8. `architecture/2026-10-04_snapshot.md` — the **historical** (superseded) architecture snapshot; audit trail only, not current truth.

Implementation truth is established by `CURRENT_PROJECT_STATE.md`, `ARCHITECTURE.md`, current source code, and runtime evidence. Product-design truth for RPG Progression is established by `RPG_PROGRESSION_PRODUCT_SPEC_V1.0.md`. Other files under `docs/` remain background, work logs, evidence, research, dated reports, or historical deliverables unless promoted by an applicable source-of-truth document.

Use this order when documents disagree:

```text
CURRENT_PROJECT_STATE.md / ARCHITECTURE.md
→ current implementation and runtime evidence
→ dated reports / WORK_LOG / deliverables / research / old prompts
```

Do not delete, move, or bulk-rewrite historical documents merely because they are stale. They remain useful audit evidence. When an old report conflicts with the current source of truth, treat the old report as historical context.

Verification numbers are time-stamped evidence, not permanent invariants. Do not copy changing counts into Rules or Skills unless the count itself is part of an explicit contract.


## 2026-10-10 当前工程/Controller 增量导航

本项目的 Factory/Legacy 状态请先看 docs/CURRENT_PROJECT_STATE.md 顶部2026-10-10增量，其他历史 Snapshot 不等于实时结论。ChatGPT–Cursor Controller 跨代手册入口 C:\Users\wn\.cursor\controller-loop\START_HERE_CONTROLLER.md；最新事实文件 SUCCESSOR_DELTA_20261010.md、HANDOFF_CHANGELOG_20261010.md、TAKEOVER_STATE.json。注意新增 tests/characterize/test_m4_agent_prompts_contract.py 目前是 untracked，三项synthetic unittest实测3/3PASS，来源未知且Controller独立审查尚未 ACCEPTED；M4旧Review与总Batch OPEN 未自动改变。真实笔记、用户SQLite、生产配置未在本轮交接改动。
