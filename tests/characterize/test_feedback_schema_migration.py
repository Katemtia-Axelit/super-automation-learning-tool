"""M1.4B-3 J: server.schema.feedback task_completion_feedback migration.

Scope (LT_M1_4B3_FACTORY_FEEDBACK_SCHEMA_REPAIR_20261011_J):

- The original production schema for ``task_completion_feedback`` is
  authoritative in ``_archive/06_测试脚本/rebuild_tasks.py:180-182``:

      id INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id INTEGER NOT NULL,
      energy_after INTEGER,
      mood_after INTEGER,
      timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (task_id) REFERENCES tasks(id)

  ``server.schema.feedback.ensure_schema`` previously only created
  ``task_feedback_events``. ``server.repositories.feedback_repo.insert_completion_feedback``
  inserts into ``task_completion_feedback`` though, so the synthetic
  Factory — and any database that has not yet been initialized by the
  legacy rebuild script — fails POST /api/tasks/<id>/feedback with HTTP 500
  (no such table: task_completion_feedback). This test pins the schema
  behavior of ``ensure_schema`` for that table.

Contract:

- ``ensure_schema(conn)`` creates both tables (task_feedback_events and
  task_completion_feedback) when invoked on a database that has the
  ``tasks`` table but no feedback tables.
- Calling ``ensure_schema`` a second time on the same DB is a no-op for
  existing data: pre-existing rows are preserved verbatim.
- ``task_completion_feedback`` column shape matches the historical
  archive definition (id/task_id/energy_after/mood_after/timestamp).
- ``feedback_repo.insert_completion_feedback`` writes the row shape
  expected by POST /api/tasks/<id>/feedback (task_id, energy_after,
  mood_after, timestamp).

All fixtures are pure in-memory SQLite (``":memory:"``); no real
``data/task_publisher.db*``, ``src/notes/**``, ``config/config.json`` or
``.cursor/hooks/**`` are touched. The test does NOT spawn a subprocess.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

# Allow importing ``server.*`` modules from the project root.
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.schema.feedback import ensure_schema  # noqa: E402
from server.repositories import feedback_repo  # noqa: E402


def _create_tasks_table(conn: sqlite3.Connection) -> None:
    """Minimal ``tasks`` table so the FOREIGN KEY clause in feedback tables
    is satisfied when foreign_keys=ON. Schema mirrors what the real
    schema.ensure_all eventually creates; we only need the columns that
    feedback tables point to (tasks.id) to exist as INTEGER PRIMARY KEY.
    """
    conn.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            completed INTEGER DEFAULT 0,
            prerequisite_ids TEXT DEFAULT '[]',
            is_unlocked INTEGER DEFAULT 1
        )
        """
    )
    conn.commit()


def _seed_one_task(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (id, name) VALUES (?, ?)",
        (1, "synthetic-schema-task"),
    )
    conn.commit()
    return 1


def _column_names(conn: sqlite3.Connection, table: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


class TaskCompletionFeedbackSchemaTests(unittest.TestCase):
    """Pin the schema added by server.schema.feedback.ensure_schema."""

    def _new_conn(self) -> sqlite3.Connection:
        # Pure in-memory SQLite; nothing on disk.
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def test_ensure_schema_creates_task_completion_feedback(self):
        conn = self._new_conn()
        try:
            _create_tasks_table(conn)
            ensure_schema(conn)

            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='task_completion_feedback'"
            )
            row = cur.fetchone()
            self.assertIsNotNone(
                row,
                "ensure_schema() must create task_completion_feedback "
                "so the synthetic Factory POST /api/tasks/<id>/feedback "
                "no longer fails with no such table",
            )

            # Column shape must match the historical archive definition.
            cols = _column_names(conn, "task_completion_feedback")
            self.assertEqual(
                cols,
                ["id", "task_id", "energy_after", "mood_after", "timestamp"],
                "task_completion_feedback must mirror the archive schema",
            )

            # task_feedback_events must still be present (no regression).
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='task_feedback_events'"
            )
            self.assertIsNotNone(cur.fetchone())
            self.assertIn("created_at", _column_names(conn, "task_feedback_events"))
        finally:
            conn.close()

    def test_ensure_schema_is_idempotent_and_preserves_rows(self):
        conn = self._new_conn()
        try:
            _create_tasks_table(conn)
            task_id = _seed_one_task(conn)
            ensure_schema(conn)

            # Seed a row in task_completion_feedback as if it had been
            # written by the legacy production schema script. This
            # exercises the contract that pre-existing data survives a
            # subsequent ensure_schema() call.
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO task_completion_feedback "
                "(task_id, energy_after, mood_after, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (task_id, 5, 3, "2026-10-10T00:00:00"),
            )
            conn.commit()

            # Re-run ensure_schema. Must not drop / rename / truncate.
            ensure_schema(conn)

            cur.execute(
                "SELECT id, task_id, energy_after, mood_after, timestamp "
                "FROM task_completion_feedback WHERE task_id=?",
                (task_id,),
            )
            row = cur.fetchone()
            self.assertIsNotNone(
                row,
                "ensure_schema() must not destroy pre-existing rows "
                "in task_completion_feedback",
            )
            self.assertEqual(row[1], task_id)
            self.assertEqual(row[2], 5)
            self.assertEqual(row[3], 3)
            self.assertEqual(row[4], "2026-10-10T00:00:00")
        finally:
            conn.close()

    def test_feedback_repo_insert_writes_expected_shape(self):
        """End-to-end shape test: the real repo function must produce a
        row that the production /api/tasks/<id>/feedback handler expects.
        """
        conn = self._new_conn()
        try:
            _create_tasks_table(conn)
            ensure_schema(conn)
            task_id = _seed_one_task(conn)

            feedback_repo.insert_completion_feedback(
                conn,
                task_id=task_id,
                energy_after=7,
                mood_after=2,
            )

            cur = conn.cursor()
            cur.execute(
                "SELECT task_id, energy_after, mood_after "
                "FROM task_completion_feedback WHERE task_id=?",
                (task_id,),
            )
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], task_id)
            self.assertEqual(row[1], 7)
            self.assertEqual(row[2], 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)