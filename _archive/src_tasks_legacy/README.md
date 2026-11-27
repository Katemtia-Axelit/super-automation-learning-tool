# 归档：桌面端任务发布器（`src/tasks/` → `_archive/src_tasks_legacy/`）

> **归档提交**：`d4a5f0b`（`chore(archive): record legacy desktop task app`）
> **归档日期**：2026-08-16
> **状态**：**只读归档**。此树**不在** Web 应用的构建/运行路径上。

本文件是归档的 **唯一** 权威说明：真实文件清单、迁移映射、回滚方法、
依赖说明，以及与历史文档的差异记录。

---

## 1. 为什么归档

Web 后端（`server/` + `data/task_publisher.db`）已经成为任务数据的 **唯一**
权威来源。桌面端（PySide6）的那一套 `models/` / `services/` / `ui/` Python
代码**不再**接入 Web 构建路径，其能力被 API 面（Blueprint）取代。

因此桌面端代码被 **整体移动**（不是复制、不是删除）到本目录，保留完整
可回溯性。

---

## 2. 真实文件清单（17 个 `.py`，逐字节未改动）

`d4a5f0b` 以 **纯 rename**（100% similarity，0 行增删）记录了全部 17 个
`.py` 文件。下表的"字节数"是当前工作区的实测值；"一致性"一列由
`tests/characterize/test_desktop_archive_integrity.py` 用
`git show d4a5f0b:<path>` 的 sha256 **逐文件**比对得出。

| # | 归档路径（相对本目录） | 字节数 | 与 `d4a5f0b` 一致 |
|---|---|---|---|
| 1 | `__init__.py` | 0 | ✅ |
| 2 | `models/__init__.py` | 0 | ✅ |
| 3 | `models/database.py` | 31648 | ✅ |
| 4 | `models/task.py` | 9484 | ✅ |
| 5 | `services/__init__.py` | 0 | ✅ |
| 6 | `services/ai_import_processor.py` | 12877 | ✅ |
| 7 | `services/ai_import_service.py` | 5622 | ✅ |
| 8 | `services/export_service.py` | 3299 | ✅ |
| 9 | `services/gacha_service.py` | 11653 | ✅ |
| 10 | `services/state_service.py` | 8791 | ✅ |
| 11 | `services/task_service.py` | 13996 | ✅ |
| 12 | `ui/__init__.py` | 0 | ✅ |
| 13 | `ui/dependency_graph.py` | 25452 | ✅ |
| 14 | `ui/filter_dialog.py` | 17642 | ✅ |
| 15 | `ui/gacha_window.py` | 45804 | ✅ |
| 16 | `ui/main_window.py` | 66568 | ✅ |
| 17 | `ui/schedule_window.py` | 21480 | ✅ |

**合计 17 个 `.py` 文件。**

> **`__pycache__/` 不计入清单。** 归档树里残留的 `__pycache__/`（含
> `.cpython-311/312/313.pyc`）是 **构建产物**，从未被 git 跟踪，也不在
> 迁移映射内。它对归档完整性没有意义；如需清理由用户在 Cursor 之外执行
> （本项目的 Cursor 写操作不得删除工作区内容）。

### 2.1 `utils/` 目录（空壳残留，已删除）

历史文档（如 `STATUS_REPORT_2026-08-16.md` §1.2、`src/tasks/README.md`
的早期版本）把本目录描述为含 `utils/`。**实测：git 历史里从无 `utils/`**
（`git log --all --diff-filter=A -- "src/tasks/utils/*"` 返回空），
`_archive/src_tasks_legacy/utils/` 是一个 **空的未跟踪目录** —— 归档后
遗留的空壳，不含任何文件。P1 已将其删除。

---

## 3. 迁移映射（`git mv` 语义，零内容改动）

`d4a5f0b` 的 rename 映射（`git show --numstat d4a5f0b` 原样）：

```
{src/tasks => _archive/src_tasks_legacy}/__init__.py
{src/tasks => _archive/src_tasks_legacy}/models/__init__.py
{src/tasks => _archive/src_tasks_legacy}/models/database.py
{src/tasks => _archive/src_tasks_legacy}/models/task.py
{src/tasks => _archive/src_tasks_legacy}/services/__init__.py
{src/tasks => _archive/src_tasks_legacy}/services/ai_import_processor.py
{src/tasks => _archive/src_tasks_legacy}/services/ai_import_service.py
{src/tasks => _archive/src_tasks_legacy}/services/export_service.py
{src/tasks => _archive/src_tasks_legacy}/services/gacha_service.py
{src/tasks => _archive/src_tasks_legacy}/services/state_service.py
{src/tasks => _archive/src_tasks_legacy}/services/task_service.py
{src/tasks => _archive/src_tasks_legacy}/ui/__init__.py
{src/tasks => _archive/src_tasks_legacy}/ui/dependency_graph.py
{src/tasks => _archive/src_tasks_legacy}/ui/filter_dialog.py
{src/tasks => _archive/src_tasks_legacy}/ui/gacha_window.py
{src/tasks => _archive/src_tasks_legacy}/ui/main_window.py
{src/tasks => _archive/src_tasks_legacy}/ui/schedule_window.py
```

映射规则：**目录整体平移一级**，相对路径 **完全不变**：

```
src/tasks/<X>  →  _archive/src_tasks_legacy/<X>
```

因此归档树内部的 **任何** 相对 import（`from .models.task import Task`、
`from services.task_service import ...`）在归档后 **依然成立**，无需改写。
这也是"零内容改动"能成立的技术前提。

---

## 4. 回滚方法

### 4.1 完整回滚（把桌面端搬回 `src/tasks/`）

```bash
git mv _archive/src_tasks_legacy src/tasks
git commit -m "chore(archive): restore legacy desktop task app"
```

（`src/tasks/README.md` 位于 `src/tasks/` **之外**，它本身不在被移动的
树内 —— 见 §6。）

### 4.2 只读使用（不搬家）

归档树带 `__init__.py`，因此 **可以** 作为包导入：

```python
from _archive.src_tasks_legacy.ui.main_window import MainWindow
```

但注意：`_archive` 没有 `__init__.py`，需以 **namespace package**
（PEP 420）方式解析；从仓库根目录运行 Python 时才可用。

### 4.3 运行入口

`scripts/main.py` 在 P1 之后 **fail closed**（不再必然 `ModuleNotFoundError`
栈崩），它会：

1. 明确说明桌面端已归档；
2. 指出归档路径与两种恢复方式；
3. 以 **非 0 退出码** 结束。

Web 应用（当前受支持的产品入口）请用：

```
scripts/启动学习工具.bat
```

---

## 5. 依赖说明

| 依赖 | 说明 |
|---|---|
| **PySide6** | 本树 **专属**。`ui/*.py` 全部依赖 PySide6（`QMainWindow` / `QDialog` / `QVBoxLayout` …）。Web 应用 **零引用**。 |
| **`data/task_publisher.db`** | 桌面端通过 `models/database.py` 直连 SQLite。Web 端通过 `server/` 的 Repository/Blueprint 层访问同一份数据。 |
| **无 Web 依赖** | 本树 **不** import `server.*`、**不** import `flask`、**不** 依赖 `static/` 或 `src/index.html`。 |
| **AI 导入** | `services/ai_import_*.py` 含桌面端自己的 AI 导入流水线，与 P1 的"no-model-API Agent"方向 **无关**，且 Web 端零引用。 |

**结论**：本归档树可以安全地留在仓库里，不会被 Web 构建/启动路径加载，
也不会触碰生产数据。

---

## 6. 与 `src/tasks/README.md` 的关系

`src/tasks/README.md` **留在原地**（不在被移动的树内），作用是"路牌"：
告诉路过的人"这里曾经有什么、东西去哪了"。它指向本文件。

- 本文件（`_archive/src_tasks_legacy/README.md`）= **归档内容的权威说明**
  （清单 / 映射 / 回滚 / 依赖 / 差异记录）。
- `src/tasks/README.md` = **入口路牌**（指向本文件）。

两者对"17 个 `.py`"这一事实的表述 **一致**。

---

## 7. 与历史文档的差异记录（重要）

历史文档（`STATUS_REPORT_2026-08-16.md` §1.2 等）声称归档了 **"45 files"**。
**实测不成立**：

| 说法 | 实测 | 依据 |
|---|---|---|
| "45 files" | **17 个 `.py`** | `git show --numstat d4a5f0b` 只列出 17 个 `.py` 的 rename（+ 1 个新增 `src/tasks/README.md`） |
| 含 `utils/` | **git 历史从无 `utils/`** | `git log --all --diff-filter=A -- "src/tasks/utils/*"` 返回空 |
| "内容零改动" | ✅ 成立 | 17 个文件在 `d4a5f0b` 的 numstat 全部为 `0  0`（纯 rename） |

**"45 files"** 很可能是把 `__pycache__/` 里的 `.pyc`（本机多版本
CPython 产物）、`README.md`、以及其它杂项一并计入的统计口径问题。
**P1 的冻结清单以 git 事实为准：17 个 `.py`。**

---

## 8. 归档完整性验证

只读校验（不写任何文件、不改 git 历史）：

```bash
.venv\Scripts\python.exe -m pytest tests/characterize/test_desktop_archive_integrity.py -q
```

该测试逐文件比对 `git show d4a5f0b:<path>` 与工作区文件的 sha256，
并断言：

- 归档树恰有 17 个 `.py`；
- 每个文件与 `d4a5f0b` **逐字节一致**；
- `utils/` 空壳已不存在；
- 运行入口（`scripts/main.py`）不再引用 `src.tasks.*`；
- Web 运行路径（`server/` / `static/`）**零引用**本归档树。
