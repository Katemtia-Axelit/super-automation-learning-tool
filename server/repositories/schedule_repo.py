"""server.repositories.schedule_repo - schedule domain CRUD (Phase 2 / Todo 2).

Pure SQL functions for `user_schedule`, `daily_schedules`, `activities` tables.
Migrated from backend_api.py schedule block (L2072-2255).

Conventions:
- All functions take a `conn` argument (caller manages connection lifecycle).
- Return rows as `dict` (sqlite3.Row converted by caller) or scalar.
- No Flask imports — pure data layer.
- All datetime comparisons use ISO date strings ('YYYY-MM-DD').
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# =============================================================================
# user_schedule (weekly)
# =============================================================================

def get_weekly_schedule(conn) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Return weekly schedule as nested dict {day_of_week: {slot_id: {...}}}.

    All 7 day keys (0-6) are guaranteed present; each maps to a dict of slot
    entries with keys: id, activity, notes.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id, day_of_week, time_slot, activity FROM user_schedule "
        "ORDER BY day_of_week, time_slot"
    )
    rows = [dict(r) for r in cur.fetchall()]
    result: Dict[str, Dict[str, Dict[str, Any]]] = {str(d): {} for d in range(7)}
    for row in rows:
        day = str(row["day_of_week"])
        slot = row["time_slot"]
        if day not in result:
            result[day] = {}
        result[day][slot] = {
            "id": row["id"],
            "activity": row["activity"] or "",
            "notes": "",
        }
    return result


def save_weekly_entry(conn, day_of_week, slot_id, activity) -> None:
    """DELETE existing row for (day, slot) then INSERT if activity is non-empty.

    Side effect: also INSERT OR IGNORE into activities to keep the activity list fresh.
    Mirrors backend_api.py L2125-2132.
    """
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM user_schedule WHERE day_of_week=? AND time_slot=?",
        (day_of_week, slot_id),
    )
    if activity:
        cur.execute(
            "INSERT INTO user_schedule (day_of_week, time_slot, activity, is_regular) "
            "VALUES (?,?,?,1)",
            (day_of_week, slot_id, activity),
        )
        cur.execute("INSERT OR IGNORE INTO activities (name) VALUES (?)", (activity,))
    conn.commit()


# =============================================================================
# daily_schedules
# =============================================================================

def get_daily_schedule(conn, date: str) -> List[Dict[str, Any]]:
    """Return daily schedule for `date` ordered by time_slot.

    Each entry has keys: id, date, slot_id (=time_slot), activity, notes.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id, date, time_slot, activity, notes FROM daily_schedules "
        "WHERE date=? ORDER BY time_slot",
        (date,),
    )
    return [
        {
            "id": r["id"],
            "date": r["date"],
            "slot_id": r["time_slot"],
            "activity": r["activity"] or "",
            "notes": r["notes"] or "",
        }
        for r in cur.fetchall()
    ]


def save_daily_schedule(conn, date_str, slot_id, activity, notes) -> None:
    """UPSERT a daily_schedules row for (date, slot_id).

    Rules (mirrors backend_api.py L2164-2196):
    - If activity is empty AND existing row → DELETE.
    - If existing row → UPDATE activity/notes.
    - Otherwise INSERT new row + INSERT OR IGNORE into activities.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM daily_schedules WHERE date=? AND time_slot=?",
        (date_str, slot_id),
    )
    existing = cur.fetchone()
    if not activity:
        if existing:
            cur.execute("DELETE FROM daily_schedules WHERE id=?", (existing["id"],))
    elif existing:
        cur.execute(
            "UPDATE daily_schedules SET activity=?, notes=? WHERE id=?",
            (activity, notes, existing["id"]),
        )
    else:
        cur.execute(
            "INSERT INTO daily_schedules (date, time_slot, activity, notes) "
            "VALUES (?,?,?,?)",
            (date_str, slot_id, activity, notes),
        )
        cur.execute("INSERT OR IGNORE INTO activities (name) VALUES (?)", (activity,))
    conn.commit()


# =============================================================================
# activities
# =============================================================================

def list_activities(conn) -> List[Dict[str, Any]]:
    """Return all activities ordered by name."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM activities ORDER BY name")
    return [dict(r) for r in cur.fetchall()]


def find_activity_by_name(conn, name: str) -> Optional[Dict[str, Any]]:
    """Return first row matching `name` or None."""
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM activities WHERE name=?", (name,))
    row = cur.fetchone()
    return dict(row) if row else None


def insert_activity(conn, name: str) -> int:
    """INSERT a new activity by name; return the new row id."""
    cur = conn.cursor()
    cur.execute("INSERT INTO activities (name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def delete_activity(conn, act_id: int) -> bool:
    """DELETE activity by id; return True if a row was actually deleted."""
    cur = conn.cursor()
    cur.execute("DELETE FROM activities WHERE id=?", (act_id,))
    conn.commit()
    return cur.rowcount > 0


__all__ = [
    "get_weekly_schedule",
    "save_weekly_entry",
    "get_daily_schedule",
    "save_daily_schedule",
    "list_activities",
    "find_activity_by_name",
    "insert_activity",
    "delete_activity",
]
