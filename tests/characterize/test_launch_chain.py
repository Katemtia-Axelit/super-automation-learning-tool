"""Smoke-test real launch_server.py selecting Factory and Legacy in sandbox."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen

from sandbox_env import SOURCE_ROOT, available_port, materialize, seed


class LaunchChainTests(unittest.TestCase):
    def test_factory_default_and_legacy_fallback_start(self):
        for mode in ("factory", "legacy"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="lt_chain_") as temp:
                port = available_port()
                root = materialize(Path(temp) / "sandbox", port)
                seed(root)
                scripts = root / "scripts"
                scripts.mkdir()
                shutil.copyfile(
                    SOURCE_ROOT / "scripts" / "launch_server.py",
                    scripts / "launch_server.py",
                )
                shutil.copyfile(SOURCE_ROOT / "run_app.py", root / "run_app.py")
                env = {k:v for k,v in os.environ.items()
                       if "API_KEY" not in k.upper()
                       and "TOKEN" not in k.upper()
                       and k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                env["LEARNING_TOOL_BACKEND"] = mode
                pid = None
                try:
                    launched = subprocess.run(
                        [sys.executable, "-I", str(scripts / "launch_server.py")],
                        cwd=root, env=env, capture_output=True, text=True, timeout=8,
                    )
                    self.assertEqual(launched.returncode,0,launched.stderr)
                    self.assertIn(f"BACKEND={mode}", launched.stdout)
                    pid = int((root / ".run" / "server.pid").read_text().strip())
                    deadline = time.monotonic() + 12
                    while time.monotonic() < deadline:
                        try:
                            with urlopen(f"http://127.0.0.1:{port}/api/health",timeout=0.5) as r:
                                if r.status == 200:
                                    break
                        except (OSError,TimeoutError):
                            time.sleep(0.15)
                    else:
                        log = (root / ".run" / "server.log").read_text(encoding="utf-8",errors="replace")
                        self.fail(f"{mode} real launcher did not serve health: {log[-700:]}")
                finally:
                    if pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        time.sleep(0.4)


if __name__ == "__main__":
    unittest.main()
