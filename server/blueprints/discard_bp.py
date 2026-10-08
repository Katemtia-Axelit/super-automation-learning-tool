# ⚠️ Phase 2 STUB: 无 Blueprint 实例，勿注册 ⚠️
#
# This module is a Phase 1 re-export wrapper around `server.backend_api`.
# It contains NO `Blueprint(...)` instance and NO route decorators.
# Do NOT register it via `app.register_blueprint(...)` — there is nothing
# to register. Phase 2 will replace this file with a real Blueprint.
#
# Lazy loading (PEP 562): importing `server.blueprints.discard_bp` alone
# does NOT force-import `server.backend_api`. The backend_api import only
# fires the first time an attribute is read.

from __future__ import annotations

_BACKEND_API_NAMES = {
    "api_get_discard_pile",
    "api_restore_from_discard",
    "api_move_to_discard",
}

__all__ = sorted(_BACKEND_API_NAMES)


def __getattr__(name):
    if name in _BACKEND_API_NAMES:
        from server import backend_api  # lazy, fires once per process
        value = getattr(backend_api, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(_BACKEND_API_NAMES))
