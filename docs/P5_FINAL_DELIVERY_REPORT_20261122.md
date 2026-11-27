# AR03-P5 最终交付报告

> **里程碑**：AR03-P5 —— Legacy 最终收敛 + Schema 一致性 + 目录治理 + 最终交付
> **交付日期**：2026-11-23
> **口径权威**：本报告 + `docs/ARCHITECTURE.md`（当前架构）+ `docs/CURRENT_PROJECT_STATE.md`（当前状态）
> **归档索引**：`docs/ARCHIVE_INDEX.md`
> **目录治理明细**：`docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md`

---

## 1. 范围与 todo 对照表

原计划 `ar03-p5_legacy_schema_governance_df1dad98.plan.md` 的 8 个 todo：

| # | todo | 状态 | 证据 |
|---|---|---|---|
| 1 | `p4-closeout` | ✅ 已完成 | `docs/P4_AUDIT_CORRECTIONS_20261122.md`（4 项 P4 表述纠错） |
| 2 | `schema-gate` | ✅ 已完成 | `scripts/check_schema_consistency.py`（C1–C8）；`tests/characterize/test_schema_consistency_gate.py`（17 用例） |
| 3 | `health-unify` | ✅ 已完成 | `tests/characterize/test_health_contract.py`（8 用例）；`/api/health` → `{"phase":1,"status":"ok"}` |
| 4 | `legacy-converge` | ✅ 已完成（收尾批次补齐下游测试） | 兼容桥归档 + 6 个下游测试改双形态；本轮修复最后 2 个红测 |
| 5 | `reduced-motion` | ✅ 已完成 | `tests/e2e/reduced-motion-regression.spec.js`（9 用例，真实浏览器 `reducedMotion: 'reduce'`） |
| 6 | `scripts-archive` | ✅ 已完成 | 批次 11 建立；收尾批次再归档 8 个一次性脚本 + 6 项根目录临时产物 |
| 7 | `architecture-doc` | ✅ 已完成 | 旧快照归档至 `docs/architecture/2026-10-04_snapshot.md`；新 `docs/ARCHITECTURE.md`（284 行，5 张 Mermaid） |
| 8 | `final-delivery` | ✅ 已完成 | 本报告 + `docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md` + `docs/ARCHIVE_INDEX.md` |

### 1.1 收尾批次新发现并修复的 2 个回归

原计划的 todo 列表 **未覆盖** 这 2 项 —— 它们由 `server/app/legacy_compat.py`
归档引发，且都不在原计划列出的受影响测试子集内：

| # | 失败测试 | 症状 | 根因 | 修复 |
|---|---|---|---|---|
| R1 | `tests/characterize/test_free_task_blueprint.py::test_free_task_preview_is_wired_only_by_explicit_factory_opt_in` | `ModuleNotFoundError: No module named 'server.app.legacy_compat'` | 无条件 `monkeypatch.setattr("server.app.legacy_compat.register_legacy_compat", ...)` | 改为 **双形态**：可替换则替换；不可替换（已归档）则断言 `server/**` **零** AST 运行时引用。`legacy_calls` 的"零次调用"不变量依然成立且更强（模块根本不存在） |
| R2 | `tests/characterize/test_stage5_config_export.py::Stage5LayeringTests::test_compat_bridge_exact_routes_is_empty` | `FileNotFoundError: server/app/legacy_compat.py` | 无条件 `read_text()` 读取已归档文件 | 改为 **双形态**：文件在原位 → 断言 `EXACT_ROUTES == set()`；文件已归档 → 断言原位文件 **不存在** 且 `_archive/11_AR03_P5_一次性脚本/server/app/legacy_compat.py` **存在**（证明是"被归档"而非"被删除"） |

---

## 2. Schema 一致性门禁结论

**权威归属规则**（由 `scripts/check_schema_consistency.py` 机械强制，退出码 0 = 全绿）：

- **14 张集中式表** 的 DDL **只能**出现在 `server/schema/` 内，且 **只能**由
  `ensure_all()` 产出：

  `tasks` · `tags` · `task_tags` · `task_dependencies` · `gacha_records` ·
  `task_rejection_log` · `timer_sessions` · `daily_user_state` ·
  `state_assessments` · `user_schedule` · `daily_schedules` · `activities` ·
  `task_feedback_events` · `task_completion_feedback`

- **2 张 Store 自有表** 由各自的 Store 在构造时建表，`ensure_all()` **不**创建：

  | 表 | 拥有者 | 原因 |
  |---|---|---|
  | `free_task_events` | `FreeTaskEventStore`（`server/services/free_task_events.py`） | 追加式触发器 + 部分唯一索引语义，由拥有者自建才不被破坏 |
  | `free_task_session_ownership` | `SessionOwnershipStore`（`server/services/free_task_session_ownership.py`） | 会话归属原语，独立于集中式编排 |

**C1–C8 检查项**：

| 编号 | 检查 | 本轮结果 |
|---|---|---|
| C1 | `REQUIRED_TABLES` 完整性（14 张空库全产出） | PASS |
| C2 | 14+2 归属（两张专用表由各 Store 创建，`ensure_all` 不创建） | PASS |
| C3 | 域覆盖（tasks/gacha/timer/state/feedback 五域无遗漏无重复） | PASS |
| C4 | 未授权重复 DDL（AST 扫描 `server/**`，`CREATE TABLE` 须落在白名单内） | PASS |
| C5 | 幂等（`ensure_all()` 连跑两次 → 表/列/索引集合完全一致） | PASS |
| C6 | 空库可初始化（临时 SQLite 上 `ensure_all()` 成功） | PASS |
| C7 | 实际表集合 ⊇ 权威定义 | PASS |
| C8 | 数据保全（既有行不删、旧列不改） | PASS |

**门禁输出**：`PASS —— Schema 一致性全部通过（14 集中 + 2 专用 Store）。`（exit 0）

---

## 3. Health 契约

| 项 | 值 |
|---|---|
| 路由 | `GET /api/health` |
| 权威响应 | `{"status": "ok", "phase": 1}` —— **逐键不变** |
| 契约锁定 | `tests/characterize/test_health_contract.py`（8 用例） |
| 启动链依赖 | 只依赖 HTTP 200，**不解析** 响应体 → 统一形状无需改启动脚本 |
| 历史 oracle | legacy 的 `{"status":"healthy"}` 只存在于冻结 fixture `tests/fixtures/legacy_baseline.json`，活代码中 **无第二处** |

---

## 4. Legacy 收敛的双形态证据

`server/app/legacy_compat.py` 已 **归档** 到
`_archive/11_AR03_P5_一次性脚本/server/app/legacy_compat.py`。

### 4.1 不变量（归档前后都成立）

| 不变量 | 保留时 | 归档后 |
|---|---|---|
| 挂载路由数 | 0 | 0（模块不存在） |
| `server/**` 运行时引用 | 无 | 无（AST 扫描断言） |
| 副作用 | 无 | 无 |

### 4.2 双形态测试清单

归档不是删除，因此断言的是 **不变量** 而非"文件必须在原地"：

| 测试 | 归档前形态 | 归档后形态 |
|---|---|---|
| `test_free_task_factory_optin.py` | 替换 `register_legacy_compat`，断言零次调用 | 断言 `server/**` 零 AST 引用 |
| `test_free_task_blueprint.py` | 同上 | 同上（**本轮修复** R1） |
| `test_stage5_config_export.py` | 读文件断言 `EXACT_ROUTES == set()` | 断言原位不存在 + 归档副本存在（**本轮修复** R2） |
| `test_stage6_prompts_agent.py` / `test_factory_bootstrap.py` / `test_legacy_surface_inventory.py` | 已有双形态 | 已有双形态 |

---

## 5. Reduced-motion 证据

`tests/e2e/reduced-motion-regression.spec.js` —— **9 passed**，真实 Chromium
（`reducedMotion: 'reduce'` 置于 `use` 顶层），网络层全 mock，**不**启动 Flask、
**不**访问 `127.0.0.1:5000`、**不**触碰生产 DB / notes / config。

覆盖：

1. reduced-motion 上下文确实生效（自检）；
2. 动画态卡牌 `pointer-events` 恢复为 `auto`；
3. 六个动画态全部恢复；
4. `animation-duration` 被压缩到近 0；
5. `playCardAnim` 的 Promise 在 reduced-motion 下 resolve（不挂死）；
6. 抽卡流程：Promise resolve + **无重复提交**；
7. 拒绝流程：同样 resolve + **恰好一次**提交；
8. 弃牌流程：`pointer-events` 恢复 + **恰好一次**提交；
9. 连续两次 `playCardAnim` 各自独立 resolve（无串扰）。

实现口径：reduced-motion 下 **零** `animationend` 监听器；状态推进由 JS
`setTimeout` 状态机负责；`0.01ms` duration 保留派发能力而不把逻辑与 CSS 解耦。

---

## 6. 脚本归档分类

批次 `11_AR03_P5_一次性脚本` 的分类（详见
`_archive/11_AR03_P5_一次性脚本/ARCHIVE_NOTE.md`）：

| 类别 | 目录 | 内容 |
|---|---|---|
| A | `scripts/A_一次性探查_直接读写生产DB/` | 12 个直连生产 DB 的一次性探查脚本 |
| B | `scripts/B_一次性测试_打生产端口/` | 9 个打生产端口（5000）的测试脚本 |
| C | `scripts/C_一次性内容提取/` | 10 个内容提取脚本 |
| D | `scripts/D_一次性构建与迁移/` | 26 个构建 / 迁移期脚本 |
| E | `scripts/E_一次性调试探针/` | 3 个调试探针 |
| F | `scripts/F_迁移期迁移器/` | 2 个迁移期生成器（产物已冻结） |
| G | `scripts/G_用户运维脚本/` | 2 个指向已失效 `.\笔记` 目录的运维脚本 |

**收尾批次新增归档**（8 个脚本 + 6 项根目录临时产物）见
`docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md` §3。

---

## 7. 目录治理清单

| 项 | 处置 |
|---|---|
| `scripts/` P5 scratch（3 个） | → 批次 11 `scripts/` |
| `scripts/` 迁移期生成器（2 个） | → 批次 11 `scripts/F_迁移期迁移器/` |
| `scripts/` 失效运维脚本（2 个） | → 批次 11 `scripts/G_用户运维脚本/` |
| `.p5_script_refs.json` / `.git_p5_status.txt` / `_metrics.txt` / `_pip.log` | → 批次 11 `_temp_artifacts/root/` + `.gitignore` |
| `.tmp_p1check/`（3 文件） | → 批次 11 `_temp_artifacts/root/.tmp_p1check/` |
| `tests/phase2_gacha_golden_*.log` | 由 `phase2_gacha_golden.py` **每次运行重新生成** → `.gitignore`（归档副本保留在批次 11） |
| `docs/ARCHITECTURE.md`（旧） | → `docs/architecture/2026-10-04_snapshot.md` |
| `server/app/legacy_compat.py` | → 批次 11 `server/app/` |
| `server/config.py` / `server/utils/` | → 批次 11 `server/` |

**明确保留原位**（附理由）：

| 项 | 理由 |
|---|---|
| `scripts/main.py` | **被 3 个活的 characterization 测试断言**（`test_desktop_archive_integrity.py`）。归档它会让这些测试失效 |
| `scripts/legacy_divergence_probe.py` | 被 `test_legacy_divergence_ledger.py` import |
| `scripts/route_inventory.py` / `golden_snapshot.py` | 静态路由清单 / 黄金 HTTP 快照 oracle，被 characterization 测试 import |
| `scripts/check_*.js` / `check_schema_consistency.py` / `verify_p0_cleanup.py` / `phase2_gacha_golden.py` / `run_e2e_isolated.js` | 活的门禁与隔离 E2E 入口 |
| `server/backend_api.py` | 薄别名 + 历史 import 路径兼容入口。默认生产链 **已不依赖** 它 |

---

## 8. ARCHITECTURE 重写说明

| 项 | 旧（2026-10-04 快照） | 新（2026-11-23） |
|---|---|---|
| 入口 | `server/backend_api.py`（~3395 行单体，默认入口） | `run_app.py` → `server/app/app_factory.py::create_app()` |
| 路由 | ~42 条 legacy inline `@app.route` + 5 个 BP | **14 BP / 82 条路由**（80 API + health + static） |
| 表 | 未治理 | **14 集中 + 2 Store 自有**，机械门禁强制 |
| Mermaid | 0 张 | **5 张**（启动链 / 后端分层 / 装配顺序 / schema 归属 / 前端装配） |
| 行数 | 424 | 284 |

旧快照 **保留** 在 `docs/architecture/2026-10-04_snapshot.md`，仅供追溯；
其中的 "42 live @app.route"、"backend_api 是默认入口"、"Stage 7 起…P5 再做最终退役"
等表述 **已全部失效**，不得再作为事实引用。

---

## 9. 验收证据汇总

全部在 **2026-11-23** 于本工作区实测。

### 9.1 机械门禁（全部 exit 0）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `node scripts/check_css_architecture.js` | `PASS —— 全部门禁通过`（exit 0） |
| 2 | `node scripts/check_layout_utility_conflicts.js` | `冲突数: 0` / `PASS`（exit 0） |
| 3 | `node scripts/check_module_imports.js` | `通过：模块边界无违规`（exit 0） |
| 4 | `python scripts/check_schema_consistency.py` | `PASS —— Schema 一致性全部通过（14 集中 + 2 专用 Store）`（exit 0） |
| 5 | `python scripts/verify_p0_cleanup.py` | `ALL ASSERTIONS PASSED`（exit 0） |
| 6 | `python scripts/phase2_gacha_golden.py` | `Total: pass=100250 fail=0 max_diff=0.000e+00` / `RESULT: OK`（exit 0） |

### 9.2 Characterization

```
pytest tests/characterize -q
→ 1738 passed, 12 skipped, 442 subtests passed in 262.91s
```

**零失败。** 修复前为 `1736 passed, 2 failed, 12 skipped`。

### 9.3 Reduced-motion E2E

```
npx playwright test --config=tests/e2e/playwright.reduced-motion.config.js
→ 9 passed (6.8s)   exit 0
```

### 9.4 隔离 E2E（36/36）

```
$env:PYTHON="$PWD\.venv\Scripts\python.exe"
node scripts/run_e2e_isolated.js
→ 测试结果: 36 通过, 0 失败
→ [run_e2e_isolated] 审计记录数 = 3806 / 3810 / 3819（三次运行实测值）
→ [run_e2e_isolated] ✅ 合成服务器未触碰任何生产受保护路径
→ [run_e2e_isolated] ✅ 生产数据 fs 守卫全程未被触发（未读取任何生产文件）
→ [run_e2e_isolated] e2e-manual.js 退出码 = 0（0 = 全部通过）
```

> **注**：审计事件数在 3806–3819 间浮动，随合成环境内的请求条数变化，
> **不是**契约。契约是"退出码 0 + `36 通过, 0 失败` + 生产受保护路径
> **0** 次触碰"。
>
> **注**：本 runner 需要 `PYTHON` 环境变量指向 venv 解释器（默认取 `python`）。
> 未设置时子进程以 `code=9009` 退出 —— 这不是产品缺陷，但调用方必须知道。

### 9.5 已知限制（**不结案**）

`/api/tasks/21` 出现 **1 次 HTTP 500**，请求方法未确定，根因未确认。
按 `docs/P4_AUDIT_CORRECTIONS_20261122.md` §"与 P2 历史诊断的区分"：
P2 / Stage 8 的 `_probe_task_get_500.py` 结论针对 **另一次事件**，不能据此
断言同源或不同源。本项 **登记为已知限制，不结案**。

---

## 10. 遗留项

| # | 项 | 状态 |
|---|---|---|
| 1 | `/api/tasks/21` 的 1 次 HTTP 500 | **已知限制，未结案**（见 §9.5） |
| 2 | 自由任务受保护预览的 **生产阻断项** | 宽松全局 CORS、无 CSRF、无真实认证 / 会话 / 速率限制、无数据留存策略 → **不允许生产部署**。本轮 **未** 触碰 |
| 3 | `scripts/run_e2e_isolated.js` 的 `PYTHON` 默认值 | 仍默认 `python`（PATH 依赖）。可改为自动探测 `.venv`，但属运行时行为变更，本轮 **未** 触碰（超出 P5 范围） |
| 4 | 前端 `app.js`（2685 行 classic 全局） | 仍是 UI 主体；`modules/` 只接管了任务编辑器与抽卡 owner。剩余迁移不在 P5 范围 |
| 5 | 工作区未提交改动 | 保持原样，**未** 提交（遵循计划 §3） |

---

## 11. 数据红线声明

本轮全部操作 **零触碰** 以下路径：

- `src/notes/**` —— Obsidian 知识库（本地用户数据）
- `data/task_publisher.db`（+ `-wal` / `-shm`）
- `config/config.json` —— 含密钥与路径的运行时配置

隔离保障：

- characterization 全部走 `tests/characterize/sandbox_env.py` 合成根
  （`%TEMP%` 下），`materialize()` 带 reparse-point 防护；
- E2E 全部走 `scripts/run_e2e_isolated.js` —— 合成 Factory（随机端口 +
  `%TEMP%` 合成根）+ **事前** 生产数据 fs 守卫（阻断 `data/**`、`config/**`、
  `src/notes/**`）+ Python 审计钩子；
- 本轮对生产路径的读取 **仅限** `config/config.json` 的 **存在性** 由既有
  测试夹具处理，**未**发生任何写入。

归档动作全部是 **移动**（move），不涉及任何数据文件。

---

## 12. 交接

| 后续 | 输入 |
|---|---|
| Controller | 本报告 + `docs/ARCHIVE_INDEX.md` + `docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md` |
| 下一阶段工程 | `docs/ARCHITECTURE.md`（当前架构权威） |
| 当前状态 / 基线 | `docs/CURRENT_PROJECT_STATE.md` 顶部增量段 |

### 12.1 文档索引变更

- 新建：`docs/P5_FINAL_DELIVERY_REPORT_20261122.md`（本文件）
- 新建：`docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md`
- 新建：`docs/ARCHIVE_INDEX.md`
- 新建：`docs/architecture/2026-10-04_snapshot.md`
- 重写：`docs/ARCHITECTURE.md`
- 更新：`docs/README.md`（导航）
- 更新：`docs/CURRENT_PROJECT_STATE.md`（顶部增量段）
- 更新：`docs/deliverables/P2_HANDOFF.md`（§1.2 启动链 → `run_app.py`；§6 遗留表第 5/6/7 行标记 P5 已完成）
- 更新：`server/backend_api.py`（docstring 标注 P5 退役定位）
- 更新：`README.md`（scripts/ 与 _archive/ 目录树）
- 更新：`.gitignore`（P5 临时产物）
- 更新：`_archive/11_AR03_P5_一次性脚本/ARCHIVE_NOTE.md`（收尾批次）

### 12.2 悬空引用归零

本报告与 `docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md` 建立后，
原先 7 处指向 **不存在** 文件的引用全部归位：

| 引用方 | 原引用 |
|---|---|
| `docs/CURRENT_PROJECT_STATE.md` | `docs/P5_FINAL_DELIVERY_REPORT_20261122.md` |
| `docs/P2_FINAL_CLOSURE_20261121.md` | 同上 |
| `docs/P4_AUDIT_CORRECTIONS_20261122.md`（2 处） | 同上 |
| `docs/P4_CSS_THEME_DELIVERY_20261122.md`（2 处） | 同上 |
| `docs/P4_CSS_THEME_DELIVERY_20261122.md`（§8.3） | `docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md` |
