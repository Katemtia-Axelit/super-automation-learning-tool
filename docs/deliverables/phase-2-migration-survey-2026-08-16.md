# Phase 2 后端模块化迁移调查 (2026-08-16)

> **任务**：为 Phase 2 后端 Blueprint 迁移（`docs\deliverables\phase-2-backend-migration-2026-08-16.md`）生成 **per-BP 迁移参考**。
> **方法**：read-only 调查，所有结论标注 `server/backend_api.py` 原始行号。
> **上下文**：`backend_api.py` 实际 3483 行（≥ plan 中估算的 3466）；9 个 BP stub 已落地但未注册；3 个真 BP（tasks/gacha/tags）已注册。
> **基线**：`tests/baseline_2026-08-16.summary.txt` 36/36 E2E 全绿；`scripts/verify_p0_cleanup.py` 22/22 断言通过（Phase 1 锁定）。

---

## 0. 全局前置（影响所有 BP）

### 0.1 backend_api.py file fact
- 文件路径：`server/backend_api.py`
- 实际总行数：**3483 行**（最后行 `app.run(host=host, port=port, debug=debug)` 位于 L3483；plan 估算 3466 略有偏差）
- 含 `21` 个 `@app.route` 旧入口 + 7 个 `ensure_*` schema + 6 个 `_calculate_*` 抽卡权重 + 1 个 `_weighted_pick` + 1 个 `select_weighted_random_task`

### 0.2 9 个 BP 切分时**必须**保留的全局契约
| 资源 | 行号（backend_api.py） | 迁移策略 |
|---|---|---|
| `load_config()` | L12–22 | 已有 `server/app/config.py::load_config()` 等价实现，BP 直接 `from server.app.config import load_config` |
| `CONFIG`（module-level dict） | L24 | 改用 `current_app.config` 或 `cfg["..."]`（`app_factory` 已注入 `_db_path` / `_notes_dir` / `_project_root`） |
| `NOTES_DIR = CONFIG['obsidian']['notes_directory']` | L32 | 改用 `current_app.config["_notes_dir"]`（以 `server/app/config.py` 解析后的绝对路径为准） |
| `get_db_connection()` | L288–292 | 改用 `server.extensions.make_request_conn(db_path)`，确保 `PRAGMA foreign_keys=ON + WAL + busy_timeout` |
| `SQLITE_BUSY_TIMEOUT_MS = 30_000` | L285 | 直接 import `server.extensions.SQLITE_BUSY_TIMEOUT_MS` |
| `Task` dataclass + 4 个 Enum | L34–239 | 待 Phase 2 决定迁移到 `server/models/task.py`（不在本次 todo 范围） |
| `configure_sqlite(conn)` | L3456–3460 | 已有 `server.app.extensions.configure_sqlite` 等价实现 |

### 0.3 7 个 `ensure_*` 切流
> Phase 1 已在 `server/schema/__init__.py::ensure_all` 编排全部 7 个；Phase 2 删 `backend_api.py` 同源实现，完全由 `server.schema` 接管。
- `ensure_task_dependency_schema` → `server/schema/tasks.py::ensure_schema`（L15-44）
- `ensure_schedule_schema` → `server/schema/state.py::ensure_schema` 内段 1（L69-105）
- `ensure_timer_schema` → `server/schema/__init__.py::ensure_timer_schema`（L120-157）[Phase 1 已存在但是放错位置——state.py 注释说 timer 应在 schema/timer.py；Todo 11 需改进]
- `ensure_task_feedback_events_schema` → `server/schema/feedback.py::ensure_schema`（L19-56）
- `ensure_assessment_schema` → `server/schema/state.py::ensure_schema` 内段 3（L138-167）
- `ensure_daily_state_schema` → `server/schema/state.py::ensure_schema` 内段 2（L108-135）
- `ensure_indexes` → `server/schema/tasks.py::ensure_indexes`（L47-75）

### 0.4 抽卡权重公式横跨状态 BP / gacha BP
- `_calculate_full_weight` / `_calculate_*` / `_weighted_pick` / `select_weighted_random_task` / `draw_single` / `get_available_tasks_for_gacha` 在 `backend_api.py` L1019–1240
- 抽卡既被 `gacha_bp` 调用（`api_draw_task` 等）又被 `state_bp` 调用（理论上 `daily-tone` 影响权重，但实际**没有**引用）；详见每个 BP 的 Section E

---

## 1. State BP (Todo 1)

> 来源注释：`backend_api.py:2224 # TODO(phase2): migrate to server.app.blueprints.state_bp`
> 实际范围：11 个 endpoint（L2225–L2334 + L3357–L3454），且 `state_assessments` 引用被 plan 文档归入 state。

### Section A: Routes in backend_api.py

| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/state/daily-tone` | `api_get_daily_tone` | **L2225** | L2226–2235 | `/api/state` | 读当日 `daily_user_state`（无 row 返回默认空字典） |
| 2 | POST | `/api/state/daily-tone` | `api_set_daily_tone` | **L2237** | L2238–2254 | `/api/state` | UPSERT 当日 `daily_user_state.daily_tone` |
| 3 | POST | `/api/state/energy` | `api_record_energy` | **L2256** | L2257–2275 | `/api/state` | UPSERT `energy_morning/afternoon/evening`（动态列名） |
| 4 | GET | `/api/state/sleep` | `api_get_sleep` | **L2277** | L2278–2286 | `/api/state` | 读最近 14 天 `bed_time` + `sleep_early_streak` |
| 5 | POST | `/api/state/sleep` | `api_record_sleep` | **L2288** | L2289–2323 | `/api/state` | UPSERT 当日 `bed_time`；按状态更新 `sleep_early_streak`（手写 HH:MM 校验） |
| 6 | GET | `/api/state/weekly-energy` | `api_get_weekly_energy` | **L2325** | L2326–2334 | `/api/state` | 读最近 14 天 morning/afternoon/evening/tone |
| 7 | GET | `/api/state/questions` | `api_get_assessment_questions` | **L3357** | L3358–3359 | `/api/state` | 返回 `ASSESSMENT_QUESTIONS`（常量） |
| 8 | GET | `/api/state/assessment` | `api_get_today_assessment` | **L3361** | L3362–3382 | `/api/state` | 当日 `state_assessments` + 未完成时返回 question 模板 |
| 9 | POST | `/api/state/assessment` | `api_submit_assessment` | **L3384** | L3385–3405 | `/api/state` | `INSERT OR REPLACE` + 函数 `calculate_state_scores` |
| 10 | GET | `/api/state/assessment/history` | `api_get_assessment_history` | **L3407** | L3408–3417 | `/api/state` | 读 N 天评估（默认 14） |
| 11 | GET | `/api/state/assessment/correlate` | `api_get_correlation` | **L3419** | L3420–3454 | `/api/state` | 关联评估 vs 完成率（≥3 样本） |

### Section B: Helper functions called from those routes
| 调用者 | Helper | 行号 | 共享性 |
|---|---|---|---|
| `api_get_daily_tone`, `api_set_daily_tone`, `api_record_energy`, `api_get_sleep`, `api_record_sleep`, `api_get_weekly_energy`, `api_get_today_assessment`, `api_submit_assessment`, `api_get_assessment_history`, `api_get_correlation` | `get_db_connection` | L288–292 | **shared**（所有 BP 都用） |
| `api_submit_assessment` | `calculate_state_scores(answers, version=1)` | **L3321–3355** | state-BP 专用（但纯函数，可直接搬到 `services/state.py`） |
| 三个 assessment endpoint | `ASSESSMENT_QUESTIONS` 常量 | **L3312–3319** | state-BP 专用（评估问卷） |
| `api_record_sleep` 内联 | `re.match(r'^\d{2}:\d{2}$', bed_time)` | L2296 | 内联；不复用 |
| 全部 endpoint | `datetime.now()` / `datetime.now().strftime('%Y-%m-%d')` | 散落 | 内联；BP 还是 service 处理都行 |

### Section C: Database tables accessed
| 表 | 读/写 | schema 归属 | 备注 |
|---|---|---|---|
| `daily_user_state` | R + W | `server/schema/state.py::ensure_schema`（L107–135） | state BP 唯一所有；Phase 1 schema owner 已就绪 |
| `state_assessments` | R + W | `server/schema/state.py::ensure_schema`（L137–167） | state BP 唯一所有；formula 列 |
| `task_completion_feedback` (read-only on correlate) | R | **inline in backend_api.py**（**未**有 `ensure_*`！） | 由 `_archive/06_测试脚本/inspect_db_schema.py` 和部署脚本 `_archive/06_测试脚本/rebuild_tasks.py:180-182` 隐式创建；**Phase 2 切流需补 schema owner**（建议放 `server/schema/feedback.py`） |
| `tasks` (subquery for correlate) | R | `server/schema/tasks.py` | 跨域 read，不修改 |

### Section D: Stub state
- `server/blueprints/state_bp.py`：**41 行** PEP 562 stub，`_BACKEND_API_NAMES` 列出 11 个函数名（与上表 1–11 完全对应），无 `Blueprint(...)` 实例。
- `server/services/state.py`：**不存在**（需新建，迁移 `calculate_state_scores` + `ASSESSMENT_QUESTIONS`）。

> 后端全局 grep 显示 `server/services/state.py` 没有文件——stub 目录中**没有**为 state 预留占位符；todo 1 需新建。

- `server/repositories/state_repo.py`：**24 行** stub；提供 3 个 NotImplementedError：`get_daily_tone` / `get_weekly_energy` / `get_today_assessment`（注释明确"Phase 2 will introduce pure data functions"）。

### Section E: Dependencies on other BPs / globals
- **Globals**：`datetime.now()`；`NOTES_DIR` 仅 knowledge_bp 用，state 不依赖；`CONFIG` 不依赖。
- **跨 BP 耦合**：`api_submit_assessment` 经 `calculate_state_scores`（纯函数）→ 写 `state_assessments`，**无跨域读**。`api_get_correlation` 跨域 read `task_completion_feedback`（feedback 表）和 `tasks`（tasks 表），但通过 SQL join/subquery，不依赖 BP handler。
- **跨 schema**：`task_completion_feedback` 无 schema owner（详见 Section C）—— migration risk point #1。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**medium**（最复杂，因为 assessment 公式要在 service 层重写 + 1 个孤立表 schema 归属待补）。todo 1 排在最开始是合理的：先把 state 域（含跨域读 correlation）抽干净，下面的 feedback BP 才能干净地依赖 task_completion_feedback schema。

---

## 2. Schedule BP (Todo 2)

> 来源注释：`backend_api.py:2039 # TODO(phase2): migrate to server.app.blueprints.schedule_bp`

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/schedule/slots` | `api_get_schedule_slots` | **L2053** | L2054–2055 | `/api/schedule` | 返回常量 `SCHEDULE_SLOTS`（10 个时间槽） |
| 2 | GET | `/api/schedule/weekly` | `api_get_weekly_schedule` | **L2057** | L2058–2079 | `/api/schedule` | 读 `user_schedule`（按 day_of_week+time_slot 嵌套字典） |
| 3 | POST | `/api/schedule/weekly` | `api_save_weekly_schedule` | **L2081** | L2082–2104 | `/api/schedule` | DELETE + INSERT user_schedule + 联动 INSERT activity |
| 4 | GET | `/api/schedule/daily` | `api_get_daily_schedule` | **L2106** | L2107–2127 | `/api/schedule` | 读 `daily_schedules`（按 date） |
| 5 | POST | `/api/schedule/daily` | `api_save_daily_schedule` | **L2129** | L2130–2162 | `/api/schedule` | UPSERT `daily_schedules`（DELETE 当 activity 为空） |
| 6 | GET | `/api/schedule/activities` | `api_get_activities` | **L2164** | L2165–2172 | `/api/schedule` | 读 `activities` |
| 7 | POST | `/api/schedule/activities` | `api_add_activity` | **L2174** | L2175–2208 | `/api/schedule` | INSERT 幂等（重名返回 200 + added=False） |
| 8 | DELETE | `/api/schedule/activities/<int:act_id>` | `api_delete_activity` | **L2210** | L2211–2221 | `/api/schedule` | DELETE + 检查 rowcount |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `get_db_connection` | L288–292 | shared |
| `SCHEDULE_SLOTS` 常量 | L2040–2051 | schedule-BP 专用（可搬到 `services/schedule.py`，10 个时间槽无依赖） |
| `migrate_legacy_schedule_tables` (called by `ensure_schedule_schema`) | L866–892 | **共享**：被 `ensure_schedule_schema` 调用（已搬到 `server/schema/state.py::_migrate_legacy_schedule_tables`） |

### Section C: Database tables accessed
| 表 | 读/写 | schema 归属 |
|---|---|---|
| `user_schedule` | R + W | `server/schema/state.py::ensure_schema` 内段 1（**注**：state 路径命名不准，但现状如此） |
| `daily_schedules` | R + W | 同上 |
| `activities` | R + W | 同上 |
| `weekly_schedule`（legacy）| R only（迁移） | **不在 schema**（由旧表推断） |
| `daily_schedule`（legacy）| R only（迁移） | **不在 schema** |

### Section D: Stub state
- `server/blueprints/schedule_bp.py`：**39 行** PEP 562 stub；`_BACKEND_API_NAMES` 列出 8 个函数名（`api_get_schedule_slots` + 7 个 schedule route）。
- `server/services/schedule.py`：**5 行** placeholder（仅 `__all__: list = []`）。
- `server/repositories/schedule_repo.py`：**不存在**（todos 列表未列入；可与 knowledge 复用 `note_index_repo` 模式，或加新 stub）。

### Section E: Dependencies on other BPs / globals
- **Globals**：`datetime.now()` 用于缺省日期（GET/POST daily）。
- **跨 BP 耦合**：`api_save_weekly_schedule` + `api_save_daily_schedule` 写 `activities` 表——这是 schedule 域**跨域**写，但同一个 DB。把它放 `schedule_bp` 内部合理。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**easy**（逻辑纯 SQL，schedule 操作无副作用，难点 10 个时间槽常量需搬到 service）。约 8 个 endpoint。

---

## 3. Feedback BP (Todo 3)

> 来源注释：`backend_api.py:2337 # TODO(phase2): migrate to server.app.blueprints.feedback_bp`
> **注意**：plan Todo 3 写 ≈3 endpoints；实际 backend_api.py 里有 **3 个** 反馈路径，其中 1 个在 tasks 域（`/api/tasks/<id>/feedback`），2 个在 feedback 域（`/api/task-feedback`）。这里的 3 都归 feedback BP。

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/tasks/<int:task_id>/feedback` | `api_task_feedback` | **L2338** | L2339–2362 | `/api/tasks`（任务域）→ 但属于 feedback 业务 | 写 `task_completion_feedback` + 联动写 `daily_user_state`（state 域） |
| 2 | POST | `/api/task-feedback` | `api_create_task_feedback` | **L2364** | L2365–2392 | `/api/task-feedback` | 写 `task_feedback_events`（带事件分类校验） |
| 3 | GET | `/api/task-feedback` | `api_list_task_feedback` | **L2394** | L2395–2413 | `/api/task-feedback` | 读 `task_feedback_events`（按 task_id 过滤） |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `get_db_connection` | L288–292 | shared |
| `get_task_by_id(task_id)` | L367–379 | **shared**（tasks_bp 已用；feedback BP 沿用） |
| `insert_task_feedback_event(data)` | **L786–810** | feedback-BP 专用 |
| `TASK_FEEDBACK_EVENT_TYPES` | **L745–747** | feedback-BP 专用（5 个事件类型） |
| `TASK_FEEDBACK_REASON_CATEGORIES` | **L748–751** | feedback-BP 专用（7 个原因分类） |
| `api_task_feedback` 内部 | `datetime.now().hour` → 推断 period | **裸 inline**（没抽取 helper；可直接写 service） |

### Section C: Database tables accessed
| 表 | 读/写 | schema 归属 |
|---|---|---|
| `task_completion_feedback` | W | **inline / 外部脚本**（无 `ensure_*`；见 state BP Section C 风险点） |
| `task_feedback_events` | R + W | `server/schema/feedback.py::ensure_schema`（L19-56） |
| `daily_user_state` | W（仅 `api_task_feedback` 联动） | `server/schema/state.py` |
| `tasks` | R (existence check) | `server/schema/tasks.py` |

### Section D: Stub state
- `server/blueprints/feedback_bp.py`：**32 行** stub；`_BACKEND_API_NAMES` 仅列 **2** 个（`api_create_task_feedback`、`api_list_task_feedback`）—— **`api_task_feedback` 未列入**。Todo 3 需补这一项。
- `server/services/feedback.py`：**不存在**（需新建）。
- `server/repositories/feedback_repo.py`：**15 行** stub：提供 `insert_event(data)` 已**直通** `insert_task_feedback_event`（L13–14）；`list_feedback` 仍 NotImplementedError。

### Section E: Dependencies on other BPs / globals
- **跨 BP 写**：`api_task_feedback` 写 `daily_user_state`（state 域）。这是显著的跨域写；倾向于在 service 层把它当 `feedback_service.record_task_completion(...)` 调用一个 `state_service.update_energy(period, value)`，但循环依赖风险存在——**Resolve 方案**：让 `state_repo` 提供低层 `update_energy(conn, date, period, value)`，feedback service 直接用 conn 调；不依赖 state_bp/state_service。
- **跨 BP 读**：`api_create_task_feedback` 调 `get_task_by_id`（task BP 工具函数）。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**medium**（表 owner 不齐 + 跨域写 + stub 漏列 1 个 endpoint）。todo 3 紧跟 state 之后做：state BP 把 `daily_user_state` repo 抽干净后，feedback BP 才能干净地跨域写。

---

## 4. Timer BP (Todo 4)

> 来源注释：`backend_api.py:3014 # TODO(phase2): migrate to server.app.blueprints.timer_bp`

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/timer/start` | `api_timer_start` | **L3015** | L3016–3036 | `/api/timer` | 启动 session（拒绝重入） |
| 2 | POST | `/api/timer/complete` | `api_timer_complete` | **L3038** | L3039–3060 | `/api/timer` | 结束 session（允许 running / paused 状态） |
| 3 | GET | `/api/timer/active` | `api_timer_active` | **L3062** | L3063–3079 | `/api/timer` | 读最新 active session（join tasks 取 task_name） |
| 4 | POST | `/api/timer/pause` | `api_timer_pause` | **L3081** | L3082–3114 | `/api/timer` | 累加 paused_seconds（P3 bug 修复） |
| 5 | POST | `/api/timer/resume` | `api_timer_resume` | **L3116** | L3117–3142 | `/api/timer` | 重置 started_at 为 now |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `get_db_connection` | L288–292 | shared |
| `ensure_timer_schema`（启动时调） | L710–743 | timer-BP 专用（已搬到 `server/schema/__init__.py::ensure_timer_schema`，但**应**移到 `server/schema/timer.py`——见 plan 注释） |

### Section C: Database tables accessed
| 表 | 读/写 | schema 归属 |
|---|---|---|
| `timer_sessions` | R + W | `server/schema/__init__.py::ensure_timer_schema`（L120-157） |
| `tasks` (join, 取 task_name) | R | `server/schema/tasks.py` |

### Section D: Stub state
- `server/blueprints/timer_bp.py`：**35 行** stub；`_BACKEND_API_NAMES` 列 5 个（与上表 1–5 完全对应）。
- `server/services/timer.py`：**5 行** placeholder。
- `server/repositories/timer_repo.py`：**不存在**（todo 4 需新建）。

### Section E: Dependencies on other BPs / globals
- **跨 BP**：join `tasks` 表（不依赖 schema，但 SQL 引用 `tasks.name`）。无需跨 BP handler。
- **P3 bug**：pause/resume/active 涉及 `paused_seconds` 字段（`ensure_timer_schema` 中 ALTER 添加）；schema 已有保障。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**easy**（5 个 endpoint 全部纯 SQL，无业务规则；难点仅 `paused_seconds` 暂停累计语义）。约 5 个 endpoint。

---

## 5. Knowledge BP (Todo 5)

> 来源注释：`backend_api.py:1561 # TODO(phase2): migrate to server.app.blueprints.knowledge_bp`
> 标记 **9 endpoints**（最大域）。

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/knowledge/categories` | `api_get_knowledge_categories` | **L1562** | L1563–1595 | `/api/knowledge` | 5 个固定科目（高数/大物/线代/电子/计算机），统计 .md 文件数 |
| 2 | GET | `/api/knowledge/points` | `api_get_knowledge_points` | **L1597** | L1598–1631 | `/api/knowledge` | 读 `src/notes/知识点/*.md` |
| 3 | GET | `/api/knowledge/graph` | `api_get_knowledge_graph` | **L1813** | L1814–1815 | `/api/knowledge` | 包装 `build_vault_knowledge_graph()` |
| 4 | GET | `/api/knowledge/note/<path:note_path>` | `api_get_note_content` | **L1817** | L1818–1828 | `/api/knowledge` | 读 vault 单文件 |
| 5 | GET | `/api/knowledge/recent` | `api_get_recent_knowledge` | **L1830** | L1831–1838 | `/api/knowledge` | **硬编码 4 个静态条目**（P3 known issue） |
| 6 | GET | `/api/knowledge/notes` | `api_get_notes` | **L1840** | L1841–1857 | `/api/knowledge` | 走 vault 根目录直接 os.listdir |
| 7 | GET | `/api/knowledge/note-content/<path:note_path>` | `api_get_note_content_full` | **L1859** | L1860–1870 | `/api/knowledge` | 同 #4，但 path 解析带 `path:` 转换 |
| 8 | GET | `/api/knowledge/point-detail/<subject>/<point_name>` | `api_get_knowledge_point_detail` | **L1872** | L1873–1885 | `/api/knowledge` | 读 `src/notes/知识点/<subject>/<point>.md` |
| 9 | POST | `/api/knowledge/open-in-obsidian` | `api_open_in_obsidian` | **L1887** | L1888–1912 | `/api/knowledge` | 启动 `obsidian://` URI（用 `subprocess.Popen(['start', '', uri], shell=True)`） |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `NOTES_DIR` (global) | L32 | **shared**（agent_bp 也用） |
| `get_category_id(subject)` | **L1633–1641** | knowledge-BP 专用（5 个科目映射） |
| `get_category_name(category_id)` | **L1643–1651** | knowledge-BP 专用 |
| `_wiki_link_target(raw)` | **L1658–1664** | knowledge-BP 专用 |
| `_vault_rel_path(root, full_path)` | **L1666–1668** | knowledge-BP 专用 |
| `_note_category(rel_path)` | **L1670–1676** | knowledge-BP 专用 |
| `_parse_note_tags(content)` | **L1678–1689** | knowledge-BP 专用 |
| `_resolve_wiki_target(target, current_rel, stem_index, path_index)` | **L1691–1709** | knowledge-BP 专用 |
| `_resolve_md_link(href, current_rel, path_index)` | **L1711–1722** | knowledge-BP 专用 |
| `_extract_links_from_content(content, source_id, current_rel, stem_index, path_index)` | **L1724–1743** | knowledge-BP 专用 |
| `build_vault_knowledge_graph()` | **L1745–1811** | knowledge-BP 专用 |
| `_WIKI_LINK_RE` / `_MD_LINK_RE` / `_TAG_RE` / `_FRONTMATTER_TAGS_RE` | L1653–1656 | knowledge-BP 专用（正则 module-level） |
| `api_open_in_obsidian` 内联 `import subprocess` | L1904 | inline |
| `api_open_in_obsidian` 内联 `import urllib.parse` | L1905 | inline |

### Section C: Database tables accessed
**无 SQLite 表**——knowledge 域完全走文件系统（`src/notes/vault`/未分类/已分类）。
- `server/schema/notes.py` 存在但 `ensure_schema` 是 no-op placeholder（forward-compat for Phase 2/3 索引）。
- `server/repositories/note_index_repo.py`（15 行）stub：2 个 NotImplementedError（`categories` / `recent_notes`）。

### Section D: Stub state
- `server/blueprints/knowledge_bp.py`：**39 行** stub；`_BACKEND_API_NAMES` 列 9 个（与上表 1–9 完全对应）。
- `server/services/knowledge.py`：**5 行** placeholder。
- `server/repositories/note_index_repo.py`：**15 行** stub（已存在）。

### Section E: Dependencies on other BPs / globals
- **Globals**：`NOTES_DIR`（L32）—— agent_bp 也用，**不是 knowledge 私有**；迁移后建议注入 `current_app.config["_notes_dir"]`。
- **跨 BP**：`api_get_knowledge_points` 用 `get_category_id` / `get_category_name`（同文件内 helper，无跨 BP）。
- **Possible cycle**：`api_open_in_obsidian` 用 `subprocess.Popen(['start', '', uri], shell=True)` 调用 Windows shell；service 层不要直接吃这个副作用，让 BP 层负责。
- **P3 issue**：`api_get_recent_knowledge` 硬编码 4 个 fake 笔记条目（不是 bug，是 stub）；BP 迁移时保留现状即可。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**medium**（9 个 endpoint 中 7 个是文件 IO + 2 个图谱构建；最大负担是 `build_vault_knowledge_graph` (66 行) + 5 个 regex/helper 拆分）。属于体量大但逻辑纯。

---

## 6. Config BP (Todo 6)

> 来源注释：`backend_api.py:1915 # TODO(phase2): migrate to server.app.blueprints.config_bp`
> 同时：plan Todo 6 标 ≈3 endpoints；实际 4 个（含 `api_health_check` 和 `api_export_system_state` —— 后者 plan 标"(or a new export_bp)"）。

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/config` | `api_get_config` | **L1916** | L1917–1926 | `/api/config` | 返回 `CONFIG` 字段（port / notes_dir / vault_path / api keys 存在性） |
| 2 | POST | `/api/config/save` | `api_save_config` | **L1928** | L1929–1963 | `/api/config` | 深度合并 `config/config.json` + 重新 `load_config()` |
| 3 | GET | `/api/health` | `api_health_check` | **L1556** | L1557–1558 | `/api/health` | 简单 status 校验 |
| 4 | GET | `/api/export` | `api_export_system_state` | **L2527** | L2528–2538 | `/api/export` | 10 张表全导出 |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `CONFIG` (global) | L24 | **shared** |
| `load_config()` | L12–22 | **shared**（已在 `server/app/config.py` 有等价实现） |
| `get_db_connection` | L288–292 | shared |
| `api_save_config` 内联 `json.dump(..., ensure_ascii=False, indent=4)` | L1954 | inline |
| `api_save_config` 写完后 `global CONFIG; CONFIG = load_config()` | L1958 | inline（**副作用**：重置全局，BP 迁移后必须改成 `app.config["CONFIG"]` 风格） |

### Section C: Database tables accessed
- `api_export_system_state` 读 10 张表：`tasks`, `tags`, `task_tags`, `task_dependencies`, `user_schedule`, `daily_schedules`, `daily_user_state`, `gacha_records`, `task_rejection_log`, `task_completion_feedback`（L2533 hardcoded list）
- 这 10 张表**横跨所有 BP**；export 跨域 read 但不写
- 表 schema 分散在 `server/schema/*.py` 各文件

### Section D: Stub state
- `server/blueprints/config_bp.py`：**34 行** stub；`_BACKEND_API_NAMES` 列 **4** 个（含 `api_health_check` + `api_export_system_state`——这两个 plan 说"or a new export_bp"）。
- `server/services/ai.py`：**5 行** placeholder（**不对应 config**——AI reuse LLM 服务）。
- `server/services/config.py`：**不存在**（需新建）。
- `server/repositories/config_repo.py`：**不存在**（需新建；或加 `export_repo.py`）。

### Section E: Dependencies on other BPs / globals
- **Globals**：`CONFIG` `load_config` 直接被读 + 写；BP 迁移后必须用 `current_app.config["CONFIG"]` 或持久化服务。
- **跨 BP**：export 跨域读 10 张表，但仅 SQL，不依赖其他 BP。
- **Closure / decorator / 全局**：`api_save_config` 的 `global CONFIG` 重置是**隐藏副作用**——BP 迁移到 service 后必须改成函数化（返回新 config dict 或 set in app.config）。

### Section F: Migration complexity
**medium**（全局 `CONFIG` 重置要重构 + export 跨域 read 10 张表的 SQL 列表要维护）。建议拆 `api_export_system_state` 到独立 `export_bp`（plan 标注 "(or a new export_bp)"）。

---

## 7. Prompts BP (Todo 7)

> 来源注释：`backend_api.py:3145 # TODO(phase2): migrate to server.app.blueprints.prompts_bp`

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/prompts` | `api_list_prompts` | **L3207** | L3208–3224 | `/api/prompts` | 列 `prompts/*.md` 文件 |
| 2 | GET | `/api/prompts/<path:name>/backup/latest` | `api_prompt_backup_latest` | **L3226** | L3227–3245 | `/api/prompts` | 查最新 save 备份 |
| 3 | POST | `/api/prompts/<path:name>/restore-latest` | `api_prompt_restore_latest` | **L3247** | L3248–3268 | `/api/prompts` | 恢复 + 落 restore 备份 |
| 4 | GET | `/api/prompts/<path:name>` | `api_get_prompt` | **L3270** | L3271–3279 | `/api/prompts` | 读单个 prompt |
| 5 | PUT | `/api/prompts/<path:name>` | `api_save_prompt` | **L3281** | L3282–3305 | `/api/prompts` | 写（含 save 备份 + atomic tmp+replace） |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `PROMPTS_DIR` (global) | **L2583** | **shared**（agent_bp 也用） |
| `PROMPTS_BACKUP_DIR` (global) | **L3146** | prompts-BP 私有 |
| `_safe_prompt_basename(name)` | **L3148–3162** | prompts-BP 专用（防路径穿越） |
| `_prompt_file_path(name)` | **L3164–3172** | prompts-BP 专用 |
| `_create_prompt_backup_file(fpath, basename, kind='save')` | **L3174–3183** | prompts-BP 专用 |
| `_latest_prompt_backup_name(basename, kind='save')` | **L3185–3205** | prompts-BP 专用（兼容旧备份命名） |

### Section C: Database tables accessed
**无 SQLite 表**——纯文件系统（`src/notes/prompts/` + `.backups/`）。

### Section D: Stub state
- `server/blueprints/prompts_bp.py`：**35 行** stub；`_BACKEND_API_NAMES` 列 5 个（与上表 1–5 完全对应）。
- `server/services/prompts.py`：**不存在**（需新建）。
- `server/repositories/prompts_repo.py`：**不存在**（文件系统无需 SQL repo，可直接 in service）。

### Section E: Dependencies on other BPs / globals
- **Globals**：`PROMPTS_DIR`（L2583，**与 agent_bp 共享**）。BP 迁移后改 `current_app.config["_prompts_dir"]` 或 `cfg["_prompts_dir"]`。
- **跨 BP**：无。
- **Closure / decorator / 全局**：无。
- **安全语义**：`_safe_prompt_basename` 严格防 `..` / `:` / `/` / `.backups` 字样；BP 层移到 service 时**必须保留这些检查**。

### Section F: Migration complexity
**easy**（5 个 endpoint 全是文件 IO，无跨域，逻辑封闭）。约 5 个 endpoint。

---

## 8. Agent BP (Todo 8)

> 来源注释：`backend_api.py:2581 # TODO(phase2): migrate to server.app.blueprints.agent_bp`
> 含 LLM 写能力（`api_agent_save_note` / `api_agent_import_tasks`），**plan 标最后迁移 + 顶部加安全标注**。

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/agent/agents` | `api_list_agents` | **L2673** | L2674–2682 | `/api/agent` | 枚举 `AGENT_CONFIG` |
| 2 | GET | `/api/agent/files/raw` | `api_list_raw_files` | **L2684** | L2685–2725 | `/api/agent` | 读 `src/notes/未分类/` + `已分类/` |
| 3 | GET | `/api/agent/files/vault` | `api_list_vault_files` | **L2727** | L2728–2751 | `/api/agent` | 读 `src/notes/<subject>/` |
| 4 | GET | `/api/agent/agents/<agent_id>/prompt` | `api_get_agent_prompt` | **L2819** | L2820–2842 | `/api/agent` | 读 prompt 文件 |
| 5 | GET | `/api/agent/files/raw/content` | `api_get_raw_file_content` | **L2844** | L2845–2852 | `/api/agent` | 读单 txt |
| 6 | GET | `/api/agent/files/vault/content` | `api_get_vault_file_content` | **L2854** | L2855–2863 | `/api/agent` | 读单 md |
| 7 | POST | `/api/agent/process` | `api_agent_process` | **L2865** | L2866–2952 | `/api/agent` | 调 LLM（**含写**：`api_agent_save_note` 由前端二次调用） |
| 8 | POST | `/api/agent/save-note` | `api_agent_save_note` | **L2954** | L2955–2975 | `/api/agent` | **写**：落 vault md |
| 9 | POST | `/api/agent/import-tasks` | `api_agent_import_tasks` | **L2977** | L2978–3011 | `/api/agent` | **写**：解析 LLM JSON → `add_task` |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `PROMPTS_DIR` (global) | L2583 | **shared** |
| `RAW_DIR` (global) | L2584 | agent-BP 专用（src/notes/未分类） |
| `CLASSIFIED_DIR` (global) | L2585 | agent-BP 专用（src/notes/已分类） |
| `SUBJECT_MAP` | **L2588** | agent-BP 专用 |
| `AGENT_CONFIG` | **L2590–2621** | agent-BP 专用（5 个 agent 元数据） |
| `INPUT_TYPE_LABELS` | **L2753–2757** | agent-BP 专用 |
| `ACTION_LABELS` | **L2758–2762** | agent-BP 专用 |
| `load_prompt(agent_id)` | **L2623–2631** | agent-BP 专用 |
| `call_llm(system_prompt, user_message)` | **L2633–2649** | agent-BP 专用（**含__import__('urllib')** 内联） |
| `_resolve_agent_prompt_path(prompt_file)` | **L2764–2774** | agent-BP 专用 |
| `_safe_agent_raw_path(rel)` | **L2776–2797** | agent-BP 专用（防路径穿越） |
| `_safe_agent_vault_path(rel)` | **L2799–2817** | agent-BP 专用（防路径穿越） |
| `_build_task_context()` | **L2651–2671** | agent-BP 专用（为 task_publisher agent 注入任务上下文） |
| `add_task(task)` | L381–417 | **shared**（task_bp 已有等价实现，agent_bp 沿用） |
| `api_agent_import_tasks` 内联 `Task(...)` dataclass 构造 | L2998 | **shared**（来自 backend_api.py L63–238） |
| `get_db_connection` | L288–292 | shared |

### Section C: Database tables accessed
- `tasks`（仅 `api_agent_import_tasks` 写）
- 无其他表读/写

### Section D: Stub state
- `server/blueprints/agent_bp.py`：**44 行** stub；`_BACKEND_API_NAMES` 列 9 个（与上表 1–9 完全对应）。
- `server/services/ai.py`：**5 行** placeholder（plan 标"含 Agent 调用"）。
- `server/services/agent.py`：**不存在**（或直接放 `ai.py`）。
- `server/ai/llm_client.py`：**存在**（task 计划 §提到；未读取——建议 todo 8 确认 `load_prompt`/`call_llm` 是否已迁过去）。
- `server/repositories/agent_repo.py`：**不存在**（agent 业务大多无 DB；如需 tasks 持久化可复用 `task_repo`）。

### E: Dependencies on other BPs / globals
- **Globals**：`PROMPTS_DIR` / `RAW_DIR` / `CLASSIFIED_DIR` / `CONFIG['api'][...]`（在 `call_llm` 里读 api_key）—— 全部移到 `current_app.config`。
- **跨 BP 写**：
  - `api_agent_import_tasks` 写 `tasks` 表（**task BP 域**）—— 通过 `add_task` helper，与 task_bp 复用。
  - `api_agent_save_note` **写 `src/notes/`**（**knowledge 域的安全敏感**）—— 这是 Agent BP 唯一高风险写点。
- **LLM 副作用**：`call_llm` 实际发 HTTP 请求；BP 迁移后 service 层保留，业务流在 service 完成。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**hard**（9 endpoint + 5 个 agent 配置 + LLM 集成 + 跨域写 + 路径穿越防护），同时**业务安全敏感**。plan 把 todo 8 排最后迁移是合理的。

---

## 9. Discard BP (Todo 9)

> 来源注释：`backend_api.py:1535 # TODO(phase2): migrate to server.app.blueprints.discard_bp`

### Section A: Routes in backend_api.py
| # | HTTP | URL | Function | Decorator 行 | Body 行范围 | URL 前缀 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/discard-pile` | `api_get_discard_pile` | **L1536** | L1537–1539 | `/api/discard-pile` | 读 `in_discard_pile=1` 任务 |
| 2 | POST | `/api/discard-pile/<int:task_id>/restore` | `api_restore_from_discard` | **L1541** | L1542–1549 | `/api/discard-pile` | 还原（mark in_discard_pile=0） |
| 3 | POST | `/api/tasks/<int:task_id>/move-to-discard` | `api_move_to_discard` | **L1551** | L1552–1554 | `/api/tasks`（任务域）→ 但属于 discard 业务 | 移到弃牌堆（mark in_discard_pile=1） |

### Section B: Helper functions called from those routes
| Helper | 行号 | 共享性 |
|---|---|---|
| `get_discard_pile_tasks()` | **L1242–1259** | discard-BP 专用 |
| `move_task_to_discard_pile(task_id)` | **L1261–1276** | discard-BP 专用 |
| `move_task_to_gacha_pile(task_id)` | **L1278–1290** | discard-BP 专用 |
| `get_task_by_id` | L367–379 | **shared** |
| `_attach_tags` | L313–324 | **shared**（task_bp 内部用） |
| `get_task_tags` | L296–299 | **shared** |
| `get_db_connection` | L288–292 | shared |

### Section C: Database tables accessed
- `tasks`（R + W：仅 `in_discard_pile` 字段）—— schema 在 `server/schema/tasks.py`

### Section D: Stub state
- `server/blueprints/discard_bp.py`：**33 行** stub；`_BACKEND_API_NAMES` 列 3 个（与上表 1–3 完全对应）。
- `server/services/discard.py`：**不存在**（需新建）。
- `server/repositories/task_repo.py` 已存在（已含 `get_discard_pile` / `move_to_discard` / `move_to_gacha_pile` 3 个直通函数）—— **完美复用**。

### Section E: Dependencies on other BPs / globals
- **跨 BP**：operation 全在 `tasks` 表，但语义属于 discard 域；不是"跨域"——业务正确归属。
- **Closure / decorator / 全局**：无。

### Section F: Migration complexity
**easy**（3 endpoint 全部单字段更新，task_repo 已有 3 个 helper 直通）。约 3 个 endpoint。

---

## 10. Gacha 切流（Todo 10）

> 复杂度按 plan 单独 todo 抽出来；无独立 BP 文件，但涉及删除 `backend_api.py` 6 个 `_calculate_*` + `_weighted_pick` + 切换 `select_weighted_random_task` 内部调用。

### 10.1 抽卡算法函数清单（backend_api.py）
| 函数 | 行号 | 状态 |
|---|---|---|
| `_calculate_full_weight(task, current_energy, session_context=None)` | **L1019–1032** | 切流时**删除** |
| `_calculate_deadline_urgency(task)` | **L1034–1052** | 切流时**删除** |
| `_calculate_energy_match(task, current_energy)` | **L1054–1059** | 切流时**删除** |
| `_calculate_resistance_factor(task)` | **L1061–1063** | 切流时**删除** |
| `_calculate_profile_strategy_weight(task)` | **L1065–1097** | 切流时**删除** |
| `_calculate_cooldown_factor(task, session_context)` | **L1099–1114** | 切流时**删除** |
| `select_weighted_random_task(current_energy="medium", session_context=None)` | **L1116–1138** | 切流时**重写**为调 `DefaultGachaAlgo` |
| `_weighted_pick(tasks, energy, session)` | **L1210–1224** | 切流时**删除**（被 `draw_single` 调用） |

### 10.2 函数调用关系（必须无遗漏）
调用 `_calculate_*` 的位置：
- `select_weighted_random_task` L1125 → `_calculate_full_weight`（L1116–1138）
- `_weighted_pick` L1214 → `_calculate_full_weight`（L1210–1224）
- `_calculate_full_weight` L1022 / L1023 / L1024 / L1027 / L1030 → 5 个 `_calculate_*` helper

调用 `select_weighted_random_task` 的位置：
- **无直接调用**（grep 验证：仅函数定义在 L1116，没在 backend_api.py 其他位置调用）—— 这意味着 `select_weighted_random_task` 是**死代码**？

> ⚠️ grep 验证：`grep -n "select_weighted_random_task" server/backend_api.py` 仅命中 L1116（定义本身）。在 `gacha_bp.py` / `tasks_bp.py` / `archive/` 中均无引用。Todo 10 切流时**可删除** `select_weighted_random_task` 而不影响 36/36 E2E。

调用 `_weighted_pick` 的位置：
- `draw_single` L1196 → `_weighted_pick`（L1210–1224）
- `draw_single` 被调用：
  - `api_draw_task` L1492
  - `api_care_gacha_draw` L1520
  - `api_gacha_replace` L2496

### 10.3 `DefaultGachaAlgo` 接口签名（来自 server/services/gacha.py）
- `class WeightInputs`（L23-32 数据类）：
  ```python
  @dataclass
  class WeightInputs:
      task: object               # duck-typed: priority/energy_required/resistance/success_rate/refusal_count/draw_count_today/category/task_profile/deadline/id
      current_energy: str         # 'low' | 'medium' | 'high'
      session_context: Optional[object] = None  # duck-typed: last_drawn_task_id / last_drawn_category / category_count_in_last_3
      deadline: Optional[str] = None
      task_profile: Optional[str] = None
      draw_count_today: int = 0
  ```
- `class DefaultGachaAlgo`（L50–184）：
  - `compute_weight(self, inputs: WeightInputs) -> float`（L65–94）
  - `pick(self, n: int, weights: List[float], rng: object) -> int`（L96–109）

### 10.4 1:1 等价测试计划（推荐）

**目标**：1000 task × 100 energy = 100k 组合，|W_old − W_new| < 1e-9。

**输入采样**：
- 1000 个 task：覆盖 5 种维度笛卡尔积的稀疏集
  - `priority` ∈ {1, 3, 5, 7, 10}（5 个）
  - `energy_required` ∈ {low, medium, high}（3 个）
  - `resistance` ∈ {low, medium, high}（3 个）
  - `success_rate` ∈ {0.0, 0.3, 0.5, 0.8, 1.0}（5 个）
  - `refusal_count` ∈ {0, 1, 3, 5, 10}（5 个）
  - `task_profile` ∈ {daily_habit, weekly_routine, deadline_flexible, deadline_progressive}（4 个）
  - `deadline` ∈ {None, 1 day, 3 days, 7 days, 30 days}（5 个）
  - `draw_count_today` ∈ {0, 1, 3, 5}（4 个）
  - 5×3×3×5×5×4×5×4 = **540,000** already，截断 + 随机采样到 1000
- 100 种 `current_energy` 组合：
  - `current_energy` ∈ {low, medium, high}（3 个）
  - 100 个 = 33 low + 33 medium + 34 high
  - 同时**对齐** `current_energy` 与 `session_context` 的全笛卡尔（小量级）

**对比接口**：
```python
W_old = backend_api._calculate_full_weight(task, current_energy, session_context)
W_new = DefaultGachaAlgo().compute_weight(WeightInputs(
    task=task,
    current_energy=current_energy,
    session_context=session_context,
    deadline=task.deadline,
    task_profile=task.task_profile,
    draw_count_today=task.draw_count_today,
))
assert abs(W_old - W_new) < 1e-9
```

**已知等价性问题**（agent 报告 STATUS_REPORT §2 bug 7 提示）：
- **未做 1:1 黄金对比等价验证**（plan L37）
- 潜在差异点：`task.draw_count_today` 在 `_calculate_cooldown_factor`（L1099–1114）从 `task.draw_count_today` 读，`DefaultGachaAlgo._cooldown` 从 `inputs.draw_count_today` 读（取 max 0.2 因子时一致——但若 weight_inputs 没传就会 diff）—— 切流时**必须保证 `draw_count_today` 被传入**。
- `select_weighted_random_task` L1116 与 `_weighted_pick` L1210 在 `total <= 0` 路径下用 `random.choice(tasks)` 退路；切流时 `DefaultGachaAlgo.pick` 的对应分支是 `rng.randrange(n)`，**随机性不同**——黄金对比应**比较 weight 一致性而非 task 选择**。

**推荐输出**：
- 落在 `tests/phase2_gacha_golden_2026-08-16.log`（plan L186）
- 脚本：`scripts/phase2_gacha_golden.py`（plan L100）

---

## 11. 切流风险汇总（下游 Migration Agent 必看）

### 11.1 Schema Owner 缺失风险
- `task_completion_feedback` 表**无 `ensure_*` 函数**，由 `_archive/06_测试脚本/rebuild_tasks.py:180-182` 隐式创建。state BP 的 `api_get_correlation` 跨域读它，feedback BP 的 `api_task_feedback` 跨域写它。
- **Todo 11 必补**：`server/schema/feedback.py::ensure_schema` 增加 `task_completion_feedback` DDL（参考 `_archive/06_测试脚本/rebuild_tasks.py:180-182`）。

### 11.2 全局 `CONFIG` 重置副作用
- `api_save_config` 内有 `global CONFIG; CONFIG = load_config()`（L1958–1959）。
- BP 迁移后必须改成函数化：
  - 方案 A：返回新 config dict，BP 层更新 `current_app.config["CONFIG"]`
  - 方案 B：`config_service.save(payload)` 内部 `load_config()` 并挂到 `app.config`

### 11.3 `api_task_feedback` 跨域写 `daily_user_state`
- feedback BP 写 state 域表。避免 BP→BP 循环依赖：
  - 让 `state_repo.update_energy(conn, date, period, value)` 提供低层 SQL；feedback service 直接用 conn 调。
  - 不要让 `feedback_service` import `state_service`。

### 11.4 `api_export_system_state` 跨域读 10 张表
- 列出 10 张表名字符串（L2533），**任何未来的 schema 重命名/扩表都会失效**。
- 建议：让 `server/schema/__init__.py` 暴露一个 `TABLE_REGISTRY` 列表，export BP 直接读这列表。

### 11.5 `select_weighted_random_task` 是死代码
- L1116–1138，`grep` 全项目**仅命中定义本身**，没有调用方。
- Todo 10 切流时可以**直接删除**，无需替换。

### 11.6 `PROMPTS_DIR` / `NOTES_DIR` / `RAW_DIR` / `CLASSIFIED_DIR` 全局路径
- 被 agent_bp + knowledge_bp + prompts_bp 共享；BP 迁移后改 `current_app.config["_prompts_dir"]` 等。
- `server/app/config.py` 已有 `_db_path` / `_notes_dir` / `_project_root` 衍生字段——**建议**追加 `_prompts_dir` / `_raw_dir` / `_classified_dir`（在 `app_factory.py` L41–43 一带）。

### 11.7 `api_open_in_obsidian` 用 `subprocess.Popen(['start', '', uri], shell=True)`
- 仅 Windows 有效；service 层不抽这个副作用，让 BP 层负责。

### 11.8 `api_health_check` 归到 config_bp 不优雅
- plan "Todo 6: config_bp 迁移 ~3 endpoints" 没把 `/api/health` 算进去；但 stub 列了。
- 建议 todo 12（`backend_api.py` 收尾）时把 `/api/health` 留在 `app_factory.py` 的 `_health` 函数（L61–63）—— Phase 1 已有等价。

### 11.9 Stub BP 漏列 endpoint
- `feedback_bp.py` stub 漏列 `api_task_feedback`（仅 2 个，缺第 3 个）。Todo 3 升级到真 BP 时**必须包含**这个 3 个 endpoint。

### 11.10 36/36 E2E baseline 必跑
- 每个 todo 完成后**必跑** `node tests/e2e-manual.js`（plan 硬约束 #4）。
- `verify_p0_cleanup.py` 22/22 断言也在每个 todo 完成后必跑（plan 硬约束 #7 防 PEP 562 误改）。

---

## 12. 统计 Summary

### 12.1 9 BP 端点数（按 plan Todo 排序）
| BP | 端点数 | URL 前缀 | 复杂度 |
|---|---|---|---|
| state_bp | **11** | `/api/state` | medium |
| schedule_bp | **8** | `/api/schedule` | easy |
| feedback_bp | **3** | `/api/task-feedback` + 1 cross | medium |
| timer_bp | **5** | `/api/timer` | easy |
| knowledge_bp | **9** | `/api/knowledge` | medium |
| config_bp | **4**（含 /api/health + /api/export） | `/api/config` | medium |
| prompts_bp | **5** | `/api/prompts` | easy |
| agent_bp | **9** | `/api/agent` | hard |
| discard_bp | **3** | `/api/discard-pile` + 1 cross | easy |
| **合计** | **57 endpoint** | 9 个 BP | — |

> 注：3 个真 BP（tasks/gacha/tags）已迁移并**已注册**到 `create_app()`（见 `server/app/app_factory.py` L57–59），不在本文档范围。最终 `create_app()` 注册 9+3=12 个 BP，对应 30+ 路由（参见 plan L232 "21 个旧路由 + 9 个新 BP 路由 + /api/health = 30"）。

### 12.2 Todo 顺序重排建议
- Plan 顺序：state → schedule → feedback → timer → knowledge → config → prompts → agent → discard
- 推荐（基于"依赖方向"）：
  1. **state_bp**（必须先做：定 `daily_user_state` / `state_assessments` repo，feedback BP 才能干净跨域写）
  2. **schedule_bp**（独立）
  3. **feedback_bp**（依赖 state_repo 提供 `update_energy`）
  4. **timer_bp**（独立）
  5. **knowledge_bp**（独立，体量大但逻辑纯）
  6. **discard_bp**（独立，3 个 endpoint，task_repo 已有 helper）
  7. **prompts_bp**（独立）
  8. **config_bp**（含 export 跨域）
  9. **agent_bp**（最后 + 安全标注）

### 12.3 路径与命名 checklist
- BP 路径：`server/blueprints/<name>_bp.py` ✅ Phase 1 已就绪
- Service 路径：`server/services/<name>.py`（**state / schedule / timer / knowledge / feedback / prompts / agent / discard 待新建**）
- Repository 路径：`server/repositories/<name>_repo.py`（**schedule / timer / knowledge / config / prompts / agent / discard 待新建**）
- Schema 路径：`server/schema/<name>.py`（**已就绪 feedback / state / tasks / notes / gacha**；timer 路径不一致见 Section 0.3）

---

## 13. 交付状态

- **报告生成时间**：2026-08-16
- **生成方式**：read-only 调查（仅 Grep/Read / Write new report）
- **未做改动文件**：`server/backend_api.py` / `server/blueprints/*_bp.py` / `server/services/*` / `server/repositories/*` / `server/schema/*` 全部保持原样
- **下游使用**：本报告可作为 Todo 1–13 实施时的真值表（line numbers 是权威）；所有 cross-BP 边界与风险点见 §11
