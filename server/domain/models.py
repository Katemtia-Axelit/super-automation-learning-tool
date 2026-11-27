"""server.domain.models — 领域模型（Task / 枚举 / 抽卡会话上下文）。

AR03-P2 / Stage 7
-----------------
Stage 7 之前，这些 **领域模型** 住在 legacy 单体
``server/backend_api.py`` 里（``Task`` / ``TaskCategory`` / ``TaskProfile`` /
``Resistance`` / ``EnergyRequired`` / ``RepeatType`` / ``GachaPool`` /
``GachaSessionContext``）。Stage 7 把 legacy 收成薄别名时，它们必须先
有一个 **真正的 owner**，否则：

* ``scripts/phase2_gacha_golden.py`` 无法再从 ``server.backend_api`` 取到
  ``Task`` / ``TaskProfile`` / ``GachaSessionContext``；
* 抽卡域（:mod:`server.services.gacha`）与任务域
  （:mod:`server.services.tasks`）都要引用同一份模型 —— **单一权威**。

设计约束
--------
* **纯数据模型**：不依赖 Flask、���依赖数据库、不做任何 IO；
* 字段与默认值与迁移前 **逐条一致**（黄金快照锁定）；
* ``from_dict`` / ``from_row`` / ``to_dict`` 三个转换入口保持原语义。

⚠️ ``Task.from_dict`` / ``Task.from_row`` 的历史默认值
-------------------------------------------------------
``from_dict`` 的 ``task_type`` 缺省是 ``"other"``、``from_row`` 的
``category`` 缺省也是 ``"other"`` —— 这与 ``Task.__init__`` 的
``"daily"`` **不同**，是迁移前就存在的历史差异。
本模块 **原样保留**（不做"顺手修正"），以免改变既有数据行为；
读取侧的归一由 :func:`server.services.tasks.normalize_card_type` 负责。
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

__all__ = [
    "DrawResult",
    "EnergyRequired",
    "GachaPool",
    "GachaSessionContext",
    "RepeatType",
    "Resistance",
    "Task",
    "TaskCategory",
    "TaskProfile",
]


class TaskCategory(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    FLEXIBLE_DDL = "flexible_ddl"
    ACCUMULATION = "accumulation"


class RepeatType(Enum):
    NONE = "none"
    SINGLE = "single"
    DAILY = "daily"
    WEEKLY = "weekly"
    ACCUMULATION = "accumulation"


class TaskProfile(Enum):
    DAILY_HABIT = "daily_habit"
    WEEKLY_ROUTINE = "weekly_routine"
    DEADLINE_FLEXIBLE = "deadline_flexible"
    DEADLINE_PROGRESSIVE = "deadline_progressive"


class Resistance(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EnergyRequired(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GachaPool(Enum):
    FRAGMENT = "fragment"
    TOMATO = "tomato"
    DEEP = "deep"


class Task:
    """任务领域模型（纯数据，不含行为依赖）。"""

    def __init__(
        self,
        id=None,
        name="",
        category="daily",
        description=None,
        estimated_time=30,
        preferred_time=None,
        deadline=None,
        resistance="medium",
        energy_required="medium",
        rarity="common",
        priority=5,
        success_rate=0.0,
        refusal_count=0,
        is_daily=False,
        task_type="other",
        repeat_type="none",
        task_profile="deadline_flexible",
        parent_task_id=None,
        group_id=None,
        last_completed_at=None,
        next_available_at=None,
        last_drawn_at=None,
        draw_count_today=0,
        min_push_time="20:00",
        in_discard_pile=False,
        completed_count=0,
        tags=None,
        completed=False,
        difficulty=None,
        created_at=None,
        updated_at=None,
        prerequisite_ids=None,
        is_unlocked=True,
        linked_note_path=None,
    ):
        self.id = id
        self.name = name
        self.category = category
        self.description = description
        self.estimated_time = estimated_time
        self.preferred_time = preferred_time
        self.deadline = deadline
        self.resistance = resistance
        self.energy_required = energy_required
        self.rarity = rarity
        self.priority = priority
        self.success_rate = success_rate
        self.refusal_count = refusal_count
        self.is_daily = is_daily
        self.task_type = task_type
        self.repeat_type = repeat_type
        self.task_profile = task_profile
        self.parent_task_id = parent_task_id
        self.group_id = group_id
        self.last_completed_at = last_completed_at
        self.next_available_at = next_available_at
        self.last_drawn_at = last_drawn_at
        self.draw_count_today = draw_count_today
        self.min_push_time = min_push_time
        self.in_discard_pile = in_discard_pile
        self.completed_count = completed_count
        self.tags = tags or []
        self.completed = completed
        self.difficulty = difficulty
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
        self.prerequisite_ids = prerequisite_ids or []
        self.is_unlocked = is_unlocked
        self.linked_note_path = linked_note_path

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "estimated_time": self.estimated_time,
            "preferred_time": self.preferred_time,
            "deadline": self.deadline,
            "resistance": self.resistance,
            "energy_required": self.energy_required,
            "rarity": self.rarity,
            "priority": self.priority,
            "success_rate": self.success_rate,
            "refusal_count": self.refusal_count,
            "is_daily": self.is_daily,
            "task_type": self.task_type,
            "repeat_type": self.repeat_type,
            "task_profile": self.task_profile,
            "parent_task_id": self.parent_task_id,
            "group_id": self.group_id,
            "last_completed_at": self.last_completed_at,
            "next_available_at": self.next_available_at,
            "last_drawn_at": self.last_drawn_at,
            "draw_count_today": self.draw_count_today,
            "min_push_time": self.min_push_time,
            "in_discard_pile": self.in_discard_pile,
            "completed_count": self.completed_count,
            "tags": self.tags,
            "completed": self.completed,
            "difficulty": self.difficulty,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "prerequisite_ids": self.prerequisite_ids,
            "is_unlocked": self.is_unlocked,
            "linked_note_path": self.linked_note_path,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            category=data.get("category", "daily"),
            description=data.get("description"),
            estimated_time=data.get("estimated_time", 30),
            preferred_time=data.get("preferred_time"),
            deadline=data.get("deadline"),
            resistance=data.get("resistance", "medium"),
            energy_required=data.get("energy_required", "medium"),
            rarity=data.get("rarity", "common"),
            priority=data.get("priority", 5),
            success_rate=data.get("success_rate", 0.0),
            refusal_count=data.get("refusal_count", 0),
            is_daily=data.get("is_daily", False),
            task_type=data.get("task_type", "other"),
            repeat_type=data.get("repeat_type", "none"),
            task_profile=data.get("task_profile", "deadline_flexible"),
            parent_task_id=data.get("parent_task_id"),
            group_id=data.get("group_id"),
            last_completed_at=data.get("last_completed_at"),
            next_available_at=data.get("next_available_at"),
            last_drawn_at=data.get("last_drawn_at"),
            draw_count_today=data.get("draw_count_today", 0),
            min_push_time=data.get("min_push_time", "20:00"),
            in_discard_pile=data.get("in_discard_pile", False),
            completed_count=data.get("completed_count", 0),
            tags=data.get("tags", []),
            completed=data.get("completed", False),
            difficulty=data.get("difficulty"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            prerequisite_ids=data.get("prerequisite_ids", []),
            is_unlocked=data.get("is_unlocked", True),
        )

    @classmethod
    def from_row(cls, row):
        def safe_get(row, key, default=None):
            try:
                value = row[key]
                return value if value is not None else default
            except (KeyError, IndexError):
                return default

        prereq_raw = safe_get(row, "prerequisite_ids")
        prereq_ids: List[Any] = []
        if prereq_raw:
            try:
                prereq_ids = json.loads(prereq_raw)
            except (TypeError, ValueError):
                pass

        return cls(
            id=safe_get(row, "id"),
            name=safe_get(row, "name", ""),
            category=safe_get(row, "category", "other"),
            description=safe_get(row, "description", ""),
            estimated_time=safe_get(row, "estimated_time", 30),
            preferred_time=safe_get(row, "preferred_time"),
            deadline=safe_get(row, "deadline"),
            resistance=safe_get(row, "resistance", "medium"),
            energy_required=safe_get(row, "energy_required", "medium"),
            rarity=safe_get(row, "rarity", "common"),
            priority=safe_get(row, "priority", 5),
            success_rate=safe_get(row, "success_rate", 0.0),
            refusal_count=safe_get(row, "refusal_count", 0),
            is_daily=bool(safe_get(row, "is_daily", False)),
            task_type=safe_get(row, "task_type", "other"),
            repeat_type=safe_get(row, "repeat_type", "none"),
            task_profile=safe_get(row, "task_profile", "deadline_flexible"),
            parent_task_id=safe_get(row, "parent_task_id"),
            group_id=safe_get(row, "group_id"),
            last_completed_at=safe_get(row, "last_completed_at"),
            next_available_at=safe_get(row, "next_available_at"),
            last_drawn_at=safe_get(row, "last_drawn_at"),
            draw_count_today=safe_get(row, "draw_count_today", 0),
            min_push_time=safe_get(row, "min_push_time", "20:00"),
            in_discard_pile=bool(safe_get(row, "in_discard_pile", False)),
            completed_count=safe_get(row, "completed_count", 0),
            tags=safe_get(row, "tags", []),
            completed=bool(safe_get(row, "completed", False)),
            difficulty=safe_get(row, "difficulty"),
            created_at=safe_get(row, "created_at"),
            updated_at=safe_get(row, "updated_at"),
            prerequisite_ids=prereq_ids,
            is_unlocked=bool(safe_get(row, "is_unlocked", True)),
            linked_note_path=safe_get(row, "linked_note_path"),
        )


class GachaSessionContext:
    """一次抽卡会话的上下文（换牌状态、分类历史等）。"""

    def __init__(self):
        self.last_drawn_task_id = None
        self.last_drawn_category = None
        self.category_history: List[Any] = []
        self.replace_count = 0
        self.max_replace_count = 1
        self.replace_used = False
        self.replaced_task_id = None
        self.replace_timestamp = None

    def record_draw(self, task):
        self.last_drawn_task_id = task.id
        self.last_drawn_category = task.category
        self.category_history.append(task.category)
        if len(self.category_history) > 3:
            self.category_history.pop(0)

    def can_replace(self):
        return not self.replace_used

    def use_replace(self, task_id):
        self.replace_used = True
        self.replaced_task_id = task_id
        self.replace_timestamp = datetime.now()

    @property
    def category_count_in_last_3(self):
        counts: Dict[str, int] = {}
        for cat in self.category_history:
            counts[cat] = counts.get(cat, 0) + 1
        return counts


class DrawResult:
    """一次抽卡的结果。"""

    def __init__(
        self, task=None, pool=None, can_replace=False, is_replacement=False
    ):
        self.task = task
        self.pool = pool
        self.can_replace = can_replace
        self.is_replacement = is_replacement
