"""server.schema.state — daily_user_state + state_assessments + schedule.

Migrates `ensure_daily_state_schema()` + `ensure_assessment_schema()` +
`ensure_schedule_schema()` + `migrate_legacy_schedule_tables()` from
`backend_api.py`.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple


def _ensure_table_columns(cur, table: str, columns: List[Tuple[str, str, Optional[str]]]) -> None:
    """Idempotent column add.  Migration of `backend_api._ensure_table_columns`."""
    cur.execute(f'PRAGMA table_info({table})')
    existing = {row[1] for row in cur.fetchall()}
    for name, col_type, default in columns:
        if name in existing:
            continue
        try:
            if default is not None:
                cur.execute(
                    f'ALTER TABLE {table} ADD COLUMN {name} {col_type} DEFAULT {default}'
                )
            else:
                cur.execute(f'ALTER TABLE {table} ADD COLUMN {name} {col_type}')
        except sqlite3.OperationalError:
            pass


def _migrate_legacy_schedule_tables(conn) -> None:
    """Copy weekly_schedule / daily_schedule into user_schedule / daily_schedules.

    Migration of `backend_api.migrate_legacy_schedule_tables(conn)`.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_schedule'"
    )
    if cur.fetchone():
        try:
            cur.execute('SELECT COUNT(*) AS c FROM user_schedule')
            if cur.fetchone()['c'] == 0:
                cur.execute('SELECT day_of_week, slot_id, activity FROM weekly_schedule')
                for row in cur.fetchall():
                    cur.execute(
                        'INSERT OR IGNORE INTO user_schedule (day_of_week, time_slot, activity, is_regular) VALUES (?,?,?,1)',
                        (row['day_of_week'], row['slot_id'], row['activity'] or ''),
                    )
        except sqlite3.OperationalError:
            pass
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_schedule'"
    )
    if cur.fetchone():
        try:
            cur.execute(
                '''
                INSERT OR IGNORE INTO daily_schedules (date, time_slot, activity, notes)
                SELECT date, slot_id, COALESCE(activity, ''), COALESCE(notes, '')
                FROM daily_schedule
                '''
            )
        except sqlite3.OperationalError:
            pass
    conn.commit()


def ensure_schema(conn) -> None:
    """Combined entry — runs in order: schedule → daily_state → assessment."""
    cur = conn.cursor()
    # 1) schedule tables (user_schedule, daily_schedules, activities)
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS user_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER,
            time_slot TEXT,
            activity TEXT,
            is_regular BOOLEAN DEFAULT 1
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS daily_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            activity TEXT NOT NULL,
            notes TEXT,
            UNIQUE(date, time_slot)
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        '''
    )
    conn.commit()
    _migrate_legacy_schedule_tables(conn)

    # 2) daily_user_state
    cur.execute(
        '''
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
        '''
    )
    _ensure_table_columns(
        cur,
        'daily_user_state',
        [
            ('date', 'TEXT', None),
            ('daily_tone', 'TEXT', "'normal'"),
            ('energy_morning', 'INTEGER', None),
            ('energy_afternoon', 'INTEGER', None),
            ('energy_evening', 'INTEGER', None),
            ('bed_time', 'TEXT', None),
            ('sleep_early_streak', 'INTEGER', '0'),
        ],
    )
    conn.commit()

    # 3) state_assessments
    cur.execute(
        '''
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
        '''
    )
    _ensure_table_columns(
        cur,
        'state_assessments',
        [
            ('date', 'TEXT', None),
            ('answers', 'TEXT', None),
            ('daily_tone', 'TEXT', None),
            ('energy_score', 'REAL', None),
            ('focus_score', 'REAL', None),
            ('mood_score', 'REAL', None),
            ('formula_version', 'INTEGER', '1'),
            ('timestamp', 'TEXT', 'CURRENT_TIMESTAMP'),
        ],
    )
    conn.commit()