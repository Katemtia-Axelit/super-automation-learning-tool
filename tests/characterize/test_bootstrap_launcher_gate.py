"""Synthetic-only characterisation tests for the safe launch chain.

Covers (LT_BOOTSTRAP_SAFE_LAUNCH_G1_20261022_C):

- ``scripts/launch_server.py`` forces ``SAL_ENFORCE_AGENT_POLICY=1`` into the
  *child* environment (parent env ``0`` cannot disable the gate).
- The parent process environment is not permanently modified.
- The legacy backend fallback is refused **fail closed**: no PID file, no log
  file, no spawned process.
- ``scripts/launch_alpha_local.py`` forces the gate on for its own process,
  and its ``--check`` mode stays strictly read-only (no Flask, no DB write).

Nothing here touches the real project: no real DB, no ``config/config.json``
read/write, no ``src/notes/**``. Every artifact lives under ``%TEMP%``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCH_SERVER = PROJECT_ROOT / "scripts" / "launch_server.py"
LAUNCH_ALPHA = PROJECT_ROOT / "scripts" / "launch_alpha_local.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LaunchServerGateTests(unittest.TestCase):
    """The safe launcher must always start a *protected* Factory child."""

    def setUp(self):
        self.launcher = _load_module(LAUNCH_SERVER, "_synthetic_launch_server")
        self.tmp = Path(tempfile.mkdtemp(prefix="lt_safe_launch_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

        # Synthetic project root: only the entrypoint stub is needed.
        (self.tmp / "run_app.py").write_text(
            "# synthetic entrypoint stub\n", encoding="utf-8"
        )
        self.run_dir = self.tmp / ".run"
        self.pid_file = self.run_dir / "server.pid"
        self.log_file = self.run_dir / "server.log"

        self.patches = [
            patch.object(self.launcher, "ROOT", str(self.tmp)),
            patch.object(self.launcher, "RUN_DIR", str(self.run_dir)),
            patch.object(self.launcher, "PID_FILE", str(self.pid_file)),
            patch.object(self.launcher, "LOG_FILE", str(self.log_file)),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def _run_main_with_fake_popen(self, env_overrides):
        """Run ``main()`` with a stubbed Popen; return the captured call.

        The returned dict also carries ``parent_env_snapshot``: the parent
        environment *as seen while the launcher ran*. It is captured inside
        the patched context because ``patch.dict`` restores the previous
        environment once the block exits.
        """
        captured = {}

        class _FakeProc:
            pid = 424242

        def _fake_popen(args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProc()

        with patch.dict(os.environ, env_overrides, clear=False):
            with patch.object(self.launcher.subprocess, "Popen", _fake_popen):
                self.launcher.main()
            captured["parent_env_snapshot"] = dict(os.environ)
        return captured

    # --- 1. child env always carries the gate -----------------------------

    def test_child_env_forces_gate_on(self):
        captured = self._run_main_with_fake_popen({"LEARNING_TOOL_BACKEND": "factory"})
        child_env = captured["kwargs"]["env"]
        self.assertEqual(child_env["SAL_ENFORCE_AGENT_POLICY"], "1")

    def test_parent_env_zero_cannot_disable_the_gate(self):
        captured = self._run_main_with_fake_popen(
            {"LEARNING_TOOL_BACKEND": "factory", "SAL_ENFORCE_AGENT_POLICY": "0"}
        )
        child_env = captured["kwargs"]["env"]
        self.assertEqual(child_env["SAL_ENFORCE_AGENT_POLICY"], "1")
        # The parent environment itself must stay untouched by the launcher.
        self.assertEqual(
            captured["parent_env_snapshot"].get("SAL_ENFORCE_AGENT_POLICY"), "0"
        )

    def test_child_env_is_a_new_dictionary(self):
        base = {"SAL_ENFORCE_AGENT_POLICY": "0", "PATH": os.environ.get("PATH", "")}
        env = self.launcher.build_child_env(base)
        self.assertEqual(env["SAL_ENFORCE_AGENT_POLICY"], "1")
        self.assertEqual(base["SAL_ENFORCE_AGENT_POLICY"], "0")

    def test_popen_and_pid_log_mechanism_is_preserved(self):
        captured = self._run_main_with_fake_popen({"LEARNING_TOOL_BACKEND": "factory"})
        self.assertEqual(captured["args"][0], sys.executable)
        self.assertEqual(Path(captured["args"][1]), self.tmp / "run_app.py")
        self.assertEqual(captured["kwargs"]["cwd"], str(self.tmp))
        self.assertTrue(self.pid_file.is_file())
        self.assertEqual(self.pid_file.read_text(encoding="utf-8").strip(), "424242")
        self.assertTrue(self.log_file.is_file())
        self.assertIn("server start: factory", self.log_file.read_text(encoding="utf-8"))

    # --- 2. legacy fallback fails closed ----------------------------------

    def test_legacy_fallback_is_refused_without_pid_log_or_process(self):
        spawned = []

        def _fake_popen(args, **kwargs):  # pragma: no cover - must not run
            spawned.append((args, kwargs))
            raise AssertionError("legacy backend must not be spawned")

        env = {"LEARNING_TOOL_BACKEND": "legacy"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(self.launcher.subprocess, "Popen", _fake_popen):
                with self.assertRaises(SystemExit) as ctx:
                    self.launcher.main()
        message = str(ctx.exception)
        self.assertIn("REFUSED", message)
        self.assertIn("legacy", message)
        self.assertEqual(spawned, [])
        self.assertFalse(self.run_dir.exists())
        self.assertFalse(self.pid_file.exists())
        self.assertFalse(self.log_file.exists())

    # --- 3. pure function unchanged ---------------------------------------

    def test_select_entrypoint_behaviour_is_unchanged(self):
        with patch.dict(os.environ, {"LEARNING_TOOL_BACKEND": "factory"}):
            mode, entry = self.launcher.select_entrypoint(str(self.tmp))
        self.assertEqual(mode, "factory")
        self.assertEqual(Path(entry), self.tmp / "run_app.py")
        with patch.dict(os.environ, {"LEARNING_TOOL_BACKEND": "legacy"}):
            mode, entry = self.launcher.select_entrypoint(str(self.tmp))
        self.assertEqual(mode, "legacy")
        self.assertEqual(Path(entry), self.tmp / "server" / "backend_api.py")


class LaunchAlphaGateTests(unittest.TestCase):
    """The Alpha launcher must be protected too, and ``--check`` read-only."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lt_safe_alpha_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _synthetic_root(self) -> Path:
        root = self.tmp / "alpha_root"
        (root / "scripts").mkdir(parents=True)
        (root / "server" / "app").mkdir(parents=True)
        (root / "data").mkdir()
        (root / "config").mkdir()
        shutil.copyfile(LAUNCH_ALPHA, root / "scripts" / "launch_alpha_local.py")
        (root / "server" / "__init__.py").write_text("", encoding="utf-8")
        (root / "server" / "app" / "__init__.py").write_text("", encoding="utf-8")
        port = _free_port()
        db_path = root / "data" / "synthetic.sqlite3"
        db_path.write_bytes(b"synthetic")
        config_module = (
            "import os\n"
            "ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
            "def load_config():\n"
            "    return {\n"
            "        'server': {'host': '127.0.0.1', 'port': %d, 'debug': False},\n"
            "        '_project_root': ROOT,\n"
            "        '_static_dir': os.path.join(ROOT, 'static'),\n"
            "        '_db_path': os.path.join(ROOT, 'data', 'synthetic.sqlite3'),\n"
            "        '_notes_dir': os.path.join(ROOT, 'vault'),\n"
            "    }\n" % port
        )
        (root / "server" / "app" / "config.py").write_text(config_module, encoding="utf-8")
        (root / "config" / "config.json").write_text(
            json.dumps({"server": {"port": port}}), encoding="utf-8"
        )
        return root

    def test_alpha_forces_gate_on_for_its_own_process(self):
        module = _load_module(LAUNCH_ALPHA, "_synthetic_launch_alpha")
        with patch.dict(os.environ, {"SAL_ENFORCE_AGENT_POLICY": "0"}):
            value = module.enforce_agent_policy_gate()
            self.assertEqual(value, "1")
            self.assertEqual(os.environ["SAL_ENFORCE_AGENT_POLICY"], "1")

    def test_alpha_check_mode_is_read_only(self):
        root = self._synthetic_root()
        db_path = root / "data" / "synthetic.sqlite3"
        before = (db_path.stat().st_mtime_ns, db_path.stat().st_size)
        env = {
            k: v for k, v in os.environ.items()
            if k.upper() not in ("PYTHONPATH", "PYTHONHOME")
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["SAL_ENFORCE_AGENT_POLICY"] = "0"
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "launch_alpha_local.py"), "--check"],
            cwd=str(root), env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[Alpha CHECK PASS]", result.stdout)
        after = (db_path.stat().st_mtime_ns, db_path.stat().st_size)
        self.assertEqual(before, after)
        # No Flask app object was created and nothing was written besides the
        # synthetic config/db that already existed.
        self.assertFalse((root / "data" / "agent-policy").exists())
        self.assertFalse((root / "src").exists())


if __name__ == "__main__":
    unittest.main()
