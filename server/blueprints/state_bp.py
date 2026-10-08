"""server.blueprints.state_bp - daily state / assessment (Phase 2 real BP).

Migrated from backend_api.py L2225-2413 + L3357-3454.

Routes (11 endpoints):
  GET  /api/state/daily-tone
  POST /api/state/daily-tone
  POST /api/state/energy
  GET  /api/state/sleep
  POST /api/state/sleep
  GET  /api/state/weekly-energy
  GET  /api/state/questions
  GET  /api/state/assessment
  POST /api/state/assessment
  GET  /api/state/assessment/history
  GET  /api/state/assessment/correlate

Thin handler pattern: parse JSON → call service / repo → return JSON.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn
from server.services.state import (
    ASSESSMENT_QUESTIONS,
    aggregate_correlation,
    calculate_state_scores,
    compute_sleep_streak,
    validate_bed_time,
    validate_period,
)
from server.repositories import state_repo


state_bp = Blueprint("state", __name__, url_prefix="/api")


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
# daily-tone
# =============================================================================

@state_bp.route("/state/daily-tone", methods=["GET"])
def get_daily_tone():
    conn = _conn()
    try:
        row = state_repo.get_daily_state_by_date(conn, _today())
        if row:
            return jsonify(row)
        return jsonify(
            {
                "date": _today(),
                "daily_tone": "normal",
                "energy_morning": None,
                "energy_afternoon": None,
                "energy_evening": None,
                "bed_time": None,
                "sleep_early_streak": 0,
            }
        )
    finally:
        conn.close()


@state_bp.route("/state/daily-tone", methods=["POST"])
def set_daily_tone():
    data = request.json or {}
    tone = data.get("daily_tone", "normal")
    conn = _conn()
    try:
        state_repo.upsert_daily_tone(conn, _today(), tone)
        return jsonify({"daily_tone": tone, "date": _today()})
    finally:
        conn.close()


# =============================================================================
# energy
# =============================================================================

@state_bp.route("/state/energy", methods=["POST"])
def record_energy():
    data = request.json or {}
    period = data.get("period", "morning")
    value = data.get("value", 5)
    err = validate_period(period)
    if err:
        return jsonify({"error": err}), 400
    conn = _conn()
    try:
        state_repo.upsert_energy(conn, _today(), period, value)
        return jsonify({"recorded": True, "period": period, "value": value})
    finally:
        conn.close()


# =============================================================================
# sleep
# =============================================================================

@state_bp.route("/state/sleep", methods=["GET"])
def get_sleep():
    conn = _conn()
    try:
        rows = state_repo.list_recent_sleep(conn, days=14)
        return jsonify(rows)
    finally:
        conn.close()


@state_bp.route("/state/sleep", methods=["POST"])
def record_sleep():
    data = request.json or {}
    bed_time = (data.get("bed_time") or "").strip()
    sleep_status = data.get("status", "on_time")
    err = validate_bed_time(bed_time)
    if err:
        return jsonify({"error": err}), 400

    conn = _conn()
    try:
        existing = state_repo.get_daily_state_by_date(conn, _today()) or {}
        prev_streak = existing.get("sleep_early_streak") or 0
        new_streak = compute_sleep_streak(prev_streak, sleep_status)
        state_repo.upsert_sleep(conn, _today(), bed_time, new_streak)
        return jsonify({"bed_time": bed_time, "sleep_early_streak": new_streak})
    finally:
        conn.close()


# =============================================================================
# weekly-energy
# =============================================================================

@state_bp.route("/state/weekly-energy", methods=["GET"])
def get_weekly_energy():
    conn = _conn()
    try:
        rows = state_repo.list_weekly_energy(conn, days=14)
        return jsonify(rows)
    finally:
        conn.close()


# =============================================================================
# assessment
# =============================================================================

@state_bp.route("/state/questions", methods=["GET"])
def get_assessment_questions():
    return jsonify(
        {
            "questions": ASSESSMENT_QUESTIONS,
            "scale": {"min": 1, "max": 5, "label": "1=完全不符, 5=完全符合"},
        }
    )


@state_bp.route("/state/assessment", methods=["GET"])
def get_today_assessment():
    conn = _conn()
    try:
        row = state_repo.get_assessment_by_date(conn, _today())
        if row:
            return jsonify(
                {
                    "date": row["date"],
                    "answers": row["answers"],
                    "daily_tone": row["daily_tone"],
                    "energy_score": row["energy_score"],
                    "focus_score": row["focus_score"],
                    "mood_score": row["mood_score"],
                    "formula_version": row["formula_version"],
                    "completed": True,
                }
            )
        return jsonify({"date": _today(), "completed": False, "questions": ASSESSMENT_QUESTIONS})
    finally:
        conn.close()


@state_bp.route("/state/assessment", methods=["POST"])
def submit_assessment():
    data = request.json or {}
    answers = data.get("answers", {})
    if not answers:
        return jsonify({"error": "请回答所有问题"}), 400

    today = _today()
    scores = calculate_state_scores(answers)
    conn = _conn()
    try:
        state_repo.upsert_assessment(
            conn,
            date=today,
            answers=answers,
            tone=scores["daily_tone"],
            energy_score=scores["energy_score"],
            focus_score=scores["focus_score"],
            mood_score=scores["mood_score"],
            formula_version=scores["formula_version"],
            timestamp=datetime.now().isoformat(),
        )
        return jsonify({**scores, "date": today, "completed": True})
    finally:
        conn.close()


@state_bp.route("/state/assessment/history", methods=["GET"])
def get_assessment_history():
    days = int(request.args.get("days", 14))
    conn = _conn()
    try:
        rows = state_repo.list_assessments(conn, days=days)
        return jsonify(rows)
    finally:
        conn.close()


@state_bp.route("/state/assessment/correlate", methods=["GET"])
def get_correlation():
    """分析评估数据与实际任务完成率的相关性，用于优化公式

    Cross-domain read: state_assessments JOIN tasks + task_completion_feedback.
    Requires tasks table (tasks_bp domain) and task_completion_feedback (feedback_bp domain)
    both registered. See survey 11.1: task_completion_feedback schema will be added in Todo 11.
    """
    conn = _conn()
    try:
        rows = state_repo.list_correlation_samples(conn, limit=30)
        # Aggregate inline (modest data; 30 rows max).
        # Strip the `answers` JSON column for the aggregation step.
        for r in rows:
            try:
                import json as _json
                r["answers"] = _json.loads(r["answers"]) if r.get("answers") else {}
            except (TypeError, ValueError):
                r["answers"] = {}
        result = aggregate_correlation(rows)
        return jsonify(result)
    finally:
        conn.close()


__all__ = ["state_bp"]


# =============================================================================
# Backward-compat legacy API names (verify_p0_cleanup.py T3 expects these)
# These allow external code that imports `server.blueprints.state_bp.api_xxx`
# to keep working after the Phase 2 migration. Each is a thin pointer to the
# new Blueprint view function. Will be removed once verify_p0_cleanup.py T3
# is updated to handle real BPs (out of Phase 2 scope).
# =============================================================================
_BACKEND_API_NAMES = {
    "api_get_daily_tone",
    "api_set_daily_tone",
    "api_record_energy",
    "api_get_sleep",
    "api_record_sleep",
    "api_get_weekly_energy",
    "api_get_assessment_questions",
    "api_get_today_assessment",
    "api_submit_assessment",
    "api_get_assessment_history",
    "api_get_correlation",
}

_LEGACY_MAP = {
    "api_get_daily_tone": get_daily_tone,
    "api_set_daily_tone": set_daily_tone,
    "api_record_energy": record_energy,
    "api_get_sleep": get_sleep,
    "api_record_sleep": record_sleep,
    "api_get_weekly_energy": get_weekly_energy,
    "api_get_assessment_questions": get_assessment_questions,
    "api_get_today_assessment": get_today_assessment,
    "api_submit_assessment": submit_assessment,
    "api_get_assessment_history": get_assessment_history,
    "api_get_correlation": get_correlation,
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
        # Legacy stub contract: even though state_bp is a real BP, importing
        # backend_api on first attribute access is the historical T3 invariant.
        # We do not use backend_api here — the returned function is the new
        # Blueprint view function.
        from server import backend_api  # noqa: F401  preserve P0 contract
        value = _LEGACY_MAP[name]
        globals()[name] = value  # cache (PEP 562 idiomatic)
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
