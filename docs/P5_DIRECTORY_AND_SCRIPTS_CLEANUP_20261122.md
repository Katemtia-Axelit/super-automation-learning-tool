# AR03-P5 目录治理与脚本清理报告

> **日期**：2026-11-23（收尾批次）/ 2026-11-22（主体批次）
> **归档批次**：`_archive/11_AR03_P5_一次性脚本/`
> **归档索引**：`docs/ARCHIVE_INDEX.md`
> **交付报告**：`docs/P5_FINAL_DELIVERY_REPORT_20261122.md`

---

## 1. 治理原则

| 原则 | 说明 |
|---|---|
| **不删除，只归档** | Cursor 的破坏性操作守卫禁止会话内永久删除工作区文件；本轮全部处置为 **移动**，历史资产全部保留 |
| **不凭命名删除** | 逐项核实运行时引用与测试依赖后才决定处置。典型：`scripts/main.py` 名字像"废弃入口"，实则被 **3 个活的 characterization 测试** 断言 —— 归档它会让测试失效 |
| **不触碰红线** | `src/notes/**` / `data/task_publisher.db{,-wal,-shm}` / `config/config.json` **零触碰** |
| **归档是交付目标，不是测试目标** | 测试断言的是 **不变量**（零路由 / 零引用 / 零副作用），而非"文件必须在原地" |

---

## 2. 目录治理前后对照

| 目录 | 治理前 | 治理后 |
|---|---|---|
| `scripts/` | 38 个成员（含 20+ 个一次性 / 迁移期 / 运维脚本） | **31 个成员**，全部是 **活的** 门禁、启动器、oracle 或长期协作工具 |
| 项目根 | `.p5_script_refs.json` / `.git_p5_status.txt` / `_metrics.txt` / `_pip.log` / `.tmp_p1check/` 散落 | **清零**（移入归档 + 加入 `.gitignore`） |
| `tests/` | `phase2_gacha_golden_2026-08-16.log` 被当作产物提交 | 加入 `.gitignore`（脚本每次运行会重新生成） |
| `docs/` | `ARCHITECTURE.md` 是 2026-10-04 快照 | 旧快照 → `docs/architecture/2026-10-04_snapshot.md`；新文档按当前代码重写 |
| `_archive/` | 批次 01–10 | 批次 **01–11** + `src_tasks_legacy/` |

---

## 3. 收尾批次（2026-11-23）逐项处置

### 3.1 归档到 `scripts/` 顶层

| 文件 | 类型 | 理由 |
|---|---|---|
| `_p5_archive_scripts.py` | P5 归档器（scratch） | 一次性使用，已产出 `ARCHIVE_NOTE.md` 与本报告 |
| `_p5_classify_scripts.py` | P5 分级器（scratch） | 同上 |
| `_p5_report_scripts.py` | P5 报告器（scratch） | 同上 |

### 3.2 归档到 `scripts/F_迁移期迁移器/`

| 文件 | 产物 | 产物状态 |
|---|---|---|
| `_build_p2_migration_map.py` | `tests/fixtures/p2_migration_map.json` | **已冻结**，被 `test_static_route_inventory.py` 等引用；生成器零运行时引用 |
| `_freeze_legacy_baseline.py` | `tests/fixtures/legacy_baseline.json` | **已冻结**，被 `test_health_contract.py` / `test_legacy_divergence_ledger.py` 引用；生成器零运行时引用 |

### 3.3 归档到 `scripts/G_用户运维脚本/`

| 文件 | 理由 |
|---|---|
| `批量处理笔记.ps1` | 面向旧目录 `.\笔记` 做批量处理；该目录 **已不存在**（现为 `src/notes/**`，且属红线）→ 脚本指向 **失效路径** |
| `remove_note_links.ps1` | 同上 |

> 二者都是 **写** 笔记的脚本。在 `src/notes/**` 成为红线之后，把这类脚本留在
> `scripts/` 里是一个 **红线误触面**：脚本一旦被误执行就会改写用户知识库。
> 归档是更安全的处置。

### 3.4 根目录产物清理

| 产物 | 去向 | 性质 |
|---|---|---|
| `.p5_script_refs.json` | `_archive/.../_temp_artifacts/root/` | 机器生成物（27 KB 引用索引） |
| `.git_p5_status.txt` | `_archive/.../_temp_artifacts/root/` | 机器生成物（14 KB git 状态快照） |
| `_metrics.txt` | `_archive/.../_temp_artifacts/root/` | 机器生成物（代码行数统计） |
| `_pip.log` | `_archive/.../_temp_artifacts/root/` | 机器生成物（0 字节） |
| `.tmp_p1check/`（3 文件） | `_archive/.../_temp_artifacts/root/.tmp_p1check/` | 临时 diff / 暂存副本 |
| `tests/phase2_gacha_golden_2026-08-16.log` | `.gitignore` + 归档副本保留 | **脚本每次运行重新生成** 的日志，不是源资产 |

同时在 `.gitignore` 追加：

```
tests/phase2_gacha_golden_*.log
.p5_script_refs.json
.git_p5_status.txt
_metrics.txt
_pip.log
.tmp_p1check/
```

> 之所以对 `phase2_gacha_golden_*.log` 用 **gitignore** 而非单纯归档：
> `scripts/phase2_gacha_golden.py` **每次运行都会重新写** 这个文件。归档后
> 它会立刻重新出现 —— 忽略规则才是可持续的处置。

### 3.5 文档与代码口径修正

| 文件 | 修正 |
|---|---|
| `docs/deliverables/P2_HANDOFF.md` §1.2 | 启动链 `server/backend_api.py` → `run_app.py`；补注 legacy 分支 fail closed |
| `server/backend_api.py` docstring | "P5 再做最终退役与文件归档" → 记录 **P5 已执行** 且最终形态是"保留为兼容别名" |
| `README.md` | `scripts/` 目录树换成现行 31 个活成员；`_archive/` 补 `11_AR03_P5_一次性脚本/` 与 `src_tasks_legacy/`；`app.js` 行数 2711 → 2685；新增 `app.entry.js` |
| `_archive/11_AR03_P5_一次性脚本/ARCHIVE_NOTE.md` | 归档总览扩到 15 项；新增 §4.1 收尾批次；"未归档项"表补齐保留理由 |

### 3.6 `.tmp_*` 残留逐项核实

`docs/P4_CSS_THEME_DELIVERY_20261122.md` §8.3 提到一批 `.tmp_*` /
`tests/e2e/.tmp_*` 残留当时 **未** 处置（受 destructive-guard 阻止）。

**本轮核实结论**：在 **活树**（排除 `_archive/` 与 `.git/`）中，
`Get-ChildItem -Recurse -Force -File -Filter '.tmp*'` 返回 **零命中**。
所有 `.tmp_*` 已随主体批次移入
`_archive/11_AR03_P5_一次性脚本/_temp_artifacts/`（root 56 项、
`tests/e2e/` 2 项）。

---

## 4. 归档批次 01–11 概览

| 批次 | 目录 | 文件数 | 内容 |
|---|---|---|---|
| 01 | `_archive/01_临时脚本/` | 18 | 早期临时脚本 |
| 02 | `_archive/02_缓存数据/` | 28 | 缓存产物 |
| 03 | `_archive/03_数据库备份/` | 8 | 数据库快照 |
| 04 | `_archive/04_PPT提取物/` | 1933 | PPT / 素材提取物 |
| 05 | `_archive/05_过时文档/` | 46 | 过期文档（含旧 Markdown 与一次性报告） |
| 06 | `_archive/06_测试脚本/` | 74 | 旧测试脚本 |
| 07 | `_archive/07_工具脚本/` | 35 | 旧工具脚本 |
| 08 | `_archive/08_提示词备份/` | 61 | 提示词备份 |
| 09 | `_archive/09_审计报告/` | 2 | 审计报告 |
| 10 | `_archive/10_其他杂项/` | 2 | 杂项 |
| 11 | `_archive/11_AR03_P5_一次性脚本/` | 238 | **AR03-P5**：legacy 退役模块 + 一次性脚本 + 临时产物 |
| — | `_archive/src_tasks_legacy/` | 46 | 已归档的 PySide6 桌面端（17 个 `.py` + README） |

批次 11 的内部结构见
`_archive/11_AR03_P5_一次性脚本/ARCHIVE_NOTE.md` §4。

---

## 5. `.run/baseline_verification_backup/`

| 项 | 说明 |
|---|---|
| 位置 | `.run/baseline_verification_backup/` |
| 内容 | `config.json`、`task_publisher.db`（2 个文件） |
| 性质 | **基线验证用的备份快照**（合成/历史副本），不是当前生产数据 |
| 治理 | `.run/` 整体已在 `.gitignore` 中 → **不入 Git**；保留在磁盘以便复现历史基线验证 |
| 是否归档 | **不归档** —— 它是 **可复现性资产**，归档反而破坏"按需回滚基线"的能力 |
| 红线 | ⚠️ 该目录下的 `task_publisher.db` 是 **副本**。**生产库** 是 `data/task_publisher.db`，本轮 **零触碰** |

`.run/` 中其余文件的处置（主体批次）：

| 文件 | 处置 |
|---|---|
| `server.log` / `server.log.err` | **保留** —— 当前运行所需（启动链写它） |
| 陈旧 `*.log`（33 个） | → `_archive/.../_temp_artifacts/run/` |

---

## 6. 恢复指引

归档件是 **纯移动**（内容零改动），因此恢复 = 移回原路径：

| 想恢复什么 | 从哪移回 |
|---|---|
| `server/app/legacy_compat.py` | `_archive/11_AR03_P5_一次性脚本/server/app/` → `server/app/` |
| `server/config.py` | `_archive/11_AR03_P5_一次性脚本/server/` → `server/` |
| `server/utils/` | `_archive/11_AR03_P5_一次性脚本/server/utils/` → `server/utils/` |
| 旧 `docs/ARCHITECTURE.md` | `docs/architecture/2026-10-04_snapshot.md` → `docs/ARCHITECTURE.md` |
| 任意一次性脚本 | `_archive/11_AR03_P5_一次性脚本/scripts/<分类>/` → `scripts/` |
| P5 中间产物 | `_archive/11_AR03_P5_一次性脚本/_temp_artifacts/` → 对应原位置 |

> ⚠️ 恢复 `legacy_compat.py` 会 **破坏** 当前状态：它会重新引入一个
> **零路由 / 零 import** 的墓碑模块，并让 `test_stage5_config_export.py`
> 与 `test_free_task_blueprint.py` 走回 "文件在原位" 分支。
> 恢复前请先读 `ARCHIVE_NOTE.md` §3.1。

---

## 7. 数据安全

本轮全部归档 / 清理操作：

- **零** 触碰 `src/notes/**`、`data/task_publisher.db{,-wal,-shm}`、
  `config/config.json`；
- 全部是 **移动**（move），不涉及任何数据文件；
- 归档件清单为 **源码文件**（`.py` / `.js` / `.ps1` / `.bat` / `.log` /
  `.txt` / `.json`）。

`.gitignore` 的变更只影响 **Git 跟踪**，不改动磁盘上的任何文件。
