"""Factory gacha ledger: each successful issuance must land in gacha_records.

Scope of this file (P0-C slice):

- POST /api/gacha/draw        -> +1 gacha_records row (accepted=0, refusal_reason=NULL)
- POST /api/gacha/care-draw   -> +1 gacha_records row (same shape as /draw)
- POST /api/gacha/multi-draw  -> +N rows where N == len(returned tasks)
- POST /api/gacha/replace when a replacement is actually issued -> +1 row
                              (the prior rejection row written by the route
                              stays intact and must not be counted as a
                              successful draw).
- POST /api/gacha/replace when no candidate is available -> 404 with
                              **zero** ledger side effects: M02-S03-G01
                              resolves the candidate before bookkeeping, so
                              no refusal row, no issuance row, no
                              `task_rejection_log` entry and no
                              `refusal_count` increment (never a fake
                              success and never a fake user refusal).

GET /api/gacha/statistics must also become truthful:

- `total_draws` and `by_pool` count ONLY issuance rows
  (rows whose `refusal_reason` IS NULL), so a replace that records
  both a refusal for the rejected id AND an issuance for the new id
  bumps total_draws by exactly 1 (and by_pool by exactly 1).
- `rejections` keeps counting rows from `task_rejection_log` (unchanged).
- `accepted` is left at 0 because users never explicitly accept a card
  in the synthetic harness; the route must not invent a non-zero value.

All mutations run inside disposable synthetic SQLite fixtures. No real
`data/task_publisher.db*`, `src/notes/**`, `config/config.json` or
`.cursor/hooks/**` are touched.
"""
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from sandbox_env import available_port, server
from test_http_characterization import make_fixture, request_json


# ---- synthetic seed -----------------------------------------------------
# Three eligible synthetic tasks tuned to exercise:
#   - pool auto-selection boundaries (15, 45)
#   - distinct IDs for multi-draw uniqueness
#   - a leftover candidate for /replace after one task is rejected
# Tasks 1..3 stay independent, not locked, not completed, not discarded.
def _seed_ledger(root: Path) -> Path:
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
                (1, "ledger-short-5", 5),
                (2, "ledger-medium-25", 25),
                (3, "ledger-long-90", 90),
            ],
        )
        # Wipe any pre-existing ledger rows so each test starts clean.
        db.execute("DELETE FROM gacha_records")
        db.execute("DELETE FROM task_rejection_log")
        db.commit()
    return db_path


def _total_draw_count(db_path: Path) -> int:
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT COALESCE(SUM(COALESCE(draw_count_today,0)),0) FROM tasks"
        ).fetchone()[0]


def _issuance_rows(db_path: Path):
    """Real issuance rows: refusal_reason IS NULL."""
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT task_id,pool_name,available_time,accepted,refusal_reason "
            "FROM gacha_records WHERE refusal_reason IS NULL "
            "ORDER BY id"
        ).fetchall()


def _refusal_rows(db_path: Path):
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT task_id,pool_name,available_time,accepted,refusal_reason "
            "FROM gacha_records WHERE refusal_reason IS NOT NULL "
            "ORDER BY id"
        ).fetchall()


# ---- the actual tests ---------------------------------------------------
class GachaStatisticsLedgerTests(unittest.TestCase):
    def test_single_and_care_draw_each_record_one_issuance(self):
        """Successful /draw and /care-draw must each insert ONE issuance row
        in gacha_records (accepted=0, refusal_reason=NULL), and that row
        must show up in /statistics.total_draws without inflating the
        historical refusal_count of the rejected task.
        """
        with TemporaryDirectory(prefix="lt_ledger_issuance_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = _seed_ledger(root)
            with server(root, "factory", port) as base:
                # /draw with time budget auto-selects the fragment pool.
                code, draw_body = request_json(base, "/api/gacha/draw", {
                    "available_time": 5,
                })
                self.assertEqual(code, 200, draw_body)
                self.assertEqual(draw_body["pool"], "fragment")

                # /care-draw with the same budget must also succeed.
                code, care_body = request_json(base, "/api/gacha/care-draw", {
                    "available_time": 25,
                })
                self.assertEqual(code, 200, care_body)
                self.assertEqual(care_body["pool"], "tomato")

                stats_code, stats = request_json(base, "/api/gacha/statistics")

            self.assertEqual(stats_code, 200, stats)
            # Both cards were successfully issued, none accepted yet.
            self.assertEqual(stats["total_draws"], 2, stats)
            self.assertEqual(stats["accepted"], 0, stats)
            # No refusal log entries -> rejections stays 0.
            self.assertEqual(stats["rejections"], 0, stats)
            # Two issuance rows, no refusal rows.
            issuance = _issuance_rows(db_path)
            refusals = _refusal_rows(db_path)
            self.assertEqual(len(issuance), 2, issuance)
            self.assertEqual(refusals, [], refusals)
            # Every row uses refused_reason=NULL, accepted=0, the chosen
            # pool, and a non-NULL available_time (legacy schema safety).
            for row in issuance:
                _id, pool, available, accepted, refusal = row
                self.assertIsNone(refusal, row)
                self.assertEqual(accepted, 0, row)
                self.assertIn(pool, ("fragment", "tomato"), row)
                self.assertIsNotNone(available, row)
                self.assertGreater(int(available), 0, row)
            # And the synthetic draw counters match the returned cards.
            self.assertEqual(_total_draw_count(db_path), 2)

    def test_multi_draw_records_one_row_per_returned_card(self):
        """Multi-draw must insert EXACTLY one gacha_records row per returned
        card (never zero, never duplicated), grouped separately from refusals.
        """
        with TemporaryDirectory(prefix="lt_ledger_multi_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = _seed_ledger(root)
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 30,
                    "count": 3,
                    "energy": "medium",
                })
                self.assertEqual(code, 200, body)
                returned_ids = [t["id"] for t in body["tasks"]]
                # The 30-minute budget can only fit task 1 (5m) and
                # task 2 (25m) -> 2 distinct cards, both within budget.
                self.assertGreaterEqual(len(returned_ids), 1, body)
                self.assertLessEqual(len(returned_ids), 3, body)
                self.assertEqual(len(returned_ids), len(set(returned_ids)), body)

                stats_code, stats = request_json(base, "/api/gacha/statistics")

            self.assertEqual(stats_code, 200, stats)
            self.assertEqual(stats["total_draws"], len(returned_ids), stats)
            self.assertEqual(stats["accepted"], 0, stats)
            # by_pool sums match total_draws so no row is double-counted.
            by_pool_sum = sum(int(p["cnt"]) for p in stats["by_pool"])
            self.assertEqual(by_pool_sum, len(returned_ids), stats)
            # gacha_records holds exactly len(returned_ids) issuance rows.
            issuance = _issuance_rows(db_path)
            self.assertEqual(len(issuance), len(returned_ids), issuance)
            self.assertEqual(_refusal_rows(db_path), [])
            # Synthetic draw counter delta equals len(returned_ids).
            self.assertEqual(_total_draw_count(db_path), len(returned_ids))

    def test_replacement_refusal_does_not_inflate_draw_stats(self):
        """Successful /replace must add exactly ONE issuance row for the
        new card, NOT one per recorded event (rejection of the old card
        + issuance of the new card would total 2). The historical refusal
        counter of the rejected task must stay intact.
        """
        with TemporaryDirectory(prefix="lt_ledger_replace_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = _seed_ledger(root)
            with server(root, "factory", port) as base:
                # Reject task 1, ask for a replacement that fits in 25.
                # `too_hard` is not in the Factory whitelist
                # (low_energy/no_time/similar_done/other); `low_energy` is
                # the semantically closest allowed literal.
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 1, "available_time": 25, "reason": "low_energy",
                })
                self.assertEqual(code, 200, body)
                new_id = body["task"]["id"]
                self.assertNotEqual(new_id, 1, body)

                stats_code, stats = request_json(base, "/api/gacha/statistics")

            self.assertEqual(stats_code, 200, stats)
            # One issuance (the new card), one refusal log entry. Crucially,
            # total_draws counts ONLY the issuance, not the refusal row.
            self.assertEqual(stats["total_draws"], 1, stats)
            self.assertEqual(stats["accepted"], 0, stats)
            self.assertEqual(stats["rejections"], 1, stats)
            # by_pool only has the issuance pool, summing to 1.
            by_pool_sum = sum(int(p["cnt"]) for p in stats["by_pool"])
            self.assertEqual(by_pool_sum, 1, stats)

            issuance = _issuance_rows(db_path)
            refusals = _refusal_rows(db_path)
            self.assertEqual(len(issuance), 1, issuance)
            self.assertEqual(len(refusals), 1, refusals)
            # The single issuance row is for the new task, not the rejected one.
            self.assertEqual(int(issuance[0][0]), new_id, issuance)
            self.assertEqual(int(refusals[0][0]), 1, refusals)
            self.assertEqual(refusals[0][4], "low_energy", refusals)
            # Refused task's counter still increments (existing semantics).
            with closing(sqlite3.connect(db_path)) as db:
                refusal_count = db.execute(
                    "SELECT refusal_count FROM tasks WHERE id=1"
                ).fetchone()[0]
            self.assertEqual(refusal_count, 1)

    def test_invalid_payload_and_no_eligible_produce_no_records(self):
        """Bad requests must never produce a fake successful issuance.

        - 400 invalid time-budget on /draw must not insert anything.
        - 404 no-candidate for /replace must not insert an issuance row
          **nor** any refusal side effect: M02-S03-G01 resolves the
          candidate before bookkeeping, so a failed replace never writes
          `task_rejection_log`, `refusal_count` or `gacha_records`.
        """
        with TemporaryDirectory(prefix="lt_ledger_invalid_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = _seed_ledger(root)
            with server(root, "factory", port) as base:
                # 400 path: out-of-range budget.
                code, body = request_json(base, "/api/gacha/draw", {
                    "available_time": 0,
                })
                self.assertEqual(code, 400, body)

                # /multi-draw with no eligible task (budget=4) -> 404.
                code, body = request_json(base, "/api/gacha/multi-draw", {
                    "available_time": 4, "count": 3,
                })
                self.assertEqual(code, 404, body)

                # /replace with no replacement available -> 404 with ZERO
                # ledger side effects (no refusal log, no refusal row).
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 1, "available_time": 5, "reason": "no_time",
                })
                self.assertEqual(code, 404, body)
                self.assertEqual(body["error"], "No replacement available")

                stats_code, stats = request_json(base, "/api/gacha/statistics")

            self.assertEqual(stats_code, 200, stats)
            # No successful issuance -> total_draws stays at 0.
            self.assertEqual(stats["total_draws"], 0, stats)
            self.assertEqual(stats["accepted"], 0, stats)
            # Zero side effects on the 404 replace path -> rejections stays 0.
            self.assertEqual(stats["rejections"], 0, stats)
            # And by_pool stays empty.
            self.assertEqual(stats["by_pool"], [], stats)

            issuance = _issuance_rows(db_path)
            refusals = _refusal_rows(db_path)
            self.assertEqual(issuance, [], issuance)
            self.assertEqual(refusals, [], refusals)
            self.assertEqual(_total_draw_count(db_path), 0)
            with closing(sqlite3.connect(db_path)) as db:
                log_rows = db.execute(
                    "SELECT COUNT(*) FROM task_rejection_log"
                ).fetchone()[0]
                refusal_count = db.execute(
                    "SELECT COALESCE(refusal_count,0) FROM tasks WHERE id=1"
                ).fetchone()[0]
            self.assertEqual(log_rows, 0, log_rows)
            self.assertEqual(refusal_count, 0, refusal_count)


if __name__ == "__main__":
    unittest.main()
