# 超级自动化学习工具 —— 结构全图与真相文档

> **生成日期**：2026-08-04  
> **依据**：仅以仓库代码、`data/task_publisher.db` 实库、实际文件为准  
> **旧文档状态**：`README.md`、`PROJECT_CHANGELOG.md`、`docs/` 既有说明、`_archive/05_过时文档/` 均为**已过时/存疑**，下文仅作「历史声称」对照，不作事实依据

---

## 1. 完整结构地图

### 1.1 技术栈（代码实测）

| 层 | 实际技术 | 入口 / 关键路径 |
|----|----------|----------------|
| Web 后端 | Flask + flask-cors，端口 **5000**（`config/config.json`） | `server/backend_api.py`（单体 ~3300+ 行，含全部 `/api/*` 与首页托管） |
| 静态托管 | Flask `static_folder=项目根/static`；首页兼容根目录或 `src/index.html` | `serve_index()`；`server/serve_static.py` 几乎为空壳 |
| 前端 | 单页：原生 HTML/CSS + 外置 JS | `src/index.html` + `static/app.js?v=20`（~2711 行） |
| 数据库 | SQLite | `data/task_publisher.db`（配置键 `database.task_db_path`） |
| 桌面端（遗留） | PySide6 | `scripts/main.py` → `src/tasks/ui/*.py`；`requirements.txt` 含 PySide6，`requirements-web.txt` 仅 Flask |
| 笔记 | Obsidian Vault（Markdown） | `src/notes/vault/`（约 1485 个 `.md`） |
| 启动 | bat + `scripts/launch_server.py` 拉起 `backend_api.py`，PID 写入 `.run/` | `scripts/start_web_safe.bat`、`scripts/启动学习工具.bat` |

**当前主路径是 Web，不是桌面 Qt。** 桌面代码仍在仓库中，与 Web 共用同一 DB 路径约定，但表集合与读写路径已分叉。

### 1.2 数据流（一句话版）

浏览器加载 `src/index.html` → 请求 `/static/app.js` → `app.js` 调 Flask `/api/*` → `backend_api.py` 读写 `data/task_publisher.db` 与 `src/notes/**` 文件 → JSON 回前端渲染（任务卡牌 / 日程 / 知识库 / 设置）。

```
[浏览器]
    │  GET /
    ▼
[server/backend_api.py] ──serve──► src/index.html + static/app.js
    │
    ├── /api/tasks|gacha|discard|timer|state|schedule|tags|...
    │         └── SQLite: data/task_publisher.db
    │
    ├── /api/knowledge/* 、 /api/agent/* 、 /api/prompts/*
    │         └── 文件: src/notes/vault|prompts|未分类|已分类
    │
    └── /api/config* ──► config/config.json
```

### 1.3 目录树与职责

```
超级自动化学习工具/
├── server/                      # Web 服务（现行主后端）
│   ├── backend_api.py           # Flask 应用：API + schema ensure + 抽卡/知识库/Agent/计时/评估
│   └── serve_static.py          # 遗留空壳（几乎无逻辑）
├── src/
│   ├── index.html               # 前端唯一页面（内联大量 CSS + 结构 DOM）
│   ├── __init__.py
│   ├── tasks/                   # 原桌面端领域层（PySide6 UI + services）
│   │   ├── models/
│   │   │   ├── database.py      # 桌面侧 SQLite 模型/迁移（与 Web ensure_* 双轨）
│   │   │   └── task.py
│   │   ├── services/            # gacha/task/state/export/ai_import（桌面用）
│   │   └── ui/                  # main_window / gacha_window / schedule / dependency_graph
│   └── notes/                   # 学习资料与 Obsidian 资产
│       ├── vault/               # 主知识库（大学物理/高等数学/电子技术/…/知识点）
│       ├── prompts/             # Agent / 提示词文件
│       ├── 未分类/              # Agent raw 输入
│       ├── 已分类/              # Agent 输出类目录
│       ├── PPT/                 # PPT 源材料
│       ├── 习题和真题/          # 试卷与习题
│       ├── Radiances Of Wisdom/ # 长文本灵感材料
│       ├── 灵感提取报告/
│       ├── vault.zip
│       └── 变更日志报告.md
├── static/
│   ├── app.js                   # 全部前端业务逻辑（高耦合单体）
│   └── test.js                  # 历史探测脚本（依赖不存在的 #testBanner）
├── data/
│   ├── task_publisher.db        # ★ 现行用户数据库
│   ├── task_publisher.before_chapter_deps_fix.db  # 修复前快照
│   ├── backup/                  # 运行时备份目录（database.py / bat）
│   ├── physics_*.txt            # 临时提取物
│   └── image_filter_report.md
├── config/
│   ├── config.json              # 端口 / vault 路径 / API Key / DB 路径
│   └── config.example.json
├── scripts/                     # 启停、备份、验收、导出校验、各种提取脚本
│   ├── launch_server.py / start_web_safe.bat / stop_web_safe.bat
│   ├── 启动学习工具.bat
│   ├── main.py / start-desktop.bat   # 桌面入口
│   ├── export_tasks_for_ai.py / validate_task_patch.py
│   ├── backup_user_data.bat / verify_transferred_project.bat
│   ├── run_stable_acceptance.bat
│   ├── _inspect_db*.py          # 一次性 DB 探查
│   └── extract_*.py / filter_*.py / read_doc*.py  # 资料处理一次性脚本
├── ai_workspace/                # 外部 AI 协作沙箱（快照 / 草稿 / 归档）
│   ├── 00_context/ … 99_archive/
│   └── README.md
├── docs/                        # 文档区（多数旧文已迁走；本文件为 2026-08-04 真相图）
│   ├── STRUCTURE_MAP_2026-08-04.md  # ← 本文
│   ├── 项目重启方案.md          # 「已过时/存疑」——仍引用 P1-Stable-1B 封版叙事
│   ├── README.md / 使用说明.txt / design-spec.txt / AI_TEAM.zip
├── _archive/                    # 2026-07 大规模清理归档
│   ├── 01_临时脚本 … 10_其他杂项
│   ├── 05_过时文档/             # 原 docs 下阶段说明等
│   └── 归档执行报告.md / 归档报告.json
├── .run/                        # server.pid / server.log（运行态，勿当源码）
├── .venv/                       # 本地虚拟环境
├── README.md                    # 「已过时/存疑」——声称 P1-Stable-1B 封版
├── PROJECT_CHANGELOG.md         # 「已过时/存疑」
├── requirements.txt             # Flask + PySide6
├── requirements-web.txt         # 仅 Flask 系
├── 执行归档清理.py / .bat
└── opencode.json
```

### 1.4 关键文件速查

| 文件 | 职责 | 改动风险 |
|------|------|----------|
| `server/backend_api.py` | 全部 Web API、抽卡权重、schema 幂等补齐、知识图谱、Agent、提示词备份 | **极高** |
| `static/app.js` | 全部 UI 交互、双计时器状态、反馈弹窗、弃牌动画 | **极高** |
| `src/index.html` | DOM 骨架 + 大段 CSS（含翻牌样式重复块） | **高** |
| `src/tasks/models/database.py` | 桌面侧表定义；许多表在实库中**不存在** | 中（若只跑 Web 则影响小） |
| `data/task_publisher.db` | 用户真相数据（344 tasks 等） | **极高（禁止误删）** |
| `config/config.json` | 运行配置 | 高 |

---

## 2. 数据模型真相

### 2.1 数据库位置

- **路径**：`data/task_publisher.db`（相对项目根；`config.json` → `database.task_db_path`）
- **引擎**：SQLite3
- **Schema 来源（双轨）**：
  1. Web：`backend_api.py` 启动时 `ensure_*_schema()` 幂等建表/补列
  2. 桌面：`src/tasks/models/database.py` `_init_tables` / `_migrate_v1_to_v1_5`
- **实库表集合 ≠ database.py 全量声明**（见下）

### 2.2 实库现存表（2026-08-04 对 `task_publisher.db` PRAGMA）

| 表名 | 行数（抽样日） | 一句话职责 | 主要读写方 |
|------|----------------|------------|------------|
| `tasks` | 344 | 任务池本体（含弃牌标记、解锁、依赖 JSON、抽卡计数等） | Web API CRUD；桌面 `task_service` |
| `tags` / `task_tags` | 26 / 910 | 标签及任务多对多 | `/api/tags*`；桌面 database |
| `task_dependencies` | 508 | 前置依赖边（与 `tasks.prerequisite_ids` 双写） | Web 依赖同步 / 解锁链 |
| `gacha_records` | 0 | 抽卡/换牌记录（实库缺 `rarity` 列） | `/api/gacha/replace` 等；桌面 `gacha_service` |
| `task_rejection_log` | 0 | 拒绝原因日志 | 桌面 gacha；Web 部分路径 | 
| `task_completion_feedback` | 15 | 完成后精力/心情（旧反馈） | `/api/tasks/<id>/feedback` |
| `task_feedback_events` | 5 | 结构化事件反馈（跳过/提前完成/超时等） | `/api/task-feedback` |
| `timer_sessions` | 21 | 计时会话 | `/api/timer/*` |
| `state_assessments` | 3 | 每日状态问卷与分数 | `/api/state/assessment*` |
| `daily_user_state` | 5 | 日基调 / 分时段精力 / 入睡 / 早睡连击 | `/api/state/*` |
| `user_schedule` | 0 | 周常日程槽 | `/api/schedule/weekly` |
| `daily_schedules` | 0 | 某日日程覆盖 | `/api/schedule/daily` |
| `activities` | 1 | 活动名词典 | `/api/schedule/activities*` |
| `sqlite_sequence` | — | SQLite 自增序列 | 系统 |

### 2.3 各表字段摘要（实库）

**tasks**  
`id, name, category, task_type, description, estimated_time, preferred_time, deadline, resistance, energy_required, rarity, priority, success_rate, refusal_count, is_daily, completed, created_at, updated_at, prerequisite_ids, is_unlocked, repeat_type, last_completed_at, next_available_at, in_discard_pile, completed_count, difficulty, draw_count_today, last_drawn_at, min_push_time, linked_note_path`  
另有杂列：`x_task_id, x_depends_on`（疑似历史迁移残留，**tags / task_tags 上也有**）。

**弃牌堆**：不是独立表，是 `tasks.in_discard_pile` 布尔标记。

**daily_user_state**  
`date, daily_tone, energy_morning/afternoon/evening, bed_time, sleep_early_streak` —— 睡眠追踪与日精力。

**timer_sessions**  
`task_id, started_at, ended_at, planned_minutes, actual_minutes, status, result, reason, notes, created_at`

**task_feedback_events**  
`task_id, event_type, planned_minutes, actual_minutes, completion_status, reason_category, reason_detail, note, created_at`  
允许的 `event_type`（代码常量）：`skip_task | finish_early | finish_on_time | timer_timeout_unfinished | abandon_task`

**state_assessments**  
`date, answers(JSON), daily_tone, energy_score, focus_score, mood_score, formula_version, timestamp`

**gacha_records（实库）**  
`timestamp, pool_name, available_time, task_id, accepted, refusal_reason` —— **无 rarity**（`database.py` 声明有 rarity，Web INSERT 也不写 rarity）。

### 2.4 仅在 `database.py` 声明、实库缺失的表

| 表名 | 设计意图（代码注释/用法） | 现状 |
|------|---------------------------|------|
| `_meta` | DB 版本号 | 缺失（桌面迁移未在此库跑通或被旁路） |
| `time_currency` | 日可用时间货币 | 缺失 |
| `task_milestones` | 任务里程碑 | 缺失 |
| `user_state` / `user_states` | 即时状态记录（两套命名并存于代码） | 缺失 |
| `user_profile` | 用户档案 | 缺失 |
| `user_health_profile` | 健康状况 | 缺失 |
| `rest_days` | 休息日 | 缺失 |
| `task_completions` | 完成明细 | 缺失 |
| `time_logs` | 时间日志 | 缺失 |
| `ai_analysis_imports` | AI 导入审计 | 缺失（桌面 `ai_import_*` 会写） |

**结论**：Web 运行时以 `ensure_*` 建出的表为准；桌面 `database.py` 是更大的「目标模型」，与现行实库不同步。

### 2.5 关系简图

```
tags ←── task_tags ──→ tasks ←── task_dependencies (depends_on_task_id)
                          │
                          ├── gacha_records
                          ├── task_rejection_log
                          ├── task_completion_feedback
                          ├── task_feedback_events
                          └── timer_sessions

daily_user_state          （按 date，无 FK）
state_assessments         （按 date，无 FK）
user_schedule / daily_schedules / activities
```

---

## 3. 前端功能清单与问题区

### 3.1 页面功能区域（来自 `src/index.html` 导航）

| 页面 `data-page` | 区域 | 能力（代码存在） |
|------------------|------|------------------|
| `gacha` | 抽卡台 | 牌堆视觉、抽卡按钮、标签筛选、可用时间、今日统计、抽中卡牌操作（开始/跳过/拒绝/换牌）、弃牌堆缩略、**计时 dock** |
| `tasks` | 任务池 | 搜索/筛选、新建编辑、批量标签、依赖图弹窗、弃牌堆列表、**第二套计时器面板** |
| `schedule` | 日程 | 睡眠追踪、近 7 日能量、状态评估与历史、日日程格、活动管理 |
| `knowledge` | 知识库 | 学科分类、笔记列表、Markdown 渲染、Obsidian 打开 |
| `config` | 设置 | 端口/笔记路径/API、提示词只读+可编辑（带备份）、智能体只读浏览入口 |

弹窗类：任务编辑、弃牌堆、状态评估问卷、任务事件反馈、关怀换牌、活动管理、依赖图、Agent 浏览、提示词 diff 等。

### 3.2 前端遗留问题痕迹（代码证据）

1. **双计时器状态机（高风险）**  
   - 抽卡页：`timerDockSession` + `pauseInlineTimer`（暂停通过**改写客户端 `started_at`** 实现，未与服务端 pause API 对齐）  
   - 任务页：`timerActiveSession` + `loadTimerPanel`  
   - 两套 UI / 两套 interval，易出现「一边显示计时、一边未同步」

2. **CSS 翻牌块整段重复（中风险）**  
   - `index.html` 中 `.task-card.is-revealing` / `.task-card-face` / `.task-card-back` 等选择器各出现 **2 次**（纵向规则后紧接「横向」覆盖块）。后者生效，前者为死代码噪音，增加回归成本。

3. **大量空 `catch` / 静默失败（中高风险）**  
   - `app.js` 中数十处 `catch (e) { /* ignore */ }` 或空 `.catch(function () {})`（含 timer stop、弃牌、统计）。排错只能靠 toast 或 `.run/server.log`，前端无统一错误上报（仅有顶部 `console.error` 包装器）。

4. **抽卡统计与 `gacha_records` 可能脱节**  
   - 实库 `gacha_records` 为 **0 行**，但 UI 有「今日已抽 / 接受率」；需确认统计是否改走任务字段 `draw_count_today` 或其他内存逻辑（以当前数据看，历史抽卡审计表几乎未用）。

5. **`static/test.js`** 引用不存在的 `#testBanner` —— 死脚本。

6. **绝对/fixed 叠层较多**：`.card-fly-layer`（z-index 500）、modal（999）、toast（9999）、牌堆/弃牌堆 absolute 定位 —— 动画与点击穿透依赖 `pointer-events: none`，属视觉层高风险区。

### 3.3 改动风险标注

| 区域 | 风险 | 说明 |
|------|------|------|
| 抽卡权重 / `select_weighted_random` / 依赖解锁 | **极高** | 旧 README 红线；逻辑在 `backend_api.py` 与桌面 `task_service` 双份 |
| `tasks` 表结构 / `task_feedback_events` | **极高** | 数据兼容与反馈契约 |
| `static/app.js` 计时 + 反馈弹窗 | **高** | 状态分散、静默 catch |
| `src/index.html` 卡牌 CSS | **中高** | 重复规则 + 动画类名耦合 JS |
| 知识库只读浏览 | **中** | 主要读 vault 文件 |
| 提示词编辑 / Agent GET | **中** | 写路径有备份；Agent POST 执行端点仍存在（见对照表） |
| `scripts/` 一次性提取脚本 | **低** | 可再归档 |
| `_archive/` | **低** | 只读历史 |

---

## 4. 真相对照表（旧 README 声称 vs 代码）

> README / 项目重启方案声称「P1-Stable-1B 一周稳定封版」——**已过时/存疑**（叙事停在 2026-06 阶段语言；代码与归档继续演进到 2026-07）。

| 旧文档声称 | 代码实况 | 判定 |
|------------|----------|------|
| 任务池 CRUD | `/api/tasks*` + 任务页 | **存在** |
| 依赖链 / 解锁 | `prerequisite_ids` + `task_dependencies` + chain_unlock | **存在** |
| 抽卡 / 换牌 / 卡牌视觉 | gacha API + 翻牌 CSS/动画 | **存在** |
| 弃牌堆浏览/恢复 | `in_discard_pile` + discard API + 弹窗 | **存在** |
| 计时器 | `timer_sessions` + 双 UI | **存在**（实现粗糙） |
| 任务事件反馈 P1-5B | `task_feedback_events` | **存在** |
| 状态评估 | `state_assessments` + 日程页面板 | **存在** |
| 睡眠追踪 | `daily_user_state.bed_time` 等 | **存在** |
| 提示词只读 + 可写备份 | `/api/prompts*` | **存在** |
| Agent **只读**（禁止执行/写 vault/import） | UI 标「只读浏览」；但后端仍有 `/api/agent/process`、`save-note`、`import-tasks` | **声称过严 / API 仍存在** |
| 外部 AI 改任务流程 | `ai_workspace/` + export/validate 脚本 | **存在** |
| 「不要恢复大段内联 JS」 | 业务在 `static/app.js`；HTML 仍内联全部 CSS | **基本符合**（CSS 未外置） |
| 桌面 PySide6 为现行主 UI | `scripts/main.py` 仍在；主启动 bat 走 Web | **桌面降级为遗留** |
| `time_currency` / 完整桌面表模型 | 实库无这些表 | **文档模型超前 / 未落地** |
| 封版「勿改抽卡算法」 | 代码可改，无技术锁 | **流程红线，非代码锁** |
| docs 下多份阶段交接文档 | 多已迁入 `_archive/05_过时文档/`；`docs/` 仅剩少量 + 本图 | **已改名/归档** |

---

## 5. 归类与重构建议（重启开发铺路）

### 5.1 建议处理的文件/目录

| 动作 | 对象 | 理由 |
|------|------|------|
| 考虑迁入 `_archive/` | `scripts/extract_*.py`、`read_doc*.py`、`filter_extracted_images.py`、`_inspect_db*.py`、`test_regex.py`、`static/test.js` | 一次性资料处理 / 探查，非运行时 |
| 考虑迁入 `_archive/` 或资料库外置 | `data/physics_*.txt`、`data/image_filter_report.md`、`src/notes/vault.zip`、超大习题 PDF | 膨胀仓库，非服务必需 |
| 明确标注遗留或拆仓 | 整棵 `src/tasks/ui/` + `scripts/main.py` | Web 已接管；避免双端逻辑继续分叉 |
| **拆分** | `server/backend_api.py` | 按 tasks / gacha / schedule / state / knowledge / agent / prompts 分模块 |
| **拆分** | `static/app.js` | 至少拆 timer、gacha、tasks、schedule、knowledge、config |
| **合并/去重** | `index.html` 重复翻牌 CSS；桌面与 Web 重复的抽卡权重函数 | 降低双份漂移 |
| **统一 schema 源** | 二选一：以 Web `ensure_*` 为唯一迁移源，或引入正式 migration；废弃实库未用的 `database.py` 表声明或补齐 | 消灭「声明有、库没有」 |
| 清理杂列 | `x_task_id` / `x_depends_on` | 确认无引用后迁移删除 |

### 5.2 职责不清的目录

- **`src/notes/`**：Vault、提示词、试卷、PPT、灵感原文混放；Agent 路径硬编码 `未分类/已分类`。
- **`scripts/`**：生产启停脚本与一次性 OCR/PPT/试卷脚本混放。
- **`docs/`**：旧阶段文档已归档，但根 README 仍指向已搬走的路径（**已过时**）。
- **`server/serve_static.py`**：名实不符，易误导。

### 5.3 建议的下一步切入点（1–3）

1. **统一计时器（前端）**：合并 `timerDockSession` / `timerActiveSession` 为单一 store；暂停改为服务端字段或明确「仅本地暂停」契约；去掉空 catch。  
2. **Schema 真相源（后端）**：以实库 14 张业务表写一份正式 migration 文档/脚本；停止在 `database.py` 暗示不存在的表仍可用。  
3. **后端模块化最小切片**：先把 `/api/timer*` + `/api/task-feedback*` + `/api/state/*` 抽离出 `backend_api.py`，降低触碰抽卡权重的风险。

---

## 6. 附录：API 面（按域）

- **任务**：`/api/tasks` CRUD、complete/skip/refuse、dependents、move-to-discard、feedback  
- **抽卡**：`/api/gacha/pools`、`draw`、`care-draw`、`replace`、`statistics`、`pools/detail`  
- **弃牌**：`/api/discard-pile`、`restore`  
- **标签 / 依赖 / 导出**：`/api/tags*`、`/api/dependencies`、`/api/export`  
- **日程**：`/api/schedule/*`  
- **状态**：daily-tone、energy、sleep、weekly-energy、assessment*  
- **计时**：`/api/timer/start|complete|active`  
- **知识库**：categories、points、graph、notes、obsidian  
- **配置 / 提示词**：`/api/config*`、`/api/prompts*`  
- **Agent**：agents、files、prompt GET；另有 process / save-note / import-tasks（写能力仍在代码中）

---

*本文仅只读审查产出；未修改既有源码与数据库。*
