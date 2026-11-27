"""M02-S01-G01-W03: 已批准 Agent 策略真的改变正式抽卡概率。

范围与红线
----------
- 只打真实 ``server.blueprints.gacha_bp`` 的正式 HTTP 路由
  （``/api/gacha/draw``、``/care-draw``、``/replace``、``/multi-draw``），
  经 Flask ``test_client``；**不** 只测孤立 helper。
- 全部状态在 ``tempfile`` 临时目录内：合成 SQLite、合成策略目录。
  不读写真实 ``data/task_publisher.db``、``src/notes/**``、
  ``config/config.json``、``data/agent-policy/**``。
- 策略只经 **真实受控 Publisher**（``scripts.agent_policy_publisher``）
  在合成目录里发布，绝不伪造"用户已批准"到真实项目。

权重契约（W03 修复的核心）
--------------------------
正式 Publisher 的合法权重域是 **[0, 1]**（见
``scripts/agent_policy_publisher._validate_weights`` 的 ``MIN_WEIGHT`` /
``MAX_WEIGHT``）。因此本文件的全部 **正向** fixture 都必须落在 [0, 1]：
W02 曾经使用的 ``5.0`` / ``4.0`` 之类根本发不出来（发布阶段即
``PublisherError invalid_weights``），那是接口契约冲突，不是测试环境问题。

``weights["category:<类别>"]`` 的语义是 **相对倾向系数**：

- ``1.0`` = 中性（该类别维持基准相对地位）；
- ``0``   = 明确停发该类别（该类别的卡被移出候选集）；
- ``0 < v < 1`` = 在基础权重之上再乘 ``v``（把该类别相对压低）。

例：``{"category:goal": 1.0, "category:free": 0.2}`` 表示 goal : free ≈
5 : 1 的相对倾向。这 **不等于**"goal 出现率变成旧基准的五倍"，也
**不允许** > 1 的值。

判据
----
1. 合法发布 + 同种子 rng：改变 ``weights["category:<类别>"]`` 必须改变
   实际抽中的卡（"同一池、其它条件相同、类别不同"）。
2. 无 ``category:`` 前缀的键（``focus``/``rest``）不得被猜成类别；
   未批准草案 / 非法权重不得激活；旧行为逐位保留。
3. 抽卡记录、时间预算等既有机制不受影响。
4. draw / care-draw / replace / multi-draw 走 **同一条** 权重接线。
5. 全部类别被停发时保守地"无卡可发"，绝不悄悄均匀退回。
6. **Publisher 契约对齐**：同一份 fixture 必须能经真实 Publisher 发出去
   （W03 之前 ``5.0`` / ``4.0`` 在这里直接失败）。
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import importlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SOURCE_ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(SOURCE_ROOT), str(SOURCE_ROOT / "scripts")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from flask import Flask  # noqa: E402

# `server.blueprints.gacha_bp` 这个名字在包级别被 Blueprint 实例遮蔽了，
# 因此按真实子模块路径取模块，才能同时拿到路由与内部权重 helper。
gacha_module = importlib.import_module("server.blueprints.gacha_bp")
publisher = importlib.import_module("agent_policy_publisher")
from server.services import agent_policy  # noqa: E402

#: 正式 Publisher 的合法权重域（本文件所有正向 fixture 必须落在其中）。
PUBLISHER_MIN_WEIGHT = publisher.MIN_WEIGHT
PUBLISHER_MAX_WEIGHT = publisher.MAX_WEIGHT

# 与 tests/characterize/sandbox_env.py 相同的合成 schema（只建用到的表）。
_SYNTH_SCHEMA = """
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, category TEXT DEFAULT 'daily',
  task_type TEXT DEFAULT 'normal', description TEXT,
  estimated_time INTEGER DEFAULT 25, preferred_time TEXT, deadline TEXT,
  resistance TEXT DEFAULT 'medium', energy_required TEXT DEFAULT 'medium',
  rarity TEXT DEFAULT 'common', priority INTEGER DEFAULT 5,
  success_rate REAL DEFAULT 0.0, refusal_count INTEGER DEFAULT 0,
  is_daily INTEGER DEFAULT 0, completed INTEGER DEFAULT 0,
  repeat_type TEXT DEFAULT 'none', task_profile TEXT DEFAULT NULL,
  parent_task_id INTEGER, group_id INTEGER, last_completed_at TEXT,
  next_available_at TEXT, last_drawn_at TEXT, draw_count_today INTEGER DEFAULT 0,
  min_push_time TEXT DEFAULT '20:00', in_discard_pile INTEGER DEFAULT 0,
  completed_count INTEGER DEFAULT 0, tags TEXT,
  difficulty TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  prerequisite_ids TEXT DEFAULT '[]', is_unlocked INTEGER DEFAULT 1,
  linked_note_path TEXT
);
CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);
CREATE TABLE task_tags (task_id INTEGER, tag_id INTEGER);
CREATE TABLE gacha_records (
  id INTEGER PRIMARY KEY, task_id INTEGER, pool_name TEXT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP, available_time INTEGER,
  accepted INTEGER DEFAULT 1, refusal_reason TEXT
);
CREATE TABLE task_rejection_log (
  id INTEGER PRIMARY KEY, task_id INTEGER, reason TEXT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextlib.contextmanager
def _patched_rng(value: float):
    """把 gacha_bp 使用的 random 换成确定性替身（只在本测试进程内）。"""
    with mock.patch.object(gacha_module, "random", _FixedRng(value)):
        yield


@contextlib.contextmanager
def _synthetic_root(prefix: str):
    """合成工作目录。

    ``ignore_cleanup_errors=True``：Windows 上 SQLite 的 WAL / SHM 副产物
    可能仍被短暂持有，清理失败 **不该** 被当成测试失败（它只发生在
    临时目录里，绝不涉及项目真实数据）。
    """
    with tempfile.TemporaryDirectory(
        prefix=prefix, ignore_cleanup_errors=True
    ) as temp:
        yield Path(temp)


class _FixedRng:
    """确定性 rng 替身：让同一请求在相同策略下抽到同一张卡。"""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value

    def randrange(self, n: int) -> int:
        return min(n - 1, int(self.value * n))


class _Harness:
    """一次性的合成 app + 合成 DB + 合成策略目录（全部在临时目录内）。"""

    def __init__(self, root: Path, enforce_bootstrap_gate: bool = False) -> None:
        self.root = root
        self.db_path = root / "synthetic.sqlite3"
        self.policy_dir = root / "agent-policy"
        self.policy_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as db:
            db.executescript(_SYNTH_SCHEMA)
            db.commit()
        self.app = Flask(__name__)
        self.app.config["_db_path"] = str(self.db_path)
        self.app.config["_project_root"] = str(root)
        self.app.config["_agent_policy_dir"] = str(self.policy_dir)
        self.app.config[agent_policy.ENFORCE_CONFIG_KEY] = bool(
            enforce_bootstrap_gate
        )
        self.app.register_blueprint(gacha_module.gacha_bp)
        if enforce_bootstrap_gate:
            # 真实服务端闸门；默认关闭是既有产品决定，本测试显式开启。
            agent_policy.install_bootstrap_gate(self.app, str(self.policy_dir))
        self.client = self.app.test_client()
        self._published = 0

    # --- 合成任务 ---------------------------------------------------------
    def add_task(self, task_id: int, name: str, category: str, **fields) -> None:
        columns = {
            "id": task_id,
            "name": name,
            "category": category,
            "estimated_time": fields.pop("estimated_time", 25),
            "priority": fields.pop("priority", 5),
            "energy_required": fields.pop("energy_required", "medium"),
            "resistance": fields.pop("resistance", "low"),
            "task_profile": fields.pop("task_profile", None),
        }
        columns.update(fields)
        placeholders = ", ".join("?" for _ in columns)
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                f"INSERT INTO tasks ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(columns.values()),
            )
            db.commit()

    # --- 合成策略（只经真实 Publisher 发布到合成目录） ---------------------
    def publish(self, weights, *, policy=None) -> dict:
        self._published += 1
        proposal = {
            "schema_version": 1,
            "version": f"2099-01-01.{self._published}",
            "effect_summary": "synthetic effect summary for policy weight wiring test",
            "weights": weights,
            "policy": policy or {},
        }
        return publisher.publish(
            str(self.policy_dir),
            proposal,
            proposal_digest_expected=publisher.proposal_digest(proposal),
            approval_evidence={
                "approved_by": "synthetic-reviewer",
                "approval_text": "synthetic approval for integration test only",
                "session_id": "lt-m02-s01-g01-w03-synthetic",
                "approved_at": _dt.datetime.now(_dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            },
            authorize=True,
            authorization_note="synthetic integration test publication",
            create_policy_dir=True,
        )

    def write_raw_latest(self, document) -> None:
        """直接放一份 latest.json（仅用于"草案/未批准"这类负向用例）。"""
        (self.policy_dir / "latest.json").write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )

    # --- 断言辅助 ---------------------------------------------------------
    def counts(self, query: str):
        with sqlite3.connect(self.db_path) as db:
            return db.execute(query).fetchone()[0]

    def drawn_id(self, **payload):
        response = self.client.post("/api/gacha/draw", json=payload)
        return response, (response.get_json() or {})


def _draft_document(weights, *, approved=True):
    return {
        "schema_version": 1,
        "version": "2099-01-01.99",
        "approved_by_user": approved,
        "approved_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "effect_summary": "synthetic draft",
        "weights": weights,
    }


class PublisherWeightDomainContractTests(unittest.TestCase):
    """W03 契约对齐：正向 fixture 必须真的能被正式 Publisher 发出去。"""

    def test_positive_fixtures_are_publishable_and_illegal_ones_are_rejected(self):
        """合法 [0,1] 能发布；>1 的值被 Publisher 直接拒绝（契约证据）。"""
        with _synthetic_root("lt_policy_domain_") as temp:
            harness = _Harness(temp)

            # 合法：相对倾向系数 1.0 / 0.2（goal : free ≈ 5 : 1）。
            harness.publish({"category:goal": 1.0, "category:free": 0.2})
            self.assertTrue((harness.policy_dir / "latest.json").is_file())

            # 边界：0 与 1 都是合法值。
            harness.publish({"category:goal": 0.0})
            harness.publish({"category:goal": 1.0})

            # >1 的值 **发不出来** —— 这正是 W02 的真实阻塞点。
            for illegal in (1.5, 4.0, 5.0, 100.0):
                with self.subTest(value=illegal):
                    with self.assertRaises(publisher.PublisherError) as caught:
                        harness.publish({"category:goal": illegal})
                    self.assertEqual(caught.exception.code, "invalid_weights")

    def test_module_coefficient_domain_matches_publisher(self):
        """模块的合法域必须与 Publisher 完全一致（否则又是接口冲突）。"""
        self.assertEqual(
            gacha_module.MIN_CATEGORY_COEFFICIENT, PUBLISHER_MIN_WEIGHT
        )
        self.assertEqual(
            gacha_module.MAX_CATEGORY_COEFFICIENT, PUBLISHER_MAX_WEIGHT
        )
        self.assertLessEqual(gacha_module.MAX_CATEGORY_COEFFICIENT, 1.0)

    def test_values_above_one_are_ignored_by_the_reader(self):
        """即使 latest.json 里被塞进 >1 的值，消费端也必须忽略它。"""
        with _synthetic_root("lt_policy_above_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "high-priority-free", "free", priority=10)
            harness.add_task(2, "low-priority-goal", "goal", priority=1)

            with _patched_rng(0.999):
                response, baseline = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, baseline)
            self.assertEqual(baseline["task"]["id"], 2, baseline)

            # 伪造一份"已批准但含 >1 系数"的 latest（绕过 Publisher）。
            harness.write_raw_latest(
                _draft_document({"category:goal": 5.0})
            )
            with _patched_rng(0.999):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(
                body["task"]["id"],
                baseline["task"]["id"],
                "out-of-domain coefficient must not change the old draw outcome",
            )


class ApprovedPolicyWeightIntegrationTests(unittest.TestCase):
    """合法批准的策略必须实际改变正式抽卡概率。"""

    def test_category_weight_changes_actual_draw_outcome(self):
        """同一池、其它条件相同、类别不同 → 系数一换，抽中的卡就换。"""
        with _synthetic_root("lt_policy_w_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "free")
            harness.add_task(2, "goal-card", "goal")

            # 压低 goal（自由卡保持中性 1.0）→ 应该抽到 free。
            harness.publish({"category:goal": 0.2})
            with _patched_rng(0.5):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["id"], 1, body)

            # 只改系数（同一 rng、同样的卡池与其它条件）→ 结果必须改变。
            harness.publish({"category:goal": 1.0, "category:free": 0.2})
            with _patched_rng(0.5):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["id"], 2, body)

            # 抽卡记录机制仍然每次落一行，权重接线没有破坏它。
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM gacha_records WHERE refusal_reason IS NULL"
                ),
                2,
            )

    def test_relative_ratio_of_coefficients_is_observable(self):
        """goal=1.0 / free=0.2 表达的是 5:1 的相对倾向（不是概率本身）。"""
        with _synthetic_root("lt_policy_ratio_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "free")
            harness.add_task(2, "goal-card", "goal")

            harness.publish({"category:goal": 1.0, "category:free": 0.2})

            # 采样 20 次：压低到 1/5 的 free 明显更少被抽到。
            drawn = []
            for _ in range(20):
                with _patched_rng(0.5):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                drawn.append(body["task"]["category"])
            goal_count = drawn.count("goal")
            free_count = drawn.count("free")
            self.assertGreater(goal_count, free_count, drawn)

    def test_unprefixed_keys_and_unapproved_draft_keep_old_behaviour(self):
        """无前缀键 / 未批准草案 / 非法权重都不得激活，旧抽卡逐位保留。"""
        cases = {
            "unprefixed_focus_rest": ({"focus": 1.0, "rest": 0.0}, True),
            "negative_value": ({"category:goal": -1.0}, True),
            "out_of_range_value": ({"category:goal": 1e9}, True),
            "above_one_value": ({"category:goal": 5.0}, True),
            "non_numeric_value": ({"category:goal": "high"}, True),
            "weights_not_object": ("category:goal=1", True),
            "draft_not_approved": ({"category:goal": 0.01}, False),
        }
        for label, (weights, approved) in cases.items():
            with self.subTest(case=label), _synthetic_root(
                "lt_policy_neg_"
            ) as temp:
                harness = _Harness(temp)
                # priority 差异让旧权重可区分：高档任务先、低档任务后。
                harness.add_task(1, "high-priority-free", "free", priority=10)
                harness.add_task(2, "low-priority-goal", "goal", priority=1)

                # 基线：完全没有策略时 rng=0.999 必须抽到权重最低的那张。
                with _patched_rng(0.999):
                    response, baseline = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, baseline)
                self.assertEqual(baseline["task"]["id"], 2, baseline)

                if isinstance(weights, str):
                    (harness.policy_dir / "latest.json").write_text(
                        weights, encoding="utf-8"
                    )
                else:
                    harness.write_raw_latest(
                        _draft_document(weights, approved=approved)
                    )

                with _patched_rng(0.999):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(
                    body["task"]["id"],
                    baseline["task"]["id"],
                    f"{label} must not change the old draw outcome",
                )

    def test_bootstrap_gate_still_blocks_writes_without_approved_policy(self):
        """无有效策略时，正式抽卡写请求仍由既有服务端闸门 fail closed。"""
        with _synthetic_root("lt_policy_gate_") as temp:
            harness = _Harness(temp, enforce_bootstrap_gate=True)
            harness.add_task(1, "free-card", "free")
            harness.write_raw_latest(_draft_document({"category:free": 0.0}, approved=False))
            response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 423, body)
            self.assertEqual(body["error"], "bootstrap-locked", body)

            harness.publish({"category:free": 1.0})
            with _patched_rng(0.5):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["id"], 1, body)

    def test_all_categories_stopped_yields_no_card_not_uniform_fallback(self):
        """整个池被停发 → 保守地"无卡可发"，绝不悄悄均匀退回。"""
        with _synthetic_root("lt_policy_zero_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "free")
            harness.add_task(2, "goal-card", "goal")
            harness.publish({"category:free": 0.0, "category:goal": 0.0})
            for rng_value in (0.1, 0.9):
                with _patched_rng(rng_value):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 404, body)
                self.assertEqual(body["error"], "No tasks available", body)
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM gacha_records WHERE refusal_reason IS NULL"
                ),
                0,
            )

    def test_single_category_stopped_survives_others_and_keeps_budget(self):
        """只停发一个类别：另一个类别照发，且时间预算仍然生效。"""
        with _synthetic_root("lt_policy_partial_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "free")
            harness.add_task(2, "goal-card", "goal")
            harness.add_task(3, "too-long", "goal", estimated_time=90)
            harness.publish({"category:free": 0.0, "category:goal": 1.0})
            for rng_value in (0.05, 0.5, 0.999):
                with _patched_rng(rng_value):
                    response, body = harness.drawn_id(
                        pool="tomato", available_time=25
                    )
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(body["task"]["category"], "goal", body)
                self.assertLessEqual(body["task"]["estimated_time"], 25, body)

    def test_zero_weight_category_is_never_drawn(self):
        """零权重类别必须被 **移出候选**，绝不在累积抽样边界上被误抽。"""
        with _synthetic_root("lt_policy_never_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "free")
            harness.add_task(2, "goal-card", "goal")
            harness.publish({"category:free": 0.0, "category:goal": 1.0})
            # 覆盖整个 [0,1] 采样区间：free 一次都不许被抽到。
            for step in range(101):
                rng_value = step / 100.0
                with _patched_rng(rng_value):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertNotEqual(body["task"]["category"], "free", body)


class SharedWeightPathTests(unittest.TestCase):
    """四条抽卡路径必须复用同一条权重接线。"""

    def _seeded(self, temp: Path) -> _Harness:
        harness = _Harness(temp)
        harness.add_task(1, "free-1", "free")
        harness.add_task(2, "free-2", "free")
        harness.add_task(3, "goal-1", "goal")
        harness.add_task(4, "goal-2", "goal")
        harness.add_task(5, "free-long", "free", estimated_time=90)
        return harness

    def test_care_draw_replace_and_multi_draw_share_policy_weights(self):
        with _synthetic_root("lt_policy_paths_") as temp:
            harness = self._seeded(temp)
            harness.publish({"category:free": 0.2, "category:goal": 1.0})

            with _patched_rng(0.5):
                care = harness.client.post(
                    "/api/gacha/care-draw", json={"pool": "tomato"}
                ).get_json()
            self.assertEqual(care["task"]["category"], "goal", care)

            with _patched_rng(0.5):
                replaced = harness.client.post(
                    "/api/gacha/replace",
                    json={"task_id": 1, "pool": "tomato", "reason": "other"},
                ).get_json()
            self.assertEqual(replaced["task"]["category"], "goal", replaced)
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM task_rejection_log WHERE task_id=1"
                ),
                1,
            )

            # multi-draw 同样走这条接线：60 分钟预算内，被压低的 free 类
            # 不再被抽到（只剩两张 goal 卡能装进预算 → 合法部分结果）。
            with _patched_rng(0.5):
                multi = harness.client.post(
                    "/api/gacha/multi-draw",
                    json={"available_time": 60, "count": 3},
                ).get_json()
            self.assertGreaterEqual(len(multi["tasks"]), 1, multi)
            self.assertEqual(
                [task["category"] for task in multi["tasks"]],
                ["goal"] * len(multi["tasks"]),
                multi,
            )
            self.assertLessEqual(multi["total_minutes"], 60, multi)
            self.assertTrue(
                all(task["estimated_time"] <= 60 for task in multi["tasks"]), multi
            )
            # 发行行（refusal_reason IS NULL）：care-draw 未走时间预算路径，
            # 按既有行为不写发行行（只写 draw_count_today）；replace 写 1 行；
            # multi-draw 每张卡写 1 行。
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM gacha_records WHERE refusal_reason IS NULL"
                ),
                1 + len(multi["tasks"]),
            )
            # 但 **抽卡计数** 四条路径都照常递增（被拒的卡只加 refusal_count，
            # 不加 draw_count_today）：care-draw 1 + replace 1 + multi-draw N。
            self.assertEqual(
                harness.counts(
                    "SELECT COALESCE(SUM(draw_count_today), 0) FROM tasks"
                ),
                2 + len(multi["tasks"]),
            )


if __name__ == "__main__":
    unittest.main()
