"""server.schema - Phase 1 收紧版：7 个 ensure_* schema 集中编排.

设计：
- ensure_all(conn) 调用全部 7 个 ensure_* 幂等迁移
- 每个 ensure_X 函数对应 backend_api.py 的同名函数，行为完全一致
- Phase 1 不删 backend_api.py 的旧 ensure_*（避免破坏 36/36 E2E）
- Phase 2 才统一权威：删 backend_api.py 同源实现，全部走这里
"""

import sqlite3


def _ensure_table_columns(cur, table, columns):
    """Idempotent ADD COLUMN: columns = [(name, type, default_or_none), ...]"""
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for name, col_type, default in columns:
        if name in existing:
            continue
        try:
            if default is not None:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {col_type} DEFAULT {default}"
                )
            else:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
        except sqlite3.OperationalError:
            pass


def ensure_indexes(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_auto_%'"
    )
    existing = {r["name"] for r in cur.fetchall()}
    indexes = {
        "idx_auto_tasks_category": "CREATE INDEX idx_auto_tasks_category ON tasks(category)",
        "idx_auto_tasks_completed": "CREATE INDEX idx_auto_tasks_completed ON tasks(completed)",
        "idx_auto_tasks_unlocked": "CREATE INDEX idx_auto_tasks_unlocked ON tasks(is_unlocked)",
        "idx_auto_tasks_discard": "CREATE INDEX idx_auto_tasks_discard ON tasks(in_discard_pile)",
        "idx_auto_tasks_deadline": "CREATE INDEX idx_auto_tasks_deadline ON tasks(deadline)",
        "idx_auto_td_task": "CREATE INDEX idx_auto_td_task ON task_dependencies(task_id)",
        "idx_auto_td_depends": "CREATE INDEX idx_auto_td_depends ON task_dependencies(depends_on_task_id)",
        "idx_auto_tt_tag": "CREATE INDEX idx_auto_tt_tag ON task_tags(tag_id)",
    }
    for name, sql in indexes.items():
        if name not in existing:
            cur.execute(sql)
    if set(indexes) - existing:
        conn.commit()
        print(f"[INDEX] Created {len(set(indexes)-existing)} new indexes")


def ensure_task_dependency_schema(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            depends_on_task_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
        )
    """
    )
    legacy_cols = [
        ("prerequisite_ids", "TEXT", "'[]'"),
        ("is_unlocked", "INTEGER", "1"),
        ("difficulty", "TEXT", "NULL"),
    ]
    for col, col_type, default in legacy_cols:
        try:
            cur.execute(
                f"ALTER TABLE tasks ADD COLUMN {col} {col_type} DEFAULT {default}"
            )
        except sqlite3.OperationalError:
            pass
    conn.commit()


def ensure_schedule_schema(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER,
            time_slot TEXT,
            activity TEXT,
            is_regular BOOLEAN DEFAULT 1
        )
    """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            activity TEXT NOT NULL,
            notes TEXT,
            UNIQUE(date, time_slot)
        )
    """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """
    )
    conn.commit()
    migrate_legacy_schedule_tables(conn)


def ensure_timer_schema(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS timer_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            planned_minutes INTEGER,
            actual_minutes INTEGER,
            status TEXT DEFAULT 'running',
            result TEXT,
            reason TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """
    )
    _ensure_table_columns(
        cur,
        "timer_sessions",
        [
            ("task_id", "INTEGER", None),
            ("started_at", "TEXT", None),
            ("ended_at", "TEXT", None),
            ("planned_minutes", "INTEGER", None),
            ("actual_minutes", "INTEGER", None),
            ("status", "TEXT", "'running'"),
            ("result", "TEXT", None),
            ("reason", "TEXT", None),
            ("notes", "TEXT", None),
            ("created_at", "TEXT", "CURRENT_TIMESTAMP"),
            ("paused_seconds", "INTEGER", "0"),
        ],
    )
    conn.commit()


def ensure_task_feedback_events_schema(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_feedback_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            planned_minutes INTEGER,
            actual_minutes INTEGER,
            completion_status TEXT,
            reason_category TEXT NOT NULL,
            reason_detail TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """
    )
    _ensure_table_columns(
        cur,
        "task_feedback_events",
        [
            ("task_id", "INTEGER", None),
            ("event_type", "TEXT", None),
            ("planned_minutes", "INTEGER", None),
            ("actual_minutes", "INTEGER", None),
            ("completion_status", "TEXT", None),
            ("reason_category", "TEXT", None),
            ("reason_detail", "TEXT", None),
            ("note", "TEXT", None),
            ("created_at", "TEXT", "CURRENT_TIMESTAMP"),
        ],
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_feedback_task ON task_feedback_events(task_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_feedback_created ON task_feedback_events(created_at)"
    )
    conn.commit()


def ensure_assessment_schema(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS state_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            answers TEXT NOT NULL,
            daily_tone TEXT,
            energy_score REAL,
            focus_score REAL,
            mood_score REAL,
            formula_version INTEGER DEFAULT 1,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    _ensure_table_columns(
        cur,
        "state_assessments",
        [
            ("date", "TEXT", None),
            ("answers", "TEXT", None),
            ("daily_tone", "TEXT", None),
            ("energy_score", "REAL", None),
            ("focus_score", "REAL", None),
            ("mood_score", "REAL", None),
            ("formula_version", "INTEGER", "1"),
            ("timestamp", "TEXT", "CURRENT_TIMESTAMP"),
        ],
    )
    conn.commit()


def ensure_daily_state_schema(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_user_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            daily_tone TEXT DEFAULT 'normal',
            energy_morning INTEGER,
            energy_afternoon INTEGER,
            energy_evening INTEGER,
            bed_time TEXT,
            sleep_early_streak INTEGER DEFAULT 0
        )
    """
    )
    _ensure_table_columns(
        cur,
        "daily_user_state",
        [
            ("date", "TEXT", None),
            ("daily_tone", "TEXT", "'normal'"),
            ("energy_morning", "INTEGER", None),
            ("energy_afternoon", "INTEGER", None),
            ("energy_evening", "INTEGER", None),
            ("bed_time", "TEXT", None),
            ("sleep_early_streak", "INTEGER", "0"),
        ],
    )
    conn.commit()


def migrate_legacy_schedule_tables(conn):
    """Sync legacy weekly_schedule / daily_schedule → user_schedule / daily_schedules."""
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_schedule'"
    )
    if cur.fetchone():
        try:
            cur.execute("SELECT COUNT(*) AS c FROM user_schedule")
            if cur.fetchone()["c"] == 0:
                cur.execute(
                    "SELECT day_of_week, slot_id, activity FROM weekly_schedule"
                )
                for row in cur.fetchall():
                    cur.execute(
                        "INSERT OR IGNORE INTO user_schedule (day_of_week, time_slot, activity, is_regular) VALUES (?,?,?,1)",
                        (row["day_of_week"], row["slot_id"], row["activity"] or ""),
                    )
        except sqlite3.OperationalError:
            pass
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_schedule'"
    )
    if cur.fetchone():
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO daily_schedules (date, time_slot, activity, notes)
                SELECT date, slot_id, COALESCE(activity, ''), COALESCE(notes, '')
                FROM daily_schedule
            """
            )
        except sqlite3.OperationalError:
            pass
    conn.commit()


def ensure_all(conn):
    """Run all 7 ensure_* migrations in dependency order. Idempotent."""
    ensure_task_dependency_schema(conn)
    ensure_schedule_schema(conn)
    ensure_timer_schema(conn)
    ensure_task_feedback_events_schema(conn)
    ensure_assessment_schema(conn)
    ensure_daily_state_schema(conn)
    ensure_indexes(conn)


__all__ = [
    "ensure_all",
    "ensure_indexes",
    "ensure_task_dependency_schema",
    "ensure_schedule_schema",
    "ensure_timer_schema",
    "ensure_task_feedback_events_schema",
    "ensure_assessment_schema",
    "ensure_daily_state_schema",
    "migrate_legacy_schedule_tables",
]
