"""server.services.feedback - business logic for task feedback domain.

Owns:
- TASK_FEEDBACK_EVENT_TYPES (5 event types)
- TASK_FEEDBACK_REASON_CATEGORIES (7 reason categories)
- infer_period() — datetime.now().hour → 'morning' / 'afternoon' / 'evening'
- record_task_completion(conn, task_id, payload) — orchestrator:
  1. Validates task exists (delegates to task_repo.get_task_by_id).
  2. Inserts task_completion_feedback row.
  3. Cross-domain write to daily_user_state via state_repo.upsert_energy
     (avoids BP→BP cycle; see survey 11.3).
- create_event(conn, event_payload) — validates event_type / reason_category,
  inserts into task_feedback_events.
- list_events(conn, task_id) — pure read wrapper.

Layered on top of:
- `server.repositories.feedback_repo` (pure SQL for feedback tables).
- `server.repositories.state_repo` (pure SQL for daily_user_state).
- `server.repositories.task_repo` (task existence check).

No Flask imports — usable from CLI or BP.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# Constants (migrated from backend_api.py L745-751)
# =============================================================================

TASK_FEEDBACK_EVENT_TYPES = frozenset({
    'skip_task',
    'finish_early',
    'finish_on_time',
    'timer_timeout_unfinished',
    'abandon_task',
})

TASK_FEEDBACK_REASON_CATEGORIES = frozenset({
    'state_issue',
    'task_definition_issue',
    'time_estimation_issue',
    'ability_issue',
    'external_interrupt',
    'priority_issue',
    'other',
})


# =============================================================================
# Period inference (migrated from backend_api.py L2389-2390 inline)
# =============================================================================

def infer_period(hour: Optional[int] = None) -> str:
    """Infer energy-tracking period from current hour.

    Mirrors backend_api.py L2389-2390:
        period = 'morning' if hour < 12 else ('afternoon' if hour < 18 else 'evening')
    """
    if hour is None:
        hour = datetime.now().hour
    if hour < 12:
        return 'morning'
    if hour < 18:
        return 'afternoon'
    return 'evening'


# =============================================================================
# Validation
# =============================================================================

def validate_event_type(event_type: Any) -> Optional[str]:
    """Return None if valid; error message if not."""
    if event_type not in TASK_FEEDBACK_EVENT_TYPES:
        return '非法 event_type'
    return None


def validate_reason_category(reason_category: Any) -> Optional[str]:
    """Return None if valid; error message if not."""
    if reason_category not in TASK_FEEDBACK_REASON_CATEGORIES:
        return '非法 reason_category'
    return None


# =============================================================================
# task_id + payload validation
# =============================================================================

def validate_task_id(task_id: Any) -> Optional[Dict[str, Any] | str]:
    """Return normalized task_id dict {value: int, error: str|None}."""
    if not task_id:
        return {'value': None, 'error': 'task_id required'}
    try:
        return {'value': int(task_id), 'error': None}
    except (TypeError, ValueError):
        return {'value': None, 'error': '非法 task_id'}


# =============================================================================
# Orchestrators
# =============================================================================

def record_task_completion(conn, task_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Record task completion feedback + cross-domain energy update.

    Steps (mirrors backend_api.py api_task_feedback L2338-2401):
    1. Validate task exists (task_repo.get_task_by_id).
    2. Insert feedback row into task_completion_feedback.
    3. If energy_after is provided, upsert daily_user_state.energy_{period}
       via state_repo.upsert_energy (cross-domain write — NO state_bp/service).
    4. Commit.

    Returns dict with keys: ok (bool), error (str|None).
    """
    from server.repositories import task_repo
    from server.repositories import feedback_repo
    from server.repositories import state_repo

    task = task_repo.get_task_by_id(task_id)
    if not task:
        return {'ok': False, 'error': 'Task not found'}

    energy = payload.get('energy_after')
    mood = payload.get('mood_after')

    feedback_repo.insert_completion_feedback(conn, task_id, energy, mood)

    today = datetime.now().strftime('%Y-%m-%d')
    if energy is not None:
        period = infer_period()
        state_repo.upsert_energy(conn, today, period, energy)

    return {'ok': True, 'error': None}


def create_event(conn, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a task_feedback_events row after validation.

    Returns dict with keys: ok (bool), id (int|None), error (str|None).
    """
    from server.repositories import feedback_repo

    tid_result = validate_task_id(payload.get('task_id'))
    if tid_result['error']:
        return {'ok': False, 'id': None, 'error': tid_result['error']}

    event_type = payload.get('event_type')
    err = validate_event_type(event_type)
    if err:
        return {'ok': False, 'id': None, 'error': err}

    reason_category = payload.get('reason_category')
    err = validate_reason_category(reason_category)
    if err:
        return {'ok': False, 'id': None, 'error': err}

    event_data = {
        'task_id': tid_result['value'],
        'event_type': event_type,
        'planned_minutes': payload.get('planned_minutes'),
        'actual_minutes': payload.get('actual_minutes'),
        'completion_status': payload.get('completion_status'),
        'reason_category': reason_category,
        'reason_detail': payload.get('reason_detail'),
        'note': payload.get('note'),
    }
    new_id = feedback_repo.insert_event(conn, event_data)
    return {'ok': True, 'id': new_id, 'error': None}


def list_events(conn, task_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List task_feedback_events rows, optionally filtered by task_id."""
    from server.repositories import feedback_repo
    return feedback_repo.list_events(conn, task_id=task_id)


__all__ = [
    'TASK_FEEDBACK_EVENT_TYPES',
    'TASK_FEEDBACK_REASON_CATEGORIES',
    'infer_period',
    'validate_event_type',
    'validate_reason_category',
    'validate_task_id',
    'record_task_completion',
    'create_event',
    'list_events',
]
