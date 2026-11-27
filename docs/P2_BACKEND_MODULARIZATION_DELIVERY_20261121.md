# AR03-P2 后端模块化交付说明（2026-11-21）

> **里程碑**：AR03-P2 —— 后端按业务域完成 Blueprint / Service / Repository 真实分层
> **执行方**：AR03-P2 Cursor Agent（单一会话串行执行 Stage 0 → Stage 8）
> **日期**：2026-11-21
> **范围**：后端分层迁移 + 兼容桥退役 + legacy 收口 + 全量验证 + 交付文档
> **数据安全**：全程 **零触碰** 生产数据（`data/task_publisher.db*`、`src/notes/**`、`config/config.json`）

---

## 0. 一页速读

| 项 | 结果 |
|---|---|
| 业务域迁移 | **9 个域全部完成**（任务/标签/弃牌/依赖图、抽卡、state/timer/schedule/knowledge/feedback、配置/导出、Prompts/Agent） |
| 活跃 Blueprint | **14 个真 BP**（+ `free_task_bp` 受保护 opt-in + 1 条 app 级 `/api/health`） |
| Blueprint 路由总数 | **80**（14 BP）+ 1（app 级） |
| Service 模块 | **24**（含 `__init__`） |
| Repository 模块 | **14**（含 `__init__`） |
| 兼容桥 `legacy_compat` | **已退役**：`EXACT_ROUTES = set()`、`PREFIX_ROUTES = ()`、`RETIRED = True`、挂载 **0** 条路由 |
| `server/backend_api.py` | 3700+ 行单体 → **290 行薄别名**，零路由、零 SQL |
| legacy 活跃路由 | **43** 条全部在 Factory 中 **原生实现**（`missing_in_factory = 0`） |
| Legacy 差异探针 | 40 用例：**32 一致 / 8 差异**（8 条全部 **已裁决**，台账完整） |
| 兼容桥转发路由 | **0**（`bridged_route_count = 0`） |
| 进程级可变全局 | **已消除**（`_DB_PATH` → app 作用域解析） |
| 全量 characterization | **1529 passed / 0 failed / 10 skipped / 441 subtests** |
| Gacha Golden | **100250 组一致，max_diff = 0.000e+00** |
| 隔离 E2E | **36/36 通过**，3519 条审计事件，生产路径零访问 |
| P0 清理验证 | **ALL ASSERTIONS PASSED**（T1–T6） |
| 模块边界检查 | 退出码 **0** |

---

## 1. 架构成果

### 1.1 三层结构（最终态）

```
HTTP 请求
   │
   ▼
server/blueprints/            ← 纯 HTTP/JSON：解析请求、调用 service、组装响应
   │  14 个真 BP（80 条路由）+ free_task_bp（受保护 opt-in）
   ▼
server/services/              ← 领域编排：事务边界、跨 repo 协调、业务规则
   │  24 个模块（tasks / gacha / tags / discard / state / timer /
   │             schedule / knowledge / feedback / config / export /
   │             prompts / agent / agent_policy / ai / free_task*）
   ▼
server/repositories/          ← 数据访问：接收显式 conn，绝不自行开连接
      14 个模块（task_repo / gacha_repo / tags_repo / discard_repo /
                state_repo / timer_repo / schedule_repo / feedback_repo /
                note_index_repo / prompt_repo / vault_repo / export_repo /
                db（统一连接/事务助手））
```

### 1.2 三条硬性分层约定（已由契约测试锁定）

1. **Repository 一律接收显式 `conn`** —— 调用方管理生命周期，只有
   `server/repositories/db.py` 负责 *开* 连接。
2. **Service 不直接写 SQL** —— SQL 只出现在 Repository 层。
3. **Repository 不读进程级全局** —— 所有路径经
   `server/repositories/db.py::resolve_db_path()` 从 **当前 app** 解析。

### 1.3 统一连接/事务助手（Stage 1 引入）

`server/repositories/db.py` 是全仓 **唯一** 的连接入口：

```python
connect(db_path=None)                     # 统一 PRAGMA 的连接
read_connection(db_path=None)             # 只读上下文（异常回滚）
write_connection(db_path=None)            # 读写上下文（正常提交 / 异常回滚）
transaction(conn, commit=True)            # 已有连接上的事务边界
resolve_db_path(db_path=None)             # app 作用域路径解析
```

PRAGMA 语义与既有 `make_request_conn` 完全一致：
`foreign_keys=ON` / `journal_mode=WAL` / `busy_timeout=30000` / `row_factory=sqlite3.Row`。

### 1.4 进程级全局消除（决策四）

`server/extensions.py` 的模块级可变全局 `_DB_PATH` 已 **删除**，改为：

1. **权威存储**：app 对象上的 `app.extensions["sal"]["db_path"]`（并镜像到 `app.config["_db_path"]`）；
2. **请求期解析**：优先当前 Flask app 上下文；
3. **兜底**：最近一次初始化的 app（仅请求期之外）；
4. **fail closed**：都没有 → `RuntimeError`，绝不静默猜路径。

契约测试：`tests/characterize/test_db_path_isolation.py`（同进程双 Factory 实例互不串扰）。

---

## 2. Stage 0–8 实施记录

| Stage | 内容 | 关键产出 |
|---|---|---|
| **0** | 隔离器修复 + P1 复验 | `scripts/run_e2e_isolated.js` 重写（fs 守卫 + 审计钩子 + 合成根自证）、`docs/P1_ADDENDUM_20261121.md`、`docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md` |
| **1** | 分层基座 + 静态 oracle | `tests/fixtures/legacy_route_surface.json`（43 条）、`tests/fixtures/golden_http_snapshot.json`（51 用例）、`server/repositories/db.py`、`docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md` |
| **2** | 任务/标签/弃牌/依赖图域 | `services/tasks.py` `services/tags.py` `services/discard.py`、`repositories/task_repo.py` `tags_repo.py` `discard_repo.py`、真 `discard_bp`、`/api/dependencies` 归入 tasks 域 |
| **3** | 抽卡域 | `services/gacha.py`（承接 pool detail / statistics / replace 编排）、`repositories/gacha_repo.py`、`gacha_bp` 只留 HTTP；Golden 保持 100250 组 `max_diff=0` |
| **4** | state/timer/schedule/knowledge/feedback 域边界收口 | `services/state.py` `timer.py` `schedule.py` `knowledge.py` `feedback.py`、`repositories/state_repo.py` `timer_repo.py` `schedule_repo.py` `feedback_repo.py` `note_index_repo.py` |
| **5** | 配置域 + 导出域 | `services/config.py` `services/export.py`、`repositories/export_repo.py`、真 `config_bp`（3 路由） |
| **6** | Prompts 域 + Agent 域 | `services/prompts.py` `services/agent.py` `services/ai.py`、`repositories/prompt_repo.py` `vault_repo.py`、真 `prompts_bp`（5）/ `agent_bp`（9）；**保留 AI 不得写 Obsidian 的 403**（原生实现，不依赖兼容桥注入） |
| **7** | legacy 收口 | `server/backend_api.py` → 290 行薄别名；`server/app/legacy_compat.py` → 退役墓碑；Factory 注册 14 BP；`/` 改 app 级路由；转发壳清理 |
| **8** | 全量验证 + 交付 | 本文件 + `docs/P2_FEATURE_MIGRATION_MAP.md` + `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md` + `docs/deliverables/P2_HANDOFF.md` + `docs/CURRENT_PROJECT_STATE.md` 增量段落 |

---

## 3. 兼容桥退役与 legacy 收口（Stage 7 核心）

### 3.1 兼容桥退役

`server/app/legacy_compat.py` 已 **完全解耦**：

```python
EXACT_ROUTES: set[str] = set()
PREFIX_ROUTES: tuple[str, ...] = ()
RETIRED = True

def register_legacy_compat(app, config) -> int:
    app.config["_compat_route_count"] = 0
    return 0
```

- 不再被 `server/app/app_factory.py` import 或调用；
- 不 import `backend_api`，不改任何全局 DB 路径；
- **挂载 0 条路由**（原 21 条）。

> **物理删除说明**：Cursor 的 `[destructive-guard]` 会拦截 `rm` / `git rm` /
> `Delete` 工具删除受跟踪文件。按项目政策，物理删除属 **带外（out-of-band）**
> Controller 操作。本里程碑以 **墓碑模块** 达成同等效果：
> 完全不可达、零路由、零副作用，并由
> `tests/characterize/test_static_route_inventory.py::test_compat_bridge_module_is_not_imported_by_server`
> （AST 扫描 `server/**` 禁止任何文件 import `legacy_compat`）机械锁定。

### 3.2 legacy 入口薄别名

`server/backend_api.py`：

- **零** Flask 路由（`@app.route` 计数 = 0）；
- **零** DDL/DML token（`CREATE TABLE` / `ALTER TABLE` / `DROP TABLE` / `INSERT INTO`）；
- 领域模型 → `server.domain.models`；
- 连接助手 → `server.app.extensions` / `server.repositories.db`；
- 启动期同步 → `server.app.bootstrap` / `services.tasks` / `services.discard`；
- `AGENT_CONFIG` / `call_llm` / `load_prompt` 等 → PEP 562 惰性再导出指向真正 owner；
- `python server/backend_api.py` **≡** `python run_app.py` **≡** `create_app()`
  （由 `tests/characterize/test_legacy_route_full_parity.py` 断言 url_map 完全一致）。

---

## 4. 功能保全证据

### 4.1 双 oracle 基准（决策三）

| Oracle | 覆盖 | 产物 |
|---|---|---|
| **迁移前 Factory 黄金 HTTP 快照** | 两侧 **共有** 的路由 | `tests/fixtures/golden_http_snapshot.json`（51 用例） |
| **Legacy 行为差异台账** | legacy **独有** 的 21 条兼容桥路由 + 重名路由的差异裁决 | `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md` + `tests/fixtures/legacy_divergence.json`（40 用例） |

两者合起来构成 **完整** 的功能等價基准。

### 4.2 冻结审计 oracle（Stage 7 引入）

Stage 7 之后 legacy 单体不再持有任何路由，"现场跑 legacy 取数" 的方式失效。
因此 legacy 侧改为读取 **一次性冻结** 的审计基准：

| 产物 | 内容 | 来源 |
|---|---|---|
| `tests/fixtures/legacy_route_surface.json` | 43 条 legacy 活跃路由的 **权威清单** | 从 Git HEAD 提取 |
| `tests/fixtures/legacy_baseline.json` | 40 条探针用例的 **状态码 + 响应体 + SQLite 表摘要** | `scripts/_freeze_legacy_baseline.py` 在合成根内实测 |
| `scripts/legacy_divergence_probe.py` | 实时 Factory ↔ 冻结基线 逐条比对 | 实时采集 |

探针因此在 legacy 收口后 **仍然具备鉴别力**：任何迁移回归都会让实时 Factory 与冻结基线产生新的差异。

### 4.3 差异裁决结果（8 条，全部已裁决）

| # | 路由 | 裁决 | 结论 |
|---|---|---|---|
| L-01 | `GET /api/health` | R1 | 保留 Factory `{"phase":1,"status":"ok"}` |
| L-02 | `POST /api/gacha/replace` 缺 reason | R1+R4 | 保留 Factory **400 `reason required`**（legacy 404 是历史缺陷） |
| L-03 | `POST /api/gacha/replace` 副作用 | R1+R4 | 保留 Factory **零副作用**（legacy 虚增 `refusal_count` 是缺陷） |
| L-04 | `GET /api/export` | R1 | 结构一致；差异来自 L-03 传导 |
| L-05 | `POST /api/agent/save-note` | R1+R5 | 保留 **403**（用户策略：AI 不得写 Obsidian；Stage 6 起 **原生实现**） |
| L-06 | `GET /api/discard-pile` | R2 | 响应体一致；副作用摘要差异来自 L-03 |
| L-07 | `POST /api/gacha/replace` reason 校验 | R1+R4 | 保留 Factory **严格白名单校验** |
| L-08 | `GET /api/agent-policy/status` | R1+R5 | 保留 Factory **200 只读**（P1 授权的新能力；legacy 侧不存在该路由） |

**32 条** 路由实测完全一致（状态码 + 响应体 + 副作用三项全同）。

### 4.4 机械保障

`tests/characterize/test_legacy_divergence_ledger.py` 断言：

1. legacy 的 **每一条** 活跃路由（43 条）在台账中都有条目；
2. 台账的每个差异判定与 `tests/fixtures/legacy_divergence.json` 实测 **不矛盾**；
3. 每条差异条目必须引用至少一个 黄金快照用例名或 差异探针用例名；
4. 探针可复现 —— 重跑计数与冻结产物一致。

---

## 5. 验证证据（Stage 8 实测）

### 5.1 验证顺序与结果

| # | 命令 | 结果 | 退出码 |
|---|---|---|---|
| 1 | `node scripts/check_module_imports.js` | 模块边界无违规 | **0** |
| 2 | `python scripts/phase2_gacha_golden.py` | **pass=100250 fail=0 max_diff=0.000e+00** | **0** |
| 3 | `python scripts/verify_p0_cleanup.py` | **ALL ASSERTIONS PASSED**（T1–T6） | **0** |
| 4 | `python -m pytest tests/characterize -q` | **1529 passed / 0 failed / 10 skipped / 441 subtests** | **0** |
| 5 | `node scripts/run_e2e_isolated.js` | **36 通过 / 0 失败**，3519 审计事件，生产路径零访问 | **0** |

> Windows 注意：`python` 在 PATH 上可能指向 Windows Store 别名，隔离 E2E 需
> `$env:PYTHON = "$PWD\.venv\Scripts\python.exe"`。

### 5.2 各域 Contract + Integration 专项

| 域 | 专项测试文件 |
|---|---|
| 任务/标签/弃牌/依赖图 | `test_stage2_tasks_domain.py`、`test_task_lifecycle_owner.py`、`test_task_skip_refuse_owner.py`、`test_task_discard_restore_owner.py` |
| 抽卡 | `test_stage3_gacha_domain.py`、`test_gacha_service_boundary.py`、`test_gacha_multi_draw.py`、`test_gacha_weighted_regression.py`、`test_gacha_policy_weights.py`、`test_gacha_time_budget.py`、`test_gacha_replace_no_repeat.py`、`test_gacha_statistics_ledger.py` |
| state/timer/schedule/knowledge/feedback | `test_stage4_domains.py`、`test_task_feedback_care_owner.py` |
| 配置/导出 | `test_stage5_config_export.py` |
| Prompts/Agent | `test_stage6_prompts_agent.py`、`test_m4_agent_prompts_contract.py` |
| 基础设施工具 | `test_static_route_inventory.py`、`test_route_inventory.py`、`test_legacy_route_full_parity.py`、`test_legacy_divergence_ledger.py`、`test_golden_http_snapshot.py`、`test_db_path_isolation.py`、`test_ar02_factory_instance_isolation.py`、`test_schema_authority.py`、`test_sandbox_isolation.py`、`test_e2e_isolation_guard.py` |

### 5.3 零生产数据触碰

`scripts/run_e2e_isolated.js` 的三重证明：

1. **Runner 侧 fs 守卫** —— 包装 `fs.readFileSync/openSync/statSync/readdirSync`，
   受保护路径（`data/**`、`config/**`、`src/notes/**`）一旦被访问 **立即抛错**；
2. **Server 侧 `sys.addaudithook`** —— 记录 `sqlite3.connect` 与文件打开事件，
   输出访问路径清单；runner 断言全部落在 `%TEMP%` 合成根内；
3. **合成根自证** —— 合成服务器启动时断言 `app.config["_db_path"]`、notes root、
   CWD 全部位于合成根，否则 **拒绝启动**。

实测：**3519 条审计事件，0 条命中生产路径**；E2E **36 通过 / 0 失败**。

---

## 6. 遗留兼容层清单

| 项 | 状态 | 说明 |
|---|---|---|
| `server/app/legacy_compat.py` | **已退役（墓碑）** | 0 路由、0 import、不可达；物理删除待带外操作 |
| `server/backend_api.py` | **薄别名** | 保留兼容入口（`python server/backend_api.py` ≡ `run_app.py`）；P5 归档 |
| `server/utils/{energy_calc,task_blocked,wiki_link}.py` | **转发壳 → 指向新 owner** | 不再是独立实现 |
| `server/repositories/{task_repo,gacha_repo}.py` | **真实现** | Stage 7 清空转发壳 |
| `server/ai/llm_client.py` | **真实现** | Stage 6 由 stub 变真 |
| `server/ai/prompts/` | 保留 | 提示词资产锚点 |
| `server/app/legacy_compat` 白名单 | **空集** | `EXACT_ROUTES = set()` / `PREFIX_ROUTES = ()` |

---

## 7. P1 纠偏事项处理结果

| 项 | 处理 | 位置 |
|---|---|---|
| E2E 隔离器生产数据库读取 | ✅ 已修复（哈希观测 → 守卫阻断 + 审计清单 + 自证） | `docs/P1_ADDENDUM_20261121.md` §1 |
| `SAL_ENFORCE_AGENT_POLICY` 表述 | ✅ 已纠错：**官方安全启动链强制开启服务端闸门**（`launch_server.py` 注入 `SAL_ENFORCE_AGENT_POLICY=1`）；Factory 默认关闭仅在绕过启动器时成立 | `docs/P1_ADDENDUM_20261121.md` §2 |
| Schema「14 + 1」归属 | ✅ 已澄清：**14 张集中 Schema 表 + 1 张 `FreeTaskEventStore` 自管表** | `docs/P1_ADDENDUM_20261121.md` §3 |
| Gacha 权重方向语义歧义 | ⏳ **保留为待用户裁决事项**（保留现有实际行为，不改算法，不改 Golden） | `docs/P1_ADDENDUM_20261121.md` §4 |

---

## 8. P1 独立验收状态（⚠️ 如实记录）

> **状态：`READY_FOR_INDEPENDENT_ACCEPTANCE` —— 外部待会签。**

- Stage 0 修复 **已由本会话完成并自审**（修复审查记录见
  `docs/P1_ADDENDUM_20261121.md`）；
- 复验 **全绿**（见 §5.1，命令 / 退出码 / 结果均已记录）；
- 证据包 **已交付**：`docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md`
  （含修复 diff 与设计说明、自审记录逐条对照任务书 §4.1、完整复验输出、
  P1 补充说明、勾选式会签清单）；
- **独立验收签字（主控 / 副 Controller 在本会话之外会签）尚未记录在本会话的
  任何输入中**。

按 P2 计划 §4.2 的硬门禁原文：

> 「本会话交付说明中，P1 独立验收一律标记为 **外部待会签**，不得写成「已完成」。」

**因此本交付说明如实标注 P1 独立验收为「外部待会签」，不宣称已完成。**
P2 的实质工程工作（Stage 1–8）已按计划完成并全量验证通过；该项会签是
**流程门禁的补签事项**，不涉及 P2 代码交付物的技术状态。

---

## 9. 已知限制与未决项

| # | 项 | 说明 | 归属 |
|---|---|---|---|
| 1 | `/api/health` 响应形状是否与 legacy 统一 | legacy `{"status":"healthy"}` vs Factory `{"phase":1,"status":"ok"}` | P5（不属 P2） |
| 2 | legacy 换牌路径的历史缺陷是否需要 **数据修复** | legacy 曾把失败的换牌记成拒绝（`task_rejection_log` / `refusal_count` 虚增） | 需单独评估；**P2 不触碰生产数据** |
| 3 | Gacha 策略系数产品语义 | 「系数越大越难被抽中」等产品语义待用户裁决 | 用户裁决（P1 遗留） |
| 4 | dual-vault 布局契约 | 历史未决 | 不属 P2 |
| 5 | `server/app/legacy_compat.py` 物理删除 | 受 `[destructive-guard]` 拦截；墓碑已达成同等效果 | 带外 Controller 操作 |
| 6 | `server/backend_api.py` 文件归档 | 按计划保留兼容入口 | P5 |
| 7 | `scripts/_probe_task_get_500.py` 临时诊断脚本清理 | Stage 8 期间用于定位 E2E 控制台的 `500 /api/tasks/<id>`；诊断已结案（任务 CRUD 的 404/200/201 语义正常，该 500 来自 **并发删除与读取的竞态**，非分层回归）。`[destructive-guard]` 拦截删除 → 属带外操作 | 带外 Controller 操作 |

---

## 10. P3 可直接继承的架构现状

- **唯一装配根**：`server/app/app_factory.py::create_app()`；
- **启动链不变**：`scripts/启动学习工具.bat` → `scripts/start_web_safe.bat` →
  `scripts/launch_server.py` → `server/backend_api.py` → `create_app()`（生产启动链 **零改动**）；
- **前端契约未变**：所有 HTTP 路径、方法、状态码、响应结构保持不变
  （前端无需为 P2 改动）；
- **新增 P3 能力时的落位规则**：
  1. HTTP → 新增/扩展 `server/blueprints/*_bp.py`；
  2. 业务规则 → `server/services/*`；
  3. SQL → `server/repositories/*_repo.py`（接收显式 `conn`）；
  4. Schema → `server/schema/*`（`ensure_all` 是唯一编排入口）；
  5. **不得**在 Blueprint 层直接写 SQL；**不得**在 Repository 层自开连接；
  6. **不得** import `server.backend_api` 或 `server.app.legacy_compat`。

---

## 11. 交付物索引

| 文档 | 内容 |
|---|---|
| `docs/P2_BACKEND_MODULARIZATION_DELIVERY_20261121.md` | **本文件** —— P2 交付说明 |
| `docs/P2_FEATURE_MIGRATION_MAP.md` | 逐条路由迁移映射（旧 → 新 → 调用方式 → 测试证据 → 台账索引） |
| `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md` | Legacy 行为差异台账全文（8 条裁决 + 43 条全覆盖） |
| `docs/deliverables/P2_HANDOFF.md` | P3 交接文档 |
| `docs/P1_ADDENDUM_20261121.md` | P1 补充说明（隔离器修复 / 表述纠错 / Schema 澄清 / Gacha 待决） |
| `docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md` | P1 独立验收证据包（待外部会签） |
| `docs/CURRENT_PROJECT_STATE.md` | 追加 2026-11-21 P2 增量段落 |
| `tests/fixtures/legacy_route_surface.json` | 冻结的 43 条 legacy 路由清单 |
| `tests/fixtures/legacy_baseline.json` | 冻结的 40 用例 legacy 运行时基线 |
| `tests/fixtures/legacy_divergence.json` | 实测差异产物（32/8） |
| `tests/fixtures/route_inventory.json` | 路由清单（`bridged: 0`） |
| `tests/fixtures/golden_http_snapshot.json` | 51 用例黄金 HTTP 快照 |
| `tests/fixtures/p2_migration_map.json` | 机读三层映射（BP → Service → Repo） |
