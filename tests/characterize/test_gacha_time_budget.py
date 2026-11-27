"""Available minutes must control Factory gacha eligibility and pool selection.

All mutations are contained in synthetic temporary SQLite fixtures.
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sandbox_env import available_port, server
from test_http_characterization import make_fixture, request_json


def seed_time_cases(root):
    db_path = root / "data" / "synthetic.sqlite3"
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("DELETE FROM task_dependencies")
        db.execute("DELETE FROM task_tags")
        db.execute("DELETE FROM tasks")
        db.executemany(
            """INSERT INTO tasks (id,name,estimated_time,category,priority,
                                   is_unlocked,completed,in_discard_pile)
               VALUES (?, ?, ?, 'daily', 5, 1, 0, 0)""",
            [(1, "short-8", 8), (2, "medium-25", 25), (3, "long-90", 90)],
        )
        db.commit()
    return db_path


class TimeBudgetDrawTests(unittest.TestCase):
    def test_draw_auto_pool_time_boundaries_and_fallback_to_shorter(self):
        with TemporaryDirectory(prefix="lt_time_auto_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            seed_time_cases(root)
            with server(root, "factory", port) as base:
                cases = [
                    (5, "fragment", 404, None),
                    (8, "fragment", 200, 1),
                    (15, "tomato", 200, 1),  # no tomato task fits; shorter is okay
                    (25, "tomato", 200, 2),
                    (45, "deep", 200, (1, 2)),  # either eligible shorter task is okay
                    (90, "deep", 200, 3),
                ]
                for minutes, expected_pool, status, expected_task in cases:
                    with self.subTest(minutes=minutes):
                        code, result = request_json(base, "/api/gacha/draw", {
                            "pool": "fragment",  # stale hidden selector must not override time
                            "available_time": minutes,
                        })
                        self.assertEqual(code, status, result)
                        if expected_task is not None:
                            self.assertEqual(result["pool"], expected_pool, result)
                            expected_ids = expected_task if isinstance(expected_task, tuple) else (expected_task,)
                            self.assertIn(result["task"]["id"], expected_ids, result)
                            self.assertLessEqual(result["task"]["estimated_time"], minutes)

    def test_care_draw_and_replace_respect_time_and_rejection(self):
        with TemporaryDirectory(prefix="lt_time_replace_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_time_cases(root)
            with server(root, "factory", port) as base:
                code, care = request_json(base, "/api/gacha/care-draw", {
                    "pool": "fragment", "available_time": 25,
                    "include_category": "daily",
                })
                self.assertEqual(code, 200, care)
                self.assertEqual(care["task"]["id"], 2)
                self.assertEqual(care["pool"], "tomato")

                code, too_short = request_json(base, "/api/gacha/replace", {
                    "task_id": 1, "pool": "fragment", "available_time": 5,
                    "reason": "no_time",
                })
                self.assertEqual(code, 404, too_short)
                # M02-S03-G01: `too_hard` is not in the Factory reason
                # whitelist (low_energy/no_time/similar_done/other); the
                # semantically closest allowed literal is `low_energy`.
                code, replacement = request_json(base, "/api/gacha/replace", {
                    "task_id": 1, "pool": "fragment", "available_time": 25,
                    "reason": "low_energy",
                })
                self.assertEqual(code, 200, replacement)
                self.assertEqual(replacement["reason"], "low_energy")
                self.assertEqual(replacement["task"]["id"], 2)
                self.assertLessEqual(replacement["task"]["estimated_time"], 25)
            with closing(sqlite3.connect(db_path)) as db:
                refusals = db.execute("SELECT refusal_count FROM tasks WHERE id=1").fetchone()[0]
                reasons = [r[0] for r in db.execute(
                    "SELECT reason FROM task_rejection_log ORDER BY id"
                ).fetchall()]
            # Only the successful replace is recorded; the earlier
            # candidate-less 404 left no refusal side effect behind.
            self.assertEqual(refusals, 1)
            self.assertEqual(reasons, ["low_energy"])

    def test_pool_detail_15_and_45_minute_boundaries(self):
        with TemporaryDirectory(prefix="lt_time_boundaries_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_time_cases(root)
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("UPDATE tasks SET estimated_time=15 WHERE id=1")
                db.execute("UPDATE tasks SET estimated_time=45 WHERE id=2")
                db.commit()
            with server(root, "factory", port) as base:
                code, pools = request_json(base, "/api/gacha/pools/detail")
                self.assertEqual(code, 200)
                pool_ids = {
                    key: {task["id"] for task in value["tasks"]}
                    for key, value in pools.items()
                }
                self.assertEqual(pool_ids["fragment"], set())
                self.assertEqual(pool_ids["tomato"], {1})
                self.assertEqual(pool_ids["deep"], {2, 3})

    def test_invalid_budget_rejected_without_draw_side_effect(self):
        with TemporaryDirectory(prefix="lt_time_invalid_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_time_cases(root)
            with server(root, "factory", port) as base:
                for minutes in (0, -1, 481, "abc", 25.5, None):
                    with self.subTest(minutes=minutes):
                        code, body = request_json(base, "/api/gacha/draw", {
                            "pool": "fragment", "available_time": minutes,
                        })
                        self.assertEqual(code, 400, body)
            with closing(sqlite3.connect(db_path)) as db:
                counts = db.execute("SELECT SUM(COALESCE(draw_count_today,0)) FROM tasks").fetchone()[0]
            self.assertEqual(counts, 0)


if __name__ == "__main__":
    unittest.main()
