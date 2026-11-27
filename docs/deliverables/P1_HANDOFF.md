# P1 交付说明（Backend Foundation & Frontend Kernel）

> **里程碑**：AR03-P1
> **交付日期**：2026-11-20
> **范围**：Schema 权威层、Factory 装配根、Gacha 用例服务边界、Frontend Micro Kernel、
> 桌面端归档收口、characterization 失败收敛、36/36 E2E 隔离复现
> **配套合同**：`docs/P1_ARCHITECTURE_CONTRACT.md`（冻结合同）、
> `docs/P1_FEATURE_MIGRATION_MAP.md`（旧→新映射）

> **重要**：本文档是**工程交付说明**，不是正式 Handoff / Receipt / Collection / Review。
> 那些由现有基础设施生成，**本 Agent 不手写**。

---

## 1. 三维评价

### 1.1 Engineering Acceptance（工程达成度）

| P1 目标 | 计划基线 | 实际达成 | 结论 |
|---|---|---|---|
| 4.1 Backend Foundation | ~70% | Schema 单一权威（空库可跑 + 幂等）、Factory 装配顺序显式化、配置唯一权威、`init_extensions` 真正生效、Legacy `__main__` 全量路由 `MISSING=0` | **达成** |
| 4.2 Frontend Micro Kernel | ~35%（大部空壳） | 17 个 core/shared 文件（14 个 `core/**` + 3 个 `shared/**`）运行期**全部真实存在**、registry 落地、router 变真 hash 路由、state 可订阅、helper 单权威、`reportBoot` 断言化、模块契约机械可校验 | **达成** |
| 4.3 Desktop Legacy Archive | ~90% | README（真实 17 个 `.py` 清单 + 迁移映射 + 回滚 + 文档差异记录）、空 `utils/` 已删、`scripts/main.py` fail closed（退出码 3）、`git show d4a5f0b` 逐文件字节一致 | **达成** |
| 4.4 Gacha Algorithm Isolation | ~55% | service 扩展为**用例服务**（过滤/权重/系数/抽样/记账/拒绝），BP 与 legacy 共同调用；95 行注释死代码删除；golden **100250 组 max_diff=0** | **达成** |
| 4.5 Schema Centralization | ~40%（有真实缺陷） | 15 张业务表全部有权威 DDL；`ensure_all` 空库成功 + 幂等；`backend_api` 8 个 `ensure_*` 全部改为委托（保留名字与签名） | **达成** |
| 36/36 E2E 硬门槛 | 无法安全复现 | **36/36 PASS**，隔离随机端口合成环境，生产 DB / Vault / config **运行前后 sha256 完全一致** | **达成** |

**全量 characterization**：基线 **78 failed / 1215 passed** → 交付 **0 failed / 1353 passed**
（另 10 skipped、1 xfailed、441 subtests passed）。

### 1.2 Contract Compliance（合同合规度）

| 项 | 状态 | 证据 |
|---|---|---|
| Workspace 身份 | 一致 | `D:\Axelit\.工作\trae\超级自动化学习工具`，branch `main`，HEAD `2236ac2e` |
| dirty/untracked 保全 | **全部保留** | 交付时 `git status --porcelain` = 271 项（与基线同量级，**未**执行 reset / clean / stash / checkout / commit / push） |
| 生产 DB 零触碰 | **零触碰** | `data/task_publisher.db*`、`config/config.json`、`src/notes/**` 运行前后只读 sha256 指纹一致（`scripts/run_e2e_isolated.js` 内建断言） |
| 计划文件未被编辑 | **未编辑** | `C:\Users\wn\.cursor\plans\ar03-p1-...plan.md` 只读引用 |
| 无跨里程碑公开合同改动 | **无** | 未改 `free_task_bp` opt-in 合同、`agent_policy` Publisher 语义、G14/G15 owner 契约、抽卡权重语义 |
| 无模型 API 引入 | **无** | 未新增任何 SDK / API key / 外部 chatbot 后端 |
| 无子代理 / `/multitask` | **无** | 全程单 Agent 串行切片 |
| 遗留脏文件未被清理 | **未清理** | 只做精确文件编辑，未触碰其它 271 项 |

### 1.3 Execution Efficiency（执行效率）

- 切片粒度：8 个串行切片，每片形成可验证稳定成果。
- 失败收敛：characterization 从 78 failed 收敛到 0 failed；其中 **13 个** 属
  "测试指向旧实现"的漂移（修复方向是**把匹配目标指向真实 owner**，
  **不改断言语义**），6 个 a11y SUBFAILED 属 owner 归属定位修正。
- 单点调试：E2E 首轮 34/36 → 定位到 P0 引导卡锁屏（产品设计，非缺陷）→
  在**合成根**内写入"已批准合成策略"解除覆盖层 → 再 34/36 → 定位到空 vault →
  在**合成根**内写入纯合成笔记 → **36/36**。两次失败都**没有**改动产品代码。

---

## 2. 切片执行记录

| # | 切片 | 交付物 | 验证 |
|---|---|---|---|
| 1 | Schema 权威层 | `server/schema/{tasks,gacha,timer,state,feedback,notes}.py` + `ensure_all` 编排；`backend_api` 8 个 `ensure_*` 委托 | `test_schema_authority.py` PASS |
| 2 | Factory 收口 | `server/app/config.py` 唯一权威；`server/config.py` 薄 re-export；`init_extensions` 生效；`create_app` 8 步显式装配；`legacy_compat` 覆盖 `__main__` 全量；`blueprints/__init__.__all__` 对齐 | `test_factory_bootstrap.py` + `test_legacy_route_full_parity.py` PASS |
| 3 | Gacha 编排下沉 | `server/services/gacha.py` 用例层（`filter_pool`/`compute_weights`/`apply_policy_coefficients`/`pick`/`draw_one`/`record_*`）；`gacha_bp.py` 只留 HTTP；`backend_api` `draw_single`/`_weighted_pick`/`select_weighted_random_task` 委托；删 95 行注释死代码；过时注释改正 | `phase2_gacha_golden.py` **100250 组 max_diff=0**；`test_gacha_service_boundary.py` PASS |
| 4 | Frontend Kernel | `core/registry.js`（新）；`core/router.js` 真 hash 路由；`core/state.js` `subscribe`/`snapshot`；`core/ui.js` 委托 `core/ui/*`；`shared/timer.js` 委托 `modules/timer` owner；`src/index.html` 追加 9 个 script；`app.js` 5 个 helper 改委托；`app.entry.js` 真 dispatch + 断言式 `reportBoot` | `test_kernel_contract.py` PASS；合成页面 `SAL.core.*` / `SAL.shared.*` 全部存在 |
| 5 | 模块边界检查 | `scripts/check_module_imports.js`（5 类规则）；`modules/{gacha,tasks}` 补具名导出 | `node scripts/check_module_imports.js` **退出码 0** |
| 6 | 桌面端归档 | `_archive/src_tasks_legacy/README.md`（新）；删空 `utils/`；`scripts/main.py` fail closed（退出码 3）；`src/tasks/README.md` 指向归档 README | `test_desktop_archive_integrity.py` 10/10 |
| 7 | 失败收敛 + E2E 隔离 | `tests/e2e-manual.js` BASE_URL 可配置；`scripts/run_e2e_isolated.js`（新，合成 Factory + 只读指纹断言）；4 个前端测试漂移修正 | characterization **0 failed**；E2E **36/36** |
| 8 | 交付与验收 | 本文档 + `docs/P1_ARCHITECTURE_CONTRACT.md` + `docs/P1_FEATURE_MIGRATION_MAP.md` + 隔离验收入口 | 见 §4 |

---

## 3. 测试证据

### 3.1 全量 characterization

```
.\.venv\Scripts\python.exe -m pytest tests/characterize -q
→ 1353 passed, 10 skipped, 1 xfailed, 441 subtests passed in 216.77s
```

基线对照：**78 failed / 1215 passed** → **0 failed / 1353 passed**。

### 3.2 P1 专项

```
.\.venv\Scripts\python.exe -m pytest \
  tests/characterize/test_schema_authority.py \
  tests/characterize/test_factory_bootstrap.py \
  tests/characterize/test_legacy_route_full_parity.py \
  tests/characterize/test_gacha_service_boundary.py \
  tests/characterize/test_kernel_contract.py \
  tests/characterize/test_desktop_archive_integrity.py -q
→ 78 passed, 47 subtests passed
```

### 3.3 抽卡 golden

```
.\.venv\Scripts\python.exe scripts/phase2_gacha_golden.py
→ Total: pass=100250 fail=0 max_diff=0.000e+00
→ RESULT: OK (1:1 equivalence on all comparisons)
```

### 3.4 模块边界

```
node scripts/check_module_imports.js
→ [check_module_imports] 通过：模块边界无违规（退出码 0）
```

### 3.5 36/36 E2E（隔离合成环境）

```
$env:PYTHON="$PWD\.venv\Scripts\python.exe"
node scripts/run_e2e_isolated.js
→ 测试结果: 36 通过, 0 失败
→ [run_e2e_isolated] ✅ 受保护数据零变化（DB / notes / config 只读指纹一致）
→ [run_e2e_isolated] e2e-manual.js 退出码 = 0（0 = 全部通过）
```

---

## 4. 独立验收入口

### 4.1 环境要求

| 项 | 值 | 确认方式 |
|---|---|---|
| Python | 项目 `.venv`（`.\.venv\Scripts\python.exe`） | — |
| Node | 已安装（`node --version`） | — |
| Chromium | `C:\Users\wn\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe` | **已确认存在**（`tests/e2e-manual.js` 的 `EXEC_PATH`） |
| playwright-core | 已在项目 `node_modules` | — |
| 端口 | 合成 Factory 使用 **随机端口**（127.0.0.1），**不占用 5000** | — |

### 4.2 命令序列

```powershell
cd 'D:\Axelit\.工作\trae\超级自动化学习工具'

# 1) 模块边界（退出码 0）
node scripts/check_module_imports.js

# 2) 抽卡 golden（100250 组 max_diff=0）
.\.venv\Scripts\python.exe scripts/phase2_gacha_golden.py

# 3) P1 专项
.\.venv\Scripts\python.exe -m pytest `
  tests/characterize/test_schema_authority.py `
  tests/characterize/test_factory_bootstrap.py `
  tests/characterize/test_legacy_route_full_parity.py `
  tests/characterize/test_gacha_service_boundary.py `
  tests/characterize/test_kernel_contract.py `
  tests/characterize/test_desktop_archive_integrity.py -q

# 4) 全量 characterization（目标 0 failed）
.\.venv\Scripts\python.exe -m pytest tests/characterize -q

# 5) 36/36 E2E 隔离复现（生产数据零触碰）
$env:PYTHON="$PWD\.venv\Scripts\python.exe"
node scripts/run_e2e_isolated.js
```

### 4.3 隔离与零触碰证明

`scripts/run_e2e_isolated.js` 的机制：

1. **合成根**：`tests/e2e/factory-sandbox-server.py` 在 `%TEMP%/lt_m14a_*/root`
   建 source-only 拷贝（只复制 `server/**.py`）+ 合成 `config/config.json`
   + 合成 SQLite（`tests/characterize/sandbox_env.py::seed`）。
2. **随机端口**：`socket.bind(('127.0.0.1', 0))` 取得空闲端口；**绝不**碰 5000。
3. **合成已批准策略**：P0 引导卡在无已批准策略时会用覆盖层锁死整个页面
   （产品设计）。runner 在**合成根**内写入一份 `data/agent-policy/latest.json`
   （`approved_by_user: true`），仅用于解除覆盖层。
   **生产 `data/agent-policy/` 从未被读写。**
4. **合成 vault**：E2E 5.1 / 5.2 断言知识库有内容，合成根默认是空 vault。
   runner 在**合成根**内写入纯合成 Markdown 笔记
   （`vault/<学科>/*.md` + `vault/知识点/<学科>/*.md`）。
   **生产 `src/notes/**` 从未被读写。**
5. **零触碰断言**：运行前后对下列路径做 **只读** sha256 + size 指纹比对，
   任一不一致即以退出码 1 失败：
   - `data/task_publisher.db`
   - `data/task_publisher.db-wal`
   - `data/task_publisher.db-shm`
   - `config/config.json`
   - `src/notes/**`（递归逐文件）

### 4.4 生成/验证分离

本文档中的日志是**工程自测证据**，**不作为验收结论**。
最终 36/36 结论应由副 Controller 在**独立会话**中执行 §4.2 的命令序列，
产生独立日志。

---

## 5. 已知限制

### 5.1 本次交付**未**解决（明确标记，非 BLOCKED）

| 项 | 状态 | 说明 |
|---|---|---|
| `SAL_ENFORCE_AGENT_POLICY` 默认关闭 | **已知限制** | 服务端权威闸门默认 **关闭**（既有业务特征套件在合成根里不带策略就直接 POST `/api/gacha/*` 等，默认开启会让它们全挂）。因此**正式部署目前并未获得服务端保护**，浏览器引导守卫仍只是 UI 层。启用方式：`SAL_ENFORCE_AGENT_POLICY=1`。这是既有产品决策，P1 未改动。 |
| 自由卡策略系数语义表述 | **待 P2 收敛** | `server/services/gacha.py` 严格复刻了 `gacha_bp._policy_weighted_weights` 的 `max(0.01, base * factor)` 实现以保证抽卡行为**逐位不变**；"系数越大越难被抽中"这一**语义解释**的表述收敛属于 P2 产品语义任务，P1 未擅自更改。 |
| 抽卡策略权重域 `[0,1]` 的产品契约 | **未改动** | P1 未触碰任何已确认的业务规则。 |
| Legacy `backend_api.py` 的 44 条未迁移路由 | **P2 范围** | `legacy_compat` 桥接保持，P1 只保证**零缺失**，未做全量迁移（计划明确列为 Non-Goal）。 |
| 8 个模块未注册进 registry | **P3 范围** | `agent-readonly` / `config` / `knowledge` / `prompts` / `schedule` / `sleep` / `state-assessment` / `timer` 目前是 **owner 工厂**（由 classic 层动态 import 使用）。P1 只保证契约**可机械校验**且不产生"契约孤儿"，未做全量 Feature 迁移（计划明确列为 Non-Goal）。 |
| `core/state.js` 的 store 尚无生产消费者 | **P3 范围** | P1 让它**运行期真实存在**且契约完整（`subscribe`/`snapshot`），但未强行接入业务（避免在 P1 引入第二份状态源）。 |
| `app.js` 仍是 3000+ 行的 classic 巨文件 | **P3 范围** | P1 只把 5 个 helper 改为委托，**业务逻辑零改动**。全量拆分属 P3。 |
| E2E 出现的 1 条 500 网络记录 | **非失败** | `500 /api/tasks/21` 出现在"删除任务"用例之后（删除后再取该任务）。既有行为，E2E 判据未受影响（36/36 PASS）。 |

### 5.2 环境相关说明

- E2E 36/36 需要 pinned Chromium 路径存在；若缺失，`tests/e2e-manual.js`
  会在 `chromium.launch()` 处失败（**不**静默降级）。
- 合成 E2E 整体耗时约 4 分钟（36 个用例，每例独立 page）。

---

## 6. 对 P2 的接口

| 能力 | 提供形式 | P2 如何使用 |
|---|---|---|
| 唯一 Schema 权威 | `server/schema/*::ensure_schema` + `ensure_all` | 迁移任何 BP 时，DB 结构只改一处 |
| 空库可启动的 Factory | `create_app(config)` 在空库成功 | 为每个域写"新库 + 注入 fixtures"的隔离集成测试 |
| 配置可替换 | `server/app/config.py::load_config` 唯一权威 | 各域 BP 用 `current_app.config` 注入 DB / notes / 策略目录 |
| 扩展生命周期 | `init_extensions` / `get_db_path` 生效 | 新 repo 统一取 DB 路径，不再散落全局 `DB_PATH` |
| Blueprint 注册边界 | `REGISTERED_BLUEPRINTS` + `legacy_compat` 桥 | 每迁一个域，从注册清单移一项、从兼容桥移一项，**可增量推进且随时可停** |
| 抽卡用例服务 | `server/services/gacha.py` 的过滤/权重/抽样/记账 API | gacha BP 只留 HTTP 层；P3 前端抽卡可对齐同一语义 |
| 前端 Kernel | `core/{api,eventBus,state,router,ui,constants,registry}` + `shared/*` 运行期真实存在 | Feature 模块直接用 `SAL.core.*`，不再自建 api / bus |
| 模块契约 + 边界检查 | `meta`/`mount`/`unmount` 契约 + `scripts/check_module_imports.js` | 迁移 5+ 个 Feature 模块时，边界由脚本机械保证 |
| 隔离 E2E 基础设施 | `sandbox_env` + `factory-sandbox-server` + 可配置 BASE_URL + `run_e2e_isolated.js` | 每个 Batch 都能在零生产风险下跑浏览器回归 |

---

## 7. 交付物清单

| # | 交付物 | 状态 |
|---|---|---|
| 1 | `docs/P1_ARCHITECTURE_CONTRACT.md` | ✅ 新建 |
| 2 | `docs/P1_FEATURE_MIGRATION_MAP.md` | ✅ 新建 |
| 3 | `docs/deliverables/P1_HANDOFF.md`（本文件） | ✅ 新建 |
| 4 | 隔离验收入口（命令序列 + 环境要求 + 零触碰断言） | ✅ §4 |
| 5 | 正式 Handoff / Receipt / Collection / Review | **由现有基础设施生成，本 Agent 不手写** |

---

## 8. P1 完成判据核对

| 判据 | 状态 | 证据 |
|---|---|---|
| Backend Foundation 可用 | ✅ | `test_factory_bootstrap.py` + `test_legacy_route_full_parity.py` |
| Frontend Kernel 运行期真实存在且有实证 | ✅ | `test_kernel_contract.py`（合成页面 `SAL.core.*` / `SAL.shared.*` 全部存在） |
| Desktop Archive 完整可追溯 | ✅ | `test_desktop_archive_integrity.py` 10/10（`git show d4a5f0b` 字节比对） |
| Gacha 算法边界清晰且 golden 逐位一致 | ✅ | `phase2_gacha_golden.py` 100250 组 `max_diff=0` |
| Schema 单一权威且空库可跑 | ✅ | `test_schema_authority.py` |
| characterization 0 failed | ✅ | 1353 passed / 0 failed |
| 36/36 E2E 在隔离合成环境通过 | ✅ | `scripts/run_e2e_isolated.js` → 36 通过 / 0 失败 + 零触碰断言 |
| 无已知功能丢失 | ✅ | 36/36 E2E 全绿；golden 逐位一致；全量 characterization 0 failed |
| 无未授权跨里程碑改动 | ✅ | 未改 free_task opt-in / agent_policy Publisher / G14-G15 owner 契约 / 抽卡权重语义 |
| P2 接口与交付记录齐备 | ✅ | §6 + §7 |
| **独立验收** | ⏳ | 需副 Controller 在独立会话执行 §4.2 并产生独立日志 |
