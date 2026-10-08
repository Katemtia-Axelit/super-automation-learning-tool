"""server.schema.tasks — task tables + dependency schema + indexes.

Migration of the legacy `ensure_task_dependency_schema()` + `ensure_indexes()`.

Why these go together: both functions touch the same `tasks` table and the
related `task_dependencies` / `task_tags` tables, so combining them keeps
the boot order tight.
"""
from __future__ import annotations

import sqlite3
from typing import List, Tuple


def ensure_schema(conn) -> None:
    """Idempotently create task_dependencies + upgrade `tasks` columns.

    Direct migration of `backend_api.ensure_task_dependency_schema(conn)`.
    """
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            depends_on_task_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
        )
        '''
    )
    legacy_cols: List[Tuple[str, str, str]] = [
        ("prerequisite_ids", "TEXT", "'[]'"),
        ("is_unlocked", "INTEGER", "1"),
        ("difficulty", "TEXT", "NULL"),
    ]
    for col, col_type, default in legacy_cols:
        try:
            cur.execute(
                f'ALTER TABLE tasks ADD COLUMN {col} {col_type} DEFAULT {default}'
            )
        except sqlite3.OperationalError:
            pass
    conn.commit()


def ensure_indexes(conn) -> None:
    """Idempotent index creation.

    Direct migration of `backend_api.ensure_indexes(conn)`. Kept in the
    same module because every index here is on `tasks` / `task_dependencies`
    / `task_tags`.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_auto_%'"
    )
    existing = {r['name'] for r in cur.fetchall()}
    indexes = {
        'idx_auto_tasks_category': 'CREATE INDEX idx_auto_tasks_category ON tasks(category)',
        'idx_auto_tasks_completed': 'CREATE INDEX idx_auto_tasks_completed ON tasks(completed)',
        'idx_auto_tasks_unlocked': 'CREATE INDEX idx_auto_tasks_unlocked ON tasks(is_unlocked)',
        'idx_auto_tasks_discard': 'CREATE INDEX idx_auto_tasks_discard ON tasks(in_discard_pile)',
        'idx_auto_tasks_deadline': 'CREATE INDEX idx_auto_tasks_deadline ON tasks(deadline)',
        'idx_auto_td_task': 'CREATE INDEX idx_auto_td_task ON task_dependencies(task_id)',
        'idx_auto_td_depends': 'CREATE INDEX idx_auto_td_depends ON task_dependencies(depends_on_task_id)',
        'idx_auto_tt_tag': 'CREATE INDEX idx_auto_tt_tag ON task_tags(tag_id)',
    }
    for name, sql in indexes.items():
        if name not in existing:
            cur.execute(sql)
    missing = set(indexes) - existing
    if missing:
        conn.commit()
        print(f"[INDEX] Created {len(missing)} new indexes")