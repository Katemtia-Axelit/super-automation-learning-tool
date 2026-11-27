# P1 架构合同（Backend Foundation & Frontend Kernel）

> **状态**：P1 冻结版（AR03-P1）
> **冻结日期**：2026-11-20
> **上游依据**：`docs/ARCHITECTURE_REDESIGN_2026-08-16.md`、
> `docs/AR03_FULL_PROJECT_REFACTOR_FIVE_GROUP_DIRECTIVE_20261120.md`
> **适用范围**：P1 交付的模块清单、唯一写者、公开接口、依赖方向、
> 受保护路径与退役条件。P2/P3 在此基础上增量推进，**不得**绕过本合同。

---

## 0. 一句话合同

> **后端**：Schema 只有一个权威、装配只有一个根、抽卡只有一个实现处。
> **前端**：内核能力在运行期真实存在、模块契约可机械校验、helper 只有一个实现。

---

## 1. 后端合同

### 1.1 Schema 唯一权威层

| 项 | 值 |
|---|---|
| 权威位置 | `server/schema/` |
| 唯一编排入口 | `server/schema/__init__.py::ensure_all(conn)` |
| 域模块 | `tasks` / `gacha` / `timer` / `state` / `feedback` / `notes` |
| 编排顺序 | tasks → gacha → timer → state → feedback → notes → indexes |
| 空库保证 | **是**（`ensure_all` 在完全空的 SQLite 文件上成功） |
| 幂等保证 | **是**（连续两次执行，表/列/索引集合完全一致） |
| 破坏性操作 | **无**（只用 `CREATE TABLE IF NOT EXISTS` + 缺列时的 `ALTER TABLE ADD COLUMN`） |

`REQUIRED_TABLES`（`ensure_all` 之后必须存在的全部业务表）：

```
tasks, tags, task_tags, task_dependencies,
gacha_records, task_rejection_log,
timer_sessions,
daily_user_state, state_assessments, user_schedule, daily_schedules, activities,
task_feedback_events, task_completion_feedback
```

**不属于本层的表**：`free_task_events` —— 它带有 append-only 触发器与部分
唯一索引语义，由 `server/services/free_task_events.py::FreeTaskEventStore`
自管，`ensure_all` **不** 创建它（避免破坏追加语义）。

**唯一写者规则**：`server/backend_api.py` 的 8 个 `ensure_*` **只保留函数名与
签名**，函数体全部委托 `server/schema`。DDL 在仓库中只允许出现在
`server/schema/**` 一处。

### 1.2 Factory 唯一装配根

`server/app/app_factory.py::create_app(config=None, *, free_task_preview=None)`

装配顺序（**不可调换**，每步 fail closed）：

| # | 步骤 | 说明 |
|---|---|---|
| 1 | opt-in 校验 | 先于任何 config / DB 访问；坏 opt-in 绝不碰数据库 |
| 2 | 配置解析 | `server/app/config.py::load_config`（**唯一**配置权威） |
| 3 | 扩展初始化 | `server.extensions::init_extensions`；此后 `get_db_path()` 可用 |
| 4 | Schema 初始化 | `server.schema::ensure_all`（空库必须成功） |
| 5 | Blueprint 注册 | `REGISTERED_BLUEPRINTS`（9 个真实 BP） |
| 6 | Legacy 兼容桥 | `server/app/legacy_compat.py::register_legacy_compat` |
| 7 | 自由任务蓝图 | **仅**在显式 opt-in 时装配 |
| 8 | 健康检查 | `GET /api/health` |

**配置唯一权威**：`server/app/config.py::load_config`。
`server/config.py` 是它的**薄 re-export**（`load_config` 名字与返回键不变）。
合并语义：默认值 ⊕ 配置文件（浅合并，逐子键）⊕ 调用方 override（顶层整块替换）
⊕ 4 个派生键（`_project_root` / `_static_dir` / `_db_path` / `_notes_dir`）。

**注册清单对齐**：`server/blueprints/__init__.py::__all__` 必须与
`app_factory.REGISTERED_BLUEPRINTS` 逐项对齐。

### 1.3 抽卡用例服务边界

`server/services/gacha.py` 是抽卡行为的**唯一实现处**，两层：

- **算法层**：`GachaAlgo` Protocol + `DefaultGachaAlgo` + `WeightInputs`。
  与历史 `backend_api._calculate_full_weight` **逐位一致**
  （100,250 组 golden 比对 `max_diff=0`）。
- **编排层**：`filter_pool` / `compute_weights` / `apply_policy_coefficients` /
  `pick` / `draw_one` / `record_draw` / `record_issuance` / `record_rejection` /
  `pool_for_minutes` / `effective_minutes` / `is_free_card` /
  `default_card_type_of` / `pick_uniform`。

硬约束：

1. **不 import Flask**（不得出现 `flask` / `current_app` / `request` / `jsonify`）。
2. **不读全局配置**：策略系数由调用方（BP）读取后以字典传入。
3. **不反向依赖 blueprints**：卡类型归一通过**注入的** `card_type_of` 完成。
4. 除 `record_*` 系列（显式接收 `conn`）外不触碰数据库。

`server/blueprints/gacha_bp.py` 与 `server/backend_api.py` 的
`draw_single` / `_weighted_pick` / `select_weighted_random_task`
**共同调用**该 service，消除"两套抽卡编排"。

### 1.4 依赖方向

```
app_factory ──► blueprints ──► services ──► repositories
      │              │
      │              └──► schema (只读 DDL 权威)
      └──► legacy_compat (只桥接未迁移路由)
```

- `blueprints → services` 允许；`services → blueprints` **禁止**。
- `services → repositories` 允许；`repositories → services` **禁止**。
- `schema` 不依赖任何上层。

---

## 2. 前端合同

### 2.1 Micro Kernel 运行期能力（**必须真实存在**）

`src/index.html` 在 `app.js` **之前**加载全部 classic kernel 脚本：

| 命名空间 | 成员 | 权威文件 |
|---|---|---|
| `SAL.core` | `eventBus` / `api` / `ui` / `theme` / `router` / `state` / `constants` / `registry` | `static/core/*.js` |
| `SAL.core.ui` | `modal` / `toast` / `theme` / `sandbox` / `xss` | `static/core/ui/*.js` |
| `SAL.shared` | `timer` / `xss` / `formatters` | `static/shared/*.js` |

**启动自检是断言式的**：`static/app.entry.js::reportBoot()` 缺任何一项即
`console.error` 且 `window.__kernelBootReport.failed` 非空；全部齐备则
`window.__kernelBootReport.ok === true`。独立验收直接读这个对象。

### 2.2 模块契约

每个 Feature 模块必须导出：

```js
export const meta = { name, version, deps? };
export function mount(rootEl, ctx) { ... }
export function unmount(rootEl) { ... }
```

`static/core/registry.js` 是这些契约的**唯一登记处**：

| API | 语义 |
|---|---|
| `register(name, meta, mount, unmount)` | 契约不完整 → **抛错**（绝不半注册） |
| `get(name)` / `has(name)` / `list()` | 查询 |
| `mount(name, ctx)` / `unmount(name)` | 幂等；未注册 → `false` + 诊断（**绝不**静默吞掉） |
| `isMounted(name)` / `mountedList()` | 挂载态 |
| `getDiagnostics()` / `clearDiagnostics()` | 诊断（`mount-missing-module` / `mount-missing-deps` / `mount-failed` / `unmount-failed`） |

`meta.deps` 是**页面级依赖名**，只做记录与校验：未知依赖**不阻断**挂载，
但会被记录成 `missingDeps` 诊断。

### 2.3 路由

`static/core/router.js` 是**真 hash 路由**：

- `parseHash(hash)` → 页面 id（`#gacha` → `'gacha'`）；非法/未注册 → `null`。
- `getCurrentPage()` → 当前页面（无合法 hash → 默认页 `'gacha'`）。
- `navigate(page)` → 写 hash 并广播；已是目标页也显式广播一次。
- `onRouteChange(cb)` → 订阅，返回取消订阅函数。
- `start()` → 监听 `hashchange`，幂等。

`static/app.entry.js::wireNav()` 把 `page:change` **真正 dispatch** 到
registry 的 mount/unmount。旧 `app.js::showPage(id)` **不被替换**
（inline handler 与既有 E2E 仍走它）。

### 2.4 helper 唯一权威

| helper | 唯一权威 | classic 层允许形态 |
|---|---|---|
| `escapeHtml` | `static/core/ui/xss.js` | `static/app.js` 薄 facade（转发 `SAL.core.*`） |
| `toast` | `static/core/ui/toast.js` | 同上 |
| `showModal` | `static/core/ui/modal.js` | 同上 |
| `closeModal` | `static/core/ui/modal.js` | 同上 |
| `api` | `static/core/api.js` | 同上 |

`static/app.js` **只**保留这 5 个委托 facade，业务逻辑零改动。

### 2.5 模块边界（机械可校验）

`scripts/check_module_imports.js` 把边界变成**可执行断言**（退出码 0 = 通过）：

| 规则 | 内容 |
|---|---|
| `contract` | Registry Feature 模块必须导出 `meta`/`mount`/`unmount`；未注册模块必须是 owner 工厂（导出 `createXxxOwner(deps)`）且 **不得** 带 registry 契约 |
| `cross-module` | `modules/*` 之间只允许 import 对方的 `index.js` 公共入口，不得越界 import 内部文件 |
| `core-no-backdep` | `core/*` 与 `shared/*` **不得** import `modules/*`（内核不反向依赖业务） |
| `helper-single-authority` | 公共 helper 不得在 classic 层重复实现 |
| `app-delegation` | `static/app.js` 的 5 个 helper 必须转发到 `SAL.core.*` |

### 2.6 当前模块清单（**冻结**）

| 模块 | 类型 | 入口 |
|---|---|---|
| `gacha` | Registry Feature | `static/modules/gacha/index.js` |
| `tasks` | Registry Feature | `static/modules/tasks/index.js` |
| `agent-readonly` | Owner 工厂 | `static/modules/agent-readonly/index.js` |
| `config` | Owner 工厂 | `static/modules/config/index.js` |
| `knowledge` | Owner 工厂 | `static/modules/knowledge/index.js` |
| `prompts` | Owner 工厂 | `static/modules/prompts/index.js` |
| `schedule` | Owner 工厂 | `static/modules/schedule/index.js` |
| `sleep` | Owner 工厂 | `static/modules/sleep/index.js` |
| `state-assessment` | Owner 工厂 | `static/modules/state-assessment/index.js` |
| `timer` | Owner 工厂 | `static/modules/timer/index.js` |

> Registry Feature 模块清单的**唯一权威**是
> `static/app.entry.js::MODULE_CONTRACTS`。清单变更必须同步修改该常量，
> 否则 `scripts/check_module_imports.js` 会失败。

---

## 3. 受保护路径（Protected Paths）

以下路径是**项目红线**，Cursor 侧**只读**：

- `src/notes/**` — Obsidian 知识库，本地用户数据，永不入 Git
- `data/task_publisher.db` — 线上应用数据库
- `data/task_publisher.db-wal` / `data/task_publisher.db-shm` — 同一数据库的原子族
- `config/config.json` — 运行时配置（含密钥与路径）

政策细节见 `.cursor/rules/data-redlines.mdc`。

---

## 4. 退役条件（Retirement Criteria）

每个条目给出**可机械判定**的退役条件，避免"看起来迁移完了"。

| 候选退役对象 | 退役条件（全部满足才可退役） |
|---|---|
| `backend_api.py` 的 8 个 `ensure_*` 副本 | 已是委托（函数体只有转发）→ 可在 P2 视情况删除，但**保留函数名与签名**直到所有调用点迁移完 |
| `backend_api.py::draw_single` / `_weighted_pick` / `select_weighted_random_task` | 已是委托 → 同上 |
| `gacha_bp.py` 的内联编排（`_draw` / `_filter_pool` / `_record_draw` / `_record_issuance` / `_policy_weighted_weights`） | 已下沉到 service → 可删内联实现，但**保留 HTTP 解析层** |
| `server/config.py` | 已是 `server/app/config.py` 的薄 re-export → 保留 re-export（P2/P5 决定是否删文件） |
| `static/core/router.js` 的旧 `PAGES` 常量 | 已由 `core/constants.js` 单一权威 → 保留兼容导出 |
| `static/app.js` 的 5 个 helper | 已是 `SAL.core.*` 委托 facade → **不退役**（inline handler 依赖这些全局名） |
| `scripts/main.py` 的桌面端入口 | 已 fail closed（退出码 3 + 可读指引）→ 指向 `_archive/src_tasks_legacy/`；**不删除** |

---

## 5. 隔离验收合同

P1 的 36/36 E2E 结论**必须**在隔离合成环境取得：

1. **可复现入口**：`node scripts/run_e2e_isolated.js`
2. **隔离保证**：随机端口 + `%TEMP%` 合成根 + 合成 SQLite + 合成 vault +
   合成已批准策略
3. **零触碰断言**：运行前后对 `data/task_publisher.db*`、
   `config/config.json`、`src/notes/**` 做 **只读** sha256/size 指纹比对，
   必须完全一致
4. **退出码**：`e2e-manual.js` 退出码 0 = 36/36 通过

细节见 `docs/deliverables/P1_HANDOFF.md` §独立验收入口。
