# AR03-P2 交接文档（Backend Modularization → P3）

> **里程碑**：AR03-P2 —— 后端按业务域完成 Blueprint / Service / Repository 真实分层
> **交付日期**：2026-11-21
> **交出方**：AR03-P2 Cursor Agent（单一会话串行执行 Stage 0 → Stage 8）
> **接手方**：AR03-P3（前端子项目迁移 / 功能对齐）
>
> **配套文档**：
> * 交付说明 → `docs/P2_BACKEND_MODULARIZATION_DELIVERY_20261121.md`
> * 迁移映射 → `docs/P2_FEATURE_MIGRATION_MAP.md`
> * 差异台账 → `docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md`
> * P1 补充 → `docs/P1_ADDENDUM_20261121.md`
> * 架构现状 → `docs/ARCHITECTURE.md`

---

## 1. P3 可以直接继承什么

### 1.1 后端 **HTTP 契约未变** —— P3 通常 **不需要** 为 P2 改前端

P2 是 **纯后端重构**。所有路由的：

- **路径** 未变；
- **HTTP 方法** 未变；
- **状态码** 未变；
- **响应 JSON 结构** 未变；
- **副作用语义** 未变（除台账中 8 条 **已裁决** 的 legacy 差异，全部按 Factory 权威侧保留）。

因此 P3 的前端工作（视觉/主题/交互迁移）**不依赖** 本里程碑的接口变更。
唯一需要 P3 知晓的 API 事实：

| 路由 | 注意事项 |
|---|---|
| `GET /api/health` | 返回 `{"phase":1,"status":"ok"}`（**不是** legacy 的 `{"status":"healthy"}`） |
| `POST /api/gacha/replace` | `reason` **必填**，缺失/空串/非字符串/未知值 → **400**；理由白名单 = `low_energy` / `no_time` / `similar_done` / `other` |
| `POST /api/agent/save-note` | 恒定 **403**（用户策略：AI 不得写 Obsidian 笔记） |
| `GET /api/agent-policy/status` | 纯只读；**从不**创建/写入/修复策略目录 |

### 1.2 生产启动链 **零改动**

```
scripts/启动学习工具.bat
  → scripts/start_web_safe.bat
    → scripts/launch_server.py       （强制 factory 后端）
      → run_app.py                   （默认生产入口）
        → server/app/app_factory.py  （唯一装配根）
```

> **AR03-P5 更新（2026-11-23）**：默认生产启动链 **不再经过**
> `server/backend_api.py`。`run_app.py` 直接
> `from server.app import create_app`，并直接调用
> `server.services.discard.recover_discard_cycle()`，因此生产启动
> **不依赖** legacy 薄别名。
>
> `python server/backend_api.py` 仍与 `run_app.py` **完全等价**
> （url_map 逐条一致，由 `tests/characterize/test_legacy_route_full_parity.py`
> 断言），但它 **只是兼容别名**，不是默认入口。
> `scripts/launch_server.py::select_entrypoint` 的 `legacy` 分支在
> `main()` 中 **fail closed** 拒绝启动。

### 1.3 唯一装配根

```python
from server.app.app_factory import create_app
app = create_app()
```

`create_app()` 负责：配置解析 → `init_extensions` → Schema 初始化 →
注册 **14 个真 Blueprint** → 自由任务 **受保护 opt-in** → app 级 `/api/health`。

---

## 2. P3 新增后端能力时的落位规则（硬约束）

| 层 | 允许 | 禁止 |
|---|---|---|
| `server/blueprints/*_bp.py` | 解析 request、调 service、`jsonify` 响应 | **禁止** 写 SQL、**禁止** 自己开连接 |
| `server/services/*` | 业务规则、事务边界、跨 repo 协调 | **禁止** 写 SQL |
| `server/repositories/*_repo.py` | 写 SQL | **禁止** 自行开连接（必须接收显式 `conn`）、**禁止** 读进程级全局 |
| `server/schema/*` | DDL、`ensure_*` | `ensure_all` 之外不得自建编排入口 |

**绝对禁止**（有机械断言锁定）：

1. import `server.backend_api`；
2. import `server.app.legacy_compat`；
3. 在 Blueprint / Service 层直接写 SQL；
4. 在 Repository 层调用 `sqlite3.connect` 自开连接；
5. 引入进程级可变全局（如路径单例）；
6. 绕过 `create_app()` 造 app。

> **机械断言位置**：
> `tests/characterize/test_static_route_inventory.py`（`legacy_compat` 不可 import、
> `backend_api` 零路由）、
> `tests/characterize/test_schema_authority.py`（`backend_api` 零 DDL/DML）、
> `tests/characterize/test_db_path_isolation.py`（双 Factory 实例隔离）。

---

## 3. P3 会不会踩到的「后端语义细节」

### 3.1 抽卡（gacha）

- 权重算法 **完全未改** —— Golden **100250 组 `max_diff = 0`**；
- 「系数越大越难被抽中」等产品语义 **待用户裁决**（P1 遗留，P2 未裁决）；
- `available_time`（1–480 分钟）时间匹配能力保留；
- 连抽 `POST /api/gacha/multi-draw` 保留；
- 换牌理由白名单与前端单选框一致。

### 3.2 自由任务（free task）

- `free_task_bp` 是 **受保护预览**，**默认不注册**；
- 需要时 **显式 opt-in**（`FREE_TASK_PREVIEW_CONFIG_KEY`）；
- 事件表由 `FreeTaskEventStore` **自管**（**不**在 `server/schema` 的 14 张集中表内）；
- P2 **未改动** 该域的任何行为。

### 3.3 Agent Policy 闸门

- **官方安全启动链强制开启**服务端闸门（`launch_server.py` 注入
  `SAL_ENFORCE_AGENT_POLICY=1`）；
- Factory 默认关闭 **仅在绕过启动器直接跑 `create_app()` 时**成立；
- 闸门逻辑、423 状态码、路径前缀集合、Publisher 语义 —— P2 **一行未改**。

### 3.4 Schema 边界

**14 张集中 Schema 表 + 1 张 `FreeTaskEventStore` 自管表**。
`server/schema/__init__.py::ensure_all` 是 **唯一编排入口**。

---

## 4. P3 的验证入口

| 目的 | 命令 |
|---|---|
| 后端全量回归 | `python -m pytest tests/characterize -q` |
| 抽卡算法等价 | `python scripts/phase2_gacha_golden.py` |
| P0 契约 | `python scripts/verify_p0_cleanup.py` |
| 前端模块边界 | `node scripts/check_module_imports.js` |
| 浏览器 E2E（**隔离**） | `$env:PYTHON="$PWD\.venv\Scripts\python.exe"; node scripts/run_e2e_isolated.js` |
| 路由清单（机读） | `python scripts/route_inventory.py` |
| Legacy 差异探针 | `python scripts/legacy_divergence_probe.py` |
| 三层映射（机读） | `python scripts/_build_p2_migration_map.py` |

> **Windows 注意**：`python` 在 PATH 上可能指向 Windows Store 别名，
> 隔离 E2E 必须显式设置 `$env:PYTHON`。

**P3 新增功能后，建议至少跑**：`pytest tests/characterize -q` +
`node scripts/check_module_imports.js` + `node scripts/run_e2e_isolated.js`。

---

## 5. 安全边界（P3 必须继承）

### 5.1 生产数据红线

以下路径是 **项目红线**，**任何** 自动化编辑会话都不得修改：

- `src/notes/**` —— Obsidian 知识库（本地用户数据，不入 Git）；
- `data/task_publisher.db` + `.db-wal` + `.db-shm` —— 活动数据库家族；
- `config/config.json` —— 运行时配置（含密钥与路径）。

### 5.2 隔离验证

`scripts/run_e2e_isolated.js` 提供 **三重** 零触碰证明：

1. **runner 侧 fs 守卫** —— 访问受保护路径 **立即抛错**（触碰即失败）；
2. **server 侧 `sys.addaudithook`** —— 记录全部 `sqlite3.connect` 与文件打开事件；
3. **合成根自证** —— 合成服务器启动时断言 DB 路径 / notes root / CWD 均在 `%TEMP%` 合成根，否则 **拒绝启动**。

P3 若新增测试，**必须** 走 `tests/characterize/sandbox_env.py` 的合成根，
**不得** 直连生产 DB。

---

## 6. 未决项（移交 P3 / P5 / 用户裁决）

| # | 项 | 归属 | 说明 |
|---|---|---|---|
| 1 | `/api/health` 响应形状是否与 legacy 统一 | **P5** | legacy `{"status":"healthy"}` vs Factory `{"phase":1,"status":"ok"}` |
| 2 | legacy 换牌路径历史缺陷的 **数据修复** | **单独评估** | legacy 曾把失败的换牌记成拒绝（`task_rejection_log` / `refusal_count` 虚增）。**P2 不触碰生产数据**，修复需独立授权 |
| 3 | Gacha 策略系数产品语义 | **用户裁决** | 保留现有实际行为与 Golden；语义歧义待用户明确 |
| 4 | dual-vault 布局契约 | 历史未决 | 不属 P2 |
| 5 | `server/app/legacy_compat.py` 物理删除 | ✅ **P5 已完成（归档）** | `[destructive-guard]` 拦截删除 → 改为 **归档** 到 `_archive/11_AR03_P5_一次性脚本/server/app/legacy_compat.py`。归档后为 **零路由 / 零 import / 零运行时引用**，且下游测试已改 **双形态**（断言不变量，而非"文件必须在原地"） |
| 6 | `server/backend_api.py` 文件归档 | ✅ **P5 已决（保留）** | 按计划保留兼容入口。**P5 收尾（2026-11-23）**确认最终形态：保留为薄别名 + 历史 import 路径兼容入口；**默认生产启动链已不再依赖它**（`run_app.py` 直接调用 `server.services.discard`），`launch_server.py` 的 legacy 分支 **fail closed** 拒绝启动 |
| 7 | `server/utils/{energy_calc,task_blocked,wiki_link}.py` 转发壳收敛 | ✅ **P5 已完成（归档）** | 三个转发壳已 **归档** 到 `_archive/11_AR03_P5_一次性脚本/server/utils/`；`server/**` 零 importer |
| 8 | `scripts/_probe_task_get_500.py` 临时诊断脚本清理 | **带外 Controller 操作** | Stage 8 定位 E2E 控制台 `500 /api/tasks/<id>` 用；诊断已结案（**并发竞态**，非分层回归）。`[destructive-guard]` 拦截删除。**增量审计纠错见 §6.1** |

### 6.1 增量审计纠错（2026-11-22，AR03-P4 独立审查）

> 本小节为 **新增** 记录，**不追溯修改**上方第 8 行的历史正文。
> 权威口径见 `docs/P4_AUDIT_CORRECTIONS_20261122.md` §1.1。

上表第 8 行的「并发竞态」结论，是 P2 Stage 8 针对 **一次具体事件** 得出的，
**仅对那一次事件成立**。

AR03-P3 与 AR03-P4 两轮隔离 E2E 又各观察到 **1 次** `/api/tasks/21` → HTTP 500
（**请求方法未被现有证据确定**）。这两次观察与 P2 的那次事件 **未经证据证明是同一问题**，
因此 **不得** 用 P2 的结论为其结案，**不得** 宣称已复现或未复现。
统一口径：**`/api/tasks/21` 出现一次 HTTP 500，请求方法未确定，根因未确认。**
CSS 迁移不触碰后端路由 → **非 P4 引入**。P5 记录为已知限制，**不结案**。

---

## 7. P1 独立验收状态（⚠️ 流程事项）

| 项 | 状态 |
|---|---|
| Stage 0 隔离器修复 | ✅ 本会话完成并自审（`docs/P1_ADDENDUM_20261121.md`） |
| P1 复验 | ✅ 全绿（命令 / 退出码见交付说明 §5.1） |
| 证据包 | ✅ `docs/P1_INDEPENDENT_ACCEPTANCE_EVIDENCE_20261121.md` |
| **独立验收会签** | ⏳ **`READY_FOR_INDEPENDENT_ACCEPTANCE` —— 外部待会签** |

按 P2 计划 §4.2 原文要求，本文档 **不** 把 P1 独立验收写成「已完成」。
该项是 **流程门禁的补签事项**，与 P2 代码交付物的技术状态无关
（P2 Stage 1–8 已按计划完成并全量验证通过）。

---

## 8. 一句话总结

> 后端已 **完全** 分层：14 个真 Blueprint（80 条路由）+ 24 个 Service + 14 个 Repository；
> 兼容桥已退役（0 转发）；legacy 已收口为 290 行薄别名；43 条 legacy 路由 **全部**
> 原生实现且行为等价（32 条逐字一致，8 条差异已逐条裁决留证）；
> 生产数据 **全程零触碰**；P3 可在 **HTTP 契约不变** 的前提下直接开始前端工作。
