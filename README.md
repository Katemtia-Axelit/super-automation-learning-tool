# 超级自动化学习工具

> **封版状态（P1-Stable-1B）**：P1-Visual-1A ✅ · P1-Stable-1 ✅ · **当前为一周稳定使用封版**

个人超级自动化学习工具雏形：通过**任务池、抽卡、卡牌展示、计时、反馈、弃牌堆、状态评估**和 **Agent 只读资产浏览**，推动学习执行——不是普通 Todo，也不是纯抽卡小游戏。

---

## 5 分钟上手

| 操作 | 命令 |
|------|------|
| **启动** | 双击 `启动学习工具.bat` |
| **停止** | `scripts\stop_web_safe.bat` |
| **备份** | `scripts\backup_user_data.bat` |
| **换电脑验证** | `scripts\verify_transferred_project.bat` |
| **导出任务给外部 AI** | `.venv\Scripts\python.exe scripts\export_tasks_for_ai.py` |
| **校验 AI 任务草稿** | `.venv\Scripts\python.exe scripts\validate_task_patch.py` |

浏览器访问：`http://127.0.0.1:5000/`（端口见 `config/config.json`）

---

## 已锁定阶段（勿随意改动）

| 阶段 | 内容 |
|------|------|
| P0 | 主链路：任务、依赖、抽卡、日程、单脚本架构 |
| P1-1 | 质量底座 |
| P1-2 | 提示词只读 + 睡眠追踪 |
| P1-3 | 提示词可写 + 活动管理 |
| P1-4 | 弃牌堆浏览/恢复 |
| P1-5A | 状态评估 + 计时器 |
| P1-5B | 任务事件反馈（`task_feedback_events`） |
| P1-6 | 智能体只读（仅 GET） |
| P1-Visual-1 / 1A | 任务卡牌牌感系统 |
| P1-Stable-1 / 1B | 一周稳定封版 + 文档 + 外部 AI 协作流程 |

**暂不进入 P1-7**（Agent 受控执行）。

---

## 文档入口

| 文档 | 解决什么问题 |
|------|--------------|
| [一周稳定使用与换电脑迁移说明](docs/一周稳定使用与换电脑迁移说明.md) | 离开电脑前做什么、日常启停、备份恢复、换电脑、排错 |
| [项目文件结构与脚本使用说明](docs/项目文件结构与脚本使用说明.md) | 每个目录/脚本是干什么的 |
| [项目逻辑与阶段交接说明](docs/项目逻辑与阶段交接说明.md) | 产品闭环、数据关系、阶段红线、下一步规划 |
| [外部 AI 协作与任务修改流程](docs/外部AI协作与任务修改流程.md) | Agent 未内置执行时，如何用网页端 AI 改任务 |

---

## 外部 AI 协作改任务（当前推荐方式）

当前 **Agent 只读**，不能自动写 vault / 不能 import tasks。

1. 运行 `scripts\export_tasks_for_ai.py` → 快照在 `ai_workspace/00_context/`
2. 把快照 + 需求发给网页端 AI（见协作流程文档中的标准提示词）
3. AI 输出 `task_patch.json` → 存到 `ai_workspace/03_task_drafts/`
4. 运行 `scripts\validate_task_patch.py` 校验格式
5. **人工**在网页「任务」页逐条修改
6. 改完后运行 `scripts\backup_user_data.bat`

详见：[docs/外部AI协作与任务修改流程.md](docs/外部AI协作与任务修改流程.md)

---

## 封版验收（开发回归）

```bat
scripts\run_stable_acceptance.bat
```

或见 [项目文件结构与脚本使用说明](docs/项目文件结构与脚本使用说明.md) 中的全量命令列表。

---

## 禁止事项（红线）

- ❌ 不要删除 `data/task_publisher.db`
- ❌ 不要随便改 `config/config.json`（路径保持相对路径）
- ❌ 不要写死绝对路径（如 `C:\Users\...`）
- ❌ 不要让 Agent 直接写 vault
- ❌ 不要让 Agent 调用 `import-tasks` / 自动导入任务
- ❌ 不要直接改数据库（用 UI 或只读导出 + 人工确认）
- ❌ 不要改抽卡算法 / 任务权重
- ❌ 不要破坏 `task_feedback_events` 结构
- ❌ 不要恢复旧的大段内联 JS（业务逻辑只在 `static/app.js`）

---

## 技术栈

- 前端：原生 HTML / CSS / JS（`index.html` + `static/app.js?v=13`）
- 后端：Flask（`server/backend_api.py`）
- 数据：SQLite（`data/task_publisher.db`）
- 启动：Python 3.10+ + `.venv` + `requirements-web.txt`

---

## 常见问题

→ 完整排错见 [docs/一周稳定使用与换电脑迁移说明.md](docs/一周稳定使用与换电脑迁移说明.md)

- **页面打不开**：先 `scripts\stop_web_safe.bat` 再启动；查 `.run\server.log`
- **/api/health 不通**：确认服务已启动、端口未被占用
- **换电脑跑不起来**：不要复制 `.venv`，在新电脑重建虚拟环境

---

## 当前版本不需要

- 公网部署 / 登录系统 / 云同步
- Agent 自动执行 / 自动写 vault / 自动导入任务

**建议：离开开发环境，进入一周稳定使用封版。**
