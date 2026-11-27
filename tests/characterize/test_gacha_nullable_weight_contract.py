"""Gacha nullable-weight contract: NULL/None in numeric weight fields must
still yield a finite, positive weight from DefaultGachaAlgo.compute_weight.

Two small stdlib unittest cases, run directly against
server.services.gacha.DefaultGachaAlgo (no sandbox, no subprocess).
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOURCE_ROOT))

from server.services.gacha import DefaultGachaAlgo, WeightInputs  # noqa: E402


def _make_task(**overrides):
    base = dict(
        id=1,
        priority=5,
        energy_required="medium",
        resistance="low",
        success_rate=0.0,
        refusal_count=0,
        deadline=None,
        category="daily",
        task_profile=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class GachaNullableWeightContractTests(unittest.TestCase):
    def test_compute_weight_with_none_numeric_fields_is_finite_positive(self):
        algo = DefaultGachaAlgo()
        task = _make_task(
            priority=None,
            success_rate=None,
            refusal_count=None,
        )
        sess = SimpleNamespace(
            last_drawn_task_id=None,
            last_drawn_category=None,
            category_count_in_last_3={},
        )
        inputs = WeightInputs(
            task=task,
            current_energy="medium",
            session_context=sess,
            draw_count_today=None,
        )
        w = algo.compute_weight(inputs)
        self.assertIsInstance(w, float)
        self.assertTrue(math.isfinite(w), f"weight must be finite, got {w!r}")
        self.assertGreater(w, 0.0, f"weight must be positive, got {w!r}")

    def test_compute_weight_priority10_strictly_greater_than_priority1(self):
        algo = DefaultGachaAlgo()
        baseline = dict(
            success_rate=0.5,
            refusal_count=0,
            energy_required="medium",
            resistance="low",
            deadline=None,
            category="daily",
            task_profile=None,
        )
        w_p10 = algo.compute_weight(
            WeightInputs(
                task=_make_task(priority=10, **baseline),
                current_energy="medium",
            )
        )
        w_p1 = algo.compute_weight(
            WeightInputs(
                task=_make_task(priority=1, **baseline),
                current_energy="medium",
            )
        )
        self.assertGreater(
            w_p10, w_p1,
            f"priority=10 weight ({w_p10}) must exceed priority=1 weight ({w_p1})",
        )


if __name__ == "__main__":
    unittest.main()
