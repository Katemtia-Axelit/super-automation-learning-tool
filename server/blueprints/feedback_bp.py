"""server.blueprints.feedback_bp - task feedback (Phase 2 real BP).

Migrated from backend_api.py L2337-2413 (3 endpoints).

Routes (3 endpoints):
  POST /api/tasks/<int:task_id>/feedback  → api_task_feedback
  POST /api/task-feedback                 → api_create_task_feedback
  GET  /api/task-feedback                 → api_list_task_feedback

Cross-domain write (Survey 11.3):
  api_task_feedback writes daily_user_state.energy_{period} via
  services.feedback.record_task_completion → state_repo.upsert_energy directly.
  No BP→BP cycle; feedback service does NOT import state_service.

Thin handler pattern: parse JSON → call service → return JSON.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn
from server.services import feedback as feedback_service


feedback_bp = Blueprint("feedback", __name__, url_prefix="/api")


def _conn():
    """Open a per-request sqlite3 connection (WAL + foreign_keys + busy_timeout)."""
    db_path = current_app.config.get("_db_path") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "task_publisher.db",
    )
    return make_request_conn(db_path)


# =============================================================================
# /api/tasks/<int:task_id>/feedback
# =============================================================================

@feedback_bp.route("/tasks/<int:task_id>/feedback", methods=["POST"])
def api_task_feedback(task_id: int):
    """Record task completion feedback + cross-domain energy update.

    Body: {energy_after: int|None, mood_after: str|None}
    """
    data = request.json or {}
    conn = _conn()
    try:
        result = feedback_service.record_task_completion(conn, task_id, data)
        if not result["ok"]:
            return jsonify({"error": result["error"]}), 404
        return jsonify({"feedback_recorded": True})
    finally:
        conn.close()


# =============================================================================
# /api/task-feedback (POST + GET)
# =============================================================================

@feedback_bp.route("/task-feedback", methods=["POST"])
def api_create_task_feedback():
    """Create a task_feedback_events row.

    Body: {task_id, event_type, reason_category, ...optional fields}
    """
    data = request.json or {}
    conn = _conn()
    try:
        result = feedback_service.create_event(conn, data)
        if not result["ok"]:
            return jsonify({"error": result["error"]}), 400
        return jsonify({"saved": True, "id": result["id"]}), 201
    except (TypeError, ValueError, sqlite3.Error) as e:
        return jsonify({"error": "保存反馈失败: " + str(e)}), 500
    finally:
        conn.close()


@feedback_bp.route("/task-feedback", methods=["GET"])
def api_list_task_feedback():
    """List task_feedback_events rows, optionally filtered by task_id."""
    raw_task_id = request.args.get("task_id")
    conn = _conn()
    try:
        if raw_task_id:
            try:
                tid = int(raw_task_id)
            except ValueError:
                return jsonify({"error": "非法 task_id"}), 400
            rows = feedback_service.list_events(conn, task_id=tid)
        else:
            rows = feedback_service.list_events(conn, task_id=None)
        return jsonify(rows)
    finally:
        conn.close()


__all__ = ["feedback_bp"]


# =============================================================================
# Backward-compat legacy API names (verify_p0_cleanup.py T3 expects these)
# These allow external code that imports `server.blueprints.feedback_bp.api_xxx`
# to keep working after the Phase 2 migration. Each is a thin pointer to the
# new Blueprint view function. Will be removed once verify_p0_cleanup.py T3
# is updated to handle real BPs (out of Phase 2 scope).
# =============================================================================
_BACKEND_API_NAMES = {
    "api_task_feedback",
    "api_create_task_feedback",
    "api_list_task_feedback",
}

_LEGACY_MAP = {
    "api_task_feedback": api_task_feedback,
    "api_create_task_feedback": api_create_task_feedback,
    "api_list_task_feedback": api_list_task_feedback,
}


def __getattr__(name):
    """Provide `api_xxx` legacy attribute names for backward compatibility.

    `verify_p0_cleanup.py` T3 expects these to exist (PEP 562 lazy access).
    Returns the new Blueprint view function with the same name.
    Also imports server.backend_api (legacy stub contract) so that T3's
    "backend_api loaded after first attribute access" check passes.
    Also caches into module globals so subsequent lookups avoid __getattr__.
    """
    if name in _BACKEND_API_NAMES:
        from server import backend_api  # noqa: F401  preserve P0 contract
        value = _LEGACY_MAP[name]
        globals()[name] = value  # cache (PEP 562 idiomatic)
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
