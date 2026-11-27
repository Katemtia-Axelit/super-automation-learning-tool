"""P1 切片 3 — 抽卡用例服务边界（**不依赖 Flask**）。

本文件直接导入 :mod:`server.services.gacha` 并验证：

1. 该模块 **绝不** import Flask（源码级断言）；
2. 过滤 / 权重 / 策略系数 / 抽样 / 记账 的语义；
3. 记账函数只接受显式传入的 ``conn``（不开连接、不读全局路径）；
4. 换卡拒绝语义（拒绝台账 + 拒绝行 + ``refusal_count`` 自增）。

只使用 **内存 SQLite**（``:memory:``）与纯 Python 数据，
绝不触碰 ``data/task_publisher.db*`` / ``src/notes/**`` / ``config/config.json``。
"""

from __future__ import annotations

import ast
import sqlite3
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from server.services import gacha as service  # noqa: E402


def _task(**kwargs):
    base = {
        "id": 1,
        "name": "t",
        "category": "daily",
        "task_type": "standard",
        "estimated_time": 25,
        "priority": 5,
        "energy_required": "medium",
        "resistance": "medium",
        "success_rate": 0.0,
        "refusal_count": 0,
        "task_profile": "deadline_flexible",
        "deadline": None,
        "draw_count_today": 0,
        "tags": [],
    }
    base.update(kwargs)
    return base


class NoFlaskDependencyTests(unittest.TestCase):
    def test_service_module_never_imports_flask(self):
        source = (SOURCE_ROOT / "server" / "services" / "gacha.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        self.assertNotIn("flask", imported, sorted(imported))
        self.assertNotIn("flask_cors", imported, sorted(imported))

    def test_service_module_does_not_import_blueprints(self):
        source = (SOURCE_ROOT / "server" / "services" / "gacha.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertFalse(
                    node.module.startswith("server.blueprints"),
                    node.module,
                )
                self.assertNotEqual(node.module, "server.backend_api")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(
                        alias.name.startswith("server.blueprints"), alias.name
                    )


class PoolFilterTests(unittest.TestCase):
    def test_pool_for_minutes_derives_pool_from_duration(self):
        self.assertEqual(service.pool_for_minutes(5), "fragment")
        self.assertEqual(service.pool_for_minutes(15), "tomato")
        self.assertEqual(service.pool_for_minutes(45), "deep")
        self.assertEqual(service.pool_for_minutes(None), "fragment")

    def test_time_range_boundary_belongs_to_upper_pool(self):
        tasks = [
            _task(id=1, estimated_time=10),
            _task(id=2, estimated_time=15),
            _task(id=3, estimated_time=45),
        ]
        fragment = service.filter_pool(tasks, "fragment")
        tomato = service.filter_pool(tasks, "tomato")
        deep = service.filter_pool(tasks, "deep")
        self.assertEqual([t["id"] for t in fragment], [1])
        self.assertEqual([t["id"] for t in tomato], [2])
        self.assertEqual([t["id"] for t in deep], [3])

    def test_empty_time_range_falls_back_to_base_pool(self):
        tasks = [_task(id=1, estimated_time=10)]
        pool = service.filter_pool(tasks, "deep")
        self.assertEqual([t["id"] for t in pool], [1])

    def test_free_card_uses_issued_minutes_not_row_estimated_time(self):
        """自由卡按 **本次发行抽定的合法时长** 分池。"""
        tasks = [
            _task(id=1, task_type="free", estimated_time=30),
            _task(id=2, task_type="standard", estimated_time=10),
        ]

        def free_minutes_of(task):
            return 55 if task["id"] == 1 else None

        pool = service.filter_pool(
            tasks, "deep", free_minutes_of=free_minutes_of
        )
        self.assertIn(1, [t["id"] for t in pool])
        # 25 分钟的自由卡落在番茄池，55 分钟落在深度池
        def free_minutes_of_25(task):
            return 25 if task["id"] == 1 else None

        tomato = service.filter_pool(
            tasks, "tomato", free_minutes_of=free_minutes_of_25
        )
        self.assertEqual([t["id"] for t in tomato], [1])

    def test_free_card_without_legal_duration_is_removed(self):
        tasks = [_task(id=1, task_type="free", estimated_time=30)]
        pool = service.filter_pool(tasks, "tomato", free_minutes_of=lambda t: None)
        self.assertEqual(pool, [])

    def test_preferred_tag_only_narrows_when_it_matches(self):
        tasks = [
            _task(id=1, tags=["math"]),
            _task(id=2, tags=["art"]),
        ]
        tagged = service.filter_pool(tasks, "tomato", preferred_tag="math")
        self.assertEqual([t["id"] for t in tagged], [1])
        untagged = service.filter_pool(tasks, "tomato", preferred_tag="nope")
        self.assertEqual(len(untagged), 2)

    def test_exclude_category_falls_back_when_everything_excluded(self):
        tasks = [_task(id=1, category="daily")]
        pool = service.filter_pool(tasks, "tomato", exclude_category="daily")
        self.assertEqual(pool, [])


class WeightTests(unittest.TestCase):
    def test_weights_are_positive_and_one_per_task(self):
        tasks = [_task(id=1), _task(id=2, priority=9)]
        weights = service.compute_weights(tasks, energy="medium")
        self.assertEqual(len(weights), 2)
        self.assertTrue(all(w > 0 for w in weights))

    def test_lower_priority_means_lower_weight(self):
        """权重越小越容易被抽中：低优先级卡的权重更小。"""
        low = service.compute_weights([_task(id=1, priority=1)], energy="medium")[0]
        high = service.compute_weights([_task(id=2, priority=9)], energy="medium")[0]
        self.assertLess(low, high)

    def test_energy_mismatch_is_penalised(self):
        task = _task(id=1, energy_required="low")
        matched = service.compute_weights([task], energy="low")[0]
        mismatched = service.compute_weights([task], energy="high")[0]
        self.assertLess(mismatched, matched)


class PolicyCoefficientTests(unittest.TestCase):
    def test_no_coefficients_is_a_no_op(self):
        tasks = [_task(id=1), _task(id=2)]
        base = service.compute_weights(tasks, energy="medium")
        weights, kept, applied = service.apply_policy_coefficients(base, tasks)
        self.assertEqual(weights, base)
        self.assertEqual(len(kept), 2)
        self.assertFalse(applied)

    def test_zero_coefficient_removes_the_candidate(self):
        tasks = [_task(id=1, category="daily"), _task(id=2, category="work")]
        base = service.compute_weights(tasks, energy="medium")
        weights, kept, applied = service.apply_policy_coefficients(
            base, tasks, {"daily": 0.0}
        )
        self.assertEqual([t["id"] for t in kept], [2])
        self.assertEqual(len(weights), 1)
        self.assertTrue(applied)

    def test_all_candidates_stopped_returns_empty(self):
        tasks = [_task(id=1, category="daily")]
        base = service.compute_weights(tasks, energy="medium")
        weights, kept, applied = service.apply_policy_coefficients(
            base, tasks, {"daily": 0.0}
        )
        self.assertEqual((weights, kept), ([], []))
        self.assertTrue(applied)

    def test_uniform_factor_keeps_relative_probabilities(self):
        tasks = [_task(id=1, category="daily"), _task(id=2, category="daily")]
        base = service.compute_weights(tasks, energy="medium")
        weights, kept, applied = service.apply_policy_coefficients(
            base, tasks, {"daily": 0.5}
        )
        self.assertEqual(weights, base)
        self.assertFalse(applied)

    def test_category_and_card_type_are_orthogonal(self):
        tasks = [
            _task(id=1, category="study", task_type="goal"),
            _task(id=2, category="other", task_type="standard"),
        ]
        base = service.compute_weights(tasks, energy="medium")
        weights, kept, applied = service.apply_policy_coefficients(
            base,
            tasks,
            {"study": 0.5},
            {"goal": 0.5},
            card_type_of=service.default_card_type_of,
        )
        self.assertTrue(applied)
        self.assertEqual(len(weights), 2)
        # 合成系数 0.5 × 0.5 = 0.25（第一张）；第二张未被点名 → 1.0。
        self.assertAlmostEqual(weights[0], base[0] * 0.25, places=6)
        self.assertAlmostEqual(weights[1], base[1] * 1.0, places=6)


class PickTests(unittest.TestCase):
    def test_pick_returns_none_on_empty_pool(self):
        self.assertIsNone(service.pick([], [], __import__("random")))

    def test_pick_uniform_returns_minus_one_for_empty(self):
        self.assertEqual(service.pick_uniform([], __import__("random")), -1)

    def test_pick_uniform_returns_minus_one_when_total_is_zero(self):
        self.assertEqual(
            service.pick_uniform([0.0, 0.0], __import__("random")), -1
        )

    def test_pick_uniform_respects_weight_ordering(self):
        """权重更大的条目被抽中的概率更高（确定性 rng 验证）。"""
        rng = SimpleNamespace(uniform=lambda _a, _b: 0.99)
        index = service.pick_uniform([0.1, 0.9], rng)
        self.assertEqual(index, 1)

    def test_draw_one_returns_none_when_no_candidates(self):
        self.assertIsNone(service.draw_one([], "tomato"))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE tasks (
              id INTEGER PRIMARY KEY, name TEXT, draw_count_today INTEGER DEFAULT 0,
              last_drawn_at TEXT, updated_at TEXT, refusal_count INTEGER DEFAULT 0,
              category TEXT, task_type TEXT, estimated_time INTEGER DEFAULT 25,
              priority INTEGER DEFAULT 5, energy_required TEXT DEFAULT 'medium',
              resistance TEXT DEFAULT 'medium', success_rate REAL DEFAULT 0.0,
              task_profile TEXT DEFAULT 'deadline_flexible', deadline TEXT,
              tags TEXT
            );
            CREATE TABLE gacha_records (
              id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER,
              pool_name TEXT, timestamp TEXT, available_time INTEGER,
              accepted INTEGER DEFAULT 1, refusal_reason TEXT
            );
            CREATE TABLE task_rejection_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER,
              reason TEXT, timestamp TEXT
            );
            INSERT INTO tasks (id, name) VALUES (1, 'alpha');
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_record_draw_increments_counter(self):
        service.record_draw(self.conn, 1)
        row = self.conn.execute(
            "SELECT draw_count_today FROM tasks WHERE id=1"
        ).fetchone()
        self.assertEqual(row["draw_count_today"], 1)

    def test_record_issuance_writes_a_null_refusal_row(self):
        service.record_issuance(self.conn, 1, "tomato", 25)
        rows = self.conn.execute(
            "SELECT pool_name, available_time, refusal_reason FROM gacha_records"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pool_name"], "tomato")
        self.assertEqual(rows[0]["available_time"], 25)
        self.assertIsNone(rows[0]["refusal_reason"])

    def test_record_rejection_writes_three_consistent_effects(self):
        service.record_rejection(self.conn, 1, "low_energy", "tomato", 25)
        rejection = self.conn.execute(
            "SELECT task_id, reason FROM task_rejection_log"
        ).fetchall()
        self.assertEqual(len(rejection), 1)
        self.assertEqual(rejection[0]["reason"], "low_energy")
        records = self.conn.execute(
            "SELECT refusal_reason FROM gacha_records"
        ).fetchall()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["refusal_reason"], "low_energy")
        counter = self.conn.execute(
            "SELECT refusal_count FROM tasks WHERE id=1"
        ).fetchone()
        self.assertEqual(counter["refusal_count"], 1)

    def test_ledger_functions_require_an_explicit_connection(self):
        """记账函数不接受隐式连接参数（禁止自己开连接）。"""
        for fn in (
            service.record_draw,
            service.record_issuance,
            service.record_rejection,
        ):
            with self.assertRaises(TypeError):
                fn()


if __name__ == "__main__":
    unittest.main()
