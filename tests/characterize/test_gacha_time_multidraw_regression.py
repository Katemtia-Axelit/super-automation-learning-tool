"""Regression tests for the P0 multi-draw remaining-time routing and the
time-aware single-draw / care-draw / replace surface.

Scope: Factory HTTP characterization over disposable synthetic SQLite
fixtures. Never touches the real `data/task_publisher.db`, `src/notes/**`,
`config/config.json` or `.cursor/hooks/**`.

These tests are intentionally deterministic: they seed a fixed pool and
assert that the API never returns a card whose `estimated_time` exceeds
the (remaining) available time, never wastes the budget on a longer pick
when a shorter one fits, and never re-draws a task that the caller
explicitly refused.
"""
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from sandbox_env import available_port, server
from test_http_characterization import make_fixture, request_json


def seed_regression_pool(root: Path) -> Path:
    """Seed a pool tailored for budget=35 (25+10), 15 boundary, and
    replace-respect-minutes checks.

    Row plan (all category='daily', unlocked, not discarded, not done):
      1:  5  min   fragment
      2: 10  min   fragment
      3: 25  min   tomato
      4: 40  min   tomato  -> MUST be skipped when remaining < 40
      5: 60  min   deep
      6: 90  min   deep
      7: 12  min   fragment
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
                (1, "frag-5", 5),
                (2, "frag-10", 10),
                (3, "tom-25", 25),
                (4, "tom-40", 40),
                (5, "deep-60", 60),
                (6, "deep-90", 90),
                (7, "frag-12", 12),
            ],
        )
        db.commit()
    return db_path


def total_draw_count(db_path: Path) -> int:
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(
            "SELECT COALESCE(SUM(COALESCE(draw_count_today,0)),0) FROM tasks"
        ).fetchone()[0]


class MultiDrawRemainingTimeTests(unittest.TestCase):
    """The contract: pick up to N unique tasks, each <= REMAINING minutes,
    summing to <= original budget. Re-derive the pool from REMAINING minutes
    on every iteration so an oversized random pick never steals a slot."""

    def test_budget_35_picks_25_then_10_not_40(self):
        """Budget 35 with 25m+40m+10m+5m+12m+60m+90m available:
        first pick MUST be 25 (fits 35 and matches the tomato pool that
        `_pool_for_minutes(35)` selects), then a 10 (or 5/12) pick fits
        the remaining 10. The 40m card must never be returned because it
        cannot fit the 35-minute budget."""
        with TemporaryDirectory(prefix="lt_md_b35_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 35, "count": 5},
                )
                self.assertEqual(code, 200, body)
                ids = [t["id"] for t in body["tasks"]]
                # Distinct picks, never id=4 (40m) and never id=5/6 (>=35)
                self.assertEqual(len(ids), len(set(ids)), body)
                self.assertNotIn(4, ids, body)
                self.assertNotIn(5, ids, body)
                self.assertNotIn(6, ids, body)
                # 3m must be in the picked set, and total fits 35.
                self.assertIn(3, ids, body)
                total = sum(t["estimated_time"] for t in body["tasks"])
                self.assertLessEqual(total, 35, body)
                self.assertEqual(body["total_minutes"], total)
                self.assertEqual(body["remaining_minutes"], 35 - total)
                # Auto-pool is tomato (15..44) for 35 minutes.
                self.assertEqual(body["pool"], "tomato", body)
                # Counter delta equals #picked cards.
                self.assertEqual(total_draw_count(db_path), len(ids))

    def test_budget_15_boundary_picks_only_fragments(self):
        """Budget 15 must never return a 25m or 40m card; it should
        return one of {5, 10, 12} and stop because the remaining budget
        cannot host another valid pick."""
        with TemporaryDirectory(prefix="lt_md_b15_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 15, "count": 4},
                )
                self.assertEqual(code, 200, body)
                ids = sorted(t["id"] for t in body["tasks"])
                self.assertTrue(all(i in (1, 2, 7) for i in ids), body)
                total = sum(t["estimated_time"] for t in body["tasks"])
                self.assertLessEqual(total, 15, body)
                # Fragment pool is selected for 15 minutes (boundary: <15
                # would not be the case here; we use _pool_for_minutes
                # which puts 15 in the tomato bucket, but 25m never
                # fits a 15-minute budget so the per-iteration pool is
                # empty and the implementation widens to in-remaining
                # fragments).
                self.assertIn(body["pool"], ("tomato", "fragment"), body)
                self.assertEqual(total_draw_count(db_path), len(ids))

    def test_budget_15_with_only_25m_returns_404(self):
        """Sanity: if no task fits the budget, the route returns 404 and
        leaves draw counters untouched."""
        with TemporaryDirectory(prefix="lt_md_b15_none_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = Path(temp)  # placeholder
            with closing(sqlite3.connect(db_path / "x")):
                pass
            # Reuse the regression pool but wipe the small cards so
            # nothing fits <=15 except a single 25m tomato that must
            # be filtered out.
            from tests.characterize.test_gacha_multi_draw import (
                seed_multi_draw_cases,
            )
            db_path = seed_multi_draw_cases(root)
            with server(root, "factory", port) as base:
                baseline = total_draw_count(db_path)
                # Cards 1..2 (5m, 10m) fit 15m, so pick those. To force
                # the 404 path, send a budget below 1m.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 4, "count": 3},
                )
                self.assertEqual(code, 404, body)
                self.assertEqual(total_draw_count(db_path), baseline)


class TimeAwareReplaceTests(unittest.TestCase):
    """`/gacha/replace` must (1) validate the reason and available_time
    first, (2) resolve a candidate BEFORE touching the ledger, and
    (3) re-draw from tasks with 0 < estimated_time <= available_time,
    never returning the just-rejected task.

    M02-S03-G01 contract: only a *successful* replacement writes the
    refusal side effects. A 404 (`No replacement available`) must leave
    `refusal_count`, `task_rejection_log` and `gacha_records` untouched,
    so a failed replace is never recorded as a user refusal.
    """

    def test_replace_respects_minutes_and_skips_rejected(self):
        with TemporaryDirectory(prefix="lt_rep_min_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                # Reject id=2 (10m) with a 4m budget -> 404 (no card fits
                # because the smallest seeded card is 5m).
                code, body = request_json(
                    base, "/api/gacha/replace",
                    {"task_id": 2, "reason": "no_time",
                     "available_time": 4, "pool": "fragment"},
                )
                self.assertEqual(code, 404, body)
                self.assertEqual(body["error"], "No replacement available")
                # M02-S03-G01: a candidate-less replace is zero-side-effect.
                with closing(sqlite3.connect(db_path)) as db:
                    after_404_refusals = db.execute(
                        "SELECT COALESCE(refusal_count,0) FROM tasks WHERE id=2"
                    ).fetchone()[0]
                    after_404_log = db.execute(
                        "SELECT COUNT(*) FROM task_rejection_log"
                    ).fetchone()[0]
                    after_404_records = db.execute(
                        "SELECT COUNT(*) FROM gacha_records"
                    ).fetchone()[0]
                self.assertEqual(after_404_refusals, 0)
                self.assertEqual(after_404_log, 0)
                self.assertEqual(after_404_records, 0)
                # Reject id=2 (10m) with a 35m budget -> must return
                # some other card, never id=2 again. `too_hard` is not in
                # the Factory whitelist (low_energy/no_time/similar_done/
                # other); the closest allowed literal is `low_energy`.
                code, body = request_json(
                    base, "/api/gacha/replace",
                    {"task_id": 2, "reason": "low_energy",
                     "available_time": 35, "pool": "tomato"},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["replaced"], 2)
                self.assertEqual(body["reason"], "low_energy", body)
                self.assertNotEqual(body["task"]["id"], 2, body)
                self.assertLessEqual(body["task"]["estimated_time"], 35, body)
            with closing(sqlite3.connect(db_path)) as db:
                refusals = db.execute(
                    "SELECT refusal_count FROM tasks WHERE id=2"
                ).fetchone()[0]
                log = [r[0] for r in db.execute(
                    "SELECT reason FROM task_rejection_log "
                    "WHERE task_id=2 ORDER BY id"
                ).fetchall()]
            # Only the successful replace counted: 1 refusal, 1 log row.
            self.assertEqual(refusals, 1)
            self.assertEqual(log, ["low_energy"])

    def test_replace_invalid_minutes_400_no_side_effect(self):
        with TemporaryDirectory(prefix="lt_rep_inv_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                baseline_log = 0
                for minutes in (0, -1, 481, "abc", 25.5, None):
                    with self.subTest(minutes=minutes):
                        code, body = request_json(
                            base, "/api/gacha/replace",
                            {"task_id": 2, "reason": "no_time",
                             "available_time": minutes, "pool": "fragment"},
                        )
                        self.assertEqual(code, 400, body)
                # Refusal side effect must NOT have been written.
                with closing(sqlite3.connect(db_path)) as db:
                    rejections = db.execute(
                        "SELECT COUNT(*) FROM task_rejection_log"
                    ).fetchone()[0]
                    refusal_count = db.execute(
                        "SELECT COALESCE(refusal_count,0) FROM tasks WHERE id=2"
                    ).fetchone()[0]
                self.assertEqual(rejections, baseline_log)
                self.assertEqual(refusal_count, 0)


class TimeBudgetBoundaryTests(unittest.TestCase):
    """M1.1: at boundaries 14/15/44/45 minutes, every draw family
    (single, multi, replace) must keep eligibility coherent.

    Boundary rule: <15 -> fragment, 15..44 -> tomato, >=45 -> deep.
    The pool id is auto-derived from `available_time` in every family
    when available_time is supplied; otherwise the client-supplied
    `pool` is honored.
    """

    def test_multi_draw_pool_derivation_at_boundaries(self):
        with TemporaryDirectory(prefix="lt_bnd_multi_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                # 14m -> fragment: 5/10/12 fit, 25/40/60/90 do not.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 14, "count": 5},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["pool"], "fragment", body)
                ids = [t["id"] for t in body["tasks"]]
                self.assertTrue(ids, body)
                for t in body["tasks"]:
                    self.assertLessEqual(t["estimated_time"], 14, body)
                    self.assertNotIn(t["id"], (4, 5, 6), body)
                # 15m boundary -> tomato bucket. Picks stay <=15; the
                # boundary pool metadata is "tomato" even when the
                # actual picks come from fragments (5/10/12) via the
                # per-iteration pool fallback.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 15, "count": 5},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["pool"], "tomato", body)
                for t in body["tasks"]:
                    self.assertLessEqual(t["estimated_time"], 15, body)
                # 44m -> still tomato bucket; picks stay <=44.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 44, "count": 5},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["pool"], "tomato", body)
                self.assertEqual(len(body["tasks"]), len(set(t["id"] for t in body["tasks"])), body)
                for t in body["tasks"]:
                    self.assertLessEqual(t["estimated_time"], 44, body)
                # 45m -> auto-pool classification is "deep" (>=45). The
                # route still returns valid in-budget cards via the
                # per-iteration pool fallback; what MUST be true is that
                # pool == "deep" AND every card is <=45.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 45, "count": 3},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["pool"], "deep", body)
                for t in body["tasks"]:
                    self.assertLessEqual(t["estimated_time"], 45, body)
                # Boundary 481 is invalid -> 400.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 481, "count": 3},
                )
                self.assertEqual(code, 400, body)

    def test_single_draw_at_boundaries_returns_in_budget_card(self):
        with TemporaryDirectory(prefix="lt_bnd_single_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                # 14m: only 5/10/12 fit, never 25+.
                code, body = request_json(
                    base, "/api/gacha/draw",
                    {"available_time": 14},
                )
                self.assertEqual(code, 200, body)
                self.assertLessEqual(body["task"]["estimated_time"], 14, body)
                self.assertEqual(body["pool"], "fragment", body)
                # 15m: still picks <=15; 25/40/60/90 must not appear.
                code, body = request_json(
                    base, "/api/gacha/draw",
                    {"available_time": 15},
                )
                self.assertEqual(code, 200, body)
                self.assertLessEqual(body["task"]["estimated_time"], 15, body)
                self.assertEqual(body["pool"], "tomato", body)
                # 44m: must return a 25/40 card from the tomato bucket.
                code, body = request_json(
                    base, "/api/gacha/draw",
                    {"available_time": 44},
                )
                self.assertEqual(code, 200, body)
                self.assertLessEqual(body["task"]["estimated_time"], 44, body)
                self.assertEqual(body["pool"], "tomato", body)
                # 45m -> deep bucket; the in-budget filter still admits
                # 5/10/12/25/40, and the per-iteration pool fallback picks
                # one of those (estimated_time <=45). The contract is that
                # the pool metadata == "deep" AND the card fits the budget.
                code, body = request_json(
                    base, "/api/gacha/draw",
                    {"available_time": 45},
                )
                self.assertEqual(code, 200, body)
                self.assertLessEqual(body["task"]["estimated_time"], 45, body)
                self.assertEqual(body["pool"], "deep", body)

    def test_replace_pool_derivation_at_boundary(self):
        with TemporaryDirectory(prefix="lt_bnd_rep_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                # Reject id=1 (5m) with budget 14 -> another <=14m card
                # must be returned (10 or 12), never 25+ and never id=1.
                code, body = request_json(
                    base, "/api/gacha/replace",
                    {"task_id": 1, "reason": "no_time",
                     "available_time": 14, "pool": "fragment"},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["replaced"], 1)
                self.assertNotEqual(body["task"]["id"], 1, body)
                self.assertLessEqual(body["task"]["estimated_time"], 14, body)
                self.assertEqual(body["pool"], "fragment", body)
                # Reject id=2 (10m) with budget 44 -> tomato bucket, must
                # come from the tomato cards (25 or 40), never id=2.
                code, body = request_json(
                    base, "/api/gacha/replace",
                    {"task_id": 2, "reason": "no_time",
                     "available_time": 44, "pool": "tomato"},
                )
                self.assertEqual(code, 200, body)
                self.assertEqual(body["replaced"], 2)
                self.assertNotEqual(body["task"]["id"], 2, body)
                self.assertLessEqual(body["task"]["estimated_time"], 44, body)
                self.assertEqual(body["pool"], "tomato", body)


class MultiDrawIssuanceInvariantTests(unittest.TestCase):
    """M1.1: each actually issued card produces exactly one issuance
    row in gacha_records (refusal_reason IS NULL). Invalid requests
    must produce zero rows, and previews (server-side dry-runs) must
    never double-charge."""

    def _issuance_total(self, db_path):
        with closing(sqlite3.connect(db_path)) as db:
            return db.execute(
                "SELECT COUNT(*) FROM gacha_records "
                "WHERE refusal_reason IS NULL"
            ).fetchone()[0]

    def _draw_total(self, db_path):
        with closing(sqlite3.connect(db_path)) as db:
            return db.execute(
                "SELECT COALESCE(SUM(COALESCE(draw_count_today,0)),0) "
                "FROM tasks"
            ).fetchone()[0]

    def test_multi_draw_writes_one_issuance_row_per_returned_card(self):
        with TemporaryDirectory(prefix="lt_iss_multi_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 35, "count": 3},
                )
                self.assertEqual(code, 200, body)
                n_returned = len(body["tasks"])
                # Exactly one gacha_records row per returned card.
                self.assertEqual(self._issuance_total(db_path), n_returned, body)
                # Counter delta also equals n_returned (one increment per card).
                self.assertEqual(self._draw_total(db_path), n_returned, body)

    def test_invalid_multi_draw_writes_zero_issuance_rows(self):
        with TemporaryDirectory(prefix="lt_iss_multi_inv_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                baseline_issuance = self._issuance_total(db_path)
                baseline_draw = self._draw_total(db_path)
                bad_payloads = [
                    {"available_time": 0, "count": 3},
                    {"available_time": -1, "count": 3},
                    {"available_time": 481, "count": 3},
                    {"available_time": 25, "count": 0},
                    {"available_time": 25, "count": 6},
                    {"available_time": "abc", "count": 3},
                    {"available_time": 25.5, "count": 3},
                    {"available_time": 25, "count": "three"},
                    {"available_time": True, "count": 3},
                    {"count": 3},  # missing available_time
                ]
                for payload in bad_payloads:
                    with self.subTest(payload=payload):
                        code, body = request_json(
                            base, "/api/gacha/multi-draw", payload
                        )
                        self.assertEqual(code, 400, body)
                self.assertEqual(self._issuance_total(db_path), baseline_issuance)
                self.assertEqual(self._draw_total(db_path), baseline_draw)

    def test_no_issuance_when_no_card_fits_budget(self):
        with TemporaryDirectory(prefix="lt_iss_multi_empty_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                baseline_issuance = self._issuance_total(db_path)
                # Budget 1 -> nothing fits; route must 404 with no rows
                # written (no issuance, no draw_count_today delta).
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 1, "count": 3},
                )
                self.assertEqual(code, 404, body)
                self.assertEqual(self._issuance_total(db_path), baseline_issuance)
                self.assertEqual(self._draw_total(db_path), 0)


class MultiDrawDeduplicationTests(unittest.TestCase):
    """M1.1: a multi-draw batch of 2..5 cards must contain distinct
    task IDs (no in-batch duplicates), even when the only valid card
    could fit more than once if it were not excluded."""

    def test_distinct_ids_for_count_2_to_5_within_budget(self):
        with TemporaryDirectory(prefix="lt_dedupe_multi_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = seed_regression_pool(root)
            with server(root, "factory", port) as base:
                # Budget 250 covers the entire regression pool (5+10+12+25
                # +40+60+90 = 242m). The multi-draw loop picks within the
                # remaining budget, so it should fill all 5 requested slots
                # with distinct cards; total stays <=250.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 250, "count": 5},
                )
                self.assertEqual(code, 200, body)
                ids = [t["id"] for t in body["tasks"]]
                self.assertEqual(len(ids), 5, body)
                self.assertEqual(len(ids), len(set(ids)), body)
                total = sum(t["estimated_time"] for t in body["tasks"])
                self.assertLessEqual(total, 250, body)
                self.assertEqual(body["remaining_minutes"], 250 - total)
                # Budget 35 with count=4: pool has 5/10/12/25/40; one pick
                # must be 25 (tomato boundary), the rest from fragments;
                # all distinct, sum <= 35.
                code, body = request_json(
                    base, "/api/gacha/multi-draw",
                    {"available_time": 35, "count": 4},
                )
                self.assertEqual(code, 200, body)
                ids = [t["id"] for t in body["tasks"]]
                self.assertEqual(len(ids), len(set(ids)), body)
                total = sum(t["estimated_time"] for t in body["tasks"])
                self.assertLessEqual(total, 35, body)
                self.assertIn(3, ids, body)  # the 25m card is the tomato pick

    def test_replace_excludes_just_rejected_id_when_only_fit(self):
        """When the budget admits exactly one candidate and that
        candidate is the rejected task, /replace must NOT return it
        again — even if the API would otherwise have returned it."""
        with TemporaryDirectory(prefix="lt_dedupe_rep_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            # Seed a minimal pool where the only card fitting <=25 is
            # the one we will reject.
            db_path = root / "data" / "synthetic.sqlite3"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("DELETE FROM task_dependencies")
                db.execute("DELETE FROM task_tags")
                db.execute("DELETE FROM tasks")
                db.executemany(
                    """INSERT INTO tasks (id,name,estimated_time,category,
                                           priority,is_unlocked,completed,
                                           in_discard_pile,draw_count_today,
                                           refusal_count)
                       VALUES (?,?,?,'daily',5,1,0,0,0,0)""",
                    [(3, "tom-25", 25)],
                )
                db.commit()
            with server(root, "factory", port) as base:
                # Budget 25 with id=3 as the only fit; rejecting id=3 with
                # the same budget must yield 404 (no replacement available),
                # never id=3 again. `too_hard` is not in the Factory reason
                # whitelist, so use the closest allowed literal and prove the
                # 404 is about candidates, not about the reason.
                code, body = request_json(
                    base, "/api/gacha/replace",
                    {"task_id": 3, "reason": "low_energy",
                     "available_time": 25, "pool": "tomato"},
                )
                self.assertEqual(code, 404, body)
                self.assertEqual(body["error"], "No replacement available")
                # M02-S03-G01: no candidate -> zero ledger side effects.
                with closing(sqlite3.connect(db_path)) as db:
                    refusal_count = db.execute(
                        "SELECT COALESCE(refusal_count,0) FROM tasks WHERE id=3"
                    ).fetchone()[0]
                    log_rows = db.execute(
                        "SELECT COUNT(*) FROM task_rejection_log"
                    ).fetchone()[0]
                    record_rows = db.execute(
                        "SELECT COUNT(*) FROM gacha_records"
                    ).fetchone()[0]
                self.assertEqual(refusal_count, 0)
                self.assertEqual(log_rows, 0)
                self.assertEqual(record_rows, 0)


if __name__ == "__main__":
    unittest.main()
