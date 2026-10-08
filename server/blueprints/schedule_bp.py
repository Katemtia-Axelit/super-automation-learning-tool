"""server.blueprints.schedule_bp - schedule domain (Phase 2 / Todo 2, real BP).

Migrated from backend_api.py L2072-2255 (8 endpoints).

Routes:
  GET    /api/schedule/slots
  GET    /api/schedule/weekly
  POST   /api/schedule/weekly
  GET    /api/schedule/daily
  POST   /api/schedule/daily
  GET    /api/schedule/activities
  POST   /api/schedule/activities
  DELETE /api/schedule/activities/<int:act_id>

Thin handler pattern: parse JSON → call service / repo → return JSON.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn
from server.services.schedule import SCHEDULE_SLOTS
from server.repositories import schedule_repo


schedule_bp = Blueprint("schedule", __name__, url_prefix="/api")


def _conn():
    """Open a per-request sqlite3 connection (WAL + foreign_keys + busy_timeout)."""
    db_path = current_app.config.get("_db_path") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "task_publisher.db",
    )
    return make_request_conn(db_path)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# =============================================================================
# slots
# =============================================================================

@schedule_bp.route("/schedule/slots", methods=["GET"])
def get_schedule_slots():
    return jsonify(SCHEDULE_SLOTS)


# =============================================================================
# weekly schedule
# =============================================================================

@schedule_bp.route("/schedule/weekly", methods=["GET"])
def get_weekly_schedule():
    conn = _conn()
    try:
        return jsonify(schedule_repo.get_weekly_schedule(conn))
    except Exception as e:
        return jsonify({"error": "日程表未就绪: " + str(e)}), 500
    finally:
        conn.close()


@schedule_bp.route("/schedule/weekly", methods=["POST"])
def save_weekly_schedule():
    data = request.json or {}
    day = data.get("day_of_week")
    slot_id = data.get("slot_id")
    activity = (data.get("activity") or "").strip()
    if day is None or not slot_id:
        return jsonify({"error": "day_of_week and slot_id required"}), 400
    conn = _conn()
    try:
        schedule_repo.save_weekly_entry(conn, day, slot_id, activity)
        return jsonify({"saved": True})
    except Exception as e:
        return jsonify({"error": "保存失败: " + str(e)}), 500
    finally:
        conn.close()


# =============================================================================
# daily schedule
# =============================================================================

@schedule_bp.route("/schedule/daily", methods=["GET"])
def get_daily_schedule():
    date_str = request.args.get("date", _today())
    conn = _conn()
    try:
        return jsonify(schedule_repo.get_daily_schedule(conn, date_str))
    except Exception as e:
        return jsonify({"error": "日程表未就绪: " + str(e)}), 500
    finally:
        conn.close()


@schedule_bp.route("/schedule/daily", methods=["POST"])
def save_daily_schedule():
    data = request.json or {}
    date_str = data.get("date", _today())
    slot_id = data.get("slot_id")
    activity = (data.get("activity") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not slot_id:
        return jsonify({"error": "slot_id required"}), 400
    conn = _conn()
    try:
        schedule_repo.save_daily_schedule(conn, date_str, slot_id, activity, notes)
        return jsonify({"saved": True})
    except Exception as e:
        return jsonify({"error": "保存失败: " + str(e)}), 500
    finally:
        conn.close()


# =============================================================================
# activities
# =============================================================================

@schedule_bp.route("/schedule/activities", methods=["GET"])
def get_activities():
    conn = _conn()
    try:
        return jsonify(schedule_repo.list_activities(conn))
    finally:
        conn.close()


@schedule_bp.route("/schedule/activities", methods=["POST"])
def add_activity():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Activity name required"}), 400
    activity_type = (data.get("type") or "custom").strip() or "custom"
    try:
        duration = int(data.get("duration_minutes", 30) or 30)
    except (TypeError, ValueError):
        duration = 30
    conn = _conn()
    try:
        existing = schedule_repo.find_activity_by_name(conn, name)
        if existing:
            return jsonify({
                "id": existing["id"],
                "name": existing["name"],
                "type": activity_type,
                "duration_minutes": duration,
                "added": False,
            })
        new_id = schedule_repo.insert_activity(conn, name)
        return jsonify({
            "id": new_id,
            "name": name,
            "type": activity_type,
            "duration_minutes": duration,
            "added": True,
        })
    finally:
        conn.close()


@schedule_bp.route("/schedule/activities/<int:act_id>", methods=["DELETE"])
def delete_activity(act_id):
    conn = _conn()
    try:
        deleted = schedule_repo.delete_activity(conn, act_id)
        if not deleted:
            return jsonify({"error": "活动不存在"}), 404
        return jsonify({"deleted": act_id})
    finally:
        conn.close()


__all__ = ["schedule_bp"]


# =============================================================================
# Backward-compat legacy API names (verify_p0_cleanup.py T3 expects these)
# Maps old api_xxx function names to new Blueprint view functions.
# PEP 562 lazy access: forces backend_api import on first attribute access.
# =============================================================================
_BACKEND_API_NAMES = {
    "api_get_schedule_slots",
    "api_get_weekly_schedule",
    "api_save_weekly_schedule",
    "api_get_daily_schedule",
    "api_save_daily_schedule",
    "api_get_activities",
    "api_add_activity",
    "api_delete_activity",
}

_LEGACY_MAP = {
    "api_get_schedule_slots": get_schedule_slots,
    "api_get_weekly_schedule": get_weekly_schedule,
    "api_save_weekly_schedule": save_weekly_schedule,
    "api_get_daily_schedule": get_daily_schedule,
    "api_save_daily_schedule": save_daily_schedule,
    "api_get_activities": get_activities,
    "api_add_activity": add_activity,
    "api_delete_activity": delete_activity,
}


def __getattr__(name):
    """Provide `api_xxx` legacy attribute names for backward compatibility.

    `verify_p0_cleanup.py` T3 contract: stub BP module exposes legacy
    `api_xxx` names that force backend_api import on first access. Even
    though schedule_bp is now a real BP (not a stub), we keep the same
    lazy-import contract so external consumers see no change.
    """
    if name in _BACKEND_API_NAMES:
        # Legacy stub contract: importing backend_api on first attribute
        # access is the historical T3 invariant. The returned value is the
        # new Blueprint view function (not backend_api's wrapper).
        from server import backend_api  # noqa: F401  preserve P0 contract
        value = _LEGACY_MAP[name]
        globals()[name] = value  # cache (PEP 562 idiomatic)
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(_BACKEND_API_NAMES) + ["schedule_bp"])
