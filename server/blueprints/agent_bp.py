# ⚠️ Phase 2 STUB: 无 Blueprint 实例，勿注册 ⚠️
#
# This module is a Phase 1 re-export wrapper around `server.backend_api`.
# It contains NO `Blueprint(...)` instance and NO route decorators.
# Do NOT register it via `app.register_blueprint(...)` — there is nothing
# to register. Phase 2 will replace this file with a real Blueprint.
#
# Note: this is the LLM agent that walks the vault and writes new notes.
# Per the Plan, agent routes must be sandboxed (R5). Phase 4 will introduce
# explicit sandbox; Phase 1 keeps the existing handler behaviour.
#
# Lazy loading (PEP 562): importing `server.blueprints.agent_bp` alone
# does NOT force-import `server.backend_api`. The backend_api import only
# fires the first time an attribute is read.

from __future__ import annotations

_BACKEND_API_NAMES = {
    "api_list_agents",
    "api_list_raw_files",
    "api_list_vault_files",
    "api_get_agent_prompt",
    "api_get_raw_file_content",
    "api_get_vault_file_content",
    "api_agent_process",
    "api_agent_save_note",
    "api_agent_import_tasks",
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
