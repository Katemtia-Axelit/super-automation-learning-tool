"""server.repositories — data-access layer (Phase 1 stub).

The full repo split (5 files: task, gacha, state, feedback, note_index)
will happen in Phase 2. Phase 1 introduces the package + skeleton modules
so `from server.repositories import task_repo` works today; the underlying
helpers still call `backend_api.get_db_connection()` for backward
compatibility.

Phase 2 will replace each `*_repo.py` body with proper functions that hide
sqlite3.Row details behind dataclasses.
"""

from . import (
    task_repo,
    gacha_repo,
    state_repo,
    feedback_repo,
    note_index_repo,
    timer_repo,
)

__all__ = [
    "task_repo",
    "gacha_repo",
    "state_repo",
    "feedback_repo",
    "note_index_repo",
    "timer_repo",
]