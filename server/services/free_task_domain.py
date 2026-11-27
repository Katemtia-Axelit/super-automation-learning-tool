"""server.services.free_task_domain - 自由任务领域逻辑的 **稳定公共入口**。

定位
----
``server/services/free_task.py`` 是自由任务领域逻辑的 **实现体**（由前任
Worker A 交付）。本模块是它面向调用方的 **正式公共入口**：

- 所有公共 API（常量、异常、函数）都从这里导入；
- 实现体 **不复制、不粘贴**：本模块只做 *转发* 与 *明确导出*；
- ``free_task.py`` **不被删除、不被改写**，因此旧导入路径继续可用
  （向后兼容）。

    10|使用方式::

    from server.services import free_task_domain
    minutes = free_task_domain.select_free_task_minutes(policy)

或::

    from server.services.free_task_domain import start_free_task

约束
----
- 本模块 **无副作用**：不碰数据库、不读 ``config/config.json``、
  不写 ``src/notes/**``、不 import Flask。
- 本模块 **不重复实现** 任何规则；所有规则仍由 ``free_task.py`` 唯一持有，
  避免双份实现漂移。
- 未来新增公共名时，只要 ``free_task.py`` 的 ``__all__`` 中出现，
  本模块即可通过 ``__getattr__`` 兜底转发（不遗漏新 API）。

相关
----
- 事件账本层：:mod:`server.services.free_task_events`（依赖本模块做校验）。
"""

from __future__ import annotations

from typing import Any

from . import free_task as _implementation

#: 内部实现体引用（只读）。需要访问实现细节时可用，公共 API 请直接用本模块。
implementation = _implementation

# --- 显式公共导出（与 ``free_task.__all__`` 一一对应） ------------------------
from .free_task import (  # noqa: E402  (放在 implementation 之后以便阅读)
    CATEGORY_ENTERTAINMENT,
    CATEGORY_STUDY,
    DEFAULT_FREE_TASK_REASON,
    EVENT_ACTIVITY_SUGGESTED,
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_INTERRUPTED,
    EVENT_PAUSED,
    EVENT_RESUMED,
    EVENT_STARTED,
    EVENT_TIMER_ELAPSED,
    FREE_TASK_MINUTES_OPTIONS,
    MAX_ACTIVITY_LENGTH,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INTERRUPTED,
    STATUS_PAUSED,
    STATUS_RUNNING,
    VALID_CATEGORIES,
    FreeTaskError,
    complete_free_task,
    fail_free_task,
    interrupt_free_task,
    normalize_reason,
    on_timer_elapsed,
    pause_free_task,
    select_free_task_minutes,
    resume_free_task,
    start_free_task,
    suggest_activity,
    validate_activity,
)

__all__ = [
    "CATEGORY_ENTERTAINMENT",
    "CATEGORY_STUDY",
    "DEFAULT_FREE_TASK_REASON",
    "EVENT_ACTIVITY_SUGGESTED",
    "EVENT_COMPLETED",
    "EVENT_FAILED",
    "EVENT_INTERRUPTED",
    "EVENT_PAUSED",
    "EVENT_RESUMED",
    "EVENT_STARTED",
    "EVENT_TIMER_ELAPSED",
    "FREE_TASK_MINUTES_OPTIONS",
    "MAX_ACTIVITY_LENGTH",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_INTERRUPTED",
    "STATUS_PAUSED",
    "STATUS_RUNNING",
    "VALID_CATEGORIES",
    "FreeTaskError",
    "complete_free_task",
    "fail_free_task",
    "implementation",
    "interrupt_free_task",
    "normalize_reason",
    "on_timer_elapsed",
    "pause_free_task",
    "select_free_task_minutes",
    "resume_free_task",
    "start_free_task",
    "suggest_activity",
    "validate_activity",
]


def __getattr__(name: str) -> Any:
    """兜底转发：实现体新增但本模块尚未显式导出的公共名。

    这样公共入口永远不会“漏掉”新 API，同时仍然保持单一实现体。
    """
    if name.startswith("_"):
        raise AttributeError(name)
    try:
        return getattr(_implementation, name)
    except AttributeError as exc:  # pragma: no cover - 防御性
        raise AttributeError(
            f"module 'server.services.free_task_domain' has no attribute {name!r}"
        ) from exc
