# 归档索引（`_archive/`）

> **日期**：2026-11-23
> **用途**：本索引登记 `_archive/` 下 **全部归档批次** 的内容分类与恢复方式。
> **原则**：**不删除，只归档**。归档件是 **纯移动**（内容零改动），
> 恢复 = 移回原路径。
> **批次 11 明细**：`_archive/11_AR03_P5_一次性脚本/ARCHIVE_NOTE.md`
> **治理报告**：`docs/P5_DIRECTORY_AND_SCRIPTS_CLEANUP_20261122.md`

---

## 批次总览

| 批次 | 目录 | 文件数 | 内容分类 |
|---|---|---|---|
| 01 | `01_临时脚本/` | 18 | 早期一次性提取 / 校验脚本（`_extract_docx.py` / `_verify_source*.py` / `_p5_3_phase*.py` 等） |
| 02 | `02_缓存数据/` | 28 | 运行缓存产物 |
| 03 | `03_数据库备份/` | 8 | 历史数据库快照（`task_publisher_backup_*.db`） |
| 04 | `04_PPT提取物/` | 1933 | PPT / 习题 / 素材提取物 |
| 05 | `05_过时文档/` | 46 | 过期 Markdown 与一次性报告 |
| 06 | `06_测试脚本/` | 74 | 旧测试与素材处理脚本（`_crop_*.py` / `_check_svg.py` 等） |
| 07 | `07_工具脚本/` | 35 | 旧工具脚本 |
| 08 | `08_提示词备份/` | 61 | 提示词历史版本 |
| 09 | `09_审计报告/` | 2 | 审计报告（`审计报告_例题全量审查.md`、`AI_TEAM.zip`） |
| 10 | `10_其他杂项/` | 2 | 杂项产物（`_p5_3_phase1.json` / `_p5_3_phase2.json`） |
| 11 | `11_AR03_P5_一次性脚本/` | 238 | **AR03-P5**：legacy 退役模块 + 一次性脚本 + 临时产物 |
| — | `src_tasks_legacy/` | 46 | 已归档的 PySide6 桌面端（17 个 `.py` + README + 其余） |

> 批次 01–10 是 **2026-07 大规模清理** 的产物。批次 11 是 **AR03-P5** 的产物。

---

## 批次 11 —— AR03-P5（结构最需要说明）

```
_archive/11_AR03_P5_一次性脚本/
├── ARCHIVE_NOTE.md              ← 逐项核实记录（归档前核查 + 不变量表）
├── server/                      ← Legacy 退役模块
│   ├── config.py                ← 零 importer 薄 re-export → 真权威 server/app/config.py
│   ├── app/legacy_compat.py     ← 墓碑（0 路由 / 0 import / 0 副作用）
│   └── utils/                   ← 3 个纯转发壳 + __init__.py
├── scripts/                     ← 一次性 / 迁移期 / 运维脚本（按 A–G 分类）
│   ├── _p5_archive_scripts.py   ← P5 归档器（scratch）
│   ├── _p5_classify_scripts.py  ← P5 分级器（scratch）
│   ├── _p5_report_scripts.py    ← P5 报告器（scratch）
│   ├── migrate_css_split.js     ← P4 一次性 CSS 迁移工具
│   ├── rewrite_index_head.js    ← P4 一次性 CSS 迁移工具
│   ├── A_一次性探查_直接读写生产DB/    (12)
│   ├── B_一次性测试_打生产端口/        (9)
│   ├── C_一次性内容提取/               (10)
│   ├── D_一次性构建与迁移/             (26)
│   ├── E_一次性调试探针/               (3)
│   ├── F_迁移期迁移器/                 (2)
│   └── G_用户运维脚本/                 (2)
├── tests/
│   ├── e2e.spec.js              ← 硬编码生产端口 5000 的活服务器 spec
│   └── characterize/            ← 一次性沙箱脚手架 + 调试脚本
├── static/test.js               ← 死脚本（`#testBanner` 已从 index.html 移除）
├── p5_diagnostics/              ← reduced-motion 诊断探针
└── _temp_artifacts/             ← 日志 / 探针 / 一次性生成物
    ├── root/                    ← 项目根临时物（含 P5 自身产物）
    ├── run/                     ← .run/ 陈旧日志
    ├── tests/                   ← tests/ 下的日志与探针
    │   ├── e2e/
    │   └── characterize/
    └── TEMP_dir/
```

---

## 恢复指引

| 想恢复什么 | 从哪移回 |
|---|---|
| `server/app/legacy_compat.py` | `11_.../server/app/` → `server/app/` |
| `server/config.py` | `11_.../server/` → `server/` |
| `server/utils/` | `11_.../server/utils/` → `server/utils/` |
| 旧 `docs/ARCHITECTURE.md` | `docs/architecture/2026-10-04_snapshot.md` → `docs/ARCHITECTURE.md` |
| 任意一次性脚本 | `11_.../scripts/<分类>/` → `scripts/` |
| `tests/e2e.spec.js` | `11_.../tests/` → `tests/` |
| `static/test.js` | `11_.../static/` → `static/` |
| 桌面端（PySide6） | `src_tasks_legacy/` → `src/tasks/`（见 `src_tasks_legacy/README.md`） |
| P5 中间产物 / 日志 | `11_.../_temp_artifacts/` → 对应原位置 |

> ⚠️ 恢复 `legacy_compat.py` 会 **破坏** 当前状态：它会重新引入一个
> **零路由 / 零 import** 的墓碑模块，并让 `test_stage5_config_export.py`
> 与 `test_free_task_blueprint.py` 走回 "文件在原位" 分支。
> 恢复前请先读 `ARCHIVE_NOTE.md` §3.1。
>
> ⚠️ 恢复 `src_tasks_legacy/` 会重新引入 `src.tasks.*` 包；
> `test_desktop_archive_integrity.py` 断言它 **必须** 在归档态
> （17 个 `.py`，逐字节等于 git 提交 `d4a5f0b`）。

---

## 与红线的边界

`_archive/` 下的归档件 **不包含** 任何生产数据：

- `src/notes/**` —— 零触碰；
- `data/task_publisher.db{,-wal,-shm}` —— 零触碰；
- `config/config.json` —— 零触碰。

批次 03 的 `task_publisher_backup_*.db` 是 **历史快照副本**，不是当前
生产库；它们已随批次 03 入档，Git 跟踪状态见 `.gitignore`。
