"""Shared helpers used across blueprints (health, decorators, error wraps).

Phase 1 introduces this package; the helpers here are minimal because
the heavy lifting still happens in `backend_api.py`.
"""
from __future__ import annotations

from typing import Any, Dict


def json_error(message: str, status: int = 400) -> tuple:
    """Return (response, status) tuple for Flask."""
    from flask import jsonify
    return jsonify({"ok": False, "error": message}), status


def json_ok(payload: Any) -> Any:
    from flask import jsonify
    return jsonify({"ok": True, "data": payload})


__all__ = ["json_error", "json_ok"]