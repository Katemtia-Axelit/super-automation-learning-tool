"""Multi-draw must return a bounded set of distinct tasks that fit the budget.

Factory-only slice; all mutations are kept inside a synthetic temporary SQLite
fixture so the real data/task_publisher.db, src/notes/**, config/config.json
and .cursor/hooks/** stay untouched. Draw counters must increment exactly once
per returned card, and rejected requests must leave counters untouched.
"""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sandbox_env import available_port, server
from test_http_characterization import make_fixture, request_json


def seed_multi_draw_cases(root):
    """Seed a deterministic pool that exercises distinct cards, fallback,
    partial selections and invalid-request side effects.

    Schema mirrors sandbox_env.seed() but is tailored for multi-draw:
    - row 1: very-short fragment (5 min)
    - row 2: short fragment (10 min)        -> fits inside a 15-min budget
    - row 3: medium tomato (25 min)
    - row 4: long tomato (40 min)
    - row 5: deep (90 min)
    - row 6: completed (excluded)
    - row 7: locked (excluded)
    - row 8: in discard pile (excluded)
    """
    db_path = root / "data" / "synthetic.sqlite3"
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("DELETE FROM task_dependencies")
        db.execute("DELETE FROM task_tags")
        db.execute("DELETE FROM tasks")
        db.executemany(
            """INSERT INTO tasks (id,name,estimated_time,category,priority,
                                   is_unlocked,completed,in_discard_pile,
                                   draw_count_today,refusal_count)
               VALUES (?, ?, ?, 'daily', 5, 1, 0, 0, 0, 0)""",
            [
                (1, "very-short-5", 5),
                (2, "short-10", 10),
                (3, "medium-25", 25),
                (4, "long-40", 40),
                (5, "deep-90", 90),
                (6, "completed-30", 30),
                (7, "locked-20", 20),
                (8, "discarded-12", 12),
            ],
        )
        db.execute("UPDATE tasks SET completed=1 WHERE id=6")
        db.execute("UPDATE tasks SET is_unlocked=0 WHERE id=7")
        db.execute("UPDATE tasks SET in_discard_pile=1 WHERE id=8")
        db.commit()
    return db_path


def total_draw_count(db_path):
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT COALESCE(SUM(COALESCE(draw_count_today,0)),0) FROM tasks"
        ).fetchone()[0]


class MultiDrawTests(unittest.TestCase):
    def test_budget_uniqueness_and_shorter_fallback(self):
        """Multi-draw must pack up to count distinct cards whose total time
        fits the budget; if no card in the strict pool fits, it must fall
        back to a strictly shorter valid card without duplicating.
        """
        with TemporaryDirectory(prefix="lt_multi_budget_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_multi_draw_cases(root)
            with server(root, "factory", port) as base:
                # Budget 15: only tasks 1 (5m) and 2 (10m) fit strictly.
                # The auto-pool is "tomato" (15 <= t < 45) but no task in
                # that strict range fits, so _filter_pool falls back to
                # the in-budget tasks.
                before = total_draw_count(db_path)
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 15,
                    "count": 3,
                    "energy": "medium",
                })
                self.assertEqual(code, 200, body)
                # The auto-selected pool is "tomato" by time boundary; the
                # fallback path returns the strictly-shorter valid cards.
                self.assertIn(body["pool"], ("tomato", "fragment"), body)
                tasks = body["tasks"]
                ids = [t["id"] for t in tasks]
                # distinct cards
                self.assertEqual(len(ids), len(set(ids)), body)
                # at most count and at least 1
                self.assertGreaterEqual(len(tasks), 1)
                self.assertLessEqual(len(tasks), 3)
                # every card must be strictly within budget
                total = sum(t["estimated_time"] for t in tasks)
                self.assertLessEqual(total, 15, body)
                self.assertEqual(body["total_minutes"], total)
                self.assertEqual(body["remaining_minutes"], 15 - total)
                # Only ids 1 and 2 are valid candidates; no duplicates.
                for tid in ids:
                    self.assertIn(tid, (1, 2), body)
                # Counter delta from this call must equal #returned cards.
                self.assertEqual(
                    total_draw_count(db_path) - before, len(ids)
                )

                # Budget 20: strict fragment + tomato (15-45) pool has only
                # card 1 (5m) and 2 (10m). A second card must come from
                # the shorter fallback path without ever exceeding 20.
                before = total_draw_count(db_path)
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 20,
                    "count": 2,
                })
                self.assertEqual(code, 200, body)
                ids = [t["id"] for t in body["tasks"]]
                self.assertEqual(len(ids), len(set(ids)), body)
                self.assertLessEqual(len(body["tasks"]), 2)
                self.assertLessEqual(body["total_minutes"], 20)
                for t in body["tasks"]:
                    self.assertLessEqual(t["estimated_time"], 20)
                # Counter delta from this call must equal #returned cards.
                after = total_draw_count(db_path)
                self.assertEqual(after - before, len(ids))

    def test_partial_exhausted_and_eligibility_filters(self):
        """If fewer than count cards fit, return the partial valid list;
        if zero fit, return 404. Completed/locked/discarded cards must be
        excluded by the eligibility filter.
        """
        with TemporaryDirectory(prefix="lt_multi_partial_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_multi_draw_cases(root)
            with server(root, "factory", port) as base:
                # Budget 25: only 5 + 10 + 25 fit strictly -> partial of 2.
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 25,
                    "count": 5,
                })
                self.assertEqual(code, 200, body)
                ids = [t["id"] for t in body["tasks"]]
                self.assertGreaterEqual(len(ids), 1)
                self.assertLess(len(ids), 5, body)
                self.assertEqual(len(ids), len(set(ids)))
                # Sum still inside budget
                self.assertLessEqual(body["total_minutes"], 25)
                # Eligibility excludes completed (6), locked (7), discarded (8)
                for tid in ids:
                    self.assertNotIn(tid, (6, 7, 8), body)
                # Partial return increments counter exactly per card.
                self.assertEqual(total_draw_count(db_path), len(ids))

                # Budget 4: nothing fits -> 404, no counters change.
                baseline = total_draw_count(db_path)
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 4,
                    "count": 3,
                })
                self.assertEqual(code, 404, body)
                self.assertEqual(total_draw_count(db_path), baseline)

                # Budget 480 with default count=3: at least one valid card.
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 480,
                })
                self.assertEqual(code, 200, body)
                self.assertLessEqual(len(body["tasks"]), 3)
                # Pool must be "deep" for 480 minutes
                self.assertEqual(body["pool"], "deep")

    def test_invalid_requests_do_not_mutate_counters(self):
        """Bad count / time must return 400 and zero draw-counter side-effects.

        Also asserts that the multi-draw path is not silently aliasing
        single-draw: counters before == counters after a 400.
        """
        with TemporaryDirectory(prefix="lt_multi_invalid_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_multi_draw_cases(root)
            with server(root, "factory", port) as base:
                baseline = total_draw_count(db_path)
                cases = [
                    {"available_time": 0, "count": 3},
                    {"available_time": -5, "count": 3},
                    {"available_time": 481, "count": 3},
                    {"available_time": 25, "count": 0},
                    {"available_time": 25, "count": 6},
                    {"available_time": 25, "count": -1},
                    {"available_time": "abc", "count": 3},
                    {"available_time": 25.5, "count": 3},
                    {"available_time": 25, "count": "three"},
                ]
                for payload in cases:
                    with self.subTest(payload=payload):
                        code, body = request_json(
                            base, "/api/gacha/multi-draw", payload
                        )
                        self.assertEqual(code, 400, body)
                # No counter drift across all invalid payloads
                self.assertEqual(total_draw_count(db_path), baseline)

                # Missing available_time is also a validation error
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "count": 3,
                })
                self.assertEqual(code, 400, body)
                self.assertEqual(total_draw_count(db_path), baseline)


if __name__ == "__main__":
    unittest.main()