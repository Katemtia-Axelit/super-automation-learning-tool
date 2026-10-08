"""server.services.schedule - business logic for schedule domain (Phase 2 / Todo 2).

Owns:
- SCHEDULE_SLOTS constant (10 time slots, day template)
- Light aggregation/transformation helpers (when needed)

Layered on top of `server.repositories.schedule_repo` (pure SQL).
No Flask imports — usable from CLI or BP.
"""
from __future__ import annotations

from typing import Any, Dict, List


# 10 个时间槽常量 — 一天的时间块模板
SCHEDULE_SLOTS: List[Dict[str, str]] = [
    {"slot_id": "am1", "name": "上午第一节", "start_time": "08:00", "end_time": "08:50"},
    {"slot_id": "am2", "name": "上午第二节", "start_time": "09:00", "end_time": "09:50"},
    {"slot_id": "am3", "name": "上午第三节", "start_time": "10:10", "end_time": "11:00"},
    {"slot_id": "am4", "name": "上午第四节", "start_time": "11:10", "end_time": "12:00"},
    {"slot_id": "noon", "name": "午休", "start_time": "12:00", "end_time": "14:00"},
    {"slot_id": "pm1", "name": "下午第一节", "start_time": "14:00", "end_time": "14:50"},
    {"slot_id": "pm2", "name": "下午第二节", "start_time": "15:00", "end_time": "15:50"},
    {"slot_id": "pm3", "name": "下午第三节", "start_time": "16:10", "end_time": "17:00"},
    {"slot_id": "pm4", "name": "下午第四节", "start_time": "17:10", "end_time": "18:00"},
    {"slot_id": "night", "name": "晚自习", "start_time": "19:00", "end_time": "21:30"},
]


__all__ = ["SCHEDULE_SLOTS"]
