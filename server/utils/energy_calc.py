"""server.utils.energy_calc — energy score calculation (Phase 1 stub).

Phase 1 keeps the actual scoring math in `backend_api.calculate_state_scores`.
Phase 2 will migrate it here.
"""
from __future__ import annotations

from typing import Any, Dict


def calculate_state_scores(answers: Dict[str, Any]) -> Dict[str, float]:
    from server.backend_api import calculate_state_scores as _impl
    return _impl(answers)