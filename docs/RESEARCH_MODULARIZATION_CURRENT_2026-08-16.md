# 摸底报告：现有项目模块化现状 + 拆分路线（跨项目，2026-08-16）

> **生成时间**：2026-08-16
> **摸底人**：Cursor AI（基于代码实测 + 现有权威报告交叉验证）
> **依据**：所有结论均引用文件路径 + 行号 + 函数/表名，证据导向，不编造
> **范围**：用户三大项目逐一摸底——超级自动化学习工具 / soulvilization / 聊天记录导出
> **声明**：本研究**只读不写**——学习工具 P0 Build 仍在跑，不触及任何工作文件
> **结构**：每项目三段——现状评估（高内聚低耦合打分 + 问题清单）+ 大文件拆分建议（模块划分方案 + 依赖图）+ 拆分 ROI
> **末尾**：跨项目「拆分优先级排序」+ 通用建议

---

## 目录

- [0. 阅读须知 / 总体结论速览](#0-阅读须知--总体结论速览)
- [1. 项目 A：超级自动化学习工具](#1-项目-a超级自动化学习工具)
  - [1.1 项目结构与规模](#11-项目结构与规模)
  - [1.2 后端模块化现状（`server/backend_api.py`，3439 行）](#12-后端模块化现状serverbackend_api-py3439-行)
  - [1.3 桌面端 PySide6 遗留层（`src/tasks/`，共 218KB）](#13-桌面端-pyside6-遗留层srctasks共-218kb)
  - [1.4 前端模块化现状（`static/app.js`，2890 行 + `src/index.html`，947 行）](#14-前端模块化现状staticappjs2890-行--srcindexhtml947-行)
  - [1.5 其他脚本与目录的状态评估](#15-其他脚本与目录的状态评估)
  - [1.6 拆分建议（讨论稿）](#16-拆分建议讨论稿)
- [2. 项目 B：soulvilization（Python + Pygame）](#2-项目-bsoulvilizationpython--pygame)
  - [2.1 项目结构与规模](#21-项目结构与规模) *(待子任务返回)*
  - [2.2 模块化现状评估](#22-模块化现状评估) *(待子任务返回)*
  - [2.3 拆分建议](#23-拆分建议) *(待子任务返回)*
- [3. 项目 C：聊天记录导出](#3-项目-c聊天记录导出)
  - [3.1 项目结构与规模](#31-项目结构与规模) *(待子任务返回)*
  - [3.2 模块化现状评估](#32-模块化现状评估) *(待子任务返回)*
  - [3.3 拆分建议](#33-拆分建议) *(待子任务返回)*
- [4. 跨项目拆分优先级排序](#4-跨项目拆分优先级排序) *(待整合)*
- [5. 通用建议（拆分类铁律）](#5-通用建议拆分类铁律) *(待写)*
- [6. 风险与未知点](#6-风险与未知点) *(待写)*

---

## 0. 阅读须知 / 总体结论速览

### 0.1 摸底方法

- **学习工具**：完整代码实测（PowerShell 扫文件 + Read 关键模块 + Grep 锚点定位）
- **soulvilization / 聊天记录导出**：并行启动两个 explore 子任务，只读模式调研
- 依据现有三份权威报告（README.md / STRUCTURE_MAP_2026-08-04_auto.md / RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md / RESEARCH_ASSISTANT_FRONTEND_DESIGN_2026-08-16.md）作为基线
- 跨交叉验证行号、文件路径、API 名

### 0.2 现状速览（先看这张表）

| 项目 | 规模 | 模块化现状 | 高内聚低耦合 | 拆分紧迫度 |
|------|------|------------|--------------|----------|
| **A. 超级自动化学习工具** | backend_api.py 137KB / app.js 117KB / index.html 68KB / 桌面端 218KB | **后端"软模块化"**（注释分块）+ 前端**零模块化**（single global）+ 桌面端已分模块但**与 Web 完全分叉** | **3/10** | **极高** |
| **B. soulvilization** | 36 Python 源文件、core + world_generation 16 模块 | 待子任务返回 | 待子任务返回 | 待子任务返回 |
| **C. 聊天记录导出** | 小工具（根据子任务） | 待子任务返回 | 待子任务返回 | 待子任务返回 |

### 0.3 跨项目通用发现

1. **没有项目做到真正的"模块化"**——所有项目都至少有一个 1000+ 行单文件
2. **学习工具最大**——后端 3439 行、前端 2890 行、桌面端 5 个 17-66KB 的 PySide6 大类
3. **学习工具桌面端与 Web 是双份逻辑**——抽卡/任务/状态的服务实现两边各写一遍（陈债红线）
4. **没有任何项目使用 ES modules / Flask Blueprint / Application Factory**——全局状态 + 单文件是各项目主流

---

## 1. 项目 A：超级自动化学习工具

### 1.1 项目结构与规模

> **路径**：`D:\Axelit\.工作\trae\超级自动化学习工具`
> **README 截至 2026-08-05 重写**；本研究摸了 2026-08-16 实际状态

#### 1.1.1 大文件清单（实测，排除 node_modules / .venv / __pycache__ / _archive / .run / ai_workspace）

| 路径 | 字节 | 估算行 | 类别 | 状态 |
|------|-----:|------:|------|------|
| `server/backend_api.py` | 137,163 | **3439** | 后端 Flask 单文件 | 现行主用 |
| `server/serve_static.py` | 272 | ~10 | 静态服务空壳 | 遗留，已被 Flask static_folder 取代 |
| `static/app.js` | 117,592 | **2890** | 前端业务逻辑全量 | 现行主用 |
| `static/test.js` | 160 | 5 | 历史探测脚本 | 死脚本 |
| `static/vendor/marked.min.js` | 36,054 | ~700 | 第三方 Markdown 库 | OK |
| `static/vendor/fontawesome/all.min.css` | 101,973 | — | 第三方图标 | OK |
| `src/index.html` | 68,703 | **947** | 前端唯一页面 + 大段内联 CSS | 现行主用 |
| `src/tasks/models/database.py` | 31,648 | ~800 | 桌面端 SQLite 模型 | 桌面端遗留 |
| `src/tasks/models/task.py` | 9,484 | ~270 | 桌面端 Task 模型 | 桌面端遗留 |
| `src/tasks/services/ai_import_processor.py` | 12,877 | ~330 | 桌面端 AI 导入 | 桌面端遗留 |
| `src/tasks/services/ai_import_service.py` | 5,622 | ~160 | 桌面端 AI 导入 | 桌面端遗留 |
| `src/tasks/services/export_service.py` | 3,299 | ~95 | 桌面端导出 | 桌面端遗留 |
| `src/tasks/services/gacha_service.py` | 11,653 | ~310 | 桌面端抽卡 | **与 Web 双份** |
| `src/tasks/services/state_service.py` | 8,791 | ~240 | 桌面端状态 | **与 Web 双份** |
| `src/tasks/services/task_service.py` | 13,996 | ~370 | 桌面端任务 | **与 Web 双份** |
| `src/tasks/ui/dependency_graph.py` | 25,452 | ~700 | 桌面端依赖图 | 桌面端遗留 |
| `src/tasks/ui/filter_dialog.py` | 17,642 | ~480 | 桌面端筛选弹窗 | 桌面端遗留 |
| `src/tasks/ui/gacha_window.py` | 45,804 | ~1200 | 桌面端抽卡窗 | **god class** |
| `src/tasks/ui/main_window.py` | 66,568 | ~1800 | 桌面端主窗口 | **god class** |
| `src/tasks/ui/schedule_window.py` | 21,480 | ~570 | 桌面端日程窗口 | 大文件 |
| `scripts/check_database.py` | 6,473 | ~180 | 一次性 | 可归档 |
| `scripts/full_verification.py` | 7,378 | ~200 | 一次性 | 可归档 |
| `scripts/migrate_fix_missing_tables.py` | 6,657 | ~180 | 一次性 migration | 长期保留 |
| `scripts/test_api_endpoints.py` | 10,913 | ~280 | 一次性 | 可归档 |
| `scripts/verify_fixes.py` | 6,153 | ~175 | 一次性 | 可归档 |
| `scripts/export_tasks_for_ai.py` | 6,007 | ~165 | 协作工具 | 长期保留 |
| `scripts/validate_task_patch.py` | 4,643 | ~130 | 协作工具 | 长期保留 |

#### 1.1.2 static 目录核实（确认静态资源组织）

只有 3 个 JS 文件（`app.js` / `test.js` / `vendor/marked.min.js`），**不存在任何 ES module 文件**——`core/`、`modules/` 之类的前端模块结构还**没有建立**。这证明任务说明里"已在进行 refactor-esmodules 任务"目前**还未产出任何模块文件**。

#### 1.1.3 src/tasks/ 桌面端核实

按 PySide6 桌面应用结构组织（`models/` / `services/` / `ui/`），但**没有被 Web 端 import**——这是 PySide6 桌面端的独占代码层。**与 Web 后端并存但完全独立**，双份 schema 验证（`backend_api.py` 自己 `ensure_*` 建表，`src/tasks/models/database.py` 也建表）。

---

### 1.2 后端模块化现状（`server/backend_api.py`，3439 行）

#### 1.2.1 路由与代码块划分（来自 Grep 锚点）

通过 `^@app.route` / `^def` / `^class` / `^# =====` 抓出 3439 行的全部骨架：

**域模型层（第 1-238 行 = 238 行）**
- 第 1-10 行：imports
- 第 12-32 行：配置加载 + Flask 实例 + `CONFIG` / `DB_PATH` / `NOTES_DIR` 三个**全局常量**
- 第 34-62 行：6 个 `Enum` 类（`TaskCategory` / `RepeatType` / `TaskProfile` / `Resistance` / `EnergyRequired`）
- 第 63-238 行：`Task` 类（~175 行，含 `__init__` + `to_dict` + 业务方法）

**数据访问层（第 288-948 行 = 660 行）**
- `get_db_connection()` — 第 288 行（SQLite 连接工厂）
- `get_task_tags` / `get_all_tags_for_tasks` / `_attach_tags` — 标签批处理
- `ensure_indexes` — 索引创建
- `get_all_tasks` / `get_task_by_id` / `add_task` / `update_task` / `set_task_tags` — 任务 CRUD
- `normalize_prereq_ids` / `get_task_prereq_ids` / `compute_is_unlocked` / `sync_prerequisite_deps` / `detect_cycle` / `validate_prerequisites` / `recompute_task_unlock` / `sync_all_unlock_states` / `get_task_dependents` — 依赖机制核心
- `ensure_task_dependency_schema` / `ensure_schedule_schema` / `_ensure_table_columns` / `ensure_timer_schema` / `ensure_task_feedback_events_schema` / `insert_task_feedback_event` / `ensure_assessment_schema` / `ensure_daily_state_schema` / `migrate_legacy_schedule_tables` — **12 个 schema 幂等创建函数**
- `delete_task` / `_complete_task` / `chain_unlock` / `record_refusal` — 任务生命周期

**抽卡业务层（第 1019-1290 行 = 271 行）**
- `GachaPool` Enum / `GachaSessionContext` / `DrawResult` — 抽卡域模型
- `_calculate_full_weight` / `_calculate_deadline_urgency` / `_calculate_energy_match` / `_calculate_resistance_factor` / `_calculate_profile_strategy_weight` / `_calculate_cooldown_factor` — 权重函数（**旧红线**）
- `select_weighted_random_task` / `get_available_tasks_for_gacha` / `draw_single` / `_weighted_pick` / `update_draw_count` — 抽卡核心
- `get_discard_pile_tasks` / `move_task_to_discard_pile` / `move_task_to_gacha_pile` — 弃牌堆

**API 路由层（第 1292-2527 行 = 1235 行）**
按域用 `==========` 注释分组：
- `/api/tasks*` 任务 CRUD — 第 1292-1468 行
- `/api/gacha/*` 抽卡 — 第 1469-1557 行
- `/api/health` — 第 1554-1557 行
- `/api/knowledge/*` 知识库 — 第 1558-1909 行（含 vault 扫描、`build_vault_knowledge_graph`（241 行的图构建算法）、wiki link 解析）
- `/api/config*` / `/api/tags*` — 第 1910-2031 行
- `/api/schedule/*` — 第 2046-2216 行
- `/api/state/*` — 第 2217-2327 行
- `/api/task-feedback` / `/api/tasks/<id>/feedback` — 第 2329-2405 行
- `/api/gacha/pools/detail` / `statistics` / `replace` — 第 2406-2491 行
- `/api/dependencies` / `/api/export` — 第 2492-2527 行

**首页与 AI Agent（第 2553-2999 行 = 446 行）**
- `serve_index()` — 第 2553-2567 行（首页路由 + 静态文件兜底）
- `load_prompt` / `call_llm` / `_build_task_context` — Agent 辅助
- `/api/agent/*` 全部：**agents / files / process / save-note / import-tasks** — 第 2660-2999 行（**写能力全部存在，前端没接**）

**计时器/提示词/评估（第 3001-3439 行 = 438 行）**
- `/api/timer/*` — 第 3001-3129 行（start / complete / active / pause / resume）
- `/api/prompts/*` — 第 3130-3291 行（含 `_safe_prompt_basename` / `_prompt_file_path` / `_create_prompt_backup_file` 备份还原机制）
- `calculate_state_scores` + `/api/state/assessment*` — 第 3292-3438 行
- `configure_sqlite` — 第 3439 行（最后一行）

#### 1.2.2 评估：模块化现状

**这一段的高内聚低耦合打分：4/10（软模块化）**

| 维度 | 评分 | 证据 |
|------|------|------|
| 域内聚 | 6/10 | 用 `==========` 注释清楚分了 7 个域（任务/抽卡/标签/知识库/日程/状态/Agent/计时/提示词），但**域间数据流完全交叉**——抽卡要读任务，标签要 join 任务，状态评估要用任务反馈 |
| 域间耦合 | 3/10 | **所有路由共享 `CONFIG` / `DB_PATH` / `NOTES_DIR` 三个全局常量**；所有路由调用 `get_db_connection()` 拿新连接；schema 幂等函数遍布全文；**没有任何依赖注入** |
| 抽卡权重算法的"红线" | 2/10 | 1019-1240 行权重算法**全文内联**——`_calculate_full_weight` 等 6 个权重函数彼此调用，**没有任何接口抽象**、没有任何参数对象隔离、**改一个因子就要通读 200 行** |
| 双份 schema 源 | 1/10 | `backend_api.py` 自己 `ensure_*` 12 个表，`src/tasks/models/database.py` 也声明同样甚至更多表（含 `_meta` / `time_currency` / `task_milestones` / `user_state` 等**实库不存在**的表）——**两个真相源漂移** |
| API 边界 | 4/10 | **所有路由直接挂全局 `app`（不是 Blueprint）**——无法单独加载/卸载任何一个域；Flask 单元测试要 mock 整个 app |
| 名称空间 | 6/10 | 函数命名规范（`api_*` / `ensure_*` / `_calculate_*` / `_attach_*`），可读性 OK |
| 测试友好 | 2/10 | 没有 Blueprint → 不能 `with app.test_client()` 单测某域；所有 helper 直接调 SQL |

**主要问题清单：**

1. ❌ **巨大单体，3439 行**——一个 React 项目都嫌大，单文件 Flask 已经是反模式
2. ❌ **没有 Blueprint**——所有 `@app.route` 直接挂全局 `app`（行 1292-3439）
3. ❌ **没有 Application Factory**——`app = Flask(__name__)` 在文件第 27 行直接创建（行 27 实证）
4. ❌ **配置是文件级全局**——`CONFIG = load_config()` 在第 24 行；`DB_PATH = CONFIG[...]` 在第 31 行；测试无法替换
5. ❌ **抽卡权重算法是 README 红线，未做接口隔离**——1019-1240 行整段"如果想动抽卡就得通读这一坨"
6. ❌ **AI Agent 写能力裸奔**——`/api/agent/process` / `save-note` / `import-tasks` 全部存在（第 2852-2999 行），前端没接——**安全审计盲点**
7. ❌ **schema 跨文件双源**——`backend_api.py` 12 个 `ensure_*` vs `src/tasks/models/database.py` 完整声明
8. ❌ **连接管理朴素**——每个路由自己 `get_db_connection()` + `try/finally` 关闭，无连接池；虽对 SQLite 影响小，但代码冗长
9. ⚠️ **无 ORM**——所有 SQL 字符串内联，schema 改动没有 migration 工具，依赖人工检查 grep
10. ⚠️ **跨域函数调用**——`gacha/draw` 内部调 `select_weighted_random_task` → 调 `_calculate_*` × 6 → 调 `get_available_tasks_for_gacha` → 调 `get_all_tasks` → 调 `get_db_connection()`，链路过长

#### 1.2.3 拆分建议（讨论稿）

**目标**：把 3439 行单文件拆成 8-10 个 Blueprint + 1 个 Application Factory + 1 个共享 layer。

**推荐拆分结构（Flask 标准模式）：**

```
server/
├── app_factory.py            # create_app() — Application Factory（行 1-200）
├── config.py                 # Config 类（取代文件级 CONFIG 字典）
├── db.py                     # get_db() / close_db() / init_app() 工厂
├── models/                   # 域模型（对应原 34-238 行 + 240-290 行）
│   ├── __init__.py
│   ├── enums.py              # 6 个 Enum（TaskCategory / RepeatType / ...）
│   ├── task.py               # Task 类
│   ├── gacha.py              # GachaPool / GachaSessionContext / DrawResult
│   └── draws.py              # 抽卡结果模型
├── services/                 # 业务层（对应 288-1290 行）
│   ├── tasks.py              # 任务 CRUD + 依赖机制
│   ├── gacha.py              # 抽卡核心 ← 旧红线，重构为接口隔离
│   ├── tags.py               # 标签批处理
│   ├── knowledge.py          # 知识库 + vault 扫描 + graph 构建
│   ├── schedule.py           # 日程周期
│   ├── state.py              # 状态评估 + 精力 + 睡眠
│   ├── timer.py              # 计时器
│   ├── feedback.py           # 任务反馈
│   └── prompts.py            # 提示词读改 + 备份还原
├── api/                      # 路由层（蓝本）
│   ├── __init__.py
│   ├── tasks.py              # /api/tasks*
│   ├── gacha.py              # /api/gacha/*
│   ├── tags.py               # /api/tags*
│   ├── knowledge.py          # /api/knowledge/*
│   ├── schedule.py          # /api/schedule/*
│   ├── state.py              # /api/state/*
│   ├── timer.py              # /api/timer/*
│   ├── feedback.py           # /api/task-feedback*
│   ├── prompts.py            # /api/prompts/*
│   ├── agent.py              # /api/agent/* ← 安全审计重点
│   ├── deps.py               # /api/dependencies
│   ├── export.py             # /api/export
│   └── misc.py               # /api/health, serve_index
├── ai/                       # AI Agent 辅助（2620-2660 行）
│   ├── llm_client.py         # call_llm
│   ├── prompt_loader.py      # load_prompt
│   └── task_context.py       # _build_task_context
├── schema/                   # 12 个 ensure_* 集中
│   ├── __init__.py
│   ├── ensure.py             # ensure_all() 总入口
│   ├── tasks.py
│   ├── tags.py
│   ├── dependencies.py
│   ├── gacha.py
│   ├── timer.py
│   ├── feedback.py
│   ├── knowledge.py
│   ├── prompts.py
│   ├── schedule.py
│   ├── state.py
│   └── assessment.py
└── backend_api.py            # ⚠️ 仅保留 50 行：import + create_app() + app.run()
```

**依赖方向（无环）：**

```
app_factory (Flask 实例)
    ↓ 注册
api/* (Blueprint)
    ↓ 调用
services/* (纯业务)
    ↓ 调用
models/* + db.py (数据层)
    ↓ 初始化
schema/ensure.py (启动时执行一次)
```

**关键设计原则：**

1. **抽卡权重接口隔离**——`_calculate_full_weight` 等 6 个函数 + `select_weighted_random_task` 抽到 `services/gacha.py`，并定义 `class GachaWeightStrategy` 接口，将来要换算法只需换 strategy，**不破红线**
2. **AI Agent 写能力**——`api/agent.py` 显式标注"**写能力**，需前端激活 + 鉴权**"，先把 `/api/agent/process` 改成默认 403
3. **Schema 单一源**——`schema/ensure.py` 成为唯一迁移入口；`src/tasks/models/database.py` 标注为"**遗留桌面端**"，不与 Web 同步
4. **db.py 提供 Flask `g` 上的连接**——每请求一个连接，teardown 自动关闭，避免连接泄漏
5. **config.py 提供 `Config` 类**（dev / test / prod 三档），不再用文件级 `CONFIG` 字典

**重构 ROI：**
- 改动量：~3-5 天（资深 Flask 工程师）
- 风险：高（3439 行文件，E2E 26 个用例必须全绿）
- 收益：抽卡算法可单独测试、Agent 写能力可单独禁用、安全审计能枚举所有路由
- 建议时机：**P0 Build 收尾后**立刻做（避免后期越拖越难）

---

### 1.3 桌面端 PySide6 遗留层（`src/tasks/`，共 218KB）

#### 1.3.1 现状评估

**用户已基本明确表态**：PySide6 桌面端**已降级为遗留**（README.md 行 18-22 + STRUCTURE_MAP_2026-08-04_auto.md §1.1 实证）。但代码仍存，**构成两条独立执行路径**——是技术债。

**层结构：**

```
src/tasks/
├── models/                   # 桌面端 ORM（SQLAlchemy 风格或裸 SQLite）
│   ├── database.py (31KB, ~800) —— 桌面端完整 schema 声明 + migration
│   └── task.py (9KB, ~270)
├── services/                 # 桌面端业务层
│   ├── ai_import_processor.py (12KB, ~330)
│   ├── ai_import_service.py (5KB, ~160)
│   ├── export_service.py (3KB, ~95)
│   ├── gacha_service.py (11KB, ~310)   ← 与 Web 后端双份
│   ├── state_service.py (8KB, ~240)    ← 与 Web 后端双份
│   └── task_service.py (13KB, ~370)    ← 与 Web 后端双份
└── ui/                       # PySide6 窗口
    ├── dependency_graph.py (25KB, ~700)
    ├── filter_dialog.py (17KB, ~480)
    ├── gacha_window.py (45KB, ~1200)   ← god class
    ├── main_window.py (66KB, ~1800)    ← god class
    └── schedule_window.py (21KB, ~570)
```

**关键观察：**

1. **schemas 漂移**——`database.py` 声明 14 张表（含 `_meta` / `time_currency` / `task_milestones` / `user_state` / `user_profile` / `user_health_profile` / `rest_days` / `task_completions` / `time_logs` / `ai_analysis_imports`），但**实库中这些表完全不存在**（STRUCTURE_MAP_2026-08-04_auto.md 行 86-101 实证）——**桌面端 schema 是目标模型，实库是 Web ensure 出来的当前模型，两条真理线漂移**
2. **god class**——`main_window.py` 66KB ≈ 1800 行；`gacha_window.py` 45KB ≈ 1200 行
3. **双份业务逻辑**——`gacha_service.py` / `task_service.py` / `state_service.py` 三个服务**与 `backend_api.py` 里的抽卡 / 任务 / 状态函数逻辑重复**（虽然函数签名不同）；抽卡权重算法就是典型例子——`backend_api.py._calculate_full_weight` ↔ `gacha_service.py.<同名或类似>`
4. **UI 与业务混杂**——main_window.py 既是 UI 又是 controller？

#### 1.3.2 高内聚低耦合打分：3/10

| 维度 | 评分 | 证据 |
|------|------|------|
| 目录分域 | 7/10 | `models/` / `services/` / `ui/` 三层清晰 |
| 域内聚 | 3/10 | service 内聚一般（gacha_service 同时管抽卡 + 替换 + 关怀），UI 是 god class |
| 域间耦合 | 5/10 | service → model 单向；UI → service 弱耦合 |
| 业务逻辑双份 | 1/10 | 与 Web 后端 `backend_api.py` 三处核心服务重叠 |
| schema 漂移 | 1/10 | `database.py` 声明的表实库 0 行存在 |
| 体量 | 1/10 | main_window 1800 行 + gacha_window 1200 行 |

#### 1.3.3 拆分建议

**短期（处理双份逻辑）**：
- 把 `gacha_service.py` / `task_service.py` / `state_service.py` 三个服务**整体迁入 `_archive/`**（与 Web 后端对应函数已合并），保留 file 但顶部加注释"**已废弃，请使用 backend_api.py**"
- 这样 Web 与桌面端的"双份逻辑"问题变成"只剩 Web 一个真相源"

**中期（处理 schema 漂移）**：
- `database.py` 顶部加 banner："**桌面端目标模型，与 Web ensure_* 单向漂移；实库以 Web 启动时 ensure 出来的表为准**"
- 或者反过来：以 `database.py` 的目标模型为唯一 schema 源，**Web 端删除自己的 12 个 ensure_* 函数**，统一调用 `database.py.init_tables()`

**长期（彻底拆分）**：
- main_window.py 1800 行拆成 `MainController` + `MenuCoordinator` + `StatusBarView` + 多个子页面 controller
- gacha_window.py 1200 行拆成 `GachaView` + `CardAnimator` + `ReplaceDialog` + `CareDialog`
- 引入 `dataclass` / `Qt Signal/Slot` 替代手写 getter/setter

**ROI 评估：**
- 双份逻辑清理：~0.5 天（迁入 `_archive`，加注释）
- schema 漂移修复：~1-2 天（统一迁移源）
- god class 拆分：~3-5 天（依赖 UI 行为不变测试）
- **建议**：前两项**立刻做**，god class 拆分**等桌面端真重启后再做**

**优先级：低（已不主用）** 但**双份逻辑必须收尾**（一旦重启用桌面端就会引入 bug）

---

### 1.4 前端模块化现状（`static/app.js`，2890 行 + `src/index.html`，947 行）

#### 1.4.1 app.js 全文结构（Grep 锚点定位）

**这是一个 2890 行（确切 2892，含最后 startup 调用）的 single global script**，没有任何 `import`/`export`，没有任何 ES modules，没有 importmap。

**通过 `^// ============` 段落标题做的"软模块化"（11 个段）：**

| 段 | 行范围 | 行数 | 软模块名 | 职责 |
|----|------|----:|----------|------|
| 1 | 4-9 | 5 | 全局错误捕获 | `window.onerror` 兜底 |
| 2 | 10-29 | 19 | API CLIENT | `api(url, opts)` 包装 |
| 3 | 31-42 | 11 | UI HELPERS | `toast()` / `showModal()` / `closeModal()` |
| 4 | 44-54 | 10 | 温情文案库 | `WARM_MESSAGES` |
| 5 | 55-157 | 102 | 任务事件反馈 | 弹窗 + Promise 包装 |
| 6 | 159-237 | 78 | 页面切换 + 导航 | `showPage()` + 导航事件 |
| 7 | 255-359 | 104 | 卡牌主题 + 动画 | 主题色 / 翻牌动画 / 卡片 HTML 构造 |
| 8 | 360-1205 | 845 | **抽卡模块** | 抽卡全流程 + 计时器 Dock + 关怀 + 反馈 |
| 9 | 1206-1645 | 439 | **任务管理** | CRUD / 筛选 / 弃牌堆 / 依赖图 / 批量标签 |
| 10 | 1646-1767 | 121 | 日程 | 渲染 / 编辑 / 活动管理 |
| 11 | 1768-1894 | 126 | 知识库 | 分类 / 笔记 / Markdown 渲染 / Obsidian 打开 |
| 12 | 1895-2390 | 495 | 配置 + 提示词 + Agent 只读 | 表单读写 + 文件浏览 + 提示词 diff |
| 13 | 2391-2840 | 449 | 睡眠/状态评估 + 计时器 | 睡眠面板 + 问卷 + 第二计时器 |
| 14 | 2843-2892 | 50 | INIT + 启动加载 | 事件绑定 + 启动调用 |

**注意**：抽卡模块 845 行 = **全文件 29%**——最大单一模块；任务管理 439 行 = 15%。

#### 1.4.2 模块级全局状态（来自 `^var\s+` 扫描）

**直接位列 `var` 关键字定义的"模块级可变状态"**（这些是后续拆模块时**必须显式抽离到 module state** 的对象）：

| 变量 | 行 | 域 | 关键性 |
|------|----|----|--------|
| `WARM_MESSAGES` | 45 | 字符串常量 | 改 UI 文案 |
| `TASK_FEEDBACK_PRESETS` | 56 | 反馈预设 | 加新事件类型 |
| `_taskFeedbackResolve` / `_taskFeedbackContext` / `_taskFeedbackPresetKey` | 79-81 | 反馈 Promise 状态 | 抽卡反馈 |
| `CARD_THEME_SYMBOLS` / `CARD_CORNER_LABELS` / `CARD_REPEAT_LABELS` | 256-262 | 卡片主题常量 | 改主题 |
| `gachaState` | 361 | **抽卡状态机** | 改抽卡流程 |
| `isDrawing` | 362 | 抽卡锁 | 避免并发抽卡 |
| `timerDockSession` / `timerDockTick` / `timerDockPaused` / `timerDockPausedElapsed` | 405-408 | **第一计时器状态** | 改计时器 |
| `_careContext` / `CARE_ENCOURAGES` / `CARE_CATEGORY_LABELS` | 972-982 | 关怀弹窗 | 抽卡关怀 |
| `allTasks` / `allTags` / `selectedTagFilter` | 1207 | 任务数据 | 任务页 |
| `REPEAT_LABELS` | 1339 | 字符串常量 | 重复类型 |
| `schedDate` / `slots` / `weeklyData` / `dailyData` | 1647 | 日程状态 | 日程页 |
| `currentNotePath` / `_noteCache` / `_noteCacheCat` | 1769-1773 | 知识库笔记 | 缓存 |
| `agentRoList` / `agentRawSubdir` / `agentVaultSubject` | 1911-1913 | Agent 只读状态 | Agent 浏览 |
| `promptFiles` / `promptCurrentContent` / `promptOriginalContent` / `promptSelectedName` / `promptEditMode` | 2153-2157 | 提示词编辑器 | 提示词 |
| `assessmentQuestions` / `assessmentAnswers` / `TONE_LABELS` | 2412-2415 | 评估问卷 | 状态评估 |
| `timerActiveSession` / `timerTickHandle` | 2552-2553 | **第二计时器状态** | 改计时器 |

**重大发现**：**双计时器状态完全独立**（行 405-408 vs 行 2552-2553），STRUCTURE_MAP_2026-08-04_auto.md §3.3 行 231-234 实证指出"两套 UI / 两套 interval，易出现「一边显示计时、一边未同步」"——**这是 god state 的典型表现**。

#### 1.4.3 评估：模块化现状

**这一段的高内聚低耦合打分：1/10（零模块化）**

| 维度 | 评分 | 证据 |
|------|------|------|
| 文件物理拆分 | 1/10 | 2890 行单文件，**0 个 ES module 文件**（static/ 目录只有 app.js + test.js + vendor/marked.min.js） |
| 段落划分 | 4/10 | 用 `// ============` 注释分 13 段，但**纯注释，运行时全在一个闭包内** |
| 命名空间 | 5/10 | 函数命名规范（`gacha` / `task` / `sched` / `mdToHtml` 前缀分散），但**没有机制阻止域间函数互相调用** |
| 域间耦合 | 2/10 | **多处跨域直接调用**——例如 `startTask()`（任务页/抽卡页共用）调用 `initTimerDock()` 和 `toggleTimerDockPause()`；`completeWithFeedback()` 调 `playCardFlyAnimation()` |
| 共享状态 | 1/10 | 23 个 `var` 全局可变状态，**任何函数都能修改** |
| 双计时器 | 0/10 | timerDockSession（405-408） vs timerActiveSession（2552-2553）**完全独立的状态机** |
| 错误处理 | 3/10 | 顶部 `window.onerror` 兜底，但**大量空 catch 静默失败**（STRUCTURE_MAP_2026-08-04 行 239-240 实证） |
| 抽象层 | 2/10 | 无 event bus、无 router、无 module loader、无 store |

**主要问题清单：**

1. ❌ **2890 行单文件**——单文件就要命
2. ❌ **零 ES modules**——所有 200+ 函数共享全局命名空间
3. ❌ **23 个模块级可变状态**——任意函数可读写，无法追踪
4. ❌ **双计时器状态机独立**——是 god state 的代表
5. ❌ **跨域函数直接调用**——`completeWithFeedback` 调 `playCardFlyAnimation`（gacha 专属），耦合腐烂
6. ❌ **`src/index.html` 内联 947 行 HTML + 大段 CSS**——其中"翻牌块两次重复"（docs / STRUCTURE_MAP 报告附录 §3.3 行 237-239 实证）
7. ⚠️ **空 catch 静默失败**——数十处 `catch (e) { /* ignore */ }` 或空 `.catch(function(){})`
8. ⚠️ **绝对/fixed 叠层较多**——`.card-fly-layer` (z-index 500) / modal 999 / toast 9999 / 牌堆 absolute，依赖 `pointer-events: none`（STRUCTURE_MAP 行 247 实证）

#### 1.4.4 拆分建议（重构路线图）

**目标**：建立 ES modules + 事件总线 + 模块懒加载的现代前端架构。

**推荐结构（继承 RESEARCH_ASSISTANT_FRONTEND_DESIGN_2026-08-16.md §2.6 的方案）：**

```
static/
├── index.html                       # 入口（变薄，引用 app.js）
├── app.js                           # ES module 入口（200 行，路由 + 启动）
├── core/
│   ├── event-bus.js                 # 50 行 — 极简发布订阅
│   ├── state.js                     # 100 行 — 全局状态 + 订阅
│   ├── api.js                       # 100 行 — fetch 包装（继承 api() 函数）
│   ├── router.js                    # 80 行 — hash 路由
│   ├── dom.js                       # 50 行 — showModal/closeModal/toast
│   └── constants.js                 # 文案 + 标签常量
├── modules/
│   ├── gacha/
│   │   ├── index.js                 # mount/unmount
│   │   ├── card.js                  # 卡片渲染 + 主题
│   │   ├── deck.js                  # 牌堆视觉
│   │   ├── drawer.js                # 抽卡流程
│   │   ├── animation.js             # 翻牌 + 飞行动画
│   │   ├── care.js                  # 关怀问询
│   │   ├── feedback.js              # 任务事件反馈
│   │   └── timer-dock.js            # 第一计时器（主页面常驻）
│   ├── tasks/
│   │   ├── index.js                 # mount/unmount
│   │   ├── list.js                  # 任务列表
│   │   ├── editor.js                # 新建/编辑
│   │   ├── tag-batch.js             # 批量标签
│   │   ├── dep-graph.js             # 依赖图
│   │   ├── discard.js               # 弃牌堆
│   │   └── timer-panel.js           # 第二计时器（任务页）
│   ├── schedule/
│   │   ├── index.js
│   │   ├── render.js                # 周日程 + 日日程
│   │   ├── slot-edit.js             # 槽位编辑
│   │   └── activities.js            # 活动管理
│   ├── knowledge/
│   │   ├── index.js
│   │   ├── categories.js            # 学科分类
│   │   ├── notes.js                 # 笔记列表
│   │   ├── markdown.js              # Markdown 渲染（已用 marked，可升级 markdown-it）
│   │   └── obsidian.js              # Obsidian 打开
│   ├── sleep-state/
│   │   ├── index.js
│   │   ├── sleep.js                 # 睡眠面板
│   │   ├── assessment.js            # 状态评估
│   │   └── weekly-energy.js         # 7 日能量
│   ├── config/
│   │   ├── index.js
│   │   ├── form.js                  # 配置表单
│   │   ├── prompts.js               # 提示词编辑 + diff
│   │   └── agent-ro.js              # Agent 只读浏览
│   └── shared/
│       ├── modal.js                 # 模态框
│       └── warm.js                  # 温情文案
└── vendor/                          # 第三方（已存在）
```

**关键设计原则：**

1. **每个模块导出 `mount(rootEl)` / `unmount(rootEl)`**——挂载时初始化 DOM + 绑定事件，卸载时清理
2. **跨模块通信走 event-bus**——禁止直接调用其他模块函数
3. **状态机抽到独立文件**——双计时器必须合并为 `modules/shared/timer.js` 一个 store
4. **API 调用统一走 `core/api.js`**——错误处理 / 重试 / 鉴权头注入一处
5. **每页一个 `index.js`**，主入口 `app.js` 只做路由 + 懒加载
6. **CSS 同步做拆分**——`static/css/<module>.css` 各自独立（按需 `<link>` 加载）
7. **index.html 必须变薄**——内联 CSS 全部外置，仅保留骨架 + 顶级容器

**状态管理建议：**

- **极简方案**：`core/state.js` 用 `Proxy` + `EventTarget`，提供 `state.subscribe(key, callback)` API
- **避免 Redux/Zustand/Jotai**——对 2890 行项目是过度工程
- **计时器等长生命周期状态**用 `WeakMap` 绑 DOM 节点，模块 unmount 时自动 GC

**重构 ROI：**
- 改动量：~3-5 天（与后端 Blueprint 拆分并行）
- 风险：高（26 个 E2E 用例必须全绿）
- 收益：双计时器合并、跨域函数去耦合、模块懒加载（首屏时间 ↓）、CSS 与 JS 一一对应
- 建议时机：**P0 Build 收尾后**立刻做；与 backend_api.py 的 Blueprint 拆分**可以并行**（前端拆模块不依赖后端拆分）

**已知坑**（来自 AGENTS.md + 现有报告）：
- `app.js?v=23` 的 query string 缓存版本——拆分时需要确保浏览器不用旧缓存
- 现有 E2E 26 用例用 `tests/e2e-manual.js` 跑 playwright-core，依赖全局 ID；拆分后**全局 DOM ID 仍保留即可**（避免 breaking E2E）
- 顶部 `// ============ INIT ============` 块（2843-2892 行）的事件绑定，**全部要分散到各模块的 `mount()` 内部**

---

### 1.5 其他脚本与目录的状态评估

#### 1.5.1 scripts/ 目录（35 个 Python 脚本）

**评估**：启停/备份脚本（**长期保留**） vs 一次性文件（**可归档**） vs 测试 / 探查脚本（**可清理**）混放。

| 类别 | 文件 | 保留？ |
|------|------|------|
| 启停备份 | `launch_server.py` / `stop_server.py` / `start_web_safe.bat` / `stop_web_safe.bat` / `启动学习工具.bat` / `start.bat` / `start-desktop.bat` / `backup_user_data.bat` / `verify_transferred_project.bat` / `run_stable_acceptance.bat` | ✅ 长期保留 |
| 协作工具 | `export_tasks_for_ai.py` / `validate_task_patch.py` | ✅ 长期保留（ai_workspace 流程） |
| 一次性提取 | `extract_*.py` (5 个) / `read_doc*.py` (2 个) / `filter_extracted_images.py` / `split_english_course.py` | ❌ 可归档 `_archive/` |
| 一次性探查 | `_inspect_db.py` / `_inspect_db2.py` / `_read_exact.py` / `debug_tags*.py` | ❌ 可归档 |
| 一次性测试 | `test_api_endpoints.py` / `test_flask_tags*.py` / `test_health_and_tags.py` / `test_http_detailed.py` / `test_simple.py` / `test_tags.py` / `test_regex.py` | ❌ 可归档（已被正式的 `tests/e2e-manual.js` 取代） |
| 一次性验证 | `verify_fixes.py` / `full_verification.py` / `verify_tables.py` | ❌ 可归档 |
| Migration | `migrate_fix_missing_tables.py` / `check_database.py` | ✅ 长期保留（数据迁移） |

**建议**：一次性文件迁入 `_archive/06_测试脚本/` 或 `_archive/07_工具脚本/`（STRUCTURE_MAP_2026-08-04_auto.md §5.1 行 291-294 实证——已建议归档但尚未执行）。

#### 1.5.2 static/test.js（5 行）

引用 `#testBanner` 元素，**死脚本**——直接删。

#### 1.5.3 src/index.html（947 行）

947 行 HTML + 内联 ~600 行 CSS（含翻牌块两次重复）。**未拆分**，但应拆分：
- 头/导航/section 模板
- 各 page section 独立 div（已按 `data-page` 区分）
- CSS 全部外置到 `static/css/`

**拆分 ROI**：低（不是阻塞性的，但可做；建议与 app.js 拆分同步）

#### 1.5.4 src/__init__.py / src/tasks/__init__.py 等空文件

空 `__init__.py` 0 字节，**保留**（Python 包需要）。

#### 1.5.5 _archive/ 目录

已经是干净的归档区（STRUCTURE_MAP_2026-08-04_auto.md §1.3 行 99-102 实证）——**不必动**。

#### 1.5.6 ai_workspace/ 目录

外部 AI 协作沙箱（ai_workspace/README.md 4 条红线）——**不必动**。

---

### 1.6 拆分建议（讨论稿）

#### 1.6.1 立即可做（零风险，价值中等）

| 任务 | 工作量 | 收益 |
|------|------|------|
| 删除 `static/test.js` | 1 分钟 | 移除死脚本 |
| 清理 `scripts/` 一次性脚本 → `_archive/` | 0.5 天 | 减少 25+ 个文件的混乱 |
| 在 `src/tasks/` 三个 service 顶部加"已废弃"注释 | 0.5 小时 | 标明双份逻辑，给未来人留路标 |
| 在 `server/backend_api.py` 顶部加 TODO：未来拆 Blueprint | 0.5 小时 | 路径标注 |

#### 1.6.2 短期（Build 收尾后 1-2 周）

| 任务 | 工作量 | 收益 |
|------|------|------|
| 后端拆 Blueprint（按 1.2.3 方案） | 3-5 天 | 抽卡算法可单独测试、Agent 写能力可单独禁用 |
| 前端拆 ES modules（按 1.4.4 方案） | 3-5 天 | 双计时器合并、跨域函数去耦合 |
| 同步拆 `src/index.html` CSS 外置 | 1-2 天 | HTML 变薄、首屏减小 |
| 同步补 `tests/e2e-modules/` 单模块测试 | 1-2 天 | 单元测试覆盖提高 |

**先做后端还是先做前端？**
- 建议**先做后端**——Flask Blueprint 拆分后，所有 `/api/*` 路由的契约不变，前端代码不动；等后端拆完再做前端，前后端互不阻塞
- 后端拆完后**做 E2E 全量验证**（按 AGENTS.md 规则 7：开发 Agent 不自验，所以交接验证 Agent）
- 然后前端拆

#### 1.6.3 中期（1-2 月）

| 任务 | 工作量 | 收益 |
|------|------|------|
| 桌面端 PySide6 god class 拆分（如果重启用） | 3-5 天 | 主窗口 1800 行 → 6 个 ~300 行子类 |
| 升级 markdown 渲染（marked → markdown-it + wikiLinks） | 1-2 天 | vault 双链正确渲染 |
| 统一 schema 源（database.py vs ensure_*） | 1-2 天 | 消灭双份 schema 漂移 |

#### 1.6.4 长期（路线选择）

- **路线 A：继续 Web 单体**——仅做上面短期+中期
- **路线 B：迁移到 OpenClaw 嵌入模式**（见 RESEARCH_ASSISTANT_FRONTEND_2026-08-16.md 调研）——前端模块化路径可能调整为 split-view + iframe 嵌入
- **路线 C：桌面端重启用**——需要再投入清理 src/tasks/

**当前推荐**：路线 A。

---

*(以下章节待子任务返回后补全：soulvilization / 聊天记录导出 / 跨项目优先级排序 / 通用建议 / 风险与未知点)*
