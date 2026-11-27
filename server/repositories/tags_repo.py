"""server.repositories.tags_repo — tags / task_tags 的 **真 SQL** 数据访问层。

AR03-P2 / Stage 2
-----------------
P1 之前标签的 SQL 直接写在 ``server/blueprints/tags_bp.py`` 里。Stage 2 把
数据访问下沉到本模块：

* 所有函数 **接收显式 ``conn``**；
* **不** import Flask、**不** import legacy 单体、**不** 开连接；
* 事务边界由 Service 层决定。

契约保持
--------
SQL 与迁移前 ``tags_bp`` 的实现 **逐条等价**（状态码语义、
``name UNIQUE`` 冲突处理、批量插入的 "先查后插" 语义完全一致），
并由黄金快照锁定。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

__all__ = [
    "count_task_tags",
    "create_tag",
    "delete_tag",
    "find_tag_by_name",
    "list_tags",
    "link_task_tags",
    "replace_task_tags",
    "tag_exists",
    "unlink_task_tags",
]


def list_tags(conn) -> List[Dict[str, Any]]:
    """列出全部标签（按 id 升序）。"""
    rows = conn.execute("SELECT * FROM tags ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def find_tag_by_name(conn, name: str) -> Optional[Dict[str, Any]]:
    """按名称查找标签（``tags.name`` 有 UNIQUE 约束）。"""
    row = conn.execute(
        "SELECT * FROM tags WHERE name = ?", (name,)
    ).fetchone()
    return dict(row) if row else None


def tag_exists(conn, name: str) -> bool:
    """标签名是否已存在。"""
    return find_tag_by_name(conn, name) is not None


def create_tag(conn, name: str) -> int:
    """插入一个标签并返回其 id。

    调用方负责处理 ``UNIQUE`` 冲突（迁移前的 BP 是先查后插，避免抛
    ``sqlite3.IntegrityError``）。
    """
    cursor = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return int(cursor.lastrowid)


def delete_tag(conn, tag_id: int) -> None:
    """删除标签及其与任务的关联。"""
    conn.execute("DELETE FROM task_tags WHERE tag_id = ?", (tag_id,))
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))


def link_task_tags(conn, task_id: int, tag_ids: Sequence[int]) -> None:
    """为任务关联标签（追加，不去重 —— 调用方保证幂等）。"""
    conn.executemany(
        "INSERT INTO task_tags (task_id, tag_id) VALUES (?,?)",
        [(task_id, tag_id) for tag_id in tag_ids],
    )


def unlink_task_tags(conn, task_id: int) -> None:
    """解除任务的全部标签关联。"""
    conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))


def replace_task_tags(conn, task_id: int, tag_ids: Sequence[int]) -> None:
    """把任务的标签关联 **替换** 为 ``tag_ids``。"""
    unlink_task_tags(conn, task_id)
    link_task_tags(conn, task_id, tag_ids)


def count_task_tags(conn, tag_id: int) -> int:
    """统计某标签被多少任务引用。"""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM task_tags WHERE tag_id = ?", (tag_id,)
    ).fetchone()
    return int(row["cnt"]) if row else 0
