"""server.utils.task_blocked — "为什么这个任务没进卡池" 的说明（公开工具门面）。

AR03-P2 / Stage 7
-----------------
此前本模块是 **转发壳**，指向 legacy ``backend_api._task_blocked_message``。
Stage 7 把它指向 **真正的 owner**：
:func:`server.repositories.task_repo.blocked_message`。

⚠️ 签名差异（必须如实记录）
--------------------------
legacy 的 ``_task_blocked_message(task)`` 接收一个 **Task 对象**
（带 ``.is_unlocked`` / ``.completed`` / ``.prerequisite_ids`` 属性），
并 **自己** 按 id 查前置任务名称。

真正的 owner ``task_repo.blocked_message(conn, task)`` 接收
**dict** + 一条 **连接**（仓库层不做自己的连接管理）。

本门面因此要求调用方传入 ``conn``；为兼容旧的 **dict** 形状，
``task`` 参数既接受 dict，也接受带同名属性的对象。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

__all__ = ["format_blocked_reason"]


def _as_mapping(task: Any) -> Mapping[str, Any]:
    """把 Task 对象 / dict 统一成 dict 形状。"""
    if isinstance(task, Mapping):
        return task
    return {
        "is_unlocked": getattr(task, "is_unlocked", None),
        "completed": getattr(task, "completed", None),
        "prerequisite_ids": getattr(task, "prerequisite_ids", None),
    }


def format_blocked_reason(conn, task: Any) -> Optional[str]:
    """返回任务被阻塞时的说明；可执行则返回 ``None``。

    委托给 :func:`server.repositories.task_repo.blocked_message`
    （真正的 owner）。
    """
    from server.repositories.task_repo import blocked_message as _impl

    return _impl(conn, _as_mapping(task))
