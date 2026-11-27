"""Stage 0 / AR03-P2 — 隔离验证器的 **零触碰证明机制** 契约测试。

背景
----
旧版 ``scripts/run_e2e_isolated.js`` 用 ``fs.readFileSync()`` **读取**生产
``data/task_publisher.db{,-wal,-shm}`` / ``config/config.json`` /
``src/notes/**`` 并计算 SHA-256，再比较运行前后是否一致。这违反项目最高
数据保护要求：**不读取、不写入、不复制、不哈希、不恢复**真实生产 SQLite
及其 WAL/SHM。"用读取来证明没变"本身就是一次读取。

Stage 0 把证明方式改成三重、且 **全程不打开任何生产文件**：

A. **Node fs 守卫**（``scripts/guard/protected_paths_guard.js``）
   —— 事前阻断：对受保护路径的任何读取尝试立即抛错。
B. **Python 审计钩子**（``tests/e2e/synthetic_audit.py``）
   —— 事中记录：合成服务器进程内记录真实 sqlite3.connect / 文件访问。
C. **合成根启动自检**（``tests/e2e/synthetic_root_selfcheck.py``）
   —— fail closed：服务器启动前断言解析路径全部落在合成根内。

本文件对这些机制做 **机械断言**，使"隔离方式本身"不会在后续重构中被
悄悄改回"读生产文件比对哈希"。

全程只读项目 **源码**（``.py`` / ``.js`` 文本）与合成临时目录；**绝不**
打开生产 DB / WAL / SHM / Vault / config。
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_JS = PROJECT_ROOT / "scripts" / "guard" / "protected_paths_guard.js"
RUNNER_JS = PROJECT_ROOT / "scripts" / "run_e2e_isolated.js"
AUDIT_PY = PROJECT_ROOT / "tests" / "e2e" / "synthetic_audit.py"
SELFCHECK_PY = PROJECT_ROOT / "tests" / "e2e" / "synthetic_root_selfcheck.py"
SANDBOX_SERVER_PY = PROJECT_ROOT / "tests" / "e2e" / "factory-sandbox-server.py"

#: 生产受保护路径（相对项目根）。**只作为字符串参与路径计算，绝不打开。**
PROTECTED_RELATIVE = (
    "data/task_publisher.db",
    "data/task_publisher.db-wal",
    "data/task_publisher.db-shm",
    "config/config.json",
    "src/notes",
)


class IsolationGuardContractTests(unittest.TestCase):
    """A. Node fs 守卫 —— 事前阻断。"""

    def test_guard_module_exists_and_exports_apis(self):
        self.assertTrue(GUARD_JS.is_file(), "guard module missing: " + str(GUARD_JS))
        source = GUARD_JS.read_text(encoding="utf-8")
        for name in ("install", "isProtected", "describe"):
            self.assertIn(name, source)

    def test_guard_self_test_passes(self):
        """守卫自检：受保护路径全部拦截、合法路径全部放行。"""
        proc = subprocess.run(
            [node_executable(), str(GUARD_JS), "--self-test"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0, (proc.stdout, proc.stderr)
        )
        self.assertIn("自检通过", proc.stdout)

    def test_guard_blocks_every_protected_path(self):
        """逐条验证受保护路径判定结果（只做路径字符串运算，不打开文件）。"""
        probe = (
            "const g = require(process.argv[2]);"
            "const root = process.argv[3];"
            "const rels = JSON.parse(process.argv[4]);"
            "const allow = JSON.parse(process.argv[5]);"
            "let bad = 0;"
            "for (const r of rels) {"
            "  if (!g.isProtected(require('path').join(root, r))) {"
            "    console.error('NOT BLOCKED: ' + r); bad += 1;"
            "  }"
            "}"
            "for (const r of allow) {"
            "  if (g.isProtected(require('path').join(root, r))) {"
            "    console.error('WRONGLY BLOCKED: ' + r); bad += 1;"
            "  }"
            "}"
            "process.exit(bad ? 1 : 0);"
        )
        with tempfile.TemporaryDirectory(prefix="lt_guard_probe_") as temp:
            probe_path = Path(temp) / "probe.js"
            probe_path.write_text(probe, encoding="utf-8")
            allow = [
                "tests/e2e-manual.js",
                "scripts/run_e2e_isolated.js",
                "server/app/app_factory.py",
            ]
            proc = subprocess.run(
                [
                    node_executable(),
                    str(probe_path),
                    str(GUARD_JS),
                    str(PROJECT_ROOT),
                    json.dumps(list(PROTECTED_RELATIVE)),
                    json.dumps(allow),
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, (proc.stdout, proc.stderr))


class IsolationRunnerContractTests(unittest.TestCase):
    """Runner 源码层断言 —— 证明"不再读生产文件"。"""

    def setUp(self):
        self.source = RUNNER_JS.read_text(encoding="utf-8")

    def test_runner_does_not_read_production_files(self):
        """runner 源码中 **不得** 出现对生产受保护路径的读取或哈希。"""
        # 允许注释与说明文字中出现这些路径名（用于解释被禁用的旧行为），
        # 但不得出现实际读取 API 的调用形式。
        forbidden = (
            "readFileSync(path.join(PROJECT_ROOT",
            "readFileSync(PROTECTED_FILES",
            "createHash('sha256')",
            'createHash("sha256")',
            "fingerprintFile",
            "fingerprintTree",
        )
        for token in forbidden:
            self.assertNotIn(
                token,
                self.source,
                "run_e2e_isolated.js 仍包含生产文件读取/哈希逻辑: " + token,
            )

    def test_runner_installs_the_guard(self):
        self.assertIn("protected_paths_guard", self.source)
        self.assertIn("GUARD.install", self.source)

    def test_runner_asserts_audit_cleanliness(self):
        self.assertIn("protected_violations", self.source)
        self.assertIn("sqlite_outside_synthetic", self.source)

    def test_runner_reads_audit_from_synthetic_root_only(self):
        """审计清单路径必须由合成根拼出，不能指向项目根。"""
        self.assertIn("'_sandbox_audit.json'", self.source)
        self.assertNotIn(
            "PROJECT_ROOT, 'data', 'task_publisher.db'",
            self.source,
        )


class SyntheticAuditContractTests(unittest.TestCase):
    """B. Python 审计钩子。"""

    def setUp(self):
        self.source = AUDIT_PY.read_text(encoding="utf-8")

    def test_audit_module_is_valid_python(self):
        ast.parse(self.source, str(AUDIT_PY))

    def test_audit_records_sqlite_and_file_access(self):
        self.assertIn("sys.addaudithook", self.source)
        self.assertIn("sqlite3.connect", self.source)
        self.assertIn("protected_violations", self.source)
        self.assertIn("sqlite_outside_synthetic", self.source)

    def test_audit_detects_protected_access(self):
        """自检：把一个受保护路径喂给审计判定函数，必须被标记为违规。"""
        sys.path.insert(0, str(AUDIT_PY.parent))
        try:
            import synthetic_audit  # type: ignore
        finally:
            sys.path.pop(0)

        real_root = str(PROJECT_ROOT)
        synthetic_root = str(Path(tempfile.gettempdir()) / "synthetic-root-probe")
        os.environ["SAL_AUDIT_REAL_ROOT"] = real_root
        os.environ["SAL_AUDIT_SYNTHETIC_ROOT"] = synthetic_root
        try:
            summary = synthetic_audit.flush("")
        finally:
            os.environ.pop("SAL_AUDIT_REAL_ROOT", None)
            os.environ.pop("SAL_AUDIT_SYNTHETIC_ROOT", None)

        # 审计本身没有访问任何东西 → 无违规、无越界。
        self.assertEqual(summary["protected_violations"], [])
        self.assertEqual(summary["sqlite_outside_synthetic"], [])

        # 直接验证匹配判定：真实项目根下的 data/ 与 config/ 必须被识别。
        self.assertTrue(
            synthetic_audit._matches_protected(
                real_root, str(PROJECT_ROOT / "data" / "task_publisher.db")
            )
        )
        self.assertTrue(
            synthetic_audit._matches_protected(
                real_root, str(PROJECT_ROOT / "config" / "config.json")
            )
        )
        self.assertTrue(
            synthetic_audit._matches_protected(
                real_root, str(PROJECT_ROOT / "src" / "notes" / "vault")
            )
        )
        self.assertFalse(
            synthetic_audit._matches_protected(
                real_root, str(PROJECT_ROOT / "server" / "app" / "app_factory.py")
            )
        )


class SyntheticRootSelfCheckContractTests(unittest.TestCase):
    """C. 合成根启动自检（fail closed）。"""

    def setUp(self):
        sys.path.insert(0, str(SELFCHECK_PY.parent))
        try:
            import synthetic_root_selfcheck as selfcheck  # type: ignore
        finally:
            sys.path.pop(0)
        self.check = selfcheck

    def test_selfcheck_rejects_real_project_root(self):
        with self.assertRaises(self.check.IsolationError):
            self.check.assert_synthetic_root(PROJECT_ROOT, PROJECT_ROOT)

    def test_selfcheck_rejects_nested_root(self):
        nested = PROJECT_ROOT / "data" / "_synthetic_probe"
        with self.assertRaises(self.check.IsolationError):
            self.check.assert_synthetic_root(nested, PROJECT_ROOT)

    def test_selfcheck_rejects_escaping_paths(self):
        with tempfile.TemporaryDirectory(prefix="lt_selfcheck_") as temp:
            synth = Path(temp) / "root"
            synth.mkdir()
            with self.assertRaises(self.check.IsolationError):
                self.check.assert_paths_inside(
                    synth,
                    {"db_path": str(PROJECT_ROOT / "data" / "task_publisher.db")},
                )

    def test_selfcheck_accepts_well_formed_synthetic_root(self):
        with tempfile.TemporaryDirectory(prefix="lt_selfcheck_") as temp:
            synth = Path(temp) / "root"
            (synth / "data").mkdir(parents=True)
            (synth / "vault").mkdir(parents=True)
            (synth / "config").mkdir(parents=True)
            summary = self.check.self_check(
                synth,
                PROJECT_ROOT,
                {
                    "db_path": str(synth / "data" / "synthetic.sqlite3"),
                    "notes_dir": str(synth / "vault"),
                    "config_path": str(synth / "config" / "config.json"),
                },
            )
            self.assertTrue(summary["ok"])


class SandboxServerWiringTests(unittest.TestCase):
    """合成服务器必须真正安装审计与自检。"""

    def setUp(self):
        self.source = SANDBOX_SERVER_PY.read_text(encoding="utf-8")

    def test_sandbox_server_is_valid_python(self):
        ast.parse(self.source, str(SANDBOX_SERVER_PY))

    def test_sandbox_server_installs_bootstrap_and_selfcheck(self):
        self.assertIn("_install_synthetic_bootstrap", self.source)
        self.assertIn("_self_check", self.source)
        self.assertIn("_sandbox_bootstrap.py", self.source)

    def test_sandbox_server_passes_audit_env(self):
        self.assertIn("SAL_AUDIT_REAL_ROOT", self.source)
        self.assertIn("SAL_AUDIT_SYNTHETIC_ROOT", self.source)
        self.assertIn("SAL_AUDIT_OUTPUT", self.source)


def node_executable() -> str:
    """返回 node 可执行文件名（Windows 上 node.exe 即可）。"""
    return "node"


if __name__ == "__main__":
    unittest.main()
