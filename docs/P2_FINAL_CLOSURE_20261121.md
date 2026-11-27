# P2 最终收尾说明（AR03-P2 / P2 收尾）

> 日期：2026-11-21
> 范围：P2 后端分层的 **有界收尾**（Blueprint 事务职责归位、过时注释修正、
> P1 会签状态如实记录）。
> 性质：**新增** 文档，**不覆盖** 任何历史交付记录。

---

## 0. 本文档的定位与边界

### 0.1 为什么单独出这份文档

P2 的历史交付记录（`docs/P2_BACKEND_MODULARIZATION_DELIVERY_20261121.md`、
`docs/P2_FEATURE_MIGRATION_MAP.md`、
`docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md`、
`docs/deliverables/P2_HANDOFF.md`）记录的是 **Stage 1–8** 的完成状态。

本轮收尾做了三件事，其中两件会 **改变已交付代码的事实描述**（Blueprint 事务
边界、`app_factory` 注释），第三件是 **流程状态的如实归档**。

历史文档记录的是 **当时** 的事实，本文档记录的是 **收尾后** 的事实。两者
**并存**，不冲突 —— 历史文档不被改写。

### 0.2 本轮收尾 **没有** 做的事

- **没有** 把 P1 独立验收写成「已完成」；
- **没有** 追溯修改任何历史执行记录；
- **没有** 触碰 `src/notes/**` / `data/task_publisher.db{,-wal,-shm}` /
  `config/config.json`；
- **没有** 改 SQL、响应体、状态码、业务规则；
- **没有** commit / push / reset / clean / stash / checkout / switch。

---

## 1. 状态总览（如实记录）

| 项 | 状态 | 说明 |
|---|---|---|
| **P1 独立验收** | ⏳ **`READY_FOR_INDEPENDENT_ACCEPTANCE` —— 外部待会签** | 证据包已交付（`docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md`），但 **签字尚未记录在本会话的任何输入中**。按 P2 计划 §4.2 硬门禁原文，一律标记为「外部待会签」。 |
| **P2 门禁违规** | ⚠️ **如实在案** | P2 **未取得 P1 会签即进入 Stage 1–8**。这是既成事实，**不追溯修改**，仅登记。 |
| **P2 工程完成度** | ✅ **Engineering Complete** | Stage 1–8 已按计划完成；本轮收尾补齐了事务边界归位与注释准确性。 |
| **P2 验收状态** | 🟡 **Engineering Complete / Independent Acceptance Pending** | 技术侧完成；流程侧的独立会签仍缺。 |
| **P2 门禁违规是否影响代码质量** | ❌ **不影响**（技术侧） | 门禁违规是 **流程** 问题。代码侧的全部结论由 §2 的验证证据支撑，与是否完成会签 **无关**。 |
| **Export 归属** | ✅ **有意保留，无实际职责冲突** | `config_bp` 持有 `/api/export`，有独立 `services/export.py` + `repositories/export_repo.py`。不同端点、不同服务、无重叠职责。 |
| **E2E 500（历史一次性）** | ⏳ **不结案、不重跑** | 历史一次性 `/api/tasks/{id}` 500，未取得完整异常堆栈。**不结案、不重跑**；P3 最终验收若复现则按实际异常调查。 |
| **P1 遗留带外事项** | ⏳ **保留带外** | `server/app/legacy_compat.py`（墓碑，0 路由 / 0 import）与 `scripts/_probe_task_get_500.py` 受 `[destructive-guard]` 约束，**不绕过**。 |

---

## 2. 本轮收尾的代码改动

### 2.1 Blueprint 事务职责归位（§2.2）

#### 问题（已实证，非推测）

6 个 Blueprint 在 **HTTP 层** 直接持有 `with read_connection()/write_connection()
as conn:` → **事务边界落在 Blueprint**，违反「Service：业务编排、**事务生命周期**、
跨 Repository 协调」的分层约定。

涉及蓝图与调用点（收尾前）：

| Blueprint | 只读调用点 | 读写调用点 |
|---|---|---|
| `tasks_bp.py` | 4 | 6 |
| `tags_bp.py` | 1 | 3 |
| `discard_bp.py` | 1 | 2 |
| `schedule_bp.py` | 3 | 4 |
| `config_bp.py` | 1 | 0 |
| `agent_bp.py` | 0 | 2 |
| **合计** | **10** | **17** |

#### 做法

1. `server/repositories/db.py` 新增 **事务边界辅助** `service_transaction()`：
   语义 = 打开连接 → Service 在 **同一连接** 上完成全部 repo 调用 →
   Service 层决定提交 / 回滚。`commit=False` 时为 **只读语义**
   （正常退出不提交，异常回滚 —— 与旧 `read_connection()` 逐条等价）。
2. 各 Service 新增 **自持事务的整体动作入口**（`*_action`）：
   `tasks` / `tags` / `discard` / `schedule` / `agent` / `export`。
   原有 `(conn, ...)` 函数 **保留**（连接感知型，供 Service 内部复合动作使用）。
3. Blueprint 退化为「**解析请求 → 调 Service → 组装响应**」。

#### 关键不变式

| 不变式 | 保证方式 |
|---|---|
| **事务原子性** | Service 内部的多 repo 写仍在 **同一连接、同一事务** 内（`service_transaction` 复用调用方连接，绝不中途换连接丢锁）。 |
| **提交时机等价** | 旧写法 `with write_connection()` 退出时提交；新写法 Service 内部退出 `with` 时提交。**逐条等价**。 |
| **异常回滚等价** | 两条路径都在异常时 `rollback()` 并原样抛出。 |
| **只读无提交** | 只读 Service 用 `commit=False`，正常退出 **不提交**。 |
| **响应逐字不变** | 未改 SQL、响应体、状态码、业务规则。 |

#### 规则统一（重要）

收尾前计划文本存在 **规则矛盾**：一处允许 `config_bp` 保留只读直连，另一处
的契约测试要求 **全部 14 个 BP 都没有** 直接连接调用。

**本轮按「规则统一」处置**：**不存在「只读可以例外」的特例**。`config_bp`
的只读访问同样下沉到 Service（`export_service.build_export_action()`，
`commit=False`）。理由：同一仓库并存两种风格本身是缺陷；且只读蓝图日后
极可能演化为写操作，届时"例外"会成为漏洞。

#### 新增机械契约测试

`tests/characterize/test_blueprint_transaction_boundary.py`（**新增**，21 项断言）：

- 断言 **全部 15 个蓝图文件**（14 个默认真 BP + 受保护 opt-in 的
  `free_task_bp`）中 **没有** 直接 `read_connection()` /
  `write_connection()` / `sqlite3.connect(`；
- 断言蓝图 **不再** import `server.repositories.db`（它不需要了）；
- 断言蓝图仍 **不** 写裸 SQL、仍 **不** 直接 `.execute(`；
- 断言 Service 层 **确实** 使用 `service_transaction`（事务边界真的下沉了）；
- 断言 Repository 仍 **只** 接收显式 `conn`（只有 `db.py` 能开连接）；
- 行为探针（合成根内）断言：解锁副作用原子性、提交时机可见性、重名标签
  200、只读导出可用、依赖图/依赖者、404/400 错误语义、日程域、弃牌域、
  标签批量分配、Agent 导入 —— **逐条与迁移前一致**。

---

### 2.2 `app_factory.py` 过时注释修正（§2.3）

**纯注释改动**，`app_factory.py` 的 **代码逻辑一行未改**。

| 位置 | 修正前（过时） | 修正后（已核实） |
|---|---|---|
| `create_app()` docstring | "3 Blueprints registered (tasks / gacha / tags)" | "**14 real Blueprints** … + app-level `GET /api/health`" |
| `create_app()` docstring | "Note: 9 other Blueprints remain in backend_api.py for Phase 1." | 兼容桥已 **完全退役**（0 路由 / 0 import）；`backend_api.py` 是 **230 行**薄别名 |
| 模块 docstring 步骤 5 | "14 个真实 BP"（无路由数） | "14 个真实 BP，共 **80 条 API 路由** + app 级 `/api/health`" |
| `REGISTERED_BLUEPRINTS` 注释 | 无计数说明 | 明确 **14 个真 BP / 80 条 API 路由**，并注明 legacy 兼容桥 **不在** 清单中 |
| Agent Policy 注释 | "默认关闭意味着**正式部署目前并未获得服务端保护**" | **官方安全启动链强制开启**（`launch_server.py` 注入 `SAL_ENFORCE_AGENT_POLICY=1`）；Factory 默认关闭 **仅在绕过启动器直接 `create_app()` 时**成立 |

#### 修正依据（全部已实证，非推测）

- **BP 数量 = 14**、**API 路由 = 80**：`create_app()` 构造后统计
  `app.url_map` —— 总规则 82 条 = 80 条 `/api/*` + `/`（静态首页）+
  `/static/<path:filename>`（Flask 自带）。
- **legacy 兼容桥 = 0 路由 / 0 import**：`server/app/legacy_compat.py` 的
  `EXACT_ROUTES` / `PREFIX_ROUTES` 恒为空，`register_legacy_compat()`
  恒返回 0 且 **不** 调用 `app.add_url_rule`、**不** import `backend_api`；
  `app_factory.py` **不再** import 它。
- **`backend_api.py` = 230 行**（计划文本写的 "290 行" 与实际不符，此处按
  **实测值 230** 记录）。
- **Agent Policy 官方启动链强制开启**：`scripts/launch_server.py` 的
  `build_child_env()` 把 `SAL_ENFORCE_AGENT_POLICY=1` 注入子进程环境，
  **父进程即便设为 `0` 也被覆盖**；由
  `tests/characterize/test_bootstrap_launcher_gate.py` 机械锁定。表述与
  `docs/P1_ADDENDUM_20261121.md` §2 一致。

---

## 3. 验证证据（本轮收尾）

### 3.1 授权命令与结果

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/characterize -q` | ✅ **1550 passed / 10 skipped / 441 subtests**（0 failed） |
| `node scripts/check_module_imports.js` | ✅ 退出码 **0**（模块边界无违规） |
| `python scripts/verify_p0_cleanup.py` | ✅ **ALL ASSERTIONS PASSED** |

### 3.2 基线对比

| 时点 | 结果 |
|---|---|
| 收尾 **前** 基线 | 1529 passed / 10 skipped / 441 subtests |
| 收尾 **后** | **1550 passed** / 10 skipped / 441 subtests |
| 差值 | **+21**（全部来自新增的 `test_blueprint_transaction_boundary.py`） |

**0 failed**。既有断言 **一条未删、一条未放宽**。

> 唯一被修正的既有断言是
> `tests/characterize/test_stage2_tasks_domain.py::test_stage2_blueprints_use_repository_db_helper`。
> 它原本要求"蓝图通过 `server.repositories.db` 开连接" —— 该契约被本轮
> **更强** 的约束取代（蓝图 **彻底不碰** 连接）。方法已更名为
> `test_stage2_blueprints_do_not_open_connections`，断言方向反转并加强。
> 这是 **契约演进**，不是为了让测试通过而放宽。

### 3.3 未重跑的验证（及理由）

| 未重跑项 | 理由 |
|---|---|
| P2 全量 E2E | 本轮 **未触及** 抽卡算法、未改 HTTP 契约；P2 已有可信证据。P3 最终验收会跑隔离 E2E 36/36。 |
| Gacha Golden | 本轮 **一行未改** 抽卡算法；Golden 不动也不重跑。 |

---

## 4. P2 交付材料对账（§2.4）

| 文档 | 对账结论 |
|---|---|
| `docs/P2_FEATURE_MIGRATION_MAP.md` | ✅ 与实际代码一致（蓝图 / service / repo 三层映射）。 |
| `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md` | ✅ 与实际代码一致。 |
| `docs/deliverables/P2_HANDOFF.md` | ✅ §3.3 Agent Policy 表述已与 `P1_ADDENDUM` §2 一致；§6 未决项归属清晰。**无需增量更正**。 |
| `docs/P2_BACKEND_MODULARIZATION_DELIVERY_20261121.md` | ✅ §8 已如实记录 P1 待会签；§9 未决项与本文档 §1 一致。**无需增量更正**。 |

**Export 归属**已按 §2.4 记录为「**有意保留，无实际职责冲突**」。

**唯一需要的增量更正**就是本文件本身 —— 它记录了 Blueprint 事务边界归位
这一 **代码事实的变化**，而历史交付文档记录的是变化前的事实。

---

## 5. 流程违规登记（如实在案）

### 5.1 违规内容

**P2 未取得 P1 独立验收会签，即进入 Stage 1–8。**

- P2 计划 §4.2 原文要求：「本会话交付说明中，P1 独立验收一律标记为
  **外部待会签**，不得写成「已完成』」；
- 实际情况：P2 的工程工作在会签缺失的情况下 **全部完成并通过验证**；
- 交付材料 **没有** 把会签伪装成已完成 —— 这一点是 **合规的**。

### 5.2 处置原则

1. **不追溯修改**历史执行记录 —— 改写历史只会让下一次审计更难；
2. **不掩盖** —— 本文件与 P2 交付文档 §8 **同时** 载明该状态；
3. **不因此宣称技术交付无效** —— 技术结论由 §3 的可复现证据支撑；
4. **补签路径明确** —— 会签仍由主控 / 副 Controller 在会话外完成，
   完成后应更新 `docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md`
   的勾选式清单。

---

## 6. 未决项归属（移交 P3 / P5 / 用户裁决 / 带外）

| # | 项 | 归属 | 说明 |
|---|---|---|---|
| 1 | **P1 独立验收会签** | **Controller / 用户（会话外）** | 证据包齐备，缺签字。 |
| 2 | **P2 门禁违规** | **已登记，不追溯**（§5） | 流程问题；技术侧不受影响。 |
| 3 | `/api/health` 响应形状是否与 legacy 统一 | **P5** | legacy `{"status":"healthy"}` vs Factory `{"phase":1,"status":"ok"}` |
| 4 | legacy 换牌路径历史缺陷的 **数据修复** | **单独评估** | legacy 曾把失败的换牌记成拒绝。**P2 不触碰生产数据**，修复需独立授权。 |
| 5 | Gacha 策略系数产品语义 | **用户裁决** | 保留现有实际行为与 Golden；语义歧义待用户明确。 |
| 6 | dual-vault 布局契约 | **历史未决** | 不属 P2。 |
| 7 | `server/app/legacy_compat.py` 物理删除 | **带外 Controller 操作** | `[destructive-guard]` 拦截删除；墓碑模块已达成同等效果（0 路由 / 0 import / 不可达）。 |
| 8 | `server/backend_api.py` 文件归档 | **P5** | 按计划保留兼容入口。 |
| 9 | `server/utils/{energy_calc,task_blocked,wiki_link}.py` 转发壳收敛 | **P3/P5** | 已是转发壳，不再是独立实现。 |
| 10 | `scripts/_probe_task_get_500.py` 临时诊断脚本清理 | **带外 Controller 操作** | Stage 8 定位 E2E `500 /api/tasks/<id>` 用；诊断已结案（**并发竞态**，非分层回归）。<br>**增量审计纠错见 §6.1** —— 该结案结论**仅适用于它当时调查的那一次事件**。 |
| 11 | 历史一次性 E2E 500 | **不结案** | 未取得完整异常堆栈；P3 最终验收若复现则按实际异常调查。 |

### 6.1 增量审计纠错（2026-11-22，AR03-P4 独立审查）

> 本小节为 **新增** 记录，**不追溯修改**上方第 10 / 11 行的历史正文。
> 权威口径见 `docs/P4_AUDIT_CORRECTIONS_20261122.md` §1.1。

**纠错内容**：

P2 Stage 8 的诊断脚本 `scripts/_probe_task_get_500.py` 针对 **一次具体事件** 得出了
「并发删除与读取竞态」的结论。该结论 **仅对那一次事件成立**。

AR03-P3 与 AR03-P4 两轮隔离 E2E 又各观察到 **1 次** `/api/tasks/21` → HTTP 500
（**请求方法未被现有证据确定**）。这两次观察与 P2 的那次事件 **未经证据证明是同一问题**，
因此：

- ❌ **不得** 用 P2 的「并发竞态」结论为 P3 / P4 的观察结案；
- ❌ **不得** 宣称 P3 / P4 的观察「已复现」或「未复现」；
- ❌ **不得** 把它写成 `GET /api/tasks/21`（方法未确定）；
- ✅ 统一口径：**`/api/tasks/21` 出现一次 HTTP 500，请求方法未确定，根因未确认。**

**归属**：P5 记录为 **已知限制 + 明确归属**，**不结案**，不阻塞 P5 交付。
**与 P4 迁移的关系**：CSS 迁移不触碰任何后端路由 → **非 P4 引入**。

**P5 的实际处置**：见 `docs/P5_FINAL_DELIVERY_REPORT_20261122.md` 的「已知限制及其归属」章节。

---

## 7. 完成定义核对

| 判据 | 状态 |
|---|---|
| 代码与交付材料一致 | ✅ §4 对账完成；§2.2 记录的代码事实变化由本文件增量说明。 |
| Blueprint 事务职责归位并有机械契约测试 | ✅ §2.1；`test_blueprint_transaction_boundary.py`（21 项断言）。 |
| `app_factory` 过时注释已修正 | ✅ §2.2；纯注释，逻辑一行未改。 |
| P1 待会签如实记录 | ✅ §1 + §5；**未**写成「已完成」。 |
| P2 门禁违规如实记录 | ✅ §5.1。 |
| P2 其余未决事项有明确归属 | ✅ §6。 |
| 全部验证通过 | ✅ §3.1；**0 failed**。 |

---

> 本文档只陈述 **可复现的证据**。任何无法证明等价的项，一律标记为
> **未完成**，不隐藏、不宣称完成。
