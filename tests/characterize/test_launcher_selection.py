"""Validate reversible launcher mode selection without starting live services."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


LAUNCHER = Path(__file__).resolve().parents[2] / "scripts" / "launch_server.py"
spec = importlib.util.spec_from_file_location("_synthetic_launcher_selection", LAUNCHER)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherSelectionTests(unittest.TestCase):
    def test_factory_default_and_legacy_fallback(self):
        with tempfile.TemporaryDirectory(prefix="lt_launcher_") as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {"LEARNING_TOOL_BACKEND": "factory"}):
                mode, entry = launcher.select_entrypoint(str(root))
                self.assertEqual(mode, "factory")
                self.assertEqual(Path(entry), root / "run_app.py")
            with patch.dict(os.environ, {"LEARNING_TOOL_BACKEND": "legacy"}):
                mode, entry = launcher.select_entrypoint(str(root))
                self.assertEqual(mode, "legacy")
                self.assertEqual(Path(entry), root / "server" / "backend_api.py")
            with patch.dict(os.environ, {"LEARNING_TOOL_BACKEND": "invalid"}):
                with self.assertRaises(ValueError):
                    launcher.select_entrypoint(str(root))
            with patch.dict(os.environ, {}, clear=True):
                mode, entry = launcher.select_entrypoint(str(root))
                self.assertEqual(mode, "factory")


if __name__ == "__main__":
    unittest.main()
