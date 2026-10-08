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
                self.assertEqual(child[0], 1, mode)
                self.assertIn("synthetic-child", completed["unlocked_tasks"], mode)
                self.assertAlmostEqual(parent[1], 0.1, msg=mode)

    def test_skip_unlocks_without_success_rate_increment(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_skip_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    status, reply = request_json(base, "/api/tasks/3/skip", {})
                    self.assertEqual(status, 200, (mode, reply))
                    self.assertIn("synthetic-locked", reply["unlocked_tasks"])
                with closing(sqlite3.connect(root / "data" / "synthetic.sqlite3")) as db:
                    done, rate = db.execute(
                        "SELECT completed,success_rate FROM tasks WHERE id=3"
                    ).fetchone()
                    unlocked = db.execute(
                        "SELECT is_unlocked FROM tasks WHERE id=4"
                    ).fetchone()[0]
                self.assertEqual((done,unlocked), (1,1), mode)
                self.assertAlmostEqual(rate, 0.0, msg=mode)

    def test_create_task_writes_dependency_edge(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_create_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    status, created = request_json(base, "/api/tasks", {
                        "name":"synthetic-new-dependent",
                        "category":"daily",
                        "prerequisite_ids":[1],
                    })
                    self.assertEqual(status, 201, (mode, created))
                    child_id = created["id"]
                    dependent_status, dependents = request_json(
                        base, "/api/tasks/1/dependents"
                    )
                    self.assertEqual(dependent_status, 200, (mode, dependents))
                    self.assertIn(child_id, [r["id"] for r in dependents["dependents"]])
                with closing(sqlite3.connect(root / "data" / "synthetic.sqlite3")) as db:
                    edge = db.execute(
                        "SELECT count(*) FROM task_dependencies WHERE task_id=? AND depends_on_task_id=1",
                        (child_id,),
                    ).fetchone()[0]
                self.assertEqual(edge, 1, mode)

    def test_refuse_increments_synthetic_counter(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_refuse_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    status, response = request_json(base, "/api/tasks/1/refuse", {})
                    self.assertEqual(status, 200, (mode, response))
                with closing(sqlite3.connect(root / "data" / "synthetic.sqlite3")) as db:
                    count = db.execute(
                        "SELECT refusal_count FROM tasks WHERE id=1"
                    ).fetchone()[0]
                self.assertEqual(count, 1, mode)

    def test_ui_entrypoint_renders_synthetic_index(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_ui_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    with urlopen(base + "/", timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn("SYNTHETIC_ONLY_UI", response.read().decode("utf-8"))

    def test_remaining_legacy_api_coverage(self):
        endpoints = {
            "/api/config": dict,
            "/api/agent/agents": list,
            "/api/prompts": list,
            "/api/discard-pile": list,
            "/api/dependencies": dict,
        }
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_compat_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    for endpoint, expected_type in endpoints.items():
                        status, payload = request_json(base, endpoint)
                        self.assertEqual(status, 200, (mode, endpoint, payload))
                        self.assertIsInstance(payload, expected_type, (mode, endpoint))
                    if mode == "factory":
                        status, payload = request_json(
                            base, "/api/agent/save-note",
                            {"filename":"forbidden","content":"never write user notes"},
                        )
                        self.assertEqual(status, 403, payload)
                self.assertEqual(list((root / "vault").iterdir()), [])

    def test_gacha_draw_replace_and_statistics(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_replace_") as temp:
                port = available_port()
                root = make_fixture(Path(temp), port)
                with server(root, mode, port) as base:
                    status, detail = request_json(base, "/api/gacha/pools/detail")
                    self.assertEqual(status, 200, (mode, detail))
                    self.assertIn("tomato", detail)
                    self.assertIn("tasks", detail["tomato"])
                    status, draw = request_json(
                        base, "/api/gacha/draw",
                        {"pool":"tomato","energy":"medium"},
                    )
                    self.assertEqual(status, 200, (mode, draw))
                    self.assertEqual(draw["pool"], "tomato")
                    self.assertEqual(draw["can_replace"], True)
                    self.assertIn("id", draw["task"])
                    task_id = draw["task"]["id"]
                    status, replaced = request_json(
                        base, "/api/gacha/replace",
                        {"task_id":task_id, "pool":"tomato", "reason":"too_hard"},
                    )
                    self.assertEqual(status, 200, (mode, replaced))
                    self.assertEqual(replaced["replaced"], task_id)
                    self.assertEqual(replaced["reason"], "too_hard")
                    self.assertIn("task", replaced)
                    status, stats = request_json(base, "/api/gacha/statistics")
                    self.assertEqual(status, 200, (mode, stats))
                    self.assertEqual(stats["total_draws"], 1)
                    self.assertEqual(stats["rejections"], 1)
                    self.assertEqual(stats["accepted"], 0)
                with closing(sqlite3.connect(root / "data" / "synthetic.sqlite3")) as db:
                    row = db.execute(
                        "SELECT refusal_count,draw_count_today FROM tasks WHERE id=?",
                        (task_id,),
                    ).fetchone()
                    rejection = db.execute(
                        "SELECT reason FROM task_rejection_log WHERE task_id=?",
                        (task_id,),
                    ).fetchone()
                self.assertEqual(row[0], 1, mode)
                self.assertGreaterEqual(row[1], 1, mode)
                self.assertEqual(rejection[0], "too_hard", mode)

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
                             ["config", "data", "index.html", "server", "static", "vault"])
            with self.assertRaises(FileExistsError):
                materialize(root, available_port())


if __name__ == "__main__":
    unittest.main()
