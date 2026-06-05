# 外部 AI 协作与任务修改流程

当前 **Agent 只读（P1-6 已锁定）**：系统内 Agent 不能 process、不能写 vault、不能 import tasks。

离开开发环境后，如需**批量整理 / 优化任务**，请用 **网页端 AI（ChatGPT、Claude、Gemini 等）** 生成**草稿**，再在本地**人工**通过网页 UI 修改。

---

## 1. 为什么需要这套流程

| 事实 | 含义 |
|------|------|
| Agent 只读 | 不能在应用内自动改任务 |
| 网页端 AI 能力强 | 适合生成标题、标签、拆分建议 |
| 数据库不能给 AI 直接写 | 必须人工确认，避免误删/误改权重/破坏反馈记录 |
| `ai_workspace/` | 人工协作缓冲区，**无自动写入后端** |

---

## 2. 标准流程

```
① backup_user_data.bat          # 先备份
② export_tasks_for_ai.py        # 导出快照 → 00_context/
③ 把快照 + 需求发给网页端 AI
④ AI 输出 task_change_summary.md + task_patch.json
⑤ 存档：02_ai_outputs/（原始回复）、03_task_drafts/（JSON）
⑥ validate_task_patch.py        # 只校验，不写库
⑦ 人工阅读 summary
⑧ 网页「任务」页逐条编辑
⑨ 再 export 一次确认
⑩ backup_user_data.bat          # 改完再备份
```

---

## 3. 网页端 AI 标准提示词模板

复制以下内容，并附上 `tasks_snapshot_*.md` 或 `.json`：

```
你是我的学习任务整理助手。

我会给你一份当前任务快照，以及我的调整目标。

你的任务不是直接修改数据库，也不是输出 SQL，而是生成两个草稿文件：

1. task_change_summary.md
2. task_patch.json

要求：
- 只输出建议，不自动写入
- 不删除任务，只能建议 archive 或 split
- 不修改任务反馈记录（task_feedback_events）
- 不修改抽卡权重
- 不修改数据库
- 所有变更必须给出 reason
- 每条变更必须标注 risk_level：low / medium / high
- JSON 必须能被 validate_task_patch.py 校验
- version 必须是 task_patch_v1
- mode 必须是 manual_review_only

【我的调整目标】
（在这里写你的需求，例如：把英语四级任务标题统一、拆分为 25 分钟复习卡）

【任务快照】
（粘贴 export 出的内容或附件）
```

---

## 4. task_patch.json 标准格式

参考：`ai_workspace/03_task_drafts/task_patch.example.json`

```json
{
  "version": "task_patch_v1",
  "mode": "manual_review_only",
  "created_by": "external_ai",
  "changes": [
    {
      "operation": "update",
      "match_by": {
        "task_id": null,
        "title": "CET4-语法-非谓语动词与被动语态"
      },
      "new_fields": {
        "title": "CET4｜非谓语动词与被动语态复习卡",
        "estimated_minutes": 25,
        "tags": ["英语", "四级", "语法", "复习"],
        "priority": 8
      },
      "reason": "标题更清晰，标签更利于卡牌主题映射，时间保持轻量。",
      "risk_level": "low",
      "manual_action": "请在网页任务编辑界面手动修改。"
    }
  ]
}
```

**operation 允许**：`add` · `update` · `split` · `merge` · `archive`

**禁止出现在 JSON 中**：`sql`、`auto_import`、`delete_directly`、`change_weight`、`modify_feedback_events`、`direct_db_write`

---

## 5. task_change_summary.md 标准格式

```markdown
# 任务变更摘要

- 生成时间：2026-06-04
- 变更条数：3
- 最高风险：medium

## 变更 1（update · low）

- 匹配：标题「CET4-语法-…」
- 建议：改标题、加标签、25 分钟
- 原因：…
- 人工操作：任务页 → 编辑 → 保存

## 变更 2（split · medium）

…
```

---

## 6. 可以交给网页端 AI 的事

- 拆分过大的任务
- 合并重复任务（建议 merge，人工执行）
- 优化任务标题
- 补充标签（利于卡牌主题）
- 估算 / 调整预计时长建议
- 按学习目标重排优先级建议
- 生成复习卡草稿
- 把学习计划转成任务草稿列表

---

## 7. 不能交给网页端 AI 直接做的事

- ❌ 删除任务（仅建议 archive）
- ❌ 改 SQLite / 输出 SQL
- ❌ 改 `task_feedback_events`
- ❌ 改抽卡权重 / 算法
- ❌ 改计时历史
- ❌ 改 Agent 提示词（走设置页 P1-3）
- ❌ 自动写 vault
- ❌ 调用 import-tasks / 自动导入

---

## 8. 文件存放位置

| 内容 | 目录 |
|------|------|
| 任务快照 | `ai_workspace/00_context/` |
| 你的需求 | `ai_workspace/01_requests/` |
| AI 原始回复 | `ai_workspace/02_ai_outputs/` |
| task_patch.json | `ai_workspace/03_task_drafts/` |
| 确认后版本 | `ai_workspace/04_reviewed/` |
| 历史归档 | `ai_workspace/99_archive/` |

---

## 9. 人工执行修改步骤

1. 打开 `http://127.0.0.1:5000/` → **任务** Tab
2. 对照 `task_change_summary.md` 和 `task_patch.json`
3. 点击任务 **编辑**，逐条修改标题、时长、标签、优先级等
4. **split / merge**：新建任务或编辑现有任务，不要删库
5. **archive 建议**：可用「弃牌」移入弃牌堆，而非删除
6. 每轮改完：`export_tasks_for_ai.py` 对比快照
7. `backup_user_data.bat`

---

## 10. 一周稳定使用建议

- 大改前必备份
- 不要把未校验的 AI 输出当真实数据
- 单轮控制在 **5～20 条**变更
- `risk_level: high` 必须逐条仔细阅读
- 仍不会用 → 先只改 1 条练手

---

## 11. 本地命令

```bat
REM 导出（只读）
.venv\Scripts\python.exe scripts\export_tasks_for_ai.py

REM 校验（不写库）
.venv\Scripts\python.exe scripts\validate_task_patch.py

REM 指定文件校验
.venv\Scripts\python.exe scripts\validate_task_patch.py --file ai_workspace/03_task_drafts/task_patch.json
```

---

## 12. 与系统 API 的关系

本流程 **不会** 调用：

- `/api/agent/process`
- `/api/agent/import-tasks`
- `/api/agent/save-note`

任务修改仅通过网页 UI 的常规任务编辑 / 弃牌 / 完成等已有接口，由**你手动点击**触发。

---

## 相关文档

- [README.md](../README.md)
- [项目逻辑与阶段交接说明](项目逻辑与阶段交接说明.md)
- [ai_workspace/README.md](../ai_workspace/README.md)
