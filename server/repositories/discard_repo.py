"""server.repositories.discard_repo — 弃牌堆的数据访问层。

AR03-P2 / Stage 2
-----------------
弃牌堆（``tasks.in_discard_pile``）是任务域的一个 **子状态**，但它有自己
的一套语义：自然周期边界、临时屏蔽到期、幂等的完成计数。因此本模块
把它独立成一个 repository，避免任务 repo 膨胀。

* 所有函数 **接收显式 ``conn``**；
* **不** import Flask、**不** import legacy 单体、**不** 开连接；
* **纯数据访问**：周期计算等业务规则在
  :mod:`server.services.discard` 里，本模块只提供 SQL 与取值。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "get_task_row",
    "list_discard_pile",
    "mark_discard",
    "mark_discarded_completed",
    "restore_to_gacha_pile",
    "set_in_discard_pile",
]


def list_discard_pile(conn) -> List[Dict[str, Any]]:
    """列出弃牌堆中的任务（按 ``updated_at DESC, id DESC``）。"""
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE in_discard_pile = 1
        ORDER BY updated_at DESC, id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_task_row(conn, task_id: int) -> Optional[Dict[str, Any]]:
    """按 id 取任务的原始行（不做 JSON 解析）。"""
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return dict(row) if row else None


def set_in_discard_pile(
    conn,
    task_id: int,
    *,
    in_discard: bool,
    updated_at: str,
    reset_completed: bool = False,
    clear_next_available: bool = False,
) -> None:
    """设置 / 清除弃牌标记。

    * ``in_discard=False`` 且 ``reset_completed=True`` → 同时置 ``completed=0``；
    * ``clear_next_available=True`` → 同时清空 ``next_available_at``。

    **绝不** 改写 ``completed_count`` / ``last_completed_at``。
    """
    sets = ["in_discard_pile = ?", "updated_at = ?"]
    params: List[Any] = [1 if in_discard else 0, updated_at]
    if reset_completed:
        sets.append("completed = 0")
    if clear_next_available:
        sets.append("next_available_at = NULL")
    params.append(task_id)
    conn.execute(
        f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params
    )


def mark_discard(conn, task_id: int, updated_at: str) -> None:
    """手动弃牌（``completed=0`` 的任务）。

    **只** 设置 ``in_discard_pile`` 与 ``updated_at``；保留
    ``last_completed_at`` / ``completed_count`` 与既有 ``next_available_at``。
    """
    conn.execute(
        "UPDATE tasks SET in_discard_pile=1, updated_at=? WHERE id=?",
        (updated_at, task_id),
    )


def mark_discarded_completed(
    conn,
    task_id: int,
    *,
    last_completed_at: str,
    completed_count: int,
    next_available_at: Optional[str],
    updated_at: str,
) -> None:
    """已完成任务首次移入弃牌堆：记录一次完成并（可能）设置周期到期时间。

    ``next_available_at`` 为 ``None`` 时 **不** 写该列（非周期任务保持
    不可自动恢复）。
    """
    if next_available_at is not None:
        conn.execute(
            "UPDATE tasks SET in_discard_pile=1, last_completed_at=?, "
            "completed_count=?, next_available_at=?, updated_at=? WHERE id=?",
            (
                last_completed_at,
                completed_count,
                next_available_at,
                updated_at,
                task_id,
            ),
        )
        return
    conn.execute(
        "UPDATE tasks SET in_discard_pile=1, last_completed_at=?, "
        "completed_count=?, updated_at=? WHERE id=?",
        (last_completed_at, completed_count, updated_at, task_id),
    )


def restore_to_gacha_pile(
    conn,
    task_id: int,
    *,
    updated_at: str,
    reset_completed: bool = False,
    clear_next_available: bool = False,
) -> None:
    """把任务从弃牌堆恢复回抽卡池（清 ``in_discard_pile``）。

    **绝不** 改写 ``completed_count`` / ``last_completed_at``。
    """
    set_in_discard_pile(
        conn,
        task_id,
        in_discard=False,
        updated_at=updated_at,
        reset_completed=reset_completed,
        clear_next_available=clear_next_available,
    )
