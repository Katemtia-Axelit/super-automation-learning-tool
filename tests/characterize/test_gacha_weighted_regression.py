"""Gacha weighted-regression: deterministic characterization of DefaultGachaAlgo +
server.blueprints.gacha_bp._draw, run inside a source-only sandbox.

Goals (3 small deterministic tests):
1) compute_weight: same other fields, priority 10 > priority 1, and increasing
   refusal_count decreases the weight (above the 0.3 floor).
2) pick: cumulative-weight sampling, NOT uniform random.choice. With a small
   random value the high-weight item wins, with a value near 1.0 the
   low-weight item wins.
3) End-to-end through the blueprint _draw(None, tasks, "tomato") inside a
   source-only sandbox child process: two same-pool tasks (estimated_time=25,
   priority 10 vs 1) and a fixed random.random=0.05/0.999 select the
   respective high/low priority task.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
from server.services.gacha import DefaultGachaAlgo, WeightInputs  # noqa: E402

_SANDBOX_SRC = SOURCE_ROOT / "server"

def _walk_python_files(root):
    out = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            p = Path(dirpath) / f
            if p.suffix == ".py":
                out.append(p)
    return out


def _materialize_sandbox(dest):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "server").mkdir(exist_ok=True)
    for src in _walk_python_files(_SANDBOX_SRC):
        rel = src.relative_to(_SANDBOX_SRC)
        target = dest / "server" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)


def _make_task(**overrides):
    base = dict(
        id=1, priority=5, energy_required="medium", resistance="low",
        success_rate=0.0, refusal_count=0, deadline=None,
        category="daily", task_profile=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)

class DefaultGachaAlgoUnitTests(unittest.TestCase):
    def test_compute_weight_priority_and_refusal_monotonicity(self):
        algo = DefaultGachaAlgo()
        baseline = dict(
            energy_required="medium", resistance="low", success_rate=0.0,
            deadline=None, category="daily", task_profile=None,
        )
        w_low = algo.compute_weight(
            WeightInputs(task=_make_task(priority=1, **baseline), current_energy="medium")
        )
        w_high = algo.compute_weight(
            WeightInputs(task=_make_task(priority=10, **baseline), current_energy="medium")
        )
        self.assertGreater(w_high, w_low, f"p10({w_high}) must exceed p1({w_low})")
        self.assertAlmostEqual(w_high, w_low * 10.0, places=6)
        w_r0 = algo.compute_weight(
            WeightInputs(task=_make_task(priority=10, refusal_count=0, **baseline),
                         current_energy="medium")
        )
        w_r3 = algo.compute_weight(
            WeightInputs(task=_make_task(priority=10, refusal_count=3, **baseline),
                         current_energy="medium")
        )
        w_r7 = algo.compute_weight(
            WeightInputs(task=_make_task(priority=10, refusal_count=7, **baseline),
                         current_energy="medium")
        )
        self.assertGreater(w_r0, w_r3, (w_r0, w_r3))
        self.assertGreater(w_r3, w_r7, (w_r3, w_r7))
        w_r99 = algo.compute_weight(
            WeightInputs(task=_make_task(priority=10, refusal_count=99, **baseline),
                         current_energy="medium")
        )
        self.assertAlmostEqual(w_r7, w_r99, places=6)
    def test_pick_is_cumulative_weight_not_uniform(self):
        algo = DefaultGachaAlgo()
        weights = [0.10, 0.90]
        class StubRng:
            def __init__(self, value):
                self._value = value
            def random(self):
                return self._value
            def randrange(self, n):
                return int(self._value * n) % n
        idx_small = algo.pick(2, weights, StubRng(0.05))
        idx_large = algo.pick(2, weights, StubRng(0.999))
        self.assertEqual(idx_small, 0, "small r must select the high-weight (index 0)")
        self.assertEqual(idx_large, 1, "large r must select the low-weight (index 1)")
        self.assertNotEqual(idx_small, idx_large)

_SANDBOX_DRIVER = """import json
import random
import sys
from pathlib import Path

# Sandbox root (the directory containing this driver) must be on sys.path
# so the relative server.blueprints import resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib
import server.blueprints  # ensure parent package init runs once
_gacha_module = importlib.import_module("server.blueprints.gacha_bp")

payload = json.loads(sys.argv[1])
random_value = float(sys.argv[2])

tasks = [dict(t) for t in payload["tasks"]]
random.random = lambda: random_value

selected = _gacha_module._draw(None, tasks, payload["pool"])
if selected is None:
    print("NONE")
else:
    print(json.dumps({"id": selected.get("id"), "name": selected.get("name")}))
"""


class SandboxSubprocessDrawTests(unittest.TestCase):
    def _run_in_sandbox(self, tasks, pool, random_value):
        with tempfile.TemporaryDirectory(prefix="lt_gacha_w_") as temp:
            root = Path(temp) / "sandbox"
            _materialize_sandbox(root)
            driver = root / "_driver.py"
            driver.write_text(_SANDBOX_DRIVER, encoding="utf-8")
            payload = json.dumps({"pool": pool, "tasks": tasks}, ensure_ascii=False)
            env = {
                "PATH": os.environ.get("PATH", ""),
                "SystemRoot": os.environ.get("SystemRoot", ""),
                "TEMP": os.environ.get("TEMP", temp),
                "TMP": os.environ.get("TMP", temp),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            proc = subprocess.run(
                [sys.executable, "-I", "_driver.py", payload, str(random_value)],
                cwd=root, env=env, capture_output=True, text=True, timeout=20,
            )
            if proc.returncode != 0:
                self.fail(
                    f"sandbox driver failed (rc={proc.returncode}); "
                    f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
                )
            return proc.stdout.strip()
    def test_draw_in_sandbox_selects_by_cumulative_weight(self):
        tasks = [
            {
                "id": 100, "name": "high-priority", "category": "daily",
                "estimated_time": 25, "energy_required": "medium",
                "resistance": "low", "success_rate": 0.0, "refusal_count": 0,
                "priority": 10, "deadline": None, "task_profile": None,
            },
            {
                "id": 200, "name": "low-priority", "category": "daily",
                "estimated_time": 25, "energy_required": "medium",
                "resistance": "low", "success_rate": 0.0, "refusal_count": 0,
                "priority": 1, "deadline": None, "task_profile": None,
            },
        ]
        out_small = self._run_in_sandbox(tasks, "tomato", 0.05)
        out_large = self._run_in_sandbox(tasks, "tomato", 0.999)
        self.assertNotEqual(out_small, "NONE", f"driver returned NONE: {out_small!r}")
        self.assertNotEqual(out_large, "NONE", f"driver returned NONE: {out_large!r}")
        result_small = json.loads(out_small)
        result_large = json.loads(out_large)
        self.assertEqual(
            result_small["id"], 100,
            f"small random.random must select high-priority task; got {result_small}",
        )
        self.assertEqual(
            result_large["id"], 200,
            f"large random.random must select low-priority task; got {result_large}",
        )


if __name__ == "__main__":
    unittest.main()