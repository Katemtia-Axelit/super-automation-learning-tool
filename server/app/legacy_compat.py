"""Compatibility routes for the Factory cutover.

Only mounts old endpoints not yet independently migrated to Blueprints.
Native Factory BPs take priority. This is temporary migration infrastructure,
not evidence that Agent/Prompts/Config business logic has been rewritten.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from flask import jsonify


EXACT_ROUTES = {
    "/",
    "/api/config",
    "/api/config/save",
    "/api/dependencies",
    "/api/export",
    "/api/discard-pile",
    "/api/discard-pile/<int:task_id>/restore",
    "/api/tasks/<int:task_id>/move-to-discard",
}
PREFIX_ROUTES = ("/api/agent/", "/api/prompts")


def register_legacy_compat(app, config):
    """Bind remaining Legacy routes to the same resolved Factory DB and root."""
    project_root = Path(config["_project_root"]).resolve(strict=True)
    spec = importlib.util.find_spec("server.backend_api")
    if not spec or not spec.origin:
        raise RuntimeError("Legacy code was not found")
    module_root = Path(spec.origin).resolve(strict=True).parent.parent
    if module_root != project_root:
        raise RuntimeError("Factory and Legacy source roots disagree")

    from server import backend_api as legacy

    # Legacy handler functions use global DB_PATH instead of Flask app config.
    # Binding the absolute path avoids a cwd-based DB mismatch.
    legacy.DB_PATH = str(Path(config["_db_path"]).resolve(strict=False))
    legacy.NOTES_DIR = config["_notes_dir"]
    existing = {(r.rule, method) for r in app.url_map.iter_rules()
                for method in r.methods - {"HEAD", "OPTIONS"}}
    count = 0
    for rule in legacy.app.url_map.iter_rules():
        if not (rule.rule in EXACT_ROUTES or
                any(rule.rule.startswith(p) for p in PREFIX_ROUTES)):
            continue
        view = legacy.app.view_functions[rule.endpoint]
        if rule.rule == "/api/agent/save-note":
            # User policy: AI may modify regular tasks, not Obsidian notes.
            def blocked_note_write(**_kwargs):
                return jsonify({"error": "AI knowledge-base writes are disabled"}), 403
            view = blocked_note_write
        methods = sorted(set(rule.methods) - {"HEAD", "OPTIONS"})
        remaining = [method for method in methods
                     if (rule.rule, method) not in existing]
        if not remaining:
            continue
        app.add_url_rule(
            rule.rule,
            endpoint="compat_" + rule.endpoint,
            view_func=view,
            methods=remaining,
        )
        count += 1
        existing.update((rule.rule, method) for method in remaining)
    app.config["_compat_route_count"] = count
    return count
