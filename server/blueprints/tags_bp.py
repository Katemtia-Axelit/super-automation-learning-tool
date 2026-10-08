"""server.blueprints.tags_bp - 标签 CRUD（Phase 1 收紧版）.

迁移自 backend_api.py L1960-2030 段。范围：
- GET /api/tags
- POST /api/tags
- DELETE /api/tags/<id>
- POST /api/tags/batch
"""

import os
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn


tags_bp = Blueprint("tags", __name__, url_prefix="/api")


def _conn():
    """Open sqlite connection for current request.

    P0 fix 2026-08-16 (bug 2): now goes through `make_request_conn()` to
    guarantee PRAGMA foreign_keys=ON + WAL + busy_timeout match the
    backend_api.py legacy connections.
    """
    db_path = current_app.config.get("_db_path") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "task_publisher.db",
    )
    return make_request_conn(db_path)


@tags_bp.route("/tags", methods=["GET"])
def list_tags():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.id, t.name, COUNT(tt.task_id) AS task_count
            FROM tags t LEFT JOIN task_tags tt ON t.id = tt.tag_id
            GROUP BY t.id
            ORDER BY t.name
        """
        )
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


@tags_bp.route("/tags", methods=["POST"])
def create_tag():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Tag name required"}), 400
    conn = _conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            conn.commit()
            return jsonify({"id": cur.lastrowid, "name": name}), 201
        except sqlite3.IntegrityError:
            conn.rollback()
            cur.execute("SELECT id, name FROM tags WHERE name = ?", (name,))
            row = cur.fetchone()
            if row:
                return jsonify({"id": row["id"], "name": row["name"]}), 200
            return jsonify({"error": "Failed to create"}), 500
    finally:
        conn.close()


@tags_bp.route("/tags/<int:tag_id>", methods=["DELETE"])
def delete_tag(tag_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM task_tags WHERE tag_id = ?", (tag_id,))
        cur.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return jsonify({"deleted": tag_id})
    finally:
        conn.close()


@tags_bp.route("/tags/batch", methods=["POST"])
def batch_assign_tags():
    data = request.json or {}
    task_ids = data.get("task_ids") or []
    tag_names = data.get("tags") or []
    if not task_ids or not tag_names:
        return jsonify({"error": "task_ids and tags required"}), 400
    conn = _conn()
    try:
        cur = conn.cursor()
        # resolve / create tag ids
        tag_ids = []
        for n in tag_names:
            n = (n or "").strip()
            if not n:
                continue
            cur.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (n,))
            cur.execute("SELECT id FROM tags WHERE name = ?", (n,))
            r = cur.fetchone()
            if r:
                tag_ids.append(r["id"])
        # set for each task
        for tid in task_ids:
            cur.execute("DELETE FROM task_tags WHERE task_id = ?", (tid,))
            for tag_id in tag_ids:
                cur.execute(
                    "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                    (tid, tag_id),
                )
        conn.commit()
        return jsonify({"assigned": len(task_ids)})
    finally:
        conn.close()


__all__ = ["tags_bp"]
