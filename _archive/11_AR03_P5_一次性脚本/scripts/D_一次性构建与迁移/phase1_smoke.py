"""phase1_smoke.py - 一次性 import 自测脚本.

跑法：
    PYTHONPATH=项目根 C:/Users/wn/AppData/Local/Programs/Python/Python312/python.exe scripts/phase1_smoke.py
"""
import os
import sys

# ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print("[1/4] import server.app.create_app ...")
from server.app import create_app  # noqa: E402

print("[2/4] create_app() ...")
app = create_app()
print("    type:", type(app).__name__)

print("[3/4] url_map rules:")
rules = sorted(f"{r.rule:40s} {sorted(r.methods - {'HEAD','OPTIONS'})}" for r in app.url_map.iter_rules())
for line in rules:
    print("   ", line)
print("    total:", len(rules))

print("[4/4] services.gacha DefaultGachaAlgo smoke ...")
from server.services.gacha import DefaultGachaAlgo, WeightInputs  # noqa: E402

class FakeTask:
    def __init__(self, **kw):
        self.priority = 5
        self.deadline = None
        self.energy_required = "medium"
        self.resistance = "low"
        self.success_rate = 0.0
        self.refusal_count = 0
        self.task_profile = "deadline_flexible"
        self.category = "daily"
        self.id = 1
        self.draw_count_today = 0
        for k, v in kw.items():
            setattr(self, k, v)

algo = DefaultGachaAlgo()
t = FakeTask(priority=5, energy_required="medium", resistance="low")
w = algo.compute_weight(WeightInputs(task=t, current_energy="medium"))
print("    weight(plain):", round(w, 4))
w2 = algo.compute_weight(WeightInputs(task=t, current_energy="high"))
print("    weight(mismatch energy):", round(w2, 4))
# pick smoke
import random
idx = algo.pick(3, [1.0, 2.0, 3.0], random)
assert idx in (0, 1, 2)
print("    pick(3, [1,2,3], random):", idx)

print("ALL OK")
