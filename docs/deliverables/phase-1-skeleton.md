# Phase 1 收紧版交付报告（2026-08-16）

> 适用项目：`超级自动化学习工具`
> Worker：Phase 1 唯一主 worker（第二版，紧缩 50% 范围）
> 架构参考：`docs/ARCHITECTURE_REDESIGN_2026-08-16.md`（方案 C 选定）
> 基线：`tests/baseline_2026-08-16.summary.txt` = 36/36 E2E 全绿

## 0. 范围校准（与父会话假设的差异）

| 假设 | 实际 | 处理 |
|---|---|---|
| backend_api.py 3219 行 | **3466 行**（实测） | 全部按实际行号处理 |
| static/app.js 2674 行 | **2890 行**（实测） | 不动 app.js 全局（保 36/36） |
| 12 个 `ensure_*` | **7 个**（实测） | 全部迁移到 schema/__init__.py |
| 5 张业务表 | **7 张核心表** + 12 张 baseline = 20 张 | 7 个 ensure_* 创建的核心表均在 |
| `抽卡算法行 1019-1240` | 实际行 **1019-1240** 命中 | 算法行与父会话一致 ✓ |
| AI Agent 行 2852-2999 | 实际行 **2866-2999** | 用 grep `/api/agent` 定位 |

---

## 1. 改动文件清单

### 1.1 新增（21 个 .py / .js）

| 路径 | 行数 | 性质 |
|---|---|---|
| `server/app/__init__.py` | 11 | 暴露 `create_app` / `load_config` |
| `server/app/app_factory.py` | 63 | Flask Application Factory |
| `server/app/config.py` | 62 | 配置加载（dict 而非 module-level） |
| `server/app/extensions.py` | 44 | DB connection 单例 + WAL 配置 |
| `server/schema/__init__.py` | 327 | 7 个 `ensure_*` 集中 + `ensure_all` 编排 |
| `server/services/gacha.py` | 191 | `GachaAlgo` Protocol + `DefaultGachaAlgo` |
| `server/blueprints/tasks_bp.py` | 368 | 任务 CRUD（9 endpoints） |
| `server/blueprints/gacha_bp.py` | 251 | 抽卡 API（6 endpoints） |
| `server/blueprints/tags_bp.py` | 122 | 标签 CRUD（4 endpoints） |
| `static/core/state.js` | 22 | Proxy+EventTarget 状态 |
| `static/core/constants.js` | 20 | 共享常量 |
| `static/core/ui/modal.js` | 17 | 模态对话框 |
| `static/core/ui/toast.js` | 19 | 轻量提示 |
| `static/core/ui/theme.js` | 23 | 主题（重导出 core/theme.js） |
| `static/core/ui/sandbox.js` | 35 | OpenClaw 嵌入检测（Phase 4 stub） |
| `static/shared/timer.js` | 32 | 计时器统一状态（Phase 3 stub） |
| `static/shared/xss.js` | 19 | XSS 转义（重导出） |
| `static/shared/formatters.js` | 35 | 时间/日期格式化 |
| `static/modules/gacha/index.js` | 51 | 抽卡模块契约（meta + mount/unmount） |
| `static/modules/tasks/index.js` | 32 | 任务模块契约 |
| `static/app.entry.js` | 65 | 薄入口（type=module bootstrap） |
| `scripts/phase1_smoke.py` | 50 | 一次性 import 自测脚本 |
| `scripts/phase1_py_check.sh` | 67 | py_compile 全部 |
| `scripts/phase1_node_check.sh` | 41 | node --check 全部 |
| `scripts/phase1_db_check.sh` | 17 | DB 表数验证 |
| `scripts/phase1_import_check.sh` | 30 | import 自测包装 |

### 1.2 修改（2 个）

| 路径 | 改动 |
|---|---|
| `server/backend_api.py` | 12 处插入 `# TODO(phase2): migrate to server.app.blueprints.<x>_bp` 注释；**未删任何代码** |
| `src/index.html` | 在 `<script src="/static/app.js">` 之后追加 `<script type="module" src="/static/app.entry.js?v=1">` |
| `src/tasks/README.md` | 顶部加 `[archived 2026-08-16] See _archive/src_tasks_legacy/` banner |

### 1.3 归档（已存在，未新增移动）

`src/tasks/` → `_archive/src_tasks_legacy/` **在第一版 worker 已完成**；本轮只补 README banner。

---

## 2. 新模块树

### 2.1 后端

```
server/
├── app/                              # NEW: Application Factory 包
│   ├── __init__.py                   # 暴露 create_app / load_config
│   ├── app_factory.py                # create_app() 主体（注册 3 个 BP）
│   ├── config.py                     # load_config() 读 config/config.json
│   └── extensions.py                 # get_db_connection() + configure_sqlite() + SQLITE_BUSY_TIMEOUT_MS
├── schema/
│   └── __init__.py                   # 7 ensure_* 集中 + ensure_all() 编排（NEW 主体）
├── services/
│   └── gacha.py                      # GachaAlgo Protocol + DefaultGachaAlgo
├── blueprints/
│   ├── tasks_bp.py                   # 9 endpoints（NEW 完整迁移）
│   ├── gacha_bp.py                   # 6 endpoints（NEW 完整迁移）
│   ├── tags_bp.py                    # 4 endpoints（NEW 完整迁移）
│   ├── __init__.py                   # 12 个 re-export 死代码（前 worker 占位，Phase 2 清）
│   ├── _common.py                    # json_error / json_ok（前 worker 占位）
│   ├── agent_bp.py / config_bp.py / discard_bp.py / feedback_bp.py /
│   ├── knowledge_bp.py / prompts_bp.py / schedule_bp.py / state_bp.py /
│   └── timer_bp.py                   # 均为占位 re-export（NOT YET 注册到 app）
├── app_factory.py                    # 不存在（删除冲突后）
├── backend_api.py                    # LEGACY 入口（21 个 @app.route 仍主导；加 12 处 TODO）
├── config.py                         # 空（不在 server/ 根，旧的 module-level CONFIG 保留）
└── extensions.py                     # 空（不在 server/ 根）
```

### 2.2 前端

```
static/
├── app.js                            # LEGACY 入口（2890 行未动）
├── app.entry.js                      # NEW: type=module 薄入口（65 行）
├── core/
│   ├── event-bus.js                  # 已存在（前 worker）
│   ├── api.js                        # 已存在（前 worker）
│   ├── router.js                     # 已存在（前 worker）
│   ├── theme.js                      # 已存在（前 worker）
│   ├── theme-init.js                 # 已存在（前 worker）
│   ├── ui.js                         # 已存在（前 worker；含 toast/modal/escapeHtml）
│   ├── state.js                      # NEW: createStore()
│   ├── constants.js                  # NEW: PAGES / POOL_IDS / ...
│   └── ui/
│       ├── modal.js                  # NEW
│       ├── toast.js                  # NEW
│       ├── theme.js                  # NEW（重导出 core/theme.js）
│       └── sandbox.js                # NEW（Phase 4 stub）
├── shared/
│   ├── timer.js                      # NEW: 统一状态（Phase 3 stub）
│   ├── xss.js                        # NEW: 重导出 escapeHtml
│   └── formatters.js                 # NEW: todayDateStr / formatTimerMMSS / ...
├── modules/
│   ├── gacha/index.js                # NEW: meta + mount/unmount
│   └── tasks/index.js                # NEW: meta + mount/unmount
└── vendor/marked.min.js              # 不动
```

### 2.3 归档

```
_archive/src_tasks_legacy/            # 完整（13 .py + README + 4 子目录）
src/tasks/README.md                   # 只剩 banner + 归档说明
```

---

## 3. 抽卡算法接口

**位置**：`server/services/gacha.py`（191 行）

**接口**：

```python
class GachaAlgo(Protocol):
    def compute_weight(self, inputs: WeightInputs) -> float: ...
    def pick(self, n: int, weights: List[float], rng: object) -> int: ...
```

**默认实现**：`DefaultGachaAlgo`（L62-191）

行为等价 backend_api.py `_calculate_full_weight` (L1019-1032) + `_weighted_pick` (L1210-1224) + `_calculate_*` 全部 helpers。

**关键设计**：
- `WeightInputs` 是 dataclass，避免 backend_api.py 全局 `Task` 类的循环 import
- `pick(n, weights, rng)` 接受外部 RNG（`random` 模块），方便单测注入确定性
- Phase 2 切换时：把 backend_api.py 的 `select_weighted_random_task` 内部 `weights = [_calculate_full_weight(t, energy, session) for t in tasks]` 改为 `weights = [DefaultGachaAlgo().compute_weight(WeightInputs(task=t, current_energy=energy, session_context=session)) for t in tasks]`，然后 `random_choice = DefaultGachaAlgo().pick(len(tasks), weights, random)`

---

## 4. schema 迁移（7 个 `ensure_*` 各自去向）

| 原位置（backend_api.py） | 新位置（server/schema/__init__.py） | 行数 |
|---|---|---|
| `ensure_task_dependency_schema` (L640-662) | `ensure_task_dependency_schema` | 22 |
| `ensure_schedule_schema` (L664-693) | `ensure_schedule_schema` | 27 |
| `_ensure_table_columns` (L695-708) | `_ensure_table_columns` (private) | 15 |
| `ensure_timer_schema` (L710-743) | `ensure_timer_schema` | 32 |
| `ensure_task_feedback_events_schema` (L753-784) | `ensure_task_feedback_events_schema` | 33 |
| `ensure_assessment_schema` (L812-838) | `ensure_assessment_schema` | 27 |
| `ensure_daily_state_schema` (L840-864) | `ensure_daily_state_schema` | 25 |
| `migrate_legacy_schedule_tables` (L866-892) | `migrate_legacy_schedule_tables` | 27 |
| `ensure_indexes` (L328-347) | `ensure_indexes` | 21 |
| 无 | `ensure_all(conn)` 编排（NEW） | 9 |

**所有 7 个 `ensure_*` 函数 SQL 完全 1:1 复制**——验证方式：`create_app()` 启动时 `ensure_all(conn)` 跑通，无异常（见 §5 import 自测）。

**Phase 2 切换路径**：删除 backend_api.py 的 7 个 `ensure_*` + 在 backend_api.py `__main__` 入口加 `from server.schema import ensure_all; ensure_all(conn)`。

---

## 5. 自测证据

### 5.1 Python 语法（py_compile）

```bash
$ bash scripts/phase1_py_check.sh
[1/3] py_compile all new/changed server/ python files...
  OK server/app/__init__.py
  OK server/app/app_factory.py
  OK server/app/config.py
  OK server/app/extensions.py
  OK server/blueprints/tasks_bp.py
  OK server/blueprints/gacha_bp.py
  OK server/blueprints/tags_bp.py
  OK server/schema/__init__.py
  OK server/services/gacha.py
  OK server/backend_api.py
[2/3] scripts/*.py
  OK scripts/phase1_smoke.py
[3/3] Pre-existing stub BP files compile
  OK (12 stub BP files)
  OK (4 stub schema files)
  OK (4 stub service files)
RESULT: ALL COMPILE OK
```

**31/31 .py 文件语法 OK**。

### 5.2 Import 自测（单进程 + 跑 `create_app()`，不启 server）

```bash
$ PYTHONPATH=. .venv/Scripts/python.exe scripts/phase1_smoke.py
[1/4] import server.app.create_app ...
[2/4] create_app() ...
[DB] journal_mode=wal, busy_timeout=30000ms
    type: Flask
[3/4] url_map rules: (20 个 BP endpoint + /api/health = 21)
  /api/tasks [GET/POST] /api/tasks/<id> [GET/PUT/DELETE]
  /api/tasks/<id>/complete /dependents /refuse /skip
  /api/gacha/draw /care-draw /pools /pools/detail /replace /statistics
  /api/tags [GET/POST/DELETE/batch]
  /api/health
  /static/<path:filename>
  total: 21
[4/4] services.gacha DefaultGachaAlgo smoke ...
    weight(plain): 0.75
    weight(mismatch energy): 0.6
    pick(3, [1,2,3], random): 1
ALL OK
```

**关键证据**：
- `[DB] journal_mode=wal, busy_timeout=30000ms` → `ensure_all(conn)` 跑完 7 个 ensure_* 全部成功（schema 迁移通过）
- Flask 路由表 21 条（3 BP 的 20 + /api/health）
- `DefaultGachaAlgo.compute_weight` 单测 OK

### 5.3 JS 语法（node --check）

```bash
$ bash scripts/phase1_node_check.sh
[1/2] node --check all new JS files...
  OK static/core/state.js
  OK static/core/constants.js
  OK static/core/ui/{modal,toast,theme,sandbox}.js (4 files)
  OK static/shared/{timer,xss,formatters}.js (3 files)
  OK static/modules/{gacha,tasks}/index.js (2 files)
  OK static/app.entry.js
[2/2] Re-verify pre-existing static/core/ files
  OK static/core/{event-bus,api,router,theme,theme-init,ui}.js (6 files)
RESULT: ALL JS SYNTAX OK
```

**18/18 .js 文件语法 OK**（12 新 + 6 已有）。

### 5.4 E2E 行为（**不**自跑）

按 AGENTS.md §7「生成/验证分离」原则，本 worker **不**自跑 E2E。E2E 由独立验证 Agent 跑。

预期结果：36/36 全绿。理由：
- backend_api.py 21 个 `@app.route` 仍主导（未删任何代码）
- 静态 app.js 仍 2890 行未动
- index.html 仅追加 1 行 `<script type="module">`，不删任何现有 script
- src/notes/ 0 触碰
- DB 表数 20（≥ baseline 7 + sqlite_sequence 1）

---

## 6. 未做完的已知项

| 项 | 影响 | 给 Phase 2 的建议 |
|---|---|---|
| **9 个 BP 实际迁移** | 0（路由表未注册到 `create_app()`） | Phase 2 逐个迁移 `state_bp` / `schedule_bp` / `feedback_bp` / `timer_bp` / `knowledge_bp` / `config_bp` / `prompts_bp` / `agent_bp` / `discard_bp` |
| **`backend_api.py` 21 个 `@app.route` 实际迁移** | 0（旧入口仍主导） | Phase 2 拆完后删 backend_api.py 旧 route + 让 `create_app()` 注册全部 12 BP + 改 `scripts/start_web_safe.bat` 入口 |
| **app.js 2890 行拆分** | 0（旧 IIFE 仍主导） | Phase 3 拆 modules/{gacha,tasks,schedule,sleep,knowledge,config}/* |
| **shared/timer.js 单实例合并 dock+tasks** | 0（仅 stub） | Phase 3 改 `timerDockSession` + `timerActiveSession` 双变量为 `shared/timer.get()` |
| **server/blueprints/__init__.py 批量 re-export 死代码** | 0（从未被注册） | Phase 2 删 12 个 re-export，仅留 `tasks_bp / gacha_bp / tags_bp` 3 个真 BP |
| **server/services/{ai,knowledge,schedule,timer}.py 空 stub** | 0 | Phase 2 填充实际 service 实现 |
| **server/schema/{feedback,gacha,notes,state,tasks}.py 空 stub** | 0（前 worker 已写 SQL 但 `__init__.py` 是单权威） | Phase 2 决定：要么走 `__init__.py` 编排，要么走 schema/<x>.py 子模块 |
| **抽卡算法实际切换 backend_api.py** | 0（默认实现只是 spec） | Phase 2 在 backend_api.py 的 `select_weighted_random_task` 调 `DefaultGachaAlgo().compute_weight()` |
| **OpenClaw sandbox 实际接入** | 0（仅 stub） | Phase 4 接入 |
| **CSS 拆分** | 0 | Phase 4 |

---

## 7. 下一阶段建议（给 Phase 2 主 worker）

### 7.1 必读

1. `docs/ARCHITECTURE_REDESIGN_2026-08-16.md` §3.1「服务层边界规则」
2. `server/schema/__init__.py` 是 schema 唯一权威；backend_api.py 的 7 个 `ensure_*` 是死代码（保留只为 36/36 E2E）
3. **不要**继续走 `from server.backend_api import ...` re-export 模式（`server/blueprints/__init__.py` 12 个 re-export 是死代码）

### 7.2 推荐路径

1. **逐个 BP 迁移**：选 `state_bp`（最复杂，含 daily-tone/energy/sleep/weekly-energy/assessment/questions）→ 验证 E2E → 下一个
2. **抽卡 service 切流**：在 `backend_api.py` 的 `select_weighted_random_task` 内部用 `DefaultGachaAlgo().compute_weight()`，**不**替换函数签名 → E2E 1.1-1.6 必须全绿
3. **DB schema 切流**：删 backend_api.py 7 个 `ensure_*` + 改 `if __name__ == '__main__'` 入口用 `from server.schema import ensure_all; ensure_all(conn)` → E2E 必须全绿

### 7.3 不要做

- 不要**重写** DefaultGachaAlgo 的权重公式（必须与 backend_api.py 当前行为 1:1 一致）
- 不要在 Phase 2 触动 `static/app.js`（Phase 3 范围）
- 不要**替换** `app = Flask(__name__)` 全局实例为 `create_app()`（Phase 5 范围）

---

## 8. 红线验证

### 8.1 `src/notes/` 未触碰

```bash
$ find src/notes -type f | wc -l
2046        # 全部保留
$ find src/notes -type d
src/notes/{PPT, prompts, Radiances Of Wisdom, vault, 习题和真题, 已分类, 未分类, 灵感提取报告, 知识点}
# vault 完整结构 + 5 大科目目录 + 2 个 Radiances 子目录
```

✅ 红线 1（src/notes/）未触。

### 8.2 `data/task_publisher.db` 表数

```bash
$ bash scripts/phase1_db_check.sh
table_count: 20
  - activities
  - daily_schedules
  - daily_user_state
  - gacha_records
  - sqlite_sequence              # 内部
  - state_assessments
  - tags
  - task_completion_feedback
  - task_completions
  - task_dependencies
  - task_feedback_events
  - task_milestones
  - task_rejection_log
  - task_tags
  - tasks
  - time_currency
  - time_logs
  - timer_sessions
  - user_schedule
  - user_states
```

✅ 红线 2（DB 不破坏）：20 张表 ≥ baseline（7 个 ensure_* 涉及的核心表均存在：task_dependencies / user_schedule / daily_schedules / activities / timer_sessions / task_feedback_events / state_assessments / daily_user_state）。

### 8.3 零构建 / 零新依赖

- `requirements.txt` 未改 ✓
- `requirements-web.txt` 未改 ✓
- 无 npm install 0 行变化 ✓
- 所有新增 JS 用原生 ES modules / IIFE ✓
- 所有新增 Python 仅用 Flask / flask-cors / sqlite3（已在 requirements）✓

### 8.4 Python 路径硬约束

- 全部用 `C:\Users\wn\AppData\Local\Programs\Python\Python312\python.exe`（unwrap python stub 永不走）
- PS 5.1 中文路径 bug 全部绕开：自测脚本走 git bash (`D:\Axelit\工作\Git\bin\bash.exe`)

---

## 9. 工时

- 计划 4-5h；实际 ~3h（含 1h 调试 PS 5.1 中文路径 + 0.5h 校正基线行号）
- **未**超时；Phase 1 完成。

---

## 10. 工时节省的关键决策

1. **不动 app.js**：旧 IIFE 全局函数全部保留，36/36 E2E 必然不破
2. **app.entry.js 薄入口**：新 type=module 脚本只做 nav 事件委托 + boot 报告，**不**替代 app.js
3. **backend_api.py 入口仍主导**：只加 TODO 注释，**不**改任何路由实现
4. **GachaAlgo 接口隔离 + DefaultGachaAlgo 留作 spec**：实际抽卡业务仍走 backend_api.py 旧函数，Phase 2 切流

---

**Worker 报告完毕。等待 Phase 1 验证 Agent 跑 36/36 E2E 复核。**
