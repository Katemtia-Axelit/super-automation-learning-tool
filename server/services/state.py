"""server.services.state - business logic for daily state / assessment domain.

Owns:
- ASSESSMENT_QUESTIONS constant (1-5 Likert scale)
- calculate_state_scores(answers, version) — pure function
- Sleep validation (HH:MM format + range)
- Streak update logic for sleep_early_streak
- Aggregation for correlation (>=3 samples; group by daily_tone)

Layered on top of `server.repositories.state_repo` (pure SQL).
No Flask imports — usable from CLI or BP.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# 评估问题（1-5分）
# Format: id, q (question text), reverse (5→1 inversion), weight (CHANGELOG ONLY — formula uses raw values)
ASSESSMENT_QUESTIONS: List[Dict[str, Any]] = [
    {"id": "cognitive", "q": "今天脑子转得动吗？思路清晰吗？", "reverse": False, "weight": 0.25},
    {"id": "focus", "q": "做题时容易分心走神吗？", "reverse": True, "weight": 0.20},
    {"id": "physical", "q": "有头晕、眼涩或身体不适吗？", "reverse": True, "weight": 0.15},
    {"id": "alertness", "q": "经常走神打哈欠吗？", "reverse": True, "weight": 0.20},
    {"id": "efficiency", "q": "学习效率感觉怎么样？", "reverse": False, "weight": 0.15},
    {"id": "motivation", "q": "面对困难任务想逃避吗？", "reverse": True, "weight": 0.05},
]


def calculate_state_scores(answers: Dict[str, int], version: int = 1) -> Dict[str, Any]:
    """根据答题计算精力/专注/心情分数。版本号用于迭代优化。

    V1 公式：加权平均 → 映射到 1-10。
    """
    scores: Dict[str, int] = {}
    for q in ASSESSMENT_QUESTIONS:
        raw = int(answers.get(q["id"], 3))
        scores[q["id"]] = (6 - raw) if q["reverse"] else raw

    if version == 1:
        energy = (
            scores["cognitive"] * 0.30
            + scores["physical"] * 0.25
            + scores["alertness"] * 0.25
            + scores["efficiency"] * 0.20
        ) * 2
        focus = scores["focus"] * 2
        mood = (
            scores["efficiency"] * 0.40
            + scores["motivation"] * 0.35
            + scores["cognitive"] * 0.25
        ) * 2

        avg = (energy + focus + mood) / 3
        if avg >= 7.0:
            tone = "high"
        elif avg >= 5.0:
            tone = "normal"
        elif avg >= 3.0:
            tone = "low"
        else:
            tone = "rest"
    else:
        energy = focus = mood = 5.0
        tone = "normal"

    return {
        "energy_score": round(energy, 1),
        "focus_score": round(focus, 1),
        "mood_score": round(mood, 1),
        "daily_tone": tone,
        "formula_version": version,
    }


# =============================================================================
# Sleep validation
# =============================================================================

_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")


def validate_bed_time(bed_time: str) -> Optional[str]:
    """Return None if valid, error message if invalid.

    Validates HH:MM format + hour/minute range.
    Mirrors backend_api.py L2322-2329 inline validation.
    """
    if not bed_time:
        return "请输入入睡时间"
    if not _HHMM_RE.match(bed_time):
        return "入睡时间格式应为 HH:MM"
    try:
        h, m = bed_time.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            return "入睡时间无效"
    except ValueError:
        return "入睡时间无效"
    return None


def compute_sleep_streak(prev_streak: int, status: str) -> int:
    """Apply streak update rule: on_time → +1, else → 0."""
    if status == "on_time":
        return prev_streak + 1
    return 0


# =============================================================================
# Correlation aggregation
# =============================================================================

def aggregate_correlation(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Group correlation samples by daily_tone; return aggregated stats.

    Mirrors backend_api.py L3457-3478 inline logic.
    Returns dict with 'samples' (count) and 'tone_stats' (per-tone stats).
    """
    total = len(rows)
    if total < 3:
        return {"message": "样本不足，需至少3天数据", "samples": total}

    tone_stats: Dict[str, Dict[str, int]] = {}
    for r in rows:
        t = r["daily_tone"]
        if t not in tone_stats:
            tone_stats[t] = {"days": 0, "total_completed": 0}
        tone_stats[t]["days"] += 1
        tone_stats[t]["total_completed"] += r["completed"] or 0

    for t in tone_stats:
        tone_stats[t]["avg_completed"] = round(
            tone_stats[t]["total_completed"] / max(1, tone_stats[t]["days"]), 1
        )

    return {
        "samples": total,
        "tone_stats": tone_stats,
        "latest": rows[:7],
    }


# =============================================================================
# Energy period validation
# =============================================================================

VALID_PERIODS = ("morning", "afternoon", "evening")


def validate_period(period: str) -> Optional[str]:
    """Return None if valid; error message if not."""
    if period not in VALID_PERIODS:
        return f"period must be one of {VALID_PERIODS}"
    return None


__all__ = [
    "ASSESSMENT_QUESTIONS",
    "calculate_state_scores",
    "validate_bed_time",
    "compute_sleep_streak",
    "aggregate_correlation",
    "validate_period",
    "VALID_PERIODS",
]
