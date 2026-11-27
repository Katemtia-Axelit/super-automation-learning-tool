"""P1 切片 6：桌面端归档完整性（只读 git + 只读文件系统）。

验证 ``_archive/src_tasks_legacy/`` 归档的 **可追溯性**：

  A. 清单事实
     - 归档树恰有 **17** 个 ``.py``（与历史文档声称的 "45 files" 不符 ——
       见归档 README §7 的差异记录）；
     - ``utils/`` 空壳残留已删除。

  B. 逐字节一致性
     - 每个 ``.py`` 与 ``git show d4a5f0b:<path>`` 的 sha256 **完全一致**
       （纯 rename，零内容改动）。

  C. 运行入口 fail closed
     - ``scripts/main.py`` 不再无条件 import ``src.tasks.*``；
     - 它捕获 ``ModuleNotFoundError`` 并以 **非 0** 退出码结束。

  D. Web 运行路径零引用
     - ``server/`` 与 ``static/`` **不 import** 本归档树。

约束：本文件 **只读** git 历史（``git show`` / ``git ls-tree``），
**不** amend / rebase / checkout / reset；**不**触碰生产 DB / config /
notes。``__pycache__`` 下的 ``.pyc`` 是构建产物，不计入清单。
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parents[1]
ARCHIVE_ROOT = PROJECT_ROOT / "_archive" / "src_tasks_legacy"

#: 归档提交（纯 rename，17 个 .py）。
ARCHIVE_COMMIT = "d4a5f0b"

#: 冻结清单：归档提交里被 move 的 17 个 .py（相对 PROJECT_ROOT）。
EXPECTED_PY_FILES = (
    "_archive/src_tasks_legacy/__init__.py",
    "_archive/src_tasks_legacy/models/__init__.py",
    "_archive/src_tasks_legacy/models/database.py",
    "_archive/src_tasks_legacy/models/task.py",
    "_archive/src_tasks_legacy/services/__init__.py",
    "_archive/src_tasks_legacy/services/ai_import_processor.py",
    "_archive/src_tasks_legacy/services/ai_import_service.py",
    "_archive/src_tasks_legacy/services/export_service.py",
    "_archive/src_tasks_legacy/services/gacha_service.py",
    "_archive/src_tasks_legacy/services/state_service.py",
    "_archive/src_tasks_legacy/services/task_service.py",
    "_archive/src_tasks_legacy/ui/__init__.py",
    "_archive/src_tasks_legacy/ui/dependency_graph.py",
    "_archive/src_tasks_legacy/ui/filter_dialog.py",
    "_archive/src_tasks_legacy/ui/gacha_window.py",
    "_archive/src_tasks_legacy/ui/main_window.py",
    "_archive/src_tasks_legacy/ui/schedule_window.py",
)


def _git(*args: str) -> bytes:
    """只读 git 调用（绝不 amend / rebase / checkout）。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "git %s 失败：%s" % (" ".join(args), result.stderr.decode("utf-8", "replace"))
        )
    return result.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArchiveInventoryTests(unittest.TestCase):
    """A. 清单事实。"""

    def test_archive_tree_has_exactly_seventeen_python_files(self):
        found = sorted(
            p.relative_to(PROJECT_ROOT).as_posix()
            for p in ARCHIVE_ROOT.rglob("*.py")
        )
        self.assertEqual(
            found,
            sorted(EXPECTED_PY_FILES),
            "归档树的 .py 清单与冻结清单不一致",
        )
        self.assertEqual(len(found), 17)

    def test_empty_utils_leftover_is_gone(self):
        self.assertFalse(
            (ARCHIVE_ROOT / "utils").exists(),
            "_archive/src_tasks_legacy/utils/ 是空壳残留（git 历史从无 utils），应已删除",
        )

    def test_archive_readme_exists_and_states_the_real_count(self):
        readme = ARCHIVE_ROOT / "README.md"
        self.assertTrue(readme.exists(), "归档缺少 README.md（归档不可追溯）")
        text = readme.read_text(encoding="utf-8")
        self.assertIn("17", text, "归档 README 必须写明真实文件数")
        self.assertIn("45", text, "归档 README 必须记录历史文档的 45 files 差异")
        self.assertIn(ARCHIVE_COMMIT, text)


class ArchiveByteIdentityTests(unittest.TestCase):
    """B. 逐字节一致性（对 git 历史只读）。"""

    def test_every_archived_file_matches_the_archive_commit(self):
        for rel in EXPECTED_PY_FILES:
            with self.subTest(path=rel):
                committed = _git("show", "%s:%s" % (ARCHIVE_COMMIT, rel))
                current = (PROJECT_ROOT / rel).read_bytes()
                self.assertEqual(
                    _sha256(committed),
                    _sha256(current),
                    "%s 与 %s 不一致（归档必须是纯 rename）" % (rel, ARCHIVE_COMMIT),
                )

    def test_archive_commit_recorded_all_seventeen_as_pure_renames(self):
        """归档提交本身必须是 0 行增删的纯 rename。"""
        numstat = _git("show", "--numstat", "--format=", ARCHIVE_COMMIT).decode(
            "utf-8", "replace"
        )
        moved = []
        for line in numstat.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            added, removed, path = parts[0], parts[1], parts[2]
            if "src_tasks_legacy" not in path:
                continue
            moved.append((added, removed, path))
        self.assertEqual(
            len(moved), 17, "归档提交必须记录 17 个 .py 的 move"
        )
        for added, removed, path in moved:
            with self.subTest(path=path):
                self.assertEqual(
                    (added, removed), ("0", "0"), "归档必须是纯 rename（零内容改动）"
                )


class ArchiveRuntimeEntryTests(unittest.TestCase):
    """C. 运行入口 fail closed。"""

    def test_main_py_does_not_unconditionally_import_the_removed_path(self):
        source = (PROJECT_ROOT / "scripts" / "main.py").read_text(encoding="utf-8")
        # 旧的无保护 import 必须被 try/except 包住。
        self.assertIn("except ModuleNotFoundError", source)
        self.assertNotRegex(
            source,
            r"(?m)^from src\.tasks\.ui\.main_window import MainWindow\s*$",
            "scripts/main.py 不得有无保护的 src.tasks.* import",
        )

    def test_main_py_exits_non_zero_with_a_readable_message(self):
        import os
        import sys

        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "main.py")],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )
        self.assertNotEqual(
            result.returncode, 0, "归档入口必须以非 0 退出码结束（fail closed）"
        )
        combined = (result.stdout or "") + (result.stderr or "")
        self.assertIn("归档", combined, "失败信息必须可读且指向归档")
        self.assertIn("_archive/src_tasks_legacy", combined)

    def test_no_runtime_entry_references_the_removed_package(self):
        """除 scripts/main.py 的探测外，运行入口不得再 import src.tasks.*。"""
        offenders = []
        for path in list((PROJECT_ROOT / "server").rglob("*.py")) + list(
            (PROJECT_ROOT / "scripts").rglob("*.py")
        ):
            source = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r"^\s*from\s+src\.tasks[\w.]*\s+import|^\s*import\s+src\.tasks[\w.]*",
                source,
                re.MULTILINE,
            ):
                rel = path.relative_to(PROJECT_ROOT).as_posix()
                if rel == "scripts/main.py":
                    continue
                offenders.append(rel + " → " + match.group(0).strip())
        self.assertEqual(
            offenders, [], "运行入口不得再引用已归档的 src.tasks.*：" + ", ".join(offenders)
        )


class ArchiveIsolationTests(unittest.TestCase):
    """D. Web 运行路径零引用。"""

    def test_web_runtime_does_not_import_the_archive(self):
        offenders = []
        roots = [PROJECT_ROOT / "server", PROJECT_ROOT / "static"]
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix not in (".py", ".js"):
                    continue
                source = path.read_text(encoding="utf-8", errors="replace")
                if "src_tasks_legacy" in source:
                    rel = path.relative_to(PROJECT_ROOT).as_posix()
                    offenders.append(rel)
        self.assertEqual(
            offenders, [], "Web 运行路径不得引用归档树：" + ", ".join(offenders)
        )

    def test_archive_tree_is_not_imported_by_the_launch_chain(self):
        launchers = [
            PROJECT_ROOT / "scripts" / "启动学习工具.bat",
            PROJECT_ROOT / "scripts" / "start_web_safe.bat",
            PROJECT_ROOT / "scripts" / "launch_server.py",
        ]
        for launcher in launchers:
            if not launcher.exists():
                continue
            with self.subTest(launcher=launcher.name):
                source = launcher.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn("src_tasks_legacy", source)
                self.assertNotIn("src/tasks", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
