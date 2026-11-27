"""server.services.tags — 标签域的业务编排。

AR03-P2 / Stage 2
-----------------
迁移前标签的业务规则（"重名返回 200 而不是 201"、"批量分配的先查后插"
语义）写在 ``server/blueprints/tags_bp.py`` 里。Stage 2 把它们下沉到
本模块，Blueprint 只保留 HTTP 边界。

Service **不写 SQL**，数据访问在 :mod:`server.repositories.tags_repo`。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from server.repositories import tags_repo
from server.repositories.db import service_transaction

__all__ = [
    "assign_tags",
    "assign_tags_action",
    "create_tag",
    "create_tag_action",
    "delete_tag",
    "delete_tag_action",
    "list_tags",
    "list_tags_action",
]


def list_tags(conn) -> List[Dict[str, Any]]:
    """列出全部标签（含每个标签被引用的任务数）。

    SQL 与迁移前的 ``tags_bp.list_tags`` 逐条等价：``LEFT JOIN`` +
    ``GROUP BY t.id`` + ``ORDER BY t.name``。
    """
    rows = conn.execute(
        """
        SELECT t.id, t.name, COUNT(tt.task_id) AS task_count
        FROM tags t LEFT JOIN task_tags tt ON t.id = tt.tag_id
        GROUP BY t.id
        ORDER BY t.name
    """
    ).fetchall()
    return [dict(row) for row in rows]


def create_tag(conn, name: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """创建标签。

    返回 ``(payload, error_message)``：

    * 成功 → ``({"id": ..., "name": ...}, None)``；
    * 名称为空 → ``(None, "Tag name required")``（→ 400）；
    * 名称重复 → 返回 **已有** 标签（**不** 报错，见 ``duplicate`` 标记）。
    """
    raw = (name or "").strip() if isinstance(name, str) else ""
    if not raw:
        return None, "Tag name required"

    existing = tags_repo.find_tag_by_name(conn, raw)
    if existing is not None:
        return (
            {"id": existing["id"], "name": existing["name"], "duplicate": True},
            None,
        )
    tag_id = tags_repo.create_tag(conn, raw)
    return {"id": tag_id, "name": raw, "duplicate": False}, None


def delete_tag(conn, tag_id: int) -> Dict[str, Any]:
    """删除标签及其任务关联；返回 ``{"deleted": tag_id}``。"""
    tags_repo.delete_tag(conn, tag_id)
    return {"deleted": tag_id}


def assign_tags(
    conn, task_ids: Sequence[Any], tag_names: Sequence[Any]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """批量给任务分配标签。

    返回 ``(payload, error_message)``：

    * 成功 → ``({"assigned": len(task_ids)}, None)``；
    * ``task_ids`` 或 ``tag_names`` 为空 → ``(None, "task_ids and tags required")``。

    语义（与迁移前的 ``tags_bp.batch_assign_tags`` 逐条等价）：

    * 标签按名字 **先查后插**（``INSERT OR IGNORE`` + ``SELECT``）；
    * 每个任务的标签关联被 **整体替换**（先删后插）；
    * 空字符串的标签名被 **跳过**（不产生标签）。
    """
    if not task_ids or not tag_names:
        return None, "task_ids and tags required"

    tag_ids: List[int] = []
    for raw_name in tag_names:
        name = (raw_name or "").strip() if isinstance(raw_name, str) else ""
        if not name:
            continue
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (name,)
        ).fetchone()
        if row:
            tag_ids.append(row["id"])

    for task_id in task_ids:
        conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
        for tag_id in tag_ids:
            conn.execute(
                "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                (task_id, tag_id),
            )
    return {"assigned": len(task_ids)}, None


# ---------------------------------------------------------------------------
# 自持事务的整体动作入口（AR03-P2 / P2 收尾）
# ---------------------------------------------------------------------------
#
# 事务边界 **下沉到 Service**：Blueprint 只做「解析请求 → 调 Service →
# 组装响应」。提交时机与迁移前逐条等价（退出 with 时提交，异常回滚）。


def list_tags_action() -> List[Dict[str, Any]]:
    """只读：列出全部标签。"""
    with service_transaction(commit=False) as conn:
        return list_tags(conn)


def create_tag_action(name: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """创建标签（自持事务）。"""
    with service_transaction() as conn:
        return create_tag(conn, name)


def delete_tag_action(tag_id: int) -> Dict[str, Any]:
    """删除标签（自持事务）。"""
    with service_transaction() as conn:
        return delete_tag(conn, tag_id)


def assign_tags_action(
    task_ids: Sequence[Any], tag_names: Sequence[Any]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """批量分配标签（自持事务）。

    「先查后插」+「每个任务的标签关联整体替换」在 **同一事务** 内完成。
    """
    with service_transaction() as conn:
        return assign_tags(conn, task_ids, tag_names)
