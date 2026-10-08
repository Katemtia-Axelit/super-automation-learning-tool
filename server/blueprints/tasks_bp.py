"""server.blueprints.tasks_bp - 任务 CRUD（Phase 1 收紧版）.

迁移自 backend_api.py L1292-1470 段。范围：
- GET /api/tasks
- GET /api/tasks/<id>
- POST /api/tasks
- PUT /api/tasks/<id>
- DELETE /api/tasks/<id>
- GET /api/tasks/<id>/dependents
- POST /api/tasks/<id>/complete
- POST /api/tasks/<id>/skip
- POST /api/tasks/<id>/refuse

实现策略：
- 不依赖 backend_api.py 的全局 Task 类/Enum/函数（双权威风险）
- 直接 row→dict 返回（与原 API 行为一致）
- DB 连接通过 current_app.config["_db_path"] 读路径（避免循环 import）
- 桌面端归档后，phase 2 将从 service 层接管业务逻辑
"""

from datetime import datetime
import json
import os
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn


tasks_bp = Blueprint("tasks", __name__, url_prefix="/api")


def _conn():
    """Open sqlite connection for current request.

    P0 fix 2026-08-16 (bug 2): now goes through `make_request_conn()` to
    guarantee PRAGMA foreign_keys=ON + WAL + busy_timeout match the
    backend_api.py legacy connections. Replaces the previous ad-hoc
    sqlite3.connect(...) call which omitted foreign_keys and journal_mode.
    """
    db_path = current_app.config.get("_db_path") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "task_publisher.db",
    )
    return make_request_conn(db_path)


def _row_to_dict(row):
    """Convert sqlite3.Row to JSON-safe dict (parse prerequisite_ids JSON)."""
    d = dict(row)
    prereq = d.get("prerequisite_ids")
    if isinstance(prereq, str):
        try:
            d["prerequisite_ids"] = json.loads(prereq)
        except (TypeError, ValueError):
            d["prerequisite_ids"] = []
    return d


def _validate_prereqs_no_cycle(conn, task_id, prereq_ids):
    """Idempotent cycle detection: returns error string or None.

    Mirrors backend_api.py detect_cycle semantics (BFS over proposed edges).
    """
    if not prereq_ids:
        return None
    # build adjacency from DB + proposed new edges
    cur = conn.cursor()
    cur.execute("SELECT id, prerequisite_ids FROM tasks")
    rows = cur.fetchall()
    adj = {}
    for r in rows:
        rid = r["id"]
        try:
            cur_prereqs = json.loads(r["prerequisite_ids"] or "[]")
        except (TypeError, ValueError):
            cur_prereqs = []
        # proposed override for this task
        if task_id is not None and rid == task_id:
            cur_prereqs = list(prereq_ids)
        adj[rid] = cur_prereqs
    # BFS: any prereq chain that eventually points back to task_id?
    target = task_id
    for start in prereq_ids:
        seen = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            if node == target:
                return f"cycle detected via task {start}"
            for nxt in adj.get(node, []) or []:
                if nxt not in seen:
                    stack.append(nxt)
    return None


def _sync_dependency_edges(conn, task_id, prereq_ids):
    conn.execute("DELETE FROM task_dependencies WHERE task_id=?", (task_id,))
    conn.executemany(
        "INSERT INTO task_dependencies (task_id,depends_on_task_id) VALUES (?,?)",
        [(task_id, pid) for pid in prereq_ids],
    )


def _all_prereqs_completed(conn, prereq_ids):
    if not prereq_ids:
        return True
    unique = list(dict.fromkeys(prereq_ids))
    markers = ",".join("?" for _ in unique)
    completed = conn.execute(
        f"SELECT id FROM tasks WHERE id IN ({markers}) AND completed=1", unique
    ).fetchall()
    return len(completed) == len(unique)


def _blocked_message(conn, task):
    if task.get("is_unlocked") or task.get("completed"):
        return None
    prereqs = task.get("prerequisite_ids") or []
    if not prereqs:
        return "任务当前不可执行"
    markers = ",".join("?" for _ in prereqs)
    rows = conn.execute(
        f"SELECT id,name FROM tasks WHERE id IN ({markers})", prereqs
    ).fetchall()
    names = {r["id"]:r["name"] for r in rows}
    return "前置任务未完成：" + "、".join(
        names.get(pid, f"ID={pid}") for pid in prereqs
    )


def _unlock_dependents(conn, parent_id):
    rows = conn.execute(
        """SELECT DISTINCT t.id,t.name,t.prerequisite_ids
           FROM task_dependencies td JOIN tasks t ON td.task_id=t.id
           WHERE td.depends_on_task_id=? AND t.completed=0 AND t.is_unlocked=0""",
        (parent_id,),
    ).fetchall()
    unlocked = []
    for row in rows:
        try:
            required = json.loads(row["prerequisite_ids"] or "[]")
        except (TypeError, ValueError):
            required = []
        if _all_prereqs_completed(conn, required):
            conn.execute(
                "UPDATE tasks SET is_unlocked=1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["id"],),
            )
            unlocked.append(row["name"])
    return unlocked


@tasks_bp.route("/tasks", methods=["GET"])
def list_tasks():
    include_completed = request.args.get("include_completed", "false").lower() == "true"
    unlocked_only = request.args.get("unlocked_only", "true").lower() == "true"
    conditions = []
    if not include_completed:
        conditions.append("completed = 0")
    if unlocked_only:
        conditions.append("(is_unlocked = 1 OR is_unlocked IS NULL)")
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM tasks {where} ORDER BY created_at DESC")
        rows = cur.fetchall()
        return jsonify([_row_to_dict(r) for r in rows])
    finally:
        conn.close()


@tasks_bp.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(_row_to_dict(row))
    finally:
        conn.close()


@tasks_bp.route("/tasks", methods=["POST"])
def create_task():
    data = request.json or {}
    prereq_ids = data.get("prerequisite_ids") or []
    if not isinstance(prereq_ids, list):
        return jsonify({"error": "prerequisite_ids must be list"}), 400

    conn = _conn()
    try:
        if any(type(pid) is not int or pid <= 0 for pid in prereq_ids):
            return jsonify({"error":"invalid prerequisite_ids"}), 400
        if prereq_ids:
            markers = ",".join("?" for _ in prereq_ids)
            rows = conn.execute(
                f"SELECT id FROM tasks WHERE id IN ({markers})", prereq_ids
            ).fetchall()
            if len(rows) != len(set(prereq_ids)):
                return jsonify({"error":"前置任务不存在"}), 400
        is_unlocked = int(_all_prereqs_completed(conn, prereq_ids))

        now = datetime.now().isoformat()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks (
                name, category, task_type, description,
                estimated_time, preferred_time, deadline,
                resistance, energy_required, rarity, priority,
                is_daily, repeat_type, created_at, updated_at,
                prerequisite_ids, is_unlocked, linked_note_path
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                data.get("name", ""),
                data.get("category", "daily"),
                "normal",
                data.get("description"),
                data.get("estimated_time", 30),
                data.get("preferred_time"),
                data.get("deadline"),
                data.get("resistance", "medium"),
                data.get("energy_required", "medium"),
                data.get("rarity", "common"),
                data.get("priority", 5),
                int(bool(data.get("is_daily", False))),
                data.get("repeat_type", "none"),
                now,
                now,
                json.dumps(prereq_ids),
                is_unlocked,
                data.get("linked_note_path"),
            ),
        )
        task_id = cur.lastrowid
        _sync_dependency_edges(conn, task_id, prereq_ids)
        conn.commit()
        return jsonify({"id": task_id, "message": "Task created successfully"}), 201
    finally:
        conn.close()


@tasks_bp.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.json or {}
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        existing = cur.fetchone()
        if not existing:
            return jsonify({"error": "Task not found"}), 404

        # build new prereqs
        if "prerequisite_ids" in data:
            new_prereqs = data["prerequisite_ids"] or []
            if not isinstance(new_prereqs, list) or any(
                type(pid) is not int or pid <= 0 for pid in new_prereqs
            ):
                return jsonify({"error":"invalid prerequisite_ids"}), 400
            if new_prereqs:
                markers = ",".join("?" for _ in new_prereqs)
                ids = conn.execute(
                    f"SELECT id FROM tasks WHERE id IN ({markers})", new_prereqs
                ).fetchall()
                if len(ids) != len(set(new_prereqs)):
                    return jsonify({"error":"前置任务不存在"}), 400
            cycle = _validate_prereqs_no_cycle(conn, task_id, new_prereqs)
            if cycle:
                return jsonify({"error": f"检测到循环依赖: {cycle}"}), 400
            is_unlocked = int(_all_prereqs_completed(conn, new_prereqs))
        else:
            new_prereqs = None
            is_unlocked = None

        # field-by-field update (only provided keys)
        fields = {
            "name": data.get("name"),
            "category": data.get("category"),
            "description": data.get("description"),
            "estimated_time": data.get("estimated_time"),
            "preferred_time": data.get("preferred_time"),
            "deadline": data.get("deadline"),
            "resistance": data.get("resistance"),
            "energy_required": data.get("energy_required"),
            "rarity": data.get("rarity"),
            "priority": data.get("priority"),
            "is_daily": data.get("is_daily"),
            "repeat_type": data.get("repeat_type"),
            "linked_note_path": data.get("linked_note_path"),
        }
        # only set columns present in payload
        sets, vals = [], []
        for col, v in fields.items():
            if col in data:
                sets.append(f"{col}=?")
                vals.append(v)
        if new_prereqs is not None:
            sets.append("prerequisite_ids=?")
            vals.append(json.dumps(new_prereqs))
            sets.append("is_unlocked=?")
            vals.append(is_unlocked)
        if not sets:
            return jsonify({"message": "No fields to update"})
        sets.append("updated_at=CURRENT_TIMESTAMP")
        vals.append(task_id)
        cur.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals)
        if new_prereqs is not None:
            _sync_dependency_edges(conn, task_id, new_prereqs)
        conn.commit()
        return jsonify({"message": "Task updated successfully"})
    finally:
        conn.close()


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cur.fetchone():
            return jsonify({"error": "Task not found"}), 404
        # clean task_dependencies references
        cur.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?",
            (task_id, task_id),
        )
        cur.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
        cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return jsonify({"message": "Task deleted successfully"})
    finally:
        conn.close()


@tasks_bp.route("/tasks/<int:task_id>/dependents", methods=["GET"])
def get_dependents(task_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        if not cur.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone():
            return jsonify({"error":"Task not found"}), 404
        cur.execute(
            """
            SELECT t.id, t.name, t.completed
            FROM task_dependencies td
            JOIN tasks t ON t.id = td.task_id
            WHERE td.depends_on_task_id = ?
        """,
            (task_id,),
        )
        dependents = [dict(r) for r in cur.fetchall()]
        return jsonify(
            {
                "task_id": task_id,
                "dependents": dependents,
                "count": len(dependents),
            }
        )
    finally:
        conn.close()


def _finish_task(task_id, *, update_rate):
    """Preserve the Legacy complete/skip side effects and unlocked name list."""
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Task not found"}), 404
        blocked = _blocked_message(conn, _row_to_dict(row))
        if blocked:
            return jsonify({"error":blocked}), 400
        conn.execute(
            "UPDATE tasks SET completed=1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (task_id,),
        )
        if update_rate:
            rate = row["success_rate"] or 0.0
            conn.execute(
                "UPDATE tasks SET success_rate=? WHERE id=?",
                (min(1.0, rate + 0.1), task_id),
            )
        unlocked = _unlock_dependents(conn, task_id)
        conn.commit()
        return jsonify({
            "message": "Task completed successfully" if update_rate else "Task skipped",
            "unlocked_tasks": unlocked,
        })
    finally:
        conn.close()


@tasks_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    return _finish_task(task_id, update_rate=True)


@tasks_bp.route("/tasks/<int:task_id>/skip", methods=["POST"])
def skip_task(task_id):
    return _finish_task(task_id, update_rate=False)


@tasks_bp.route("/tasks/<int:task_id>/refuse", methods=["POST"])
def refuse_task(task_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tasks SET refusal_count = COALESCE(refusal_count, 0) + 1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (task_id,),
        )
        conn.commit()
        return jsonify({"message": "Refusal recorded"})
    finally:
        conn.close()


__all__ = ["tasks_bp"]
