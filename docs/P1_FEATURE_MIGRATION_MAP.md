# P1 功能迁移映射（旧实现 → 新实现 → 公开调用方式 → 测试证据）

> **状态**：P1 冻结版（AR03-P1）
> **冻结日期**：2026-11-20
> **用法**：P2/P3 迁移任何域之前，先在本表里查"这个能力现在归谁写"。

---

## 1. 后端：Schema 权威层

| 旧实现（双源） | 新实现（唯一权威） | 公开调用方式 | 测试证据 |
|---|---|---|---|
| `backend_api.py::ensure_indexes` (L362) | `server/schema/tasks.py::ensure_indexes` | `from server.schema import ensure_indexes` | `test_schema_authority.py` |
| `backend_api.py::ensure_task_dependency_schema` (L662) | `server/schema/tasks.py::ensure_schema` | `from server.schema import ensure_task_dependency_schema` | 同上 |
| `backend_api.py::ensure_schedule_schema` (L671) | `server/schema/state.py::ensure_schema` | `from server.schema import ensure_schedule_schema` | 同上 |
| `backend_api.py::ensure_timer_schema` (L689) | `server/schema/timer.py::ensure_schema` | `from server.schema import ensure_timer_schema` | 同上 |
| `backend_api.py::ensure_task_feedback_events_schema` (L706) | `server/schema/feedback.py::ensure_schema` | `from server.schema import ensure_task_feedback_events_schema` | 同上 |
| `backend_api.py::ensure_assessment_schema` (L741) | `server/schema/state.py::ensure_schema` | `from server.schema import ensure_assessment_schema` | 同上 |
| `backend_api.py::ensure_daily_state_schema` (L750) | `server/schema/state.py::ensure_schema` | `from server.schema import ensure_daily_state_schema` | 同上 |
| `backend_api.py::migrate_legacy_schedule_tables` | `server/schema/state.py::_migrate_legacy_schedule_tables` | `from server.schema import migrate_legacy_schedule_tables` | 同上 |
| `server/schema/__init__.py` 旧内联 7 函数编排 | `server/schema/__init__.py::ensure_all` | `from server.schema import ensure_all` | 同上（空库成功 + 幂等 + 表集合一致） |
| `free_task_events` 建表 | `server/services/free_task_events.py::FreeTaskEventStore`（**自管**，append-only 触发器语义） | 构造 store 时自动建表 | `test_free_task_*` 套件 |

**语义变化**：旧 `ensure_all` 在空库上**直接崩**
（`sqlite3.OperationalError: no such table: main.tasks`）；新 `ensure_all`
在空库上成功并产出 15 张业务表。

---

## 2. 后端：Factory 装配根

| 旧实现 | 新实现 | 公开调用方式 | 测试证据 |
|---|---|---|---|
| `server/config.py::load_config`（独立加载器，无派生键） | `server/app/config.py::load_config`（**唯一权威**，含 4 个派生键） | `from server.app.config import load_config`（`server/config.py` 是薄 re-export） | `test_factory_bootstrap.py` |
| `server/extensions.py::init_extensions`（全仓 0 引用，死代码） | `server/app/extensions.py::init_extensions`（**在 `create_app()` 内真正调用**） | `from server.extensions import init_extensions`（`server/extensions.py` 保留 re-export） | 同上 |
| `server/extensions.py::get_db_path()`（永远抛 RuntimeError） | `server/app/extensions.py::get_db_path()`（打通，`app.extensions["sal"]["db_path"]`） | `from server.app.extensions import get_db_path` | 同上 |
| `server/blueprints/__init__.py::__all__`（9 个 stub 混合） | 与 `app_factory.REGISTERED_BLUEPRINTS` 逐项对齐 | — | `test_legacy_route_full_parity.py` |
| `server/app/legacy_compat.py`（只覆盖 Legacy 导入态 44 条） | 覆盖 Legacy **`__main__`** 全量路由（49 条），`MISSING=0` | `register_legacy_compat(app, cfg)` | 同上 |

**语义变化**：`create_app()` 在**空合成库**上可创建 app 并响应 `/api/health`；
两个 app 实例的 DB 路径互不串扰。

---

## 3. 后端：抽卡编排下沉

| 旧实现 | 新实现（唯一） | 公开调用方式 | 测试证据 |
|---|---|---|---|
| `backend_api.py::_calculate_full_weight`（L1058-1152，**95 行注释死代码**） | `server/services/gacha.py::DefaultGachaAlgo.compute_weight` | `DefaultGachaAlgo().compute_weight(WeightInputs(...))` | `scripts/phase2_gacha_golden.py` → **100250 组 max_diff=0** |
| `backend_api.py::_weighted_pick` (L1034) | `server/services/gacha.py::pick_uniform`（Legacy uniform 语义逐位保留） | `from server.services.gacha import pick_uniform` | `test_gacha_*` 套件 |
| `backend_api.py::draw_single` (L971) | `server/services/gacha.py::draw_one` | `from server.services.gacha import draw_one` | 同上 |
| `backend_api.py::select_weighted_random_task` (L911) | `server/services/gacha.py::draw_one` + `pick_uniform` | 同上 | 同上 |
| `gacha_bp.py::_draw` / `_draw_one` | `server/services/gacha.py::draw_one` | BP 只留 HTTP 解析 + 响应组装 | `test_gacha_service_boundary.py` |
| `gacha_bp.py::_filter_pool` | `server/services/gacha.py::filter_pool` | 同上 | 同上 |
| `gacha_bp.py::_policy_weighted_weights` | `server/services/gacha.py::apply_policy_coefficients` | 同上 | `test_gacha_policy_weights.py` |
| `gacha_bp.py::_record_draw` | `server/services/gacha.py::record_draw` | 同上 | `test_gacha_statistics_ledger.py` |
| `gacha_bp.py::_record_issuance` | `server/services/gacha.py::record_issuance` | 同上 | 同上 |
| `gacha_bp.py` 头部注释"抽卡权重计算**不**走 DefaultGachaAlgo" | 改为指向 `server/services/gacha.py` 的真实描述 | — | — |

**保持不变的产品语义**：权重**越小越容易被抽中**；策略系数"越大越不容易被抽中"
（`max(0.01, base * factor)`）；类别系数 × 卡类型系数**正交相乘**；合成系数为 0
的候选被**移出候选集**（不留 0 权重条目）；全部候选被停发 → `([], [], True)`
（调用方走 404，**绝不**悄悄均匀退回）。

---

## 4. 前端：Micro Kernel

| 旧实现 | 新实现 | 公开调用方式 | 测试证据 |
|---|---|---|---|
| `core/router.js` 仅导出 `PAGES` 常量（**零路由能力**） | `core/router.js` 真 hash 路由 | `SAL.core.router.{parseHash,getCurrentPage,navigate,onRouteChange,start}` | `test_kernel_contract.py` |
| （不存在）模块注册表 | `static/core/registry.js` | `SAL.core.registry.{register,mount,unmount,isMounted,getDiagnostics}` | 同上 |
| `core/state.js::createStore` 从未被任何生产代码调用 | `core/state.js` 可订阅 store | `SAL.core.state.createStore({...}).subscribe(key, cb)` / `.snapshot()` | 同上 |
| `core/ui.js` 自带 `escapeHtml` / `toast`（**双份实现**） | `core/ui.js` 委托 `core/ui/{xss,modal,toast}.js` | `SAL.core.ui.escapeHtml` / `SAL.core.ui.toast` / `SAL.core.ui.showModal` / `SAL.core.ui.closeModal` | 同上 + `scripts/check_module_imports.js` |
| `shared/timer.js`（显式 stub） | `shared/timer.js` 只读快照，委托 `modules/timer/index.js` 唯一 owner | `SAL.shared.timer.set(...)` / 只读快照 | 同上 |
| `core/api.js` 与 `app.js::api()` **两份独立实现** | `core/api.js` 唯一权威；`app.js` 薄 facade | `SAL.core.api(...)`；`window.api(...)` 转发 | 同上 |
| `core/constants.js` / `core/ui/{modal,toast,theme,sandbox}.js` / `shared/{xss,formatters}.js` **未被 index.html 加载** | `src/index.html` 在 `app.js` 之前全部加载（9 个新 script 标签） | `SAL.core.constants` / `SAL.core.ui.*` / `SAL.shared.*` | 同上 |
| `app.entry.js::wireNav()` 只 `console.debug`（**契约形同虚设**） | 真正 dispatch 到 registry 的 mount/unmount | `page:change` → `registry.unmount(prev)` → `registry.mount(next)` | 同上 |
| `app.entry.js::reportBoot()` 只打日志（**无失败信号**） | 断言式自检 | `window.__kernelBootReport.{ok,failed,missing,registeredModules}` | 同上 |
| `modules/gacha/index.js` / `modules/tasks/index.js` 只导出 `default {meta,mount,unmount}` | 增加具名导出 | `import gachaModule, { meta, mount, unmount } from './modules/gacha/index.js'` | 同上 + `check_module_imports.js` |

**保持不变的公开接口**：`app.js` 的 5 个 helper 全局名
（`window.api` / `window.toast` / `window.showModal` / `window.closeModal` /
`window.escapeHtml`）**必须保留** —— `src/index.html` 的 inline handler
依赖它们。`app.js::showPage(id)` **不被替换**。

---

## 5. 前端：模块边界机械检查

| 旧状态 | 新实现 | 公开调用方式 | 测试证据 |
|---|---|---|---|
| （不存在；架构文档 §4.2 指定但从未落地） | `scripts/check_module_imports.js` | `node scripts/check_module_imports.js`（退出码 0 = 通过）；`--json` 机器可读 | `test_kernel_contract.py` 以子进程调用并断言退出码 0 |

---

## 6. 桌面端归档

| 旧实现 | 新实现 | 公开调用方式 | 测试证据 |
|---|---|---|---|
| `_archive/src_tasks_legacy/` 无 README | `_archive/src_tasks_legacy/README.md`（真实 **17 个 .py** 清单 + 字节数 + git 映射 + 回滚方法 + "45 文件"文档差异记录） | 文档 | `test_desktop_archive_integrity.py` |
| `_archive/src_tasks_legacy/utils/`（**空目录残留**） | 已删除 | — | 同上（断言 `utils/` 不存在） |
| `scripts/main.py` 第 20 行裸 `from src.tasks.ui.main_window import MainWindow`（必然 ModuleNotFoundError） | fail closed：捕获 `ModuleNotFoundError` → 可读指引 → **退出码 3** | `python scripts/main.py` | 同上 |
| `src/tasks/README.md`（与实际清单不一致） | 指向 `_archive/src_tasks_legacy/README.md` 作为**单一权威** | 文档 | 同上 |

**归档内容保真**：`git show d4a5f0b` 逐文件字节比对，17 个 `.py` 全部一致。

---

## 7. 测试基础设施

| 旧实现 | 新实现 | 公开调用方式 | 测试证据 |
|---|---|---|---|
| `tests/e2e-manual.js` 硬编码 `BASE_URL = 'http://127.0.0.1:5000'`（**生产端口**） | 可配置：命令行 `--base-url=` > 环境变量 `SAL_E2E_BASE_URL` > 默认 5000（**不破坏现有调用方式**） | `node tests/e2e-manual.js --base-url=http://127.0.0.1:<port>` | `scripts/run_e2e_isolated.js` |
| （不存在）隔离 E2E 入口 | `scripts/run_e2e_isolated.js` | `node scripts/run_e2e_isolated.js` | 36/36 PASS + 零触碰断言 |
| `test_m02_behavior_frontend_core.py` 对 `static/app.js` 做源码匹配（**测试漂移**，G14 后语义已迁至 `modules/gacha/index.js`） | 匹配目标改为 `static/modules/gacha/index.js`；Node VM harness 复制 `index.js` / `presentation.js` 为 `.mjs` 后动态 import `createGachaOwner` | — | `test_m02_behavior_frontend_core.py` 40/40 |
| `test_card_type_frontend.py` / `test_free_card_acceptance_contract.py` 的 Node VM sandbox 未加载 core 脚本（facade 委托解析不到） | 先按序求值全部 `CORE_SCRIPTS`，再求值 `app.js`；后者并实例化 `createTaskLifecycleOwner` / `createGachaOwner` 绑定 `window.__taskLifecycleOwner` / `window.__gachaOwner` | — | 33/33、77/77 |
| `test_gacha_frontend_a11y.py` 只检查 `app.js` | 追加 `_LIFECYCLE_OWNER_FUNCTIONS`（`handleSkip` / `handleRefuse` 实际在 `modules/tasks/lifecycle.js`） | — | 40/40 |

---

## 8. 新增测试文件清单

| 文件 | 覆盖 |
|---|---|
| `tests/characterize/test_schema_authority.py` | 空库 `ensure_all` 成功、全表集、幂等、与 `backend_api` 表集合一致 |
| `tests/characterize/test_factory_bootstrap.py` | Factory 在空合成库建 app、配置可注入、两实例 DB 不串扰 |
| `tests/characterize/test_legacy_route_full_parity.py` | Legacy `__main__` 全量路由 vs Factory，`MISSING=0` |
| `tests/characterize/test_gacha_service_boundary.py` | service 层抽卡编排（**不依赖 Flask**）：过滤/权重/抽样/记账/换卡拒绝语义 |
| `tests/characterize/test_kernel_contract.py` | kernel 脚本加载顺序、`SAL.core.*` / `SAL.shared.*` 存在、registry/router/state/ui/timer 契约、`check_module_imports.js` 退出码 0 |
| `tests/characterize/test_desktop_archive_integrity.py` | 17 个 `.py` 与 `d4a5f0b` 字节一致、`utils/` 已删、`scripts/main.py` fail closed、无运行入口引用 `src.tasks.*` |
