"""server.repositories.state_repo - daily state / assessment (Phase 2).

Pure SQL functions for `daily_user_state` and `state_assessments` tables.
Migrated from backend_api.py state domain (L2225-2413, L3357-3454).

Conventions:
- All functions take a `conn` argument (caller manages connection lifecycle).
- Return rows as `dict` (sqlite3.Row converted by caller) or scalar.
- No Flask imports — pure data layer.
- All datetime comparisons use ISO date strings ('YYYY-MM-DD').
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


# =============================================================================
# daily_user_state table
# =============================================================================

def get_daily_state_by_date(conn, date: str) -> Optional[Dict[str, Any]]:
    """Return the row for `date` or None."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_user_state WHERE date=?", (date,))
    row = cur.fetchone()
    return dict(row) if row else None


def upsert_daily_tone(conn, date: str, tone: str) -> None:
    """Set daily_tone for `date`, creating row if missing."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM daily_user_state WHERE date=?", (date,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE daily_user_state SET daily_tone=? WHERE id=?",
            (tone, existing["id"]),
        )
    else:
        cur.execute(
            "INSERT INTO daily_user_state (date, daily_tone) VALUES (?,?)",
            (date, tone),
        )
    conn.commit()


def upsert_energy(conn, date: str, period: str, value: int) -> None:
    """Write `energy_{period}` for `date`, creating row if missing.

    `period` must be one of 'morning', 'afternoon', 'evening' (caller-validated).
    Column name is built dynamically; safe because period is enum-validated upstream.
    """
    col = f"energy_{period}"
    cur = conn.cursor()
    cur.execute("SELECT id FROM daily_user_state WHERE date=?", (date,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            f"UPDATE daily_user_state SET {col}=? WHERE id=?",
            (value, existing["id"]),
        )
    else:
        cur.execute(
            f"INSERT INTO daily_user_state (date, {col}) VALUES (?,?)",
            (date, value),
        )
    conn.commit()


def list_recent_sleep(conn, days: int = 14) -> List[Dict[str, Any]]:
    """Return up to `days` rows of {date, bed_time, sleep_early_streak} DESC by date."""
    cur = conn.cursor()
    cur.execute(
        "SELECT date, bed_time, sleep_early_streak "
        "FROM daily_user_state ORDER BY date DESC LIMIT ?",
        (days,),
    )
    return [dict(r) for r in cur.fetchall()]


def upsert_sleep(conn, date: str, bed_time: str, streak: int) -> None:
    """Write bed_time + sleep_early_streak for `date`, creating row if missing."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, sleep_early_streak FROM daily_user_state WHERE date=?",
        (date,),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE daily_user_state SET bed_time=?, sleep_early_streak=? WHERE id=?",
            (bed_time, streak, row["id"]),
        )
    else:
        cur.execute(
            "INSERT INTO daily_user_state (date, bed_time, sleep_early_streak) "
            "VALUES (?,?,?)",
            (date, bed_time, streak),
        )
    conn.commit()


def list_weekly_energy(conn, days: int = 14) -> List[Dict[str, Any]]:
    """Return energy_morning/afternoon/evening + daily_tone for last `days` ASC by date."""
    cur = conn.cursor()
    cur.execute(
        "SELECT date, energy_morning, energy_afternoon, energy_evening, daily_tone "
        "FROM daily_user_state WHERE date >= date('now', ?) ORDER BY date",
        (f"-{days} days",),
    )
    return [dict(r) for r in cur.fetchall()]


# =============================================================================
# state_assessments table
# =============================================================================

def get_assessment_by_date(conn, date: str) -> Optional[Dict[str, Any]]:
    """Return the row for `date` or None."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM state_assessments WHERE date=?", (date,))
    row = cur.fetchone()
    if row:
        d = dict(row)
        # Mirror backend_api.py: parse answers JSON string back to dict.
        try:
            d["answers"] = json.loads(d["answers"]) if d.get("answers") else {}
        except (TypeError, ValueError):
            d["answers"] = {}
        return d
    return None


def upsert_assessment(
    conn,
    date: str,
    answers: Dict[str, int],
    tone: str,
    energy_score: float,
    focus_score: float,
    mood_score: float,
    formula_version: int,
    timestamp: str,
) -> None:
    """INSERT OR REPLACE state_assessments for `date`."""
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO state_assessments "
        "(date, answers, daily_tone, energy_score, focus_score, mood_score, "
        "formula_version, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            date,
            json.dumps(answers),
            tone,
            energy_score,
            focus_score,
            mood_score,
            formula_version,
            timestamp,
        ),
    )
    conn.commit()


def list_assessments(conn, days: int = 14) -> List[Dict[str, Any]]:
    """Return up to `days` assessment rows DESC by date."""
    cur = conn.cursor()
    cur.execute(
        "SELECT date, daily_tone, energy_score, focus_score, mood_score "
        "FROM state_assessments ORDER BY date DESC LIMIT ?",
        (days,),
    )
    return [dict(r) for r in cur.fetchall()]


def list_correlation_samples(conn, limit: int = 30) -> List[Dict[str, Any]]:
    """Return last `limit` rows + per-row task completion + feedback count.

    Joins state_assessments with subqueries on `tasks` and `task_completion_feedback`.
    Returns rows with keys: date, energy_score, focus_score, mood_score, answers,
    daily_tone, completed, feedback_count.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT sa.date, sa.energy_score, sa.focus_score, sa.mood_score, "
        "       sa.answers, sa.daily_tone, "
        "       (SELECT COUNT(*) FROM tasks "
        "        WHERE updated_at LIKE sa.date || '%' AND completed=1) AS completed, "
        "       (SELECT COUNT(*) FROM task_completion_feedback "
        "        WHERE timestamp LIKE sa.date || '%') AS feedback_count "
        "FROM state_assessments sa ORDER BY sa.date DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]


__all__ = [
    "get_daily_state_by_date",
    "upsert_daily_tone",
    "upsert_energy",
    "list_recent_sleep",
    "upsert_sleep",
    "list_weekly_energy",
    "get_assessment_by_date",
    "upsert_assessment",
    "list_assessments",
    "list_correlation_samples",
]
