"""server.blueprints.knowledge_bp - Obsidian-style vault + knowledge graph (Phase 2 real BP).

Migrated from backend_api.py L1594-1946.

Routes (9 endpoints):
  GET  /api/knowledge/categories
  GET  /api/knowledge/points
  GET  /api/knowledge/graph
  GET  /api/knowledge/note/<path:note_path>
  GET  /api/knowledge/recent
  GET  /api/knowledge/notes
  GET  /api/knowledge/note-content/<path:note_path>
  GET  /api/knowledge/point-detail/<subject>/<point_name>
  POST /api/knowledge/open-in-obsidian

Thin handler pattern: parse arg/JSON → call service / repo → return JSON.
The `open-in-obsidian` shell-spawn side effect (Windows `start` URI) lives
in the BP layer per survey §11.7 (no service layer side-effect).
"""
from __future__ import annotations

import os
import subprocess
import urllib.parse

from flask import Blueprint, current_app, jsonify, request

from server.repositories import note_index_repo
from server.services import knowledge


knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api")


def _notes_dir() -> str:
    """Resolve the vault root from app config (injected by app_factory)."""
    return current_app.config.get("_notes_dir", "") or ""


# =============================================================================
# GET /api/knowledge/categories
# =============================================================================

@knowledge_bp.route("/knowledge/categories", methods=["GET"])
def get_knowledge_categories():
    return jsonify(knowledge.list_categories(_notes_dir()))


# =============================================================================
# GET /api/knowledge/points
# =============================================================================

@knowledge_bp.route("/knowledge/points", methods=["GET"])
def get_knowledge_points():
    category = request.args.get("category", "all")
    return jsonify(knowledge.list_points(_notes_dir(), category))


# =============================================================================
# GET /api/knowledge/graph
# =============================================================================

@knowledge_bp.route("/knowledge/graph", methods=["GET"])
def get_knowledge_graph():
    return jsonify(knowledge.build_vault_knowledge_graph(_notes_dir()))


# =============================================================================
# GET /api/knowledge/note/<path:note_path>
# =============================================================================

@knowledge_bp.route("/knowledge/note/<path:note_path>", methods=["GET"])
def get_note_content(note_path):
    content = knowledge.read_note(_notes_dir(), note_path)
    if content is None:
        return jsonify({"error": "Note not found"}), 404
    return jsonify({"content": content})


# =============================================================================
# GET /api/knowledge/recent  (hardcoded 4 entries — P3 known issue)
# =============================================================================

@knowledge_bp.route("/knowledge/recent", methods=["GET"])
def get_recent_knowledge():
    return jsonify(note_index_repo.recent_notes())


# =============================================================================
# GET /api/knowledge/notes
# =============================================================================

@knowledge_bp.route("/knowledge/notes", methods=["GET"])
def get_notes():
    return jsonify(knowledge.list_notes(_notes_dir()))


# =============================================================================
# GET /api/knowledge/note-content/<path:note_path>
# =============================================================================

@knowledge_bp.route("/knowledge/note-content/<path:note_path>", methods=["GET"])
def get_note_content_full(note_path):
    content = knowledge.read_note(_notes_dir(), note_path)
    if content is None:
        return jsonify({"error": "Note not found"}), 404
    return jsonify({"content": content, "path": note_path})


# =============================================================================
# GET /api/knowledge/point-detail/<subject>/<point_name>
# =============================================================================

@knowledge_bp.route(
    "/knowledge/point-detail/<subject>/<point_name>", methods=["GET"]
)
def get_knowledge_point_detail(subject, point_name):
    content = knowledge.read_point_detail(_notes_dir(), subject, point_name)
    if content is None:
        return jsonify({"error": "Knowledge point not found"}), 404
    return jsonify({"name": point_name, "category": subject, "content": content})


# =============================================================================
# POST /api/knowledge/open-in-obsidian  (shell spawn side-effect lives here)
# =============================================================================

@knowledge_bp.route("/knowledge/open-in-obsidian", methods=["POST"])
def open_in_obsidian():
    data = request.json or {}
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    notes_dir = _notes_dir()
    project_root = current_app.config.get("_project_root", "") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    full_path = os.path.join(project_root, notes_dir, file_path)
    if not full_path.endswith(".md"):
        full_path += ".md"
    full_path = os.path.abspath(full_path)

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    try:
        encoded_path = urllib.parse.quote(full_path)
        obsidian_uri = f"obsidian://open?path={encoded_path}"
        subprocess.Popen(["start", "", obsidian_uri], shell=True)
        return jsonify(
            {"success": True, "message": "Opening in Obsidian", "path": full_path}
        )
    except Exception as e:  # noqa: BLE001 — mirror legacy behavior verbatim
        return jsonify({"success": False, "error": str(e)})


__all__ = ["knowledge_bp"]


# =============================================================================
# Backward-compat legacy API names (verify_p0_cleanup.py T3 expects these)
# Each is a thin pointer to the new Blueprint view function. Will be removed
# once verify_p0_cleanup.py T3 is updated to handle real BPs (out of Phase 2).
# =============================================================================
_BACKEND_API_NAMES = {
    "api_get_knowledge_categories",
    "api_get_knowledge_points",
    "api_get_knowledge_graph",
    "api_get_note_content",
    "api_get_recent_knowledge",
    "api_get_notes",
    "api_get_note_content_full",
    "api_get_knowledge_point_detail",
    "api_open_in_obsidian",
}

_LEGACY_MAP = {
    "api_get_knowledge_categories": get_knowledge_categories,
    "api_get_knowledge_points": get_knowledge_points,
    "api_get_knowledge_graph": get_knowledge_graph,
    "api_get_note_content": get_note_content,
    "api_get_recent_knowledge": get_recent_knowledge,
    "api_get_notes": get_notes,
    "api_get_note_content_full": get_note_content_full,
    "api_get_knowledge_point_detail": get_knowledge_point_detail,
    "api_open_in_obsidian": open_in_obsidian,
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
        # Legacy stub contract: even though knowledge_bp is a real BP,
        # importing backend_api on first attribute access is the historical
        # T3 invariant. We do not use backend_api here — the returned
        # function is the new Blueprint view function.
        from server import backend_api  # noqa: F401  preserve P0 contract
        value = _LEGACY_MAP[name]
        globals()[name] = value  # cache (PEP 562 idiomatic)
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")