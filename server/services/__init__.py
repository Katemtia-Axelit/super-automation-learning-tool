"""server.services — business-logic layer (pure functions + DI repo).

Phase 1 introduces one canonical example: `gacha.py` owns the weighted
random algorithm from `backend_api.py` (lines 1019-1240) behind a Protocol
(`GachaAlgo`) so Phase 2 can swap algorithms (e.g. learned policy) without
touching blueprints.

Phase 2 will populate timer / ai / knowledge / schedule services.
"""

from . import gacha, state, schedule, timer, feedback

__all__ = ["gacha", "state", "schedule", "timer", "feedback"]