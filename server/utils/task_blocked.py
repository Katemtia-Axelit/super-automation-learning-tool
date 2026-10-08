"""server.utils.task_blocked — "why is this task not in the gacha pool" reasoning.

Phase 1: passthrough to the legacy `_task_blocked_message` so existing
behaviour is preserved. Phase 2 will own the message strings.
"""
from __future__ import annotations

from typing import Optional


def format_blocked_reason(task: dict) -> Optional[str]:
    """Return a human-readable string explaining why the task is blocked,
    or None if not blocked.

    Phase 1: thin wrapper around the legacy helper.
    """
    from server.backend_api import _task_blocked_message as _impl
    return _impl(task)