# ai_workspace — 外部 AI 协作缓冲区

本目录**不接自动写入**。仅用于：导出任务快照 → 网页端 AI 生成草稿 → 人工校验 → 在网页 UI 手动改任务。

## 目录说明

| 目录 | 用途 |
|------|------|
| `00_context/` | 任务快照、项目/阶段说明（由 `export_tasks_for_ai.py` 写入） |
| `01_requests/` | 你写给网页端 AI 的需求说明 |
| `02_ai_outputs/` | 网页端 AI 的原始回复存档 |
| `03_task_drafts/` | AI 整理后的 `task_patch.json` 草稿 |
| `04_reviewed/` | 你确认过、准备执行的版本 |
| `99_archive/` | 历史协作记录归档 |

## 快速流程

```bat
.venv\Scripts\python.exe scripts\export_tasks_for_ai.py
.venv\Scripts\python.exe scripts\validate_task_patch.py
```

详细步骤见：`docs/外部AI协作与任务修改流程.md`

## 红线

- 不要让 AI 直接写 `data/task_publisher.db`
- 不要调用 `/api/agent/import-tasks`
- 不要让 AI 自动写 vault
- 所有变更必须人工在网页任务界面确认后执行
