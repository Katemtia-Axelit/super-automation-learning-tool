# AR03-P5 归档说明 —— 一次性脚本与 Legacy 退役模块

- **归档日期**：2026-11-22
- **归档批次**：AR03-P5
- **归档目录**：`_archive/11_AR03_P5_一次性脚本/`
- **归档原则**：**不删除，只归档**。Cursor 的破坏性操作守卫
  （`destructive-guard`）拒绝在会话内永久删除工作区文件；
  本目录以 **移动** 的方式保留全部历史资产，并附本说明。

---

## 1. 归档内容总览

| # | 归档项 | 原路径 | 类型 | 归档理由 | 当前替代 |
|---|---|---|---|---|---|
| 1 | `server/app/legacy_compat.py` | `server/app/legacy_compat.py` | **Legacy 墓碑模块** | Stage 7 起零路由 / 零 import / 零副作用，已 **彻底退役** | 无（功能已完全迁到真 Blueprint） |
| 2 | `server/config.py` | `server/config.py` | **零 importer 薄 re-export** | 唯一权威在 `server/app/config.py`；本文件只是历史 import 路径兼容层 | `server/app/config.py` |
| 3 | `server/utils/`（3 文件 + `__init__.py`） | `server/utils/` | **零 importer 转发壳** | 三个门面全部委托给真正的 owner，自身不含实现 | `server/services/state.py`<br>`server/repositories/task_repo.py`<br>`server/services/energy.py` |
| 4 | `tests/e2e.spec.js` | `tests/e2e.spec.js` | **一次性 Playwright spec** | 硬编码 `baseURL = http://127.0.0.1:5000`（**生产端口**）；是活服务器 spec，误纳入自动发现会打生产实例 | `tests/e2e/` 下的隔离 spec + `tests/e2e-manual.js` |
| 5 | `tests/characterize/sandbox_builder.py` | `tests/characterize/sandbox_builder.py` | **一次性沙箱脚手架** | **硬编码绝对路径** `D:\Axelit\.工作\trae\超级自动化学习工具`；已被 `sandbox_env.py` 取代 | `tests/characterize/sandbox_env.py` |
| 6 | `tests/characterize/debug2.py` | `tests/characterize/debug2.py` | **调试脚本** | 仅引用 `sandbox_builder`，无测试价值 | 无 |
| 7 | `tests/characterize/debug_factory.py` | `tests/characterize/debug_factory.py` | **调试脚本** | 仅引用 `sandbox_builder`，无测试价值 | 无 |
| 8 | `static/test.js` | `static/test.js` | **死脚本** | 引用 `#testBanner` —— 该元素 **已从 `src/index.html` 移除**（grep 零命中）→ 运行时必然抛 `TypeError` | 无 |
| 9 | `tests/characterize/_addendum.py` / `_new_init.py` / `_write_schema.py` / `_test.py` | `tests/characterize/_*.py` | **一次性脚手架** | 文件名 **不以 `test_` 开头** → pytest **默认不收集**；逐个检查无被其它测试 import | `tests/characterize/sandbox_env.py` |
| 10 | `tests/e2e/_debug_bootstrap.spec.js` | `tests/e2e/_debug_bootstrap.spec.js` | **无断言的诊断脚本** | 只有 `console.log`，**零断言**；无任何 Playwright config 引用它 | `tests/e2e/bootstrap-first-card.spec.js`（有独立 config，含真断言） |
| 11 | `scripts/migrate_css_split.js` / `scripts/rewrite_index_head.js` | `scripts/` | **一次性 CSS 迁移工具** | AR03-P4 的 `<style>` 拆分工具；**零** 运行时引用 | 无（迁移已完成；产物是 `static/css/` 6 文件） |
| 12 | `scripts/_p5_archive_scripts.py` / `_p5_classify_scripts.py` / `_p5_report_scripts.py` | `scripts/` | **P5 自身 scratch 工具** | 分级器 / 归档器 / 报告器；一次性使用，已产出本说明与 `docs/ARCHIVE_INDEX.md` | 无 |
| 13 | `scripts/_build_p2_migration_map.py` | `scripts/` | **迁移期迁移器（F 类）** | P2 三层映射生成器；产物 `tests/fixtures/p2_migration_map.json` **已冻结**并被 `test_static_route_inventory.py` 等引用，生成器本身零运行时引用 | 无（产物已冻结） |
| 14 | `scripts/_freeze_legacy_baseline.py` | `scripts/` | **迁移期迁移器（F 类）** | legacy 基线冻结器；产物 `tests/fixtures/legacy_baseline.json` **已冻结**并被 `test_health_contract.py` / `test_legacy_divergence_ledger.py` 引用 | 无（产物已冻结） |
| 15 | `scripts/批量处理笔记.ps1` / `remove_note_links.ps1` | `scripts/` | **用户运维脚本（G 类）** | 面向旧目录 `.\笔记` 的批量笔记处理；该目录 **已不存在**（现为 `src/notes/**`，且属红线），脚本指向失效路径 | 无 |

---

## 2. 归档前的核实（逐项，**不凭命名删除**）

### 2.1 `tests/e2e.spec.js`

| 核实项 | 结论 |
|---|---|
| Playwright 自动发现 | **不在** `tests/e2e/playwright.config.js`（`testDir: './'` = `tests/e2e/`）的发现范围内 |
| 目标地址 | `const BASE_URL = 'http://127.0.0.1:5000'` —— **生产端口**，是活服务器 spec |
| 历史价值 | `docs/ENV_INVESTIGATION_REPORT_2026-10-03.md` 记载其用途；`docs/WORK_LOG.md.todo2-result` 有执行记录 |
| 处置 | **归档**（不删除）—— 保留历史价值，同时消除「误纳入自动发现打生产实例」的风险 |

### 2.2 `tests/characterize/sandbox_builder.py`

| 核实项 | 结论 |
|---|---|
| 硬编码路径 | `PROJECT_ROOT = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具')` —— **换机即失效** |
| 引用者 | 仅 `tests/characterize/debug2.py` 与 `debug_factory.py`（两个调试脚手架） |
| 替代物 | `tests/characterize/sandbox_env.py::materialize/seed/available_port` —— **无硬编码路径**、带 reparse-point 防护 |
| 处置 | **连同两个引用者一起归档** |

### 2.3 `tests/characterize/_*.py`

| 文件 | 核实 | 处置 |
|---|---|---|
| `_addendum.py` / `_new_init.py` / `_write_schema.py` / `_test.py` | 文件名 **不以 `test_` 开头** → pytest **默认不收集**；逐个检查无被其它测试 import | **归档**（临时脚手架） |

### 2.4 `static/test.js`

| 核实项 | 结论 |
|---|---|
| 运行时依赖 | `document.getElementById('testBanner')` —— `#testBanner` 已从 `src/index.html` 移除 → **必然抛 TypeError** |
| 引用者 | `src/index.html` **零命中**（不再 `<script>` 引入） |
| 文档记载 | `README.md`（行 54 区）与多份 research 文档仍记载它 → 归档后需同步更新 `README.md` |
| 历史判定 | `docs/RESEARCH_MODULARIZATION_CURRENT_2026-08-16.md` §1.5.2 早已判为「**死脚本** —— 直接删」；本批次按「不删除，只归档」处理 |

### 2.5 `tests/e2e/_debug_bootstrap.spec.js`

| 核实项 | 结论 |
|---|---|
| 断言 | **零** —— 整个用例只有 `console.log` / `page.evaluate` 探针 |
| Playwright config 引用 | **无** —— 没有任何 `playwright.*.config.js` 的 `testMatch` 命中它 |
| 替代物 | `tests/e2e/bootstrap-first-card.spec.js`（`playwright.bootstrap-safe.config.js` 驱动，含真断言） |

### 2.6 **明确保留** 的 `tests/e2e/debug.spec.js`

> ⚠️ 名字带 "debug"，但 **不是** 一次性脚本 —— **不得** 归档。

| 核实项 | 结论 |
|---|---|
| Playwright config 引用 | **有** —— `playwright.isolated.config.js` 的 `testMatch` 显式包含 `debug\.spec\.js` |
| 隔离性 | **完全隔离** —— `page.setContent` + `page.route` 全 mock，**不** 连生产服务器（config 注释明确 "Do NOT launch the project's live Flask server"） |
| 处置 | **保留原位** |

> 这正是「**不凭命名删除**」的一个实例：若按 "debug*" 通配符清理，会误删一个被 config 显式引用的活测试资产。

---

## 3. Legacy 退役模块的 **不变量**（归档前后都成立）

### 3.1 `server/app/legacy_compat.py`

| 不变量 | 保留时 | 归档后 |
|---|---|---|
| 挂载路由数 | **0** | **0**（模块不存在） |
| import `server.backend_api` | **无** | **无** |
| `app.config["_compat_route_count"]` | **0** | **键不存在**（`None`） |
| `server/**` 运行时引用 | **无** | **无** |
| 可审计性 | 文件在原位 | 归档件在本目录 + 本说明 |

> **原则**：**归档是交付目标，不是测试目标**。
> 测试断言的是 **不变量**（零路由、零引用、零副作用），而 **不是**
> 「文件必须在原地」。
> 因此 `tests/characterize/test_stage6_prompts_agent.py`、
> `test_factory_bootstrap.py`、`test_free_task_factory_optin.py`
> 与 `test_legacy_surface_inventory.py` 均已改为 **双形态分支**。

### 3.2 `server/config.py`

- **唯一配置权威** 始终是 `server/app/config.py`；
- 归档后 `server/**` **零** `import server.config`；
- `load_config()` 的派生键（`_project_root` / `_static_dir` / `_db_path` /
  `_notes_dir`）语义 **不变**（由权威方提供）。

### 3.3 `server/utils/`

三个门面 **全部** 是纯转发（无自身实现）：

| 门面 | 真正的 owner |
|---|---|
| `energy_calc.calculate_state_scores` | `server/services/state.calculate_state_scores` |
| `task_blocked.format_blocked_reason` | `server.repositories.task_repo.blocked_message` |
| `wiki_link.*` | `server/services/wiki_link`（服务层） |

`server/**` **零** importer。

---

## 4. 目录结构

```
_archive/11_AR03_P5_一次性脚本/
├── ARCHIVE_NOTE.md                  ← 本文件
├── server/
│   ├── config.py                    ← 原 server/config.py（零 importer 薄 re-export）
│   ├── app/
│   │   └── legacy_compat.py         ← 原 server/app/legacy_compat.py（墓碑）
│   └── utils/                       ← 原 server/utils/（3 个转发壳 + __init__.py）
├── scripts/
│   ├── _p5_archive_scripts.py       ← P5 归档器（scratch）
│   ├── _p5_classify_scripts.py      ← P5 分级器（scratch）
│   ├── _p5_report_scripts.py        ← P5 报告器（scratch）
│   ├── migrate_css_split.js         ← P4 一次性 CSS 迁移工具
│   ├── rewrite_index_head.js        ← P4 一次性 CSS 迁移工具
│   ├── A_一次性探查_直接读写生产DB/
│   ├── B_一次性测试_打生产端口/
│   ├── C_一次性内容提取/
│   ├── D_一次性构建与迁移/
│   ├── E_一次性调试探针/
│   ├── F_迁移期迁移器/
│   │   ├── _build_p2_migration_map.py
│   │   └── _freeze_legacy_baseline.py
│   └── G_用户运维脚本/
│       ├── 批量处理笔记.ps1
│       └── remove_note_links.ps1
├── tests/
│   ├── e2e.spec.js                  ← 原 tests/e2e.spec.js（活服务器 spec）
│   └── characterize/
│       ├── sandbox_builder.py       ← 原（硬编码绝对路径）
│       ├── debug2.py                ← 原（调试脚本）
│       └── debug_factory.py         ← 原（调试脚本）
├── static/
│   └── test.js                      ← 原 static/test.js（死脚本）
├── p5_diagnostics/                  ← P5 reduced-motion 诊断探针
└── _temp_artifacts/                 ← 日志 / 探针 / 一次性生成物
    ├── root/                        ← 项目根临时物（含 P5 自身产物）
    ├── run/                         ← .run/ 陈旧日志
    ├── tests/                       ← tests/ 下的日志与探针
    ├── tests/e2e/                   ← tests/e2e/ 下的 .tmp_* 探针
    ├── tests/characterize/          ← tests/characterize/ 下的 _lt_*.log
    └── TEMP_dir/                    ← 误建的 %TEMP% 目录
```

### 4.1 P5 收尾批次（2026-11-23）新增的归档项

除上表 1–11 项外，AR03-P5 **收尾批次** 又归档了 4 组（表 12–15）与
一批根目录临时产物：

| 归档项 | 原路径 | 去向 |
|---|---|---|
| `.p5_script_refs.json` | 项目根 | `_temp_artifacts/root/` |
| `.git_p5_status.txt` | 项目根 | `_temp_artifacts/root/` |
| `_metrics.txt` | 项目根 | `_temp_artifacts/root/` |
| `_pip.log`（0 字节） | 项目根 | `_temp_artifacts/root/` |
| `.tmp_p1check/`（3 文件） | 项目根 | `_temp_artifacts/root/.tmp_p1check/` |
| `tests/phase2_gacha_golden_2026-08-16.log` | `tests/` | `_temp_artifacts/tests/` |

> 这些全部是 **机器生成物 / 一次性探针**，无参考价值。P5 自身产出的
> **结论** 落在 `docs/P5_FINAL_DELIVERY_REPORT_20261122.md` 与
> `docs/ARCHIVE_INDEX.md`，而非这些原始中间物。

---

## 5. 未归档项（保留原位，附理由）

| 项 | 理由 |
|---|---|
| `server/backend_api.py` | **薄别名**，保留为历史 import 路径兼容入口（`create_app()` 委托 + PEP 562 再导出）。生产启动链 **已不再** 依赖它（`run_app.py` 直接调用 `server.services.discard`）。按计划保留兼容入口，不物理删除。 |
| `server/extensions.py` | **真实 owner**（共享单例扩展层：`get_db_path` / `init_extensions` / `make_request_conn`）。**不是** legacy 兼容层。 |
| `server/app/legacy_compat.py` 之外的 `server/app/*` | 全部是当前装配根的活跃组件。 |
| `tests/e2e/` 下的正式 spec | 隔离运行（合成根），是 **活** 测试资产。 |
| `scripts/migrate_css_split.js` / `scripts/rewrite_index_head.js` | 一次性 CSS 迁移工具 —— 见下节。 |
| `scripts/main.py` | **桌面端 fail-closed 路标**。**被 3 个活的 characterization 测试断言**（`test_desktop_archive_integrity.py`：`test_main_py_does_not_unconditionally_import_the_removed_path` / `test_main_py_exits_non_zero_with_a_readable_message` / `test_no_runtime_entry_references_the_removed_package`）—— 归档它会让这些测试失效。 |
| `scripts/legacy_baseline.py` | 一次性采集器；产物已冻结，采集器本身零运行时引用。 |
| `scripts/legacy_divergence_probe.py` | **被 `test_legacy_divergence_ledger.py` import** —— 必须保留原位。 |
| `scripts/route_inventory.py` / `golden_snapshot.py` | 静态路由清单 / 黄金 HTTP 快照 oracle —— 被 characterization 测试 import。 |
| `scripts/verify_p0_cleanup.py` / `phase2_gacha_golden.py` | 活的机械门禁与 golden 回归。 |
| `scripts/check_*.js` / `check_schema_consistency.py` / `run_e2e_isolated.js` | 活的门禁与隔离 E2E 入口。 |
| `scripts/agent_policy_publisher.py` / `export_tasks_for_ai.py` / `validate_task_patch.py` | 长期保留的协作工具。 |

### 5.1 CSS 迁移工具

`scripts/migrate_css_split.js` 与 `scripts/rewrite_index_head.js` 是
AR03-P4 的 **一次性** 迁移工具（把 `src/index.html` 的 3 段内联 `<style>`
拆成 6 个 `static/css/` 文件）。它们 **非** 运行时依赖。

处置：随本批次 **归档**，理由与替代工具见上表。

---

## 6. 临时产物清理（可安全清理的类别）

本类全部是 **日志 / 机器生成物 / 一次性探针**，无参考价值但也不必保留 ——
按「临时日志和确认无用的生成文件，可以清理」的原则处理。
由于破坏性操作守卫禁止 `Remove-Item`，本批次同样采用 **移动到归档** 的方式。

| 类别 | 数量 | 位置 |
|---|---|---|
| `.tmp_*`（CSS 块 / VR 日志 / 探针 / HTML 快照 / Python 补丁） | 56 | 项目根 → `_temp_artifacts/root/` |
| `_lt_*.log` | 6 | 项目根 → `_temp_artifacts/root/` |
| `_lt_*.log` | 3 | `tests/characterize/` → `_temp_artifacts/tests/characterize/` |
| `tests/*.log` | 14 | `tests/` → `_temp_artifacts/tests/` |
| `tests/e2e/.tmp_*` | 2 | `tests/e2e/` → `_temp_artifacts/tests/e2e/` |
| `tests/{probe,diag,diff}_*` | 15 | `tests/` → `_temp_artifacts/tests/` |
| `.run/*.log`（陈旧） | 33 | `.run/` → `_temp_artifacts/run/` |
| `%TEMP%/`（误建目录） | 1 目录 | 项目根 → `_temp_artifacts/TEMP_dir/` |
| `_debug_regex.js` / `_probe_test.py` / `check_bundle*.js` / `server_out.txt` | 6 | 项目根 → `_temp_artifacts/root/` |

### **明确保留** 的 `.run/` 文件

| 文件 | 理由 |
|---|---|
| `server.log` | **当前运行** 所需（启动链写它） |
| `server.log.err` | **当前运行** 所需 |

---

## 7. 数据安全

本次归档 **不涉及** 任何数据文件：

- `src/notes/**` —— **零触碰**；
- `data/task_publisher.db{,-wal,-shm}` —— **零触碰**；
- `config/config.json` —— **零触碰**。

归档的全部是 **源码文件**（`.py` / `.js` / `.log` / `.txt`），且全部通过 **移动** 完成，
不涉及任何生产数据路径。
