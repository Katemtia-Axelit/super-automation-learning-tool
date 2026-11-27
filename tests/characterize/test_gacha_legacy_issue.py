"""Factory gacha path must record an issuance row even when no available_time is supplied.

Root product gap (P0): Factory /api/gacha/draw used to log a successful
issuance ONLY when `available_time` was present in the request. Legacy
callers (and the existing
test_http_characterization::test_gacha_draw_replace_and_statistics
sequence that POSTs `{"pool":"tomato","energy":"medium"}` without an
`available_time`) therefore slipped a successfully issued card past
the gacha_records ledger, which made /statistics under-report and the
acceptance_rate metric useless.

Required semantics (this file proves them in isolation):

  1. Factory `/api/gacha/draw` with NO `available_time` -> exactly one
     gacha_records issuance row (refusal_reason IS NULL, accepted = 0).
  2. Factory `/api/gacha/replace` of that card -> exactly one MORE
     issuance row for the new card, AND one refusal row for the
     rejected task_id.
  3. Factory `/api/gacha/statistics` MUST count only issuance rows
     (refusal rows are NOT a draw), so after /draw + /replace the
     total_draws is exactly 2 (1 from draw + 1 from replace) and
     rejections is exactly 1. `accepted` stays at 0 because the
     synthetic harness never marks user-acceptance.

Legacy mode is intentionally NOT exercised here; the legacy backend_api
draw path is out of scope for this slice, and the existing shared
characterization test already pins the legacy value at total_draws == 1.

All mutations live in a fresh synthetic SQLite fixture under a temp
directory; no real data/task_publisher.db*, src/notes/**,
config/config.json or .cursor/hooks/** are ever touched.
"""
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from sandbox_env import available_port, server
from test_http_characterization import make_fixture, request_json


# --- synthetic seed --------------------------------------------------------
# Three tomato-eligible tasks so /draw always succeeds and /replace has at
# least one candidate after the first card is rejected.
def _seed(root: Path) -> Path:
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
                (1, "legacy-issue-tomato-25-a", 25),
                (2, "legacy-issue-tomato-25-b", 25),
                (3, "legacy-issue-tomato-25-c", 25),
            ],
        )
        # Clean ledger so this test owns the counts it asserts on.
        db.execute("DELETE FROM gacha_records")
        db.execute("DELETE FROM task_rejection_log")
        db.commit()
    return db_path


def _issuance_rows(db_path: Path):
    """Successful issuance rows: refusal_reason IS NULL."""
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT task_id,pool_name,available_time,accepted,refusal_reason "
            "FROM gacha_records WHERE refusal_reason IS NULL ORDER BY id"
        ).fetchall()


def _refusal_rows(db_path: Path):
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT task_id,pool_name,available_time,accepted,refusal_reason "
            "FROM gacha_records WHERE refusal_reason IS NOT NULL ORDER BY id"
        ).fetchall()


class FactoryLegacyCompatIssueTests(unittest.TestCase):
    def test_no_budget_factory_draw_writes_one_issuance(self):
        """Factory /api/gacha/draw with NO available_time must write exactly
        one issuance row to gacha_records, paired with the draw_count_today
        increment. The historical refusal_reason stays NULL (this is a real
        issued card, not a refusal)."""
        with TemporaryDirectory(prefix="lt_factory_no_budget_draw_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = _seed(root)
            with server(root, "factory", port) as base:
                code, body = request_json(
                    base, "/api/gacha/draw",
                    {"pool": "tomato", "energy": "medium"},
                )
            self.assertEqual(code, 200, body)
            self.assertEqual(body["pool"], "tomato")
            self.assertIn("task", body)
            drawn_id = body["task"]["id"]

            issuance = _issuance_rows(db_path)
            refusals = _refusal_rows(db_path)
            # Exactly one real issuance, no refusal rows.
            self.assertEqual(len(issuance), 1, issuance)
            self.assertEqual(refusals, [], refusals)
            row = issuance[0]
            # (task_id, pool_name, available_time, accepted, refusal_reason)
            self.assertEqual(int(row[0]), drawn_id, row)
            self.assertEqual(row[1], "tomato", row)
            # Legacy-compat: available_time may legitimately be NULL because
            # the caller did not supply one; we must not assume 30/0.
            self.assertIsNone(row[2], row)
            self.assertEqual(int(row[3]), 0, row)
            self.assertIsNone(row[4], row)

    def test_no_budget_draw_plus_replace_yields_two_iss_and_one_refusal(self):
        """Factory /draw (no available_time) followed by /replace of the
        drawn card must produce exactly:
          - 2 issuance rows (the drawn card + the replacement card)
          - 1 refusal row  (the just-rejected task_id from /replace)
        /statistics MUST count only the 2 issuance rows, so total_draws=2
        and rejections=1. accepted stays 0."""
        with TemporaryDirectory(prefix="lt_factory_no_budget_replace_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = _seed(root)
            with server(root, "factory", port) as base:
                code, draw = request_json(
                    base, "/api/gacha/draw",
                    {"pool": "tomato", "energy": "medium"},
                )
                self.assertEqual(code, 200, draw)
                first_id = draw["task"]["id"]

                code, repl = request_json(
                    base, "/api/gacha/replace",
                    {"task_id": first_id, "pool": "tomato",
                     "reason": "low_energy"},
                )
                self.assertEqual(code, 200, repl)
                self.assertEqual(repl["replaced"], first_id)
                self.assertEqual(repl["reason"], "low_energy", repl)
                second_id = repl["task"]["id"]
                self.assertNotEqual(second_id, first_id)

                stats_code, stats = request_json(base, "/api/gacha/statistics")

            self.assertEqual(stats_code, 200, stats)
            # Truthful stats: 2 issued cards, 1 rejection log entry.
            self.assertEqual(stats["total_draws"], 2, stats)
            self.assertEqual(stats["accepted"], 0, stats)
            self.assertEqual(stats["rejections"], 1, stats)
            # by_pool sums to total_draws (no double-count, no missing).
            by_pool_sum = sum(int(p["cnt"]) for p in stats["by_pool"])
            self.assertEqual(by_pool_sum, 2, stats)

            issuance = _issuance_rows(db_path)
            refusals = _refusal_rows(db_path)
            self.assertEqual(len(issuance), 2, issuance)
            self.assertEqual(len(refusals), 1, refusals)
            issuance_task_ids = {int(r[0]) for r in issuance}
            self.assertEqual(
                issuance_task_ids, {first_id, second_id}, issuance,
            )
            # The single refusal row must reference the rejected card only,
            # and must store the explicit Factory reason verbatim.
            self.assertEqual(int(refusals[0][0]), first_id, refusals)
            self.assertEqual(refusals[0][4], "low_energy", refusals)
            # Refusal row must NOT inflate any pool tally.
            pool_names_in_issuance = {r[1] for r in issuance}
            self.assertEqual(pool_names_in_issuance, {"tomato"})


if __name__ == "__main__":
    unittest.main()