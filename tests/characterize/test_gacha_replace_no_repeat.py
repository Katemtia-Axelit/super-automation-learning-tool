"""Factory replacement: explicit reason validation + no false ledger writes.

M02-S03-G01 contract exercised here (synthetic SQLite + Flask Factory only):

1. ``/api/gacha/replace`` requires an **explicit** allowed reason
   (``low_energy`` / ``no_time`` / ``similar_done`` / ``other``).
   Missing / blank / non-string / unknown reasons -> 400 and **zero**
   database side effects (no counter change, no ledger rows).
2. A failed replacement (no candidate after the current task, pool, time
   budget, category filters and draw selection) -> 404
   ``error='No replacement available'`` with **zero** ledger writes: the
   request is NOT recorded as a user rejection and NOT as an issuance.
3. A successful replacement -> exactly one ``task_rejection_log`` row with
   the selected reason, exactly one ``refusal_count`` increment on the
   replaced task, exactly one ``gacha_records`` refusal row for the
   replaced task, exactly one ``gacha_records`` issuance row for the new
   card, and exactly one ``draw_count_today`` increment for the new card.

Tests use a disposable synthetic SQLite and Flask Factory instance.
"""
import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

# The characterization harness modules (sandbox_env / test_http_characterization)
# live next to this file and are imported as top-level modules.
sys.path.append(str(Path(__file__).resolve().parent))

from sandbox_env import available_port, server
from test_http_characterization import make_fixture, request_json


#: The only reasons the backend accepts (must match the product contract).
ALLOWED_REASONS = ("low_energy", "no_time", "similar_done", "other")


def only_eligible(root: Path, ids):
    db_path = root / "data" / "synthetic.sqlite3"
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("DELETE FROM task_dependencies")
        db.execute("DELETE FROM task_tags")
        db.execute("DELETE FROM tasks")
        db.executemany(
            """INSERT INTO tasks (id,name,estimated_time,category,priority,
                       is_unlocked,completed,in_discard_pile)
                   VALUES (?, ?, 25, 'daily', 5, 1, 0, 0)""",
            [(i, f"synthetic-{i}") for i in ids],
        )
        db.commit()
    return db_path


def read_ledger(db_path):
    """Snapshot the three ledger surfaces the contract talks about."""
    with closing(sqlite3.connect(db_path)) as db:
        refusal_counts = dict(db.execute(
            "SELECT id, COALESCE(refusal_count, 0) FROM tasks"
        ).fetchall())
        draw_counts = dict(db.execute(
            "SELECT id, COALESCE(draw_count_today, 0) FROM tasks"
        ).fetchall())
        rejection_log = db.execute(
            "SELECT task_id, reason FROM task_rejection_log ORDER BY id"
        ).fetchall()
        gacha_rows = db.execute(
            "SELECT task_id, accepted, refusal_reason FROM gacha_records ORDER BY id"
        ).fetchall()
    return refusal_counts, draw_counts, rejection_log, gacha_rows


def read_hide_today_state(db_path):
    """Snapshot the "hide today" surfaces: discard flag + availability + completion.

    ``in_discard_pile`` / ``next_available_at`` belong to switch B, while
    ``completed`` / ``completed_count`` / ``last_completed_at`` must stay
    untouched because hiding a card is explicitly NOT completing it.
    """
    with closing(sqlite3.connect(db_path)) as db:
        db.row_factory = sqlite3.Row
        return {
            row["id"]: (
                row["in_discard_pile"],
                row["next_available_at"],
                row["completed"],
                row["completed_count"],
                row["last_completed_at"],
            )
            for row in db.execute(
                "SELECT id, in_discard_pile, next_available_at, completed, "
                "completed_count, last_completed_at FROM tasks"
            ).fetchall()
        }


class FactoryReplacementNoRepeat(unittest.TestCase):
    def test_single_candidate_exhausted_returns_404_without_any_ledger_write(self):
        """No replacement candidate -> 404 and NO ledger side effects.

        The failed request must not be recorded as a successful user
        rejection (no task_rejection_log row, no refusal_count increment,
        no gacha_records refusal row) and must not be recorded as an
        issuance either.
        """
        with TemporaryDirectory(prefix="lt_replace_only_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [20])
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 20, "pool": "tomato", "reason": "other"
                })
                self.assertEqual(code, 404, body)
                self.assertEqual(body["error"], "No replacement available")
            refusal_counts, draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            self.assertEqual(refusal_counts.get(20, 0), 0, refusal_counts)
            self.assertEqual(draw_counts.get(20, 0), 0, draw_counts)
            self.assertEqual(rejection_log, [], rejection_log)
            self.assertEqual(gacha_rows, [], gacha_rows)

    def test_missing_reason_returns_400_without_any_side_effect(self):
        """A missing reason is NOT defaulted to 'other'."""
        with TemporaryDirectory(prefix="lt_replace_noreason_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 10, "pool": "tomato"
                })
                self.assertEqual(code, 400, body)
                self.assertIn("error", body)
                self.assertIn("reason", body["error"])
            refusal_counts, draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            self.assertEqual(refusal_counts.get(10, 0), 0, refusal_counts)
            self.assertEqual(draw_counts.get(10, 0), 0, draw_counts)
            self.assertEqual(rejection_log, [], rejection_log)
            self.assertEqual(gacha_rows, [], gacha_rows)

    def test_invalid_reasons_return_400_without_any_side_effect(self):
        """Blank / non-string / unknown reasons are all rejected."""
        invalid_reasons = [
            "",              # blank
            "   ",           # whitespace only
            "too_hard",      # unknown legacy value
            "LOW_ENERGY",    # no case folding
            "other ",        # no trimming / no fuzzy match
            None,            # non-string
            123,             # non-string
            True,            # non-string (bool)
            ["other"],       # non-string
            {"reason": "other"},  # non-string
        ]
        with TemporaryDirectory(prefix="lt_replace_badreason_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                for reason in invalid_reasons:
                    with self.subTest(reason=reason):
                        code, body = request_json(base, "/api/gacha/replace", {
                            "task_id": 10, "pool": "tomato", "reason": reason
                        })
                        self.assertEqual(code, 400, (reason, body))
                        self.assertIn("error", body)
                        self.assertIn("reason", body["error"])
            refusal_counts, draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            self.assertEqual(refusal_counts.get(10, 0), 0, refusal_counts)
            self.assertEqual(draw_counts.get(10, 0), 0, draw_counts)
            self.assertEqual(rejection_log, [], rejection_log)
            self.assertEqual(gacha_rows, [], gacha_rows)

    def test_two_candidates_replace_returns_the_other_candidate(self):
        """A successful replacement records exactly the expected writes."""
        with TemporaryDirectory(prefix="lt_replace_two_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                for rejected_id, expected_id in ((10, 11), (11, 10)):
                    code, body = request_json(base, "/api/gacha/replace", {
                        "task_id": rejected_id, "pool": "tomato",
                        "reason": "low_energy" if rejected_id == 10 else "no_time",
                    })
                    self.assertEqual(code, 200, body)
                    self.assertEqual(body["replaced"], rejected_id)
                    self.assertEqual(body["reason"],
                                     "low_energy" if rejected_id == 10 else "no_time")
                    self.assertEqual(body["task"]["id"], expected_id, body)
            refusal_counts, draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            # One refusal_count increment per replaced task.
            self.assertEqual(refusal_counts.get(10), 1, refusal_counts)
            self.assertEqual(refusal_counts.get(11), 1, refusal_counts)
            # Exactly one draw_count_today increment per issued card.
            self.assertEqual(draw_counts.get(10), 1, draw_counts)
            self.assertEqual(draw_counts.get(11), 1, draw_counts)
            # One rejection-log row per replaced task, with its reason.
            self.assertEqual(rejection_log, [(10, "low_energy"), (11, "no_time")],
                             rejection_log)
            # One refusal row + one issuance row per replacement.
            self.assertEqual(len(gacha_rows), 4, gacha_rows)
            refusals = [r for r in gacha_rows if r[2] is not None]
            issuances = [r for r in gacha_rows if r[2] is None]
            self.assertEqual(len(refusals), 2, gacha_rows)
            self.assertEqual(len(issuances), 2, gacha_rows)
            self.assertEqual(
                sorted((r[0], r[2]) for r in refusals),
                [(10, "low_energy"), (11, "no_time")], gacha_rows)
            self.assertEqual(sorted(r[0] for r in issuances), [10, 11], gacha_rows)
            self.assertTrue(all(r[1] == 0 for r in gacha_rows), gacha_rows)

    def test_every_allowed_reason_is_accepted(self):
        """Each whitelisted reason is accepted verbatim and stored as-is."""
        with TemporaryDirectory(prefix="lt_replace_reasons_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                for index, reason in enumerate(ALLOWED_REASONS):
                    rejected_id = 10 if index % 2 == 0 else 11
                    code, body = request_json(base, "/api/gacha/replace", {
                        "task_id": rejected_id, "pool": "tomato", "reason": reason
                    })
                    self.assertEqual(code, 200, (reason, body))
                    self.assertEqual(body["reason"], reason, (reason, body))
            refusal_counts, _draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            self.assertEqual([row[1] for row in rejection_log], list(ALLOWED_REASONS),
                             rejection_log)
            self.assertEqual(
                sorted(r[2] for r in gacha_rows if r[2] is not None),
                sorted(ALLOWED_REASONS), gacha_rows)
            self.assertEqual(refusal_counts.get(10), 2, refusal_counts)
            self.assertEqual(refusal_counts.get(11), 2, refusal_counts)


    # ==============================================================
    # M02-S03-G01-W04 — continuous replace chain + the two switches
    # ==============================================================
    def test_exhausted_chain_without_allow_repeat_returns_404_and_no_ledger(self):
        """Chain exhausted -> 404, zero ledger writes, no hide side effect.

        Two eligible tasks only. Replacing 10 yields 11. The user then
        replaces 11 while switch A (``allow_repeat_replaced``) is off and
        the chain already contains 10 -> both tasks are excluded -> no
        candidate. Nothing may be logged and nothing may be hidden.
        """
        with TemporaryDirectory(prefix="lt_chain_exhaust_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 10, "pool": "tomato", "reason": "other",
                    "replaced_task_ids": [], "allow_repeat_replaced": False,
                })
                self.assertEqual(code, 200, body)
                self.assertEqual(body["task"]["id"], 11, body)
                before = read_ledger(db_path)
                hide_before = read_hide_today_state(db_path)
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 11, "pool": "tomato", "reason": "no_time",
                    "replaced_task_ids": [10],
                    "allow_repeat_replaced": False,
                    "hide_today": True,
                })
                self.assertEqual(code, 404, body)
                self.assertEqual(body["error"], "No replacement available")
            after = read_ledger(db_path)
            self.assertEqual(after, before, "failed chain replace must not write ledger")
            self.assertEqual(read_hide_today_state(db_path), hide_before,
                             "failed chain replace must not hide anything")

    def test_allow_repeat_lets_a_previously_replaced_card_come_back(self):
        """Switch A on -> the previous chain card is drawable again.

        The **current** task_id is still always excluded, so with only two
        eligible tasks the redraw can only be the previously replaced 10.
        """
        with TemporaryDirectory(prefix="lt_chain_repeat_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 10, "pool": "tomato", "reason": "other",
                    "replaced_task_ids": [], "allow_repeat_replaced": True,
                })
                self.assertEqual(code, 200, body)
                self.assertEqual(body["task"]["id"], 11, body)
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 11, "pool": "tomato", "reason": "low_energy",
                    "replaced_task_ids": [10],
                    "allow_repeat_replaced": True,
                })
                self.assertEqual(code, 200, body)
                self.assertEqual(body["task"]["id"], 10, body)
                self.assertEqual(body["replaced"], 11, body)

    def test_hide_today_hides_only_on_success_and_never_completes(self):
        """Switch B writes in_discard_pile/next_available_at, never completion."""
        with TemporaryDirectory(prefix="lt_chain_hide_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            before = read_hide_today_state(db_path)
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 10, "pool": "tomato", "reason": "similar_done",
                    "hide_today": True,
                })
                self.assertEqual(code, 200, body)
                self.assertEqual(body["task"]["id"], 11, body)
                # The hidden card is gone from the candidate pool: replacing
                # 11 can no longer produce 10.
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 11, "pool": "tomato", "reason": "other",
                    "allow_repeat_replaced": True,
                })
                self.assertEqual(code, 404, body)
            after = read_hide_today_state(db_path)
            hidden = after[10]
            self.assertEqual(hidden[0], 1, "in_discard_pile must be 1")
            self.assertIsNotNone(hidden[1], "next_available_at must be set")
            self.assertGreater(hidden[1], before[10][1] or "", hidden[1])
            # Hiding is NOT completing: these three fields must not move.
            self.assertEqual(hidden[2], before[10][2], "completed must not change")
            self.assertEqual(hidden[3], before[10][3], "completed_count must not change")
            self.assertEqual(hidden[4], before[10][4], "last_completed_at must not change")
            self.assertEqual(after[11], before[11],
                             "the newly issued card must not be hidden")

    def test_hide_today_false_leaves_the_card_drawable(self):
        """Without switch B the replaced card keeps no hide side effect."""
        with TemporaryDirectory(prefix="lt_chain_nohide_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            before = read_hide_today_state(db_path)
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 10, "pool": "tomato", "reason": "other",
                    "hide_today": False, "allow_repeat_replaced": True,
                })
                self.assertEqual(code, 200, body)
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 11, "pool": "tomato", "reason": "other",
                    "replaced_task_ids": [10], "allow_repeat_replaced": True,
                })
                self.assertEqual(code, 200, body)
                self.assertEqual(body["task"]["id"], 10, body)
            self.assertEqual(read_hide_today_state(db_path), before,
                             "hide_today=false must not touch the discard surfaces")

    def test_invalid_new_fields_return_400_without_any_side_effect(self):
        """Type-invalid new fields are rejected before any write."""
        invalid_payloads = [
            {"replaced_task_ids": "10"},
            {"replaced_task_ids": {"10": True}},
            {"replaced_task_ids": [True]},
            {"replaced_task_ids": ["10"]},
            {"replaced_task_ids": [None]},
            {"allow_repeat_replaced": "true"},
            {"allow_repeat_replaced": 1},
            {"allow_repeat_replaced": None},
            {"hide_today": "yes"},
            {"hide_today": 0},
        ]
        with TemporaryDirectory(prefix="lt_chain_badfields_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                for extra in invalid_payloads:
                    with self.subTest(extra=extra):
                        payload = {"task_id": 10, "pool": "tomato", "reason": "other"}
                        payload.update(extra)
                        code, body = request_json(base, "/api/gacha/replace", payload)
                        self.assertEqual(code, 400, (extra, body))
                        self.assertIn("error", body)
            refusal_counts, draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            self.assertEqual(refusal_counts.get(10, 0), 0, refusal_counts)
            self.assertEqual(refusal_counts.get(11, 0), 0, refusal_counts)
            self.assertEqual(draw_counts.get(10, 0), 0, draw_counts)
            self.assertEqual(draw_counts.get(11, 0), 0, draw_counts)
            self.assertEqual(rejection_log, [], rejection_log)
            self.assertEqual(gacha_rows, [], gacha_rows)

    def test_new_fields_are_optional_for_backward_compatibility(self):
        """Legacy callers (no new fields) still get the existing behaviour."""
        with TemporaryDirectory(prefix="lt_chain_legacy_") as temp:
            port = available_port()
            root = make_fixture(Path(temp), port)
            db_path = only_eligible(root, [10, 11])
            with server(root, "factory", port) as base:
                code, body = request_json(base, "/api/gacha/replace", {
                    "task_id": 10, "pool": "tomato", "reason": "other",
                })
                self.assertEqual(code, 200, body)
                self.assertEqual(body["task"]["id"], 11, body)
            refusal_counts, draw_counts, rejection_log, gacha_rows = read_ledger(db_path)
            self.assertEqual(refusal_counts.get(10), 1, refusal_counts)
            self.assertEqual(draw_counts.get(11), 1, draw_counts)
            self.assertEqual(rejection_log, [(10, "other")], rejection_log)
            self.assertEqual(len(gacha_rows), 2, gacha_rows)


if __name__ == "__main__":
    unittest.main()
