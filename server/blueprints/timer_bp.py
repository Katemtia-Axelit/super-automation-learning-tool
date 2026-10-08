"""server.blueprints.timer_bp - timer domain (Phase 2 real BP).

Migrated from backend_api.py L3054-3181.

Routes (5 endpoints):
  POST /api/timer/start
  POST /api/timer/complete
  GET  /api/timer/active
  POST /api/timer/pause
  POST /api/timer/resume

Thin handler pattern: parse JSON → call service → return JSON.
"""
from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn
from server.services import timer as timer_service


timer_bp = Blueprint("timer", __name__, url_prefix="/api")


def _conn():
    """Open a per-request sqlite3 connection (WAL + foreign_keys + busy_timeout)."""
    db_path = current_app.config.get("_db_path") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "task_publisher.db",
    )
    return make_request_conn(db_path)


def _err_to_response(exc: timer_service.TimerError):
    return jsonify({"error": exc.message}), exc.status


# =============================================================================
# /api/timer/start
# =============================================================================

@timer_bp.route("/timer/start", methods=["POST"])
def start_timer():
    data = request.json or {}
    task_id = data.get("task_id")
    minutes = data.get("planned_minutes", 30)
    conn = _conn()
    try:
        try:
            payload = timer_service.start(conn, task_id, minutes)
        except timer_service.TimerError as e:
            return _err_to_response(e)
        return jsonify(payload)
    finally:
        conn.close()


# =============================================================================
# /api/timer/complete
# =============================================================================

@timer_bp.route("/timer/complete", methods=["POST"])
def complete_timer():
    data = request.json or {}
    session_id = data.get("session_id")
    actual_minutes = data.get("actual_minutes")
    result = data.get("result", "completed")
    reason = data.get("reason", "")
    conn = _conn()
    try:
        try:
            payload = timer_service.complete(
                conn, session_id, actual_minutes, result, reason
            )
        except timer_service.TimerError as e:
            return _err_to_response(e)
        return jsonify(payload)
    finally:
        conn.close()


# =============================================================================
# /api/timer/active
# =============================================================================

@timer_bp.route("/timer/active", methods=["GET"])
def get_active_timer():
    conn = _conn()
    try:
        row = timer_service.active(conn)
        return jsonify(row)
    finally:
        conn.close()


# =============================================================================
# /api/timer/pause
# =============================================================================

@timer_bp.route("/timer/pause", methods=["POST"])
def pause_timer():
    conn = _conn()
    try:
        try:
            payload = timer_service.pause(conn)
        except timer_service.TimerError as e:
            return _err_to_response(e)
        return jsonify(payload)
    finally:
        conn.close()


# =============================================================================
# /api/timer/resume
# =============================================================================

@timer_bp.route("/timer/resume", methods=["POST"])
def resume_timer():
    conn = _conn()
    try:
        try:
            payload = timer_service.resume(conn)
        except timer_service.TimerError as e:
            return _err_to_response(e)
        return jsonify(payload)
    finally:
        conn.close()


__all__ = ["timer_bp"]


# =============================================================================
# Backward-compat legacy API names (verify_p0_cleanup.py T3 expects these)
# Each is a thin pointer to the new Blueprint view function. Will be removed
# once verify_p0_cleanup.py T3 is updated to handle real BPs (out of Phase 2 scope).
# =============================================================================
_BACKEND_API_NAMES = {
    "api_timer_start",
    "api_timer_complete",
    "api_timer_active",
    "api_timer_pause",
    "api_timer_resume",
}

_LEGACY_MAP = {
    "api_timer_start": start_timer,
    "api_timer_complete": complete_timer,
    "api_timer_active": get_active_timer,
    "api_timer_pause": pause_timer,
    "api_timer_resume": resume_timer,
}


def __getattr__(name):
    """Provide `api_xxx` legacy attribute names for backward compatibility.

    `verify_p0_cleanup.py` T3 expects these to exist (PEP 562 lazy access).
    Returns the new Blueprint view function with the same name.
    Imports `server.backend_api` on first attribute access to preserve T3's
    "backend_api loaded after first attribute access" invariant, then caches
    the resolved name in module globals.
    """
    if name in _BACKEND_API_NAMES:
        from server import backend_api  # noqa: F401  preserve P0 contract
        value = _LEGACY_MAP[name]
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")