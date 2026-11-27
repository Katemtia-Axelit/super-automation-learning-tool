# 归档：2026-06 Tauri/Rust 桌面形态快照

> **本目录是历史快照，不是现行架构指引。**
> **不得**把本目录的任何内容作为当前产品形态、入口、路由或技术栈的事实引用。

## 来源

这些文件是从 `origin/master`（`095d83e`，Tauri v2 + React 18 + Rust actix-web 桌面版，
45 个 commit，2026-06-02 前后）**以文件快照方式**抢救过来的。

- 抢救方式：`git checkout origin/master -- <path>`（只取文件内容，**不产生 merge**，
  不要求两条历史有共同祖先）
- `origin/master` 与 `origin/main` **无共同祖先**（`git merge-base` 退出码 1），
  是两条完全独立的历史。**两者从未被合并，也不应被合并** —— 合并会得到一个
  同时含 `app/`(Rust) 与 `server/`(Flask)、两套前端、两套入口的混合 tree，
  既不能运行也不能测试。
- `origin/master` **仍保留在远端**，未被删除或改名（默认分支已切至 `main`）。

## 内容清单

| 路径 | 原路径 | 说明 |
|---|---|---|
| `CLAUDE.md` | `CLAUDE.md` | 桌面版时代的 Claude Code 指引 |
| `FRONTEND_ISSUES.md` | `FRONTEND_ISSUES.md` | 桌面版前端问题清单 |
| `agent/prompts/*.md` | `agent/prompts/*.md` | 5 个 Agent 提示词模板（`content_reviewer` / `knowledge_extractor` / `knowledge_qa` / `note_organizer` / `structure_reviewer`） |
| `docs/api-documentation.md` | `docs/api-documentation.md` | 桌面版 API 文档 |
| `docs/backend-research.md` | `docs/backend-research.md` | 桌面版后端调研 |
| `docs/superpowers/specs/2026-06-02-ai-agent-design.md` | 同名 | Agent 设计规格 |
| `docs/superpowers/plans/2026-06-02-ai-agent-implementation.md` | 同名 | Agent 实施计划 |

## 未抢救的内容

`origin/master` 的 `app/**`（约 95 个文件：Tauri + React + Rust actix-web 应用代码、
`Cargo.lock` ×2、`package-lock.json`、图标资源）**未抢救** —— 它是已废弃的产品形态，
且引入 Rust/Node 锁文件会给当前仓库带来无关的依赖噪音。

## 现行权威

- 现状：[`docs/CURRENT_PROJECT_STATE.md`](../../CURRENT_PROJECT_STATE.md)
- 架构：[`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- 导航与权威顺序：[`docs/README.md`](../../README.md)
- Agent 行为规范：仓库根 [`AGENTS.md`](../../../AGENTS.md)（**唯一权威**）
