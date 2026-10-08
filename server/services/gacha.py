"""server.services.gacha - 抽卡算法接口隔离（Phase 1 收紧版）.

设计：
- `GachaAlgo` Protocol：定义权重计算/选取接口（鸭子类型；可被多种实现替换）
- `DefaultGachaAlgo`：行为等价 backend_api.py 内 _calculate_full_weight + select_weighted_random_task
  （原行为 100% 保留；Phase 2 替换 backend_api.py 实现时由 service 接管）
- `WeightInputs`：参数包（任务/当前精力/会话上下文）—— 不绑 Flask
- 抽卡流程编排仍由 backend_api.py 的 draw_single 负责（Phase 1 不动）

接口隔离收益（Phase 2/3 可替换）：
- 单元测试：可注入 mock algo（无随机性 / 强制返回指定 task）
- A/B 实验：可注入 ML 排序 algo
- 性能：可注入 numpy 向量化 algo
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Protocol, runtime_checkable


@dataclass
class WeightInputs:
    """Per-task input bundle for GachaAlgo.compute_weight."""

    task: object  # duck-typed: priority/energy_required/resistance/success_rate/refusal_count/...
    current_energy: str  # 'low' | 'medium' | 'high'
    session_context: Optional[object] = None  # duck-typed: last_drawn_task_id / last_drawn_category / category_count_in_last_3 / draw_count_today
    deadline: Optional[str] = None
    task_profile: Optional[str] = None
    draw_count_today: int = 0


@runtime_checkable
class GachaAlgo(Protocol):
    """抽卡算法接口。任何实现需提供：

    - compute_weight(inputs) -> float  (0.01 ~ ∞; 越小越难被选中)
    - pick(tasks, weights, rng) -> int  (返回选中的下标；rng = random module)
    """

    def compute_weight(self, inputs: WeightInputs) -> float: ...

    def pick(
        self, n: int, weights: List[float], rng: object
    ) -> int: ...


class DefaultGachaAlgo:
    """默认实现：行为等价 backend_api.py L1019-1138 段。

    1) compute_weight 综合 priority/deadline/energy/resistance/success_rate/
       refusal_count/profile_strategy/cooldown
    2) pick 走 cumulative weight 抽样
    """

    ENERGY_SCORE = {"low": 0, "medium": 1, "high": 2}
    RESISTANCE_PENALTY = {"low": 1.0, "medium": 0.8, "high": 0.6}
    DAILY_HABIT = "daily_habit"
    WEEKLY_ROUTINE = "weekly_routine"
    DEADLINE_FLEXIBLE = "deadline_flexible"
    DEADLINE_PROGRESSIVE = "deadline_progressive"

    def compute_weight(self, inputs: WeightInputs) -> float:
        t = inputs.task
        energy = inputs.current_energy
        sess = inputs.session_context
        weight = 1.0
        # priority 5 为基准
        weight *= getattr(t, "priority", 5) / 5.0
        # deadline urgency
        weight *= self._deadline_urgency(
            getattr(t, "deadline", None) or inputs.deadline
        )
        # energy match
        weight *= self._energy_match(
            getattr(t, "energy_required", "medium"), energy
        )
        # resistance penalty
        weight *= self.RESISTANCE_PENALTY.get(
            getattr(t, "resistance", "low"), 1.0
        )
        # success rate [0,1] -> [0.5, 1.0]
        weight *= 0.5 + getattr(t, "success_rate", 0.0) * 0.5
        # refusal count penalty (min 0.3)
        weight *= max(0.3, 1.0 - getattr(t, "refusal_count", 0) * 0.1)
        # profile strategy
        profile = getattr(t, "task_profile", None) or inputs.task_profile
        weight *= self._profile_strategy(profile, t)
        # cooldown / session context
        if sess is not None:
            weight *= self._cooldown(t, sess, inputs.draw_count_today)
        return max(0.01, float(weight))

    def pick(self, n, weights, rng):
        if n == 0:
            raise IndexError("Cannot pick from empty task list")
        total = sum(weights)
        if total <= 0:
            # all weights <= 0 → uniform random fallback
            return rng.randrange(n) if hasattr(rng, "randrange") else 0
        r = rng.random() * total if hasattr(rng, "random") else rng.uniform(0, total)
        cum = 0.0
        for i, w in enumerate(weights):
            cum += w
            if r <= cum:
                return i
        return n - 1

    # ----- helpers -----

    def _deadline_urgency(self, deadline):
        if not deadline:
            return 1.0
        try:
            dt = datetime.fromisoformat(deadline)
        except (TypeError, ValueError):
            return 1.0
        now = datetime.now()
        if dt <= now:
            return 3.0
        days_left = (dt - now).days
        if days_left <= 1:
            return 2.5
        if days_left <= 3:
            return 1.5
        if days_left <= 7:
            return 1.0 + (7.0 - days_left) * 0.1
        return 0.5

    def _energy_match(self, task_energy, current_energy):
        task_score = self.ENERGY_SCORE.get(task_energy, 1)
        cur_score = self.ENERGY_SCORE.get(current_energy, 1)
        diff = abs(task_score - cur_score)
        return max(0.5, 1.5 - diff * 0.3)

    def _profile_strategy(self, profile, task):
        if not profile:
            return 1.0
        now = datetime.now()
        if profile == self.DAILY_HABIT:
            return 0.0
        if profile == self.WEEKLY_ROUTINE:
            wd = now.weekday()
            if wd <= 3:
                return 0.3
            if wd <= 5:
                return 1.5
            return 3.0
        if profile == self.DEADLINE_FLEXIBLE:
            deadline = getattr(task, "deadline", None)
            if not deadline:
                return 1.0
            try:
                dt = datetime.fromisoformat(deadline)
            except (TypeError, ValueError):
                return 1.0
            days_left = (dt - now).days
            if days_left > 7:
                return 0.5
            if days_left > 3:
                return 1.0
            if days_left > 1:
                return 1.5
            return 2.5
        if profile == self.DEADLINE_PROGRESSIVE:
            return 1.0
        return 1.0

    def _cooldown(self, task, sess, draw_count_today):
        factor = 1.0
        last_id = getattr(sess, "last_drawn_task_id", None)
        if last_id is not None and getattr(task, "id", None) == last_id:
            return 0.0
        last_cat = getattr(sess, "last_drawn_category", None)
        if last_cat is not None and getattr(task, "category", None) == last_cat:
            factor *= 0.3
        cat_count = getattr(sess, "category_count_in_last_3", {}) or {}
        if cat_count.get(getattr(task, "category", None), 0) >= 2:
            factor *= 0.5
        if draw_count_today >= 3:
            factor *= 0.2
        return factor


__all__ = [
    "GachaAlgo",
    "DefaultGachaAlgo",
    "WeightInputs",
]
