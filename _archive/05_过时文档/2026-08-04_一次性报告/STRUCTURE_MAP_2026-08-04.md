# 超级自动化学习工具 —— 结构全图（2026-08-04）

> **文档性质**：只读代码审计报告，基于 2026-08-04 代码审查  
> **审查依据**：所有信息来自代码、数据库结构、实际文件，不依赖旧文档  
> **旧文档状态**：README.md 等文档已严重过时，仅作为历史参考

---

## 一、技术栈一句话版

- **前端**：原生 HTML/CSS/JS 单页应用（`src/index.html` + `static/app.js`）
- **后端**：Flask 框架（`server/backend_api.py`），端口 5000
- **数据**：SQLite 数据库（`data/task_publisher.db`）
- **启动**：Python 3.10+ + `.venv` + `requirements-web.txt`

---

## 二、完整结构地图

```
超级自动化学习工具/
├── server/                          # Flask 后端服务
│   ├── backend_api.py               # 主 API（~3000 行），包含所有 REST 端点
│   └── serve_static.py             # 静态文件服务
├── src/                             # 前端源码
│   ├── index.html                  # 单页应用入口（完整 HTML/CSS/JS 内联）
│   ├── static/                     # 外部 JS（与 index.html 并行加载）
│   │   ├── app.js                 # 前端业务逻辑（~2700 行）
│   │   └── test.js                # 测试文件
│   ├── tasks/                     # Python 业务逻辑（模块化）
│   │   ├── models/
│   │   │   ├── database.py        # SQLite 封装，含所有表定义和迁移
│   │   │   └── task.py            # Task 模型定义
│   │   ├── services/
│   │   │   ├── task_service.py    # 任务 CRUD + 依赖管理
│   │   │   ├── gacha_service.py   # 抽卡算法（3 个卡池）
│   │   │   ├── state_service.py   # 状态追踪（精力/睡眠/情绪）
│   │   │   ├── export_service.py  # 导出给 AI 的任务快照
│   │   │   ├── ai_import_service.py   # AI 导入任务处理
│   │   │   └── ai_import_processor.py # AI 导入处理器
│   │   └── ui/
│   │       ├── main_window.py     # Tkinter 主窗口（独立 GUI）
│   │       └── filter_dialog.py   # 过滤对话框
│   └── notes/                     # Obsidian 笔记库（知识库）
│       └── vault/                 # 笔记目录（见 config.json）
├── static/                         # Flask 静态目录（由 backend_api.py 引用）
│   ├── app.js                     # 前端业务逻辑主文件
│   └── test.js                    # 测试文件
├── scripts/                        # 实用脚本
│   ├── launch_server.py           # 启动服务器
│   ├── stop_server.py             # 停止服务器
│   ├── export_tasks_for_ai.py     # 导出任务快照给外部 AI
│   ├── validate_task_patch.py      # 校验 AI 输出的任务修改
│   ├── verify_tables.py           # 验证数据库表结构
│   └── ...（其他提取/处理脚本）
├── config/
│   ├── config.json               # 运行时配置（端口、路径、API Key）
│   └── config.example.json        # 配置示例
├── data/                          # 数据目录
│   ├── task_publisher.db         # SQLite 主数据库
│   └── backup/                    # 数据库自动备份
├── docs/                          # 文档目录（已大量归档到 _archive/）
│   └── STRUCTURE_MAP_2026-08-04.md  # 本文档
├── ai_workspace/                  # AI 协作工作区
│   ├── 00_context/               # 任务快照（供外部 AI 使用）
│   └── 03_task_drafts/           # AI 输出的任务修改草稿
├── _archive/                      # 归档目录（88 个文件，10 个子目录）
│   ├── 01_临时脚本/              # 临时脚本（OCR、提取等）
│   ├── 02_缓存数据/              # 缓存的 AI 导入/导出
│   ├── 03_数据库备份/            # 旧数据库备份
│   ├── 04_PPT提取物/             # PPT 内容提取
│   ├── 05_过时文档/              # 旧文档（Markdown）
│   ├── 06_测试脚本/              # 测试脚本（含 acceptance 测试）
│   ├── 07_工具脚本/              # 工具脚本（链接修复等）
│   ├── 08_提示词备份/            # 提示词备份
│   ├── 09_审计报告/              # 审计报告
│   ├── 10_其他杂项/              # 其他杂项
│   ├── 归档报告.json             # 归档记录（哪些文件去哪了）
│   └── 归档清理方案.md           # 归档方案文档
├── .run/                          # 运行时文件
│   └── server.log                 # 服务器日志
├── .venv/                         # Python 虚拟环境
├── requirements-web.txt           # Web 依赖
├── 启动学习工具.bat              # Windows 启动脚本
└── README.md                      # 项目说明（已过时）
```

---

## 三、数据流完整链路

```
┌─────────────┐
│   浏览器    │
└──────┬──────┘
       │ HTTP 请求 (如 /api/tasks)
       ▼
┌─────────────────────────────────────┐
│  server/backend_api.py              │
│  Flask 应用，端口 5000              │
│  - 路由定义                        │
│  - 请求处理                        │
│  - 业务逻辑调用                     │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  src/tasks/services/               │
│  - task_service.py (任务 CRUD)     │
│  - gacha_service.py (抽卡算法)     │
│  - state_service.py (状态追踪)     │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  src/tasks/models/                 │
│  - database.py (SQLite 封装)       │
│  - task.py (Task 模型)             │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  data/task_publisher.db            │
│  SQLite 数据库                      │
│  - 15+ 表（见下一节）              │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  响应数据 (JSON)                   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  src/static/app.js                │
│  前端 JavaScript 处理              │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  src/index.html                   │
│  DOM 更新 + 动画渲染               │
└─────────────────────────────────────┘
```

---

## 四、数据模型真相

### 4.1 数据库位置
- **路径**：`data/task_publisher.db`
- **类型**：SQLite 3
- **版本**：1.5（从 1.0 迁移而来，有迁移脚本）

### 4.2 全部表清单

| 表名 | 一句话职责 | 主要字段 | 读写模块 |
|------|----------|---------|---------|
| `tasks` | **核心任务表**，存储所有任务 | id, name, category, description, estimated_time, deadline, resistance, energy_required, rarity, priority, is_daily, completed, repeat_type, task_profile, in_discard_pile, prerequisite_ids, is_unlocked, created_at, updated_at | backend_api.py, task_service.py, gacha_service.py |
| `tags` | 标签定义表 | id, name | database.py, task_service.py |
| `task_tags` | 任务-标签多对多关系 | task_id, tag_id | database.py |
| `task_dependencies` | 任务依赖关系表 | task_id, depends_on_task_id | backend_api.py |
| `task_milestones` | 任务里程碑 | task_id, name, deadline, completed | backend_api.py |
| `task_rejection_log` | 任务拒绝/跳过记录 | task_id, reason, timestamp | gacha_service.py, backend_api.py |
| `task_completion_feedback` | 任务完成反馈 | task_id, energy_after, mood_after, timestamp | backend_api.py |
| `task_completions` | 任务完成历史 | task_id, started_at, completed_at, actual_duration | backend_api.py |
| `gacha_records` | 抽卡记录 | timestamp, pool_name, available_time, task_id, accepted, refusal_reason | gacha_service.py |
| `time_currency` | 每日时间货币 | date, total_minutes, used_minutes, wasted_minutes | backend_api.py |
| `time_logs` | 时间日志 | date, available_time, used_for_gacha, wasted_time | backend_api.py |
| `user_state` | 用户状态快照（单条） | timestamp, energy_level, mood, notes | state_service.py |
| `user_states` | 用户状态历史 | timestamp, energy_level, mood, physical_condition, notes, source | backend_api.py |
| `user_profile` | 用户档案 | name, chronic_conditions, schedule_info, preferences | backend_api.py |
| `user_health_profile` | 健康档案 | condition_name, notes | backend_api.py |
| `user_schedule` | 每周日程模板 | day_of_week, time_slot, activity, is_regular | backend_api.py |
| `daily_schedules` | 每日日程 | date, time_slot, activity, notes | backend_api.py |
| `activities` | 活动选项列表 | id, name | backend_api.py |
| `daily_user_state` | 每日用户状态（含睡眠追踪） | date, daily_tone, energy_morning, energy_afternoon, energy_evening, bed_time, sleep_early_streak | state_service.py |
| `rest_days` | 休息日记录 | date, reason | backend_api.py |
| `ai_analysis_imports` | AI 分析导入记录 | timestamp, file_path, analysis_summary, applied_changes | backend_api.py |
| `_meta` | 数据库元数据 | key, value（存储 db_version） | database.py |

### 4.3 重复/冗余表分析

| 问题 | 描述 |
|------|------|
| `user_state` vs `user_states` | 两张表功能重叠，前者只保留最新一条，后者保留历史 |
| `time_currency` vs `time_logs` | 两张表记录相似的时间数据 |
| `daily_user_state` 包含睡眠 | 睡眠追踪数据分散在 `daily_user_state` 表中 |

---

## 五、前端功能清单与问题区

### 5.1 页面功能区域

| 区域 | 页面 | 功能 | 代码位置 |
|------|------|------|---------|
| 抽卡 | gacha | 任务抽卡（碎片/番茄/深度卡池）、卡牌翻转动画、弃牌堆预览 | index.html + app.js |
| 任务管理 | tasks | 任务列表、筛选、搜索、新建/编辑、标签管理、依赖图 | index.html + app.js |
| 计时器 | tasks | 番茄钟计时、暂停、提前结束、完成反馈 | index.html + app.js |
| 日程 | schedule | 每日日程编辑、睡眠追踪、能量追踪、状态评估 | index.html + app.js |
| 知识库 | knowledge | Obsidian 笔记浏览、分类侧边栏 | index.html + app.js |
| 设置 | config | 服务器配置、AI API 配置、提示词文件浏览、Agent 只读浏览 | index.html + app.js |

### 5.2 卡牌主题系统

| 主题 | 识别关键词 | 颜色/风格 |
|------|----------|---------|
| theme-math | 数学/高数/calculus | 蓝色 |
| theme-lang | 英语/语言/单词 | 绿色 |
| theme-history | 历史/记忆/档案 | 橙色 |
| theme-code | 编程/代码/python | 青色 |
| theme-write | 写作/论文/创作 | 紫色 |
| theme-science | 科学/物理/化学 | 浅蓝 |
| theme-review | 每日/每周/复习 | 金色 |
| theme-default | 默认 | 金色 |

### 5.3 前端问题区（代码审查发现）

| 优先级 | 问题 | 位置 | 风险 |
|--------|------|------|------|
| **高** | `app.js` 引用路径问题 | `src/static/app.js` vs `static/app.js` | index.html 引用 `/static/app.js`，但文件实际在 `static/` 目录；Flask 配置 `static_folder=_STATIC_DIR` 指向根 `static/` 目录 |
| **高** | 版本号不一致 | `index.html` 引用 `app.js?v=20`，但 `server/backend_api.py` 中可能没有版本控制 | 浏览器缓存问题 |
| **中** | 静态文件双份 | `src/static/` 和 `static/` 各有一份 `app.js` | 维护困难，可能导致版本不同步 |
| **中** | app.js 未完全加载 | `Read` 工具截断在 400 行，实际文件约 2700+ 行 | 可能有隐藏问题 |
| **低** | 硬编码文本 | 部分文案硬编码在 JS 中，未抽取为 i18n | 国际化困难 |
| **低** | 无单元测试 | 前端 JS 无自动化测试 | 回归风险 |

### 5.4 改动风险评估

| 区域 | 风险等级 | 说明 |
|------|---------|------|
| 抽卡算法 | **极高** | 核心业务逻辑，任何改动影响用户体验 |
| 任务依赖系统 | **高** | 涉及解锁机制，改错会导致任务状态混乱 |
| 数据库迁移 | **高** | `database.py` 的 `_migrate_v1_to_v1_5` 是一次性迁移，后续可能需要新的迁移 |
| app.js | **中** | 代码量大，约 2700 行，建议拆分 |
| index.html CSS | **低** | 样式相对独立，但改动可能影响多个组件 |

---

## 六、真相对照表

### 6.1 README 声称 vs 实际代码

| README 声称 | 实际状态 | 备注 |
|------------|---------|------|
| P1-Stable-1B 封版 | **部分有效** | 代码已更新到 2026-07，但新功能未体现在 README |
| P1-Visual-1A 任务卡牌系统 | **已实现** | 8 种卡牌主题，完整的翻转动画 |
| P1-5B task_feedback_events | **已实现** | `TASK_FEEDBACK_PRESETS` 在 app.js 中 |
| P1-6 Agent 只读（仅 GET） | **已实现** | `/api/agent/*` 端点只提供读取 |
| 支持外部 AI 协作改任务 | **已实现** | `scripts/export_tasks_for_ai.py` + `validate_task_patch.py` |
| 服务器端口 5000 | **正确** | config.json 中 `port: 5000` |
| 使用 SQLite | **正确** | `data/task_publisher.db` |
| 业务逻辑在 `static/app.js` | **存疑** | 实际有两个 `app.js` 位置 |

### 6.2 新增/未在旧文档记录的功能

| 功能 | 发现位置 | 状态 |
|------|---------|------|
| 卡牌大小控制滑块 | index.html L530 | 未在文档记录 |
| 弃牌堆恢复功能 | app.js + backend_api.py | 部分文档提及 |
| 状态评估表单 | index.html L833-842 | 未在文档记录 |
| 活动管理 | index.html L856-872 | P1-3 提及但细节过时 |
| 关怀模态框 (careModal) | index.html L897-914 | 未在文档记录 |
| 智能体只读浏览 (agentReadonlyPanel) | index.html L695-699 | 未在文档记录 |

---

## 七、归类与重构建议

### 7.1 文件清理建议

| 建议 | 原因 | 操作 |
|------|------|------|
| 清理 `src/static/` 目录 | 与根 `static/` 重复，职责不清 | 确认 `static/app.js` 为唯一真源码后删除 |
| 清理 `_archive/01_临时脚本/` | OCR 等脚本已归档，无需保留 | 可彻底删除 |
| 清理 `src/tasks/ui/` 目录 | Tkinter GUI (`main_window.py`, `filter_dialog.py`) 看起来是遗留代码，与 Flask 应用不兼容 | 评估后决定保留或删除 |

### 7.2 目录职责不清

| 目录 | 问题 | 建议 |
|------|------|------|
| `src/tasks/` vs `server/` | 业务逻辑分布在两处，`src/tasks/services/` 存在但 Flask API (`server/backend_api.py`) 直接操作数据库 | 统一到一处 |
| `src/notes/` vs `ai_workspace/` | 笔记库和 AI 工作区分离但有关联 | 保持现状，但需文档说明 |
| `static/` vs `src/static/` | 静态文件位置不明确 | 统一为 `static/` |

### 7.3 下一步开发切入点

1. **【高优先级】静态文件路径统一**
   - 问题：`static/` 和 `src/static/` 双份 `app.js`，引用路径混乱
   - 操作：确认唯一真源码，清理重复文件，更新 `backend_api.py` 中的 `static_folder` 路径

2. **【中优先级】前端代码拆分**
   - 问题：`app.js` 约 2700 行，单文件维护困难
   - 操作：按功能拆分为 `gacha.js`、`tasks.js`、`schedule.js`、`ui.js` 等模块

3. **【中优先级】数据库表整理**
   - 问题：`user_state` vs `user_states`、`time_currency` vs `time_logs` 功能重复
   - 操作：制定迁移计划，合并重复表，清理废弃字段

---

## 八、附录：归档报告摘要

2026-07 的归档清理共移动：
- **88 个文件**
- **10 个子目录**

主要内容：
- `01_临时脚本/`：OCR、文档提取等一次性脚本
- `05_过时文档/`：旧 Markdown 文档（含开发日志、产品路线图等）
- `06_测试脚本/`：测试和调试脚本
- `07_工具脚本/`：链接修复、批量处理工具

---

*文档生成时间：2026-08-04*  
*审查范围：代码、数据库结构、实际文件*  
*不依赖：README.md、PROJECT_CHANGELOG.md 等旧文档*
