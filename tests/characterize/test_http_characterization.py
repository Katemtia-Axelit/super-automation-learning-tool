"""Synthetic-only Legacy and Factory HTTP characterization (stdlib unittest)."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sandbox_env import available_port, materialize, seed, server


def request_json(base, path, data=None):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = Request(base + path, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def make_fixture(work: Path, port: int) -> Path:
    root = materialize(work / "runtime", port)
    seed(root)
    assert not (root / "src").exists()
    assert not (root / "data" / "task_publisher.db").exists()
    return root


class CharacterizationTests(unittest.TestCase):
    def test_tasks_and_dependency_unlock(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_tasks_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    blocked, body = request_json(base, "/api/tasks/2/complete", {})
                    self.assertEqual(blocked, 400, (mode, body))
                    status, completed = request_json(base, "/api/tasks/1/complete", {})
                    self.assertEqual(status, 200, (mode, completed))
                    self.assertEqual(completed["message"], "Task completed successfully")
                with closing(sqlite3.connect(root / "data" / "synthetic.sqlite3")) as db:
                    parent = db.execute("SELECT completed, success_rate FROM tasks WHERE id=1").fetchone()
                    child = db.execute("SELECT is_unlocked FROM tasks WHERE id=2").fetchone()
                self.assertEqual(parent[0], 1)
                if mode == "legacy":
                    self.assertEqual(child[0], 1)
                    self.assertIn("synthetic-child", completed["unlocked_tasks"])
                    self.assertAlmostEqual(parent[1], 0.1)
                else:
                    # Known gap: update to Legacy parity after the M2 fix.
                    self.assertEqual(child[0], 0)
                    self.assertEqual(completed["unlocked_tasks"], [])
                    self.assertAlmostEqual(parent[1], 0.0)

    def test_gacha_invalid_pool_no_data_change(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_gacha_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    status, result = request_json(base, "/api/gacha/draw", {"pool": "invalid-pool"})
                    self.assertEqual(status, 400, (mode, result))
                with closing(sqlite3.connect(root / "data" / "synthetic.sqlite3")) as db:
                    count = db.execute("SELECT SUM(draw_count_today) FROM tasks").fetchone()[0]
                self.assertEqual(count, 0)

    def test_copy_only_python_and_synthetic_data(self):
        with TemporaryDirectory(prefix="lt_copy_") as temp:
            root = make_fixture(Path(temp), available_port())
            self.assertTrue((root / "server" / "backend_api.py").is_file())
            self.assertTrue((root / "config" / "config.json").is_file())
            self.assertEqual(sorted(x.name for x in root.iterdir()),
                             ["config", "data", "server", "static", "vault"])
            with self.assertRaises(FileExistsError):
                materialize(root, available_port())


if __name__ == "__main__":
    unittest.main()
