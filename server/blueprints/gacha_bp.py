"""server.blueprints.gacha_bp - 抽卡 API（Phase 1 收紧版）.

迁移自 backend_api.py L1469-1552 段 + L2407-2493 (gacha pools detail / statistics / replace).

范围：
- GET /api/gacha/pools
- GET /api/gacha/pools/detail
- POST /api/gacha/draw
- POST /api/gacha/care-draw
- GET /api/gacha/statistics
- POST /api/gacha/replace

设计：
- 抽卡权重计算**不**走 DefaultGachaAlgo（保持与 backend_api.py 实现一致；
  真正切换由 Phase 2 接管）
- 抽卡最小化实现：直接 SELECT + weighted_choice（random.choice 退路）
- 旧 backend_api.py 的 6 个 gacha route 仍保留（不影响 36/36 E2E）
"""

import os
import random
import sqlite3
from datetime import datetime
from types import SimpleNamespace

from server.services.gacha import DefaultGachaAlgo, WeightInputs

from flask import Blueprint, current_app, jsonify, request

from server.extensions import make_request_conn


gacha_bp = Blueprint("gacha", __name__, url_prefix="/api")


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


def _row_to_dict(row):
    d = dict(row)
    prereq = d.get("prerequisite_ids")
    if isinstance(prereq, str):
        import json

        try:
            d["prerequisite_ids"] = json.loads(prereq)
        except (TypeError, ValueError):
            d["prerequisite_ids"] = []
    return d


# 卡池定义（与 backend_api.py L1470-1476 一致）
_POOLS = [
    {"id": "fragment", "name": "碎片卡池", "description": "0-15分钟"},
    {"id": "tomato", "name": "番茄卡池", "description": "15-45分钟"},
    {"id": "deep", "name": "深度卡池", "description": "45分钟以上"},
]

_TIME_RANGES = {
    "fragment": (0, 15),
    "tomato": (15, 45),
    "deep": (45, 9999),
}


def _available_tasks(conn):
    now = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM tasks
        WHERE completed = 0
          AND (next_available_at IS NULL OR next_available_at <= ?)
          AND (in_discard_pile = 0 OR in_discard_pile IS NULL)
          AND is_unlocked = 1
        ORDER BY priority DESC, id ASC
    """,
        (now,),
    )
    tasks = [dict(r) for r in cur.fetchall()]
    ids = [task["id"] for task in tasks]
    tag_map = {task_id: [] for task_id in ids}
    if ids:
        markers = ",".join("?" for _ in ids)
        cur.execute(
            f"SELECT tt.task_id,t.name FROM task_tags tt JOIN tags t ON t.id=tt.tag_id WHERE tt.task_id IN ({markers})",
            ids,
        )
        for row in cur.fetchall():
            tag_map[row["task_id"]].append(row["name"])
    for task in tasks:
        task["tags"] = tag_map.get(task["id"], [])
    return tasks


def _filter_pool(tasks, pool_id, preferred_tag=None, include_category=None, exclude_category=None):
    lo, hi = _TIME_RANGES.get(pool_id, (0, 9999))
    pool = [t for t in tasks if lo <= (t.get("estimated_time", 0) or 0) < hi]
    if not pool:
        pool = tasks  # fallback
    if preferred_tag:
        tagged = [t for t in pool if preferred_tag in (t.get("tags") or [])]
        if tagged:
            pool = tagged
    if include_category:
        same = [t for t in pool if t.get("category") == include_category]
        if same:
            pool = same
    if exclude_category:
        pool = [t for t in pool if t.get("category") != exclude_category]
        if not pool:
            pool = [t for t in tasks if t.get("category") != exclude_category]
    return pool


def _draw(conn, tasks, pool_id, energy="medium", preferred_tag=None, include_category=None, exclude_category=None):
    pool = _filter_pool(tasks, pool_id, preferred_tag, include_category, exclude_category)
    if not pool:
        return None
    session = SimpleNamespace(
        last_drawn_task_id=None,
        last_drawn_category=None,
        category_count_in_last_3={},
    )
    algo = DefaultGachaAlgo()
    weights = [
        algo.compute_weight(WeightInputs(
            task=SimpleNamespace(**task),
            current_energy=energy,
            session_context=session,
            draw_count_today=task.get("draw_count_today") or 0,
        ))
        for task in pool
    ]
    index = algo.pick(len(pool), weights, random)
    return pool[index]


def _record_draw(conn, task_id):
    now = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE tasks
        SET draw_count_today = COALESCE(draw_count_today, 0) + 1,
            last_drawn_at = ?, updated_at = ?
        WHERE id = ?
    """,
        (now, now, task_id),
    )
    conn.commit()


@gacha_bp.route("/gacha/pools", methods=["GET"])
def list_pools():
    return jsonify(_POOLS)


@gacha_bp.route("/gacha/pools/detail", methods=["GET"])
def pools_detail():
    """Legacy response is keyed by pool id, with eligible task arrays."""
    conn = _conn()
    try:
        pools = {
            "fragment": {"name":"碎片卡池","time_range":"0-15分钟","min":0,"max":15,"tasks":[]},
            "tomato": {"name":"番茄卡池","time_range":"15-45分钟","min":15,"max":45,"tasks":[]},
            "deep": {"name":"深度卡池","time_range":"45分钟以上","min":45,"max":999,"tasks":[]},
        }
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed=0 AND in_discard_pile=0 AND is_unlocked=1"
        ).fetchall()
        tasks = [dict(r) for r in rows]
        ids = [t["id"] for t in tasks]
        tags = {tid:[] for tid in ids}
        if ids:
            markers = ",".join("?" for _ in ids)
            for row in conn.execute(
                f"SELECT tt.task_id,t.name FROM task_tags tt JOIN tags t ON t.id=tt.tag_id WHERE tt.task_id IN ({markers})",
                ids,
            ):
                tags[row["task_id"]].append(row["name"])
        for task in tasks:
            task["tags"] = tags.get(task["id"], [])
            minutes = task.get("estimated_time") or 0
            key = "fragment" if minutes <= 15 else ("tomato" if minutes <= 45 else "deep")
            pools[key]["tasks"].append(task)
        return jsonify(pools)
    finally:
        conn.close()


@gacha_bp.route("/gacha/draw", methods=["POST"])
def draw():
    data = request.json or {}
    pool_id = data.get("pool", "fragment")
    if pool_id not in _TIME_RANGES:
        return jsonify({"error": "Invalid pool"}), 400
    preferred_tag = data.get("preferred_tag")
    energy = data.get("energy", "medium")
    conn = _conn()
    try:
        tasks = _available_tasks(conn)
        selected = _draw(conn, tasks, pool_id, energy=energy, preferred_tag=preferred_tag)
        if not selected:
            return jsonify({"error": "No tasks available"}), 404
        _record_draw(conn, selected["id"])
        return jsonify(
            {
                "task": _row_to_dict(selected),
                "pool": pool_id,
                "can_replace": True,
                "is_replacement": False,
            }
        )
    finally:
        conn.close()


@gacha_bp.route("/gacha/care-draw", methods=["POST"])
def care_draw():
    data = request.json or {}
    pool_id = data.get("pool", "fragment")
    if pool_id not in _TIME_RANGES:
        return jsonify({"error": "Invalid pool"}), 400
    preferred_tag = data.get("preferred_tag")
    energy = data.get("energy", "medium")
    include_category = data.get("include_category")
    exclude_category = data.get("exclude_category")
    conn = _conn()
    try:
        tasks = _available_tasks(conn)
        selected = _draw(
            conn,
            tasks,
            pool_id,
            energy=energy,
            preferred_tag=preferred_tag,
            include_category=include_category,
            exclude_category=exclude_category,
        )
        if not selected:
            return jsonify({"error": "No tasks available"}), 404
        _record_draw(conn, selected["id"])
        return jsonify(
            {
                "task": _row_to_dict(selected),
                "pool": pool_id,
                "can_replace": True,
                "is_replacement": False,
            }
        )
    finally:
        conn.close()


@gacha_bp.route("/gacha/statistics", methods=["GET"])
def gacha_statistics():
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM gacha_records").fetchone()["n"]
        accepted = conn.execute(
            "SELECT COUNT(*) AS n FROM gacha_records WHERE accepted=1"
        ).fetchone()["n"]
        by_pool = [dict(r) for r in conn.execute(
            "SELECT pool_name,COUNT(*) AS cnt FROM gacha_records GROUP BY pool_name ORDER BY cnt DESC"
        ).fetchall()]
        rejections = conn.execute(
            "SELECT COUNT(*) AS n FROM task_rejection_log"
        ).fetchone()["n"]
        reasons = [dict(r) for r in conn.execute(
            "SELECT reason,COUNT(*) AS cnt FROM task_rejection_log "
            "WHERE timestamp>=date('now','-30 days') GROUP BY reason ORDER BY cnt DESC"
        ).fetchall()]
        return jsonify({
            "total_draws":total,"accepted":accepted,"rejections":rejections,
            "acceptance_rate":round(accepted/total*100,1) if total else 0,
            "by_pool":by_pool,"reject_reasons":reasons,
        })
    finally:
        conn.close()


@gacha_bp.route("/gacha/replace", methods=["POST"])
def gacha_replace():
    """Record refusal/history, then perform the legacy weighted redraw."""
    data = request.json or {}
    task_id = data.get("task_id")
    if not task_id:
        return jsonify({"error":"task_id required"}), 400
    reason = data.get("reason", "other")
    pool_id = data.get("pool", "fragment")
    if pool_id not in _TIME_RANGES:
        return jsonify({"error":"Invalid pool"}), 400
    energy = data.get("energy", "medium")
    conn = _conn()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO task_rejection_log (task_id,reason,timestamp) VALUES (?,?,?)",
            (task_id, reason, now),
        )
        conn.execute(
            "UPDATE tasks SET refusal_count=refusal_count+1 WHERE id=?",
            (task_id,),
        )
        conn.execute(
            "INSERT INTO gacha_records (timestamp,pool_name,available_time,task_id,accepted,refusal_reason) "
            "VALUES (?,?,?,?,?,?)",
            (now, pool_id, 30, task_id, 0, reason),
        )
        conn.commit()
        tasks = _available_tasks(conn)
        selected = _draw(
            conn, tasks, pool_id, energy=energy,
            preferred_tag=data.get("preferred_tag"),
            exclude_category=data.get("exclude_category"),
        )
        if not selected:
            return jsonify({"error":"No replacement available"}), 404
        _record_draw(conn, selected["id"])
        return jsonify({
            "task":_row_to_dict(selected),"replaced":task_id,"reason":reason,
        })
    finally:
        conn.close()


__all__ = ["gacha_bp"]
