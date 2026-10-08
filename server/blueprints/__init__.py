"""server.blueprints — thin HTTP handlers, one file per business domain.

Phase 1 keeps each handler a re-export wrapper around the matching
function in `backend_api.py`. That keeps the registered route table
identical (no route drops) while moving us to the right file layout.

Phase 2 will move the actual handler bodies into these files.

⚠️ P0 FIX 2026-08-16 (bug 3 BOMBSHELL):
   Do NOT eagerly `from . import state_bp, schedule_bp, ...` here.
   Each stub BP module does a top-level `from server.backend_api import ...`,
   which would force-import the whole 3500+ line backend_api.py (Flask app,
   21 route registrations, schema ensure_*, gacha algorithm side-effects).
   Instead, real Blueprints (tasks_bp / gacha_bp / tags_bp) are exported
   directly; the 9 stub modules remain importable on demand via PEP 562
   `__getattr__` and only trigger `backend_api` when an attribute is
   actually accessed.
"""

from .tasks_bp import tasks_bp
from .gacha_bp import gacha_bp
from .tags_bp import tags_bp

__all__ = [
    # Real Blueprints (Phase 1, registered in app_factory.create_app)
    "tasks_bp",
    "gacha_bp",
    "tags_bp",
    # Stub BP module names — lazy-loadable via __getattr__ below.
    # DO NOT register these; they contain no Blueprint instance yet.
    "state_bp",
    "schedule_bp",
    "feedback_bp",
    "timer_bp",
    "knowledge_bp",
    "config_bp",
    "prompts_bp",
    "agent_bp",
    "discard_bp",
]


# PEP 562 lazy attribute resolution for stub BP modules.
# Importing `server.blueprints` MUST NOT trigger backend_api.py; only
# accessing e.g. `server.blueprints.state_bp.api_get_daily_tone` will.
_STUB_BP_MODULES = {
    "state_bp",
    "schedule_bp",
    "feedback_bp",
    "timer_bp",
    "knowledge_bp",
    "config_bp",
    "prompts_bp",
    "agent_bp",
    "discard_bp",
}


def __getattr__(name):
    if name in _STUB_BP_MODULES:
        from importlib import import_module
        # Import the sibling submodule — its top-level `from server.backend_api import ...`
        # will fire here, but ONLY when the caller actually touches a stub attribute.
        module = import_module(f".{name}", __name__)
        # Cache on the package namespace so subsequent accesses don't re-import.
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(__all__) + list(_STUB_BP_MODULES))
