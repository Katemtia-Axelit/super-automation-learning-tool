[archived 2026-08-16] See _archive/src_tasks_legacy/

# Archived: src/tasks/

This directory was archived on **2026-08-16** as part of the 全盘模块化重构 Phase 1 desktop archival.

The desktop/Windows-side task publisher (`src/tasks/`) has been moved to:

```
_archive/src_tasks_legacy/
```

Reason: the web backend now serves as the single source of truth for task data
(via `data/task_publisher.db` and the Flask `backend_api.py` blueprints). The
desktop app's `models/` / `services/` / `ui/` / `utils/` Python code is no
longer wired into the web build path and was superseded by the API surface.

If you need to revive it: `git mv _archive/src_tasks_legacy src/tasks`.