"""M02-S01-G02-W02: 统一正式卡池的三种卡类型 + 已批准策略按卡类型派发。

范围与红线
----------
- 只打真实 ``server.blueprints.gacha_bp`` / ``server.blueprints.tasks_bp``
  的正式 HTTP 路由（``/api/gacha/draw``、``/care-draw``、``/replace``、
  ``/multi-draw``、``/api/tasks`` POST/PUT），经 Flask ``test_client``。
- 全部状态在 ``tempfile`` 临时目录内：合成 SQLite、合成策略目录。
  **绝不** 读写真实 ``data/task_publisher.db``、``src/notes/**``、
  ``config/config.json``、``data/agent-policy/**``。
- 策略只经 **真实受控 Publisher**（``scripts.agent_policy_publisher``）
  在合成目录里发布，绝不伪造"用户已批准"到真实项目。
- Harness 复用 ``tests/characterize/test_gacha_policy_weights.py`` 的形状
  （合成 schema + 合成 app + 确定性 rng 替身 + 真实 Publisher）。

核心契约
--------
1. **卡类型与内容类别正交**：``category:`` 管内容，``card_type:`` 管卡类型；
   两者相乘作用、互不覆盖、也互不猜测前缀。
2. **旧 ``task_type`` 一律按 standard**：``normal`` / ``other`` / ``NULL`` /
   空串 / 任何未知旧值 → ``standard``，**绝不** 被误当成自由卡。
3. **零系数严格停发**：``card_type:free: 0`` → 该卡 **移出候选**，
   绝不留在抽样边界上被误抽；全池清零 → 404，绝不均匀回退。
4. **未批准不生效**：草案／损坏 latest → 沿用原权重；Bootstrap 423 闸门
   依然 fail closed，绝不被绕过。
5. **旧行为不回退**：不带 ``card_type:`` 的策略、G01 的 ``category:`` 行为、
   发行记录、时间预算、四条抽卡路径的一致性全部保持。

新增任务类型写入面
------------------
``POST`` / ``PUT /api/tasks`` 显式接受 ``task_type`` 的
``free`` / ``micro`` / ``goal`` / ``standard``（以及已知历史别名），
拒绝无效新值与异常类型（400，**不可部分写入**）；省略该字段时保持既有
旧行为，**绝不** 自动给已有任务改型。
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
tasks_module = importlib.import_module("server.blueprints.tasks_bp")
publisher = importlib.import_module("agent_policy_publisher")
from server.services import agent_policy  # noqa: E402

#: 正式 Publisher 的合法权重域（本文件所有正向 fixture 必须落在其中）。
PUBLISHER_MIN_WEIGHT = publisher.MIN_WEIGHT
PUBLISHER_MAX_WEIGHT = publisher.MAX_WEIGHT

# 与 tests/characterize/test_gacha_policy_weights.py 相同的合成 schema
# （只建用到的表；``task_type`` 列是本轮行为的核心，必须存在）。
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
CREATE TABLE task_dependencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  depends_on_task_id INTEGER NOT NULL
);
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
        self.app.register_blueprint(tasks_module.tasks_bp)
        if enforce_bootstrap_gate:
            # 真实服务端闸门；默认关闭是既有产品决定，本测试显式开启。
            agent_policy.install_bootstrap_gate(self.app, str(self.policy_dir))
        self.client = self.app.test_client()
        self._published = 0

    # --- 合成任务 ---------------------------------------------------------
    def add_task(
        self,
        task_id: int,
        name: str,
        category: str,
        task_type="normal",
        **fields,
    ) -> None:
        columns = {
            "id": task_id,
            "name": name,
            "category": category,
            "task_type": task_type,
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

    def task_row(self, task_id: int):
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    # --- 合成策略（只经真实 Publisher 发布到合成目录） ---------------------
    def publish(self, weights, *, policy=None) -> dict:
        self._published += 1
        proposal = {
            "schema_version": 1,
            "version": f"2099-01-01.{self._published}",
            "effect_summary": "synthetic effect summary for card type pool test",
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
                "session_id": "lt-m02-s01-g02-w02-synthetic",
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


# ===========================================================================
# 1. 归一：历史 task_type 一律 standard，绝不误视自由卡
# ===========================================================================


class CardTypeNormalizationTests(unittest.TestCase):
    """旧 ``task_type`` 值在读取侧必须被稳妥视为 standard。"""

    def test_legacy_and_unknown_values_normalize_to_standard(self):
        """normal / other / NULL / 空串 / 未知值 → standard，绝不是 free。"""
        cases = {
            "normal": "normal",
            "other": "other",
            "null": None,
            "empty": "",
            "whitespace": "   ",
            "unknown_new_value": "brand_new_legacy_value",
            "daily": "daily",
            "note_review": "note_review",
        }
        for label, raw in cases.items():
            with self.subTest(case=label):
                normalized = gacha_module.normalize_card_type(raw)
                self.assertEqual(normalized, "standard")
                self.assertNotEqual(normalized, "free")

    def test_official_card_types_pass_through(self):
        """四种正式卡类型原样通过（只 strip，不折叠大小写）。"""
        for value in ("free", "micro", "goal", "standard"):
            with self.subTest(value=value):
                self.assertEqual(gacha_module.normalize_card_type(value), value)
        self.assertEqual(gacha_module.normalize_card_type(" free "), "free")
        # 大小写变体 **不** 被当成正式卡类型（落到 standard，绝不 free）。
        self.assertEqual(gacha_module.normalize_card_type("FREE"), "standard")

    def test_single_normalization_authority_is_shared(self):
        """抽卡侧与任务写入侧共用同一套词表（不会一处 free、一处 standard）。"""
        self.assertIs(gacha_module.CARD_TYPES, tasks_module.CARD_TYPES)
        self.assertIs(
            gacha_module.normalize_card_type, tasks_module.normalize_card_type
        )
        self.assertEqual(
            tuple(tasks_module.CARD_TYPES), ("free", "micro", "goal", "standard")
        )

    def test_legacy_cards_are_not_mistaken_for_free_in_real_draws(self):
        """真实抽卡：旧卡按 standard 而非 free（旧无卡类型策略抽样不变）。"""
        with _synthetic_root("lt_card_norm_") as temp:
            harness = _Harness(temp)
            # 同一 category、同一 priority：只有 card_type 不同。
            harness.add_task(1, "legacy-normal", "study", task_type="normal")
            harness.add_task(2, "legacy-other", "study", task_type="other")
            harness.add_task(3, "legacy-null", "study", task_type=None)

            # 只点名 free → 三张旧卡都是 standard → 系数 1.0（中性）。
            harness.publish({"card_type:free": 0.2})

            # 三张旧卡都仍可被抽到（旧卡绝非被当成 free 而被压低/停发）。
            drawn = set()
            for step in range(101):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                drawn.add(body["task"]["id"])
            self.assertEqual(drawn, {1, 2, 3}, drawn)


# ===========================================================================
# 2. 策略接线：card_type: 真的改变抽卡，零系数严格停发
# ===========================================================================


class ApprovedCardTypeWeightIntegrationTests(unittest.TestCase):
    """合法批准的 card_type: 策略必须实际改变正式抽卡结果。"""

    def test_approved_weights_without_free_duration_excludes_free(self):
        """策略只有权重、没有批准自由卡时长时，仍可发非free，不可发free。"""
        with _synthetic_root("lt_no_free_duration_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "study", task_type="free")
            harness.add_task(2, "goal-card", "study", task_type="goal")
            harness.publish({"card_type:free": 1.0, "card_type:goal": 0.2})
            for step in range(0, 101, 10):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(body["task"]["id"], 2, body)

    def test_card_type_weight_changes_actual_draw_outcome(self):
        """同一 category、只换 card_type 系数 → 抽中的卡必须换。"""
        with _synthetic_root("lt_card_draw_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "study", task_type="free")
            harness.add_task(2, "goal-card", "study", task_type="goal")

            # 压低 goal（自由卡中性）→ 应该抽到 free。
            harness.publish({"card_type:goal": 0.2}, policy={"free_task_time_strategy": {"options": [25]}})
            with _patched_rng(0.5):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["id"], 1, body)

            # 只改系数（同一 rng、同样卡池）→ 结果必须改变。
            harness.publish({"card_type:goal": 1.0, "card_type:free": 0.2}, policy={"free_task_time_strategy": {"options": [25]}})
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

    def test_zero_card_type_weight_is_never_drawn(self):
        """零系数卡类型必须被 **移出候选**，绝不在抽样边界上被误抽。"""
        with _synthetic_root("lt_card_zero_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "study", task_type="free")
            harness.add_task(2, "goal-card", "study", task_type="goal")
            harness.publish({"card_type:free": 0.0, "card_type:goal": 1.0})
            # 覆盖整个 [0,1] 采样区间：free 一次都不许被抽到。
            for step in range(101):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertNotEqual(body["task"]["task_type"], "free", body)

    def test_all_card_types_stopped_yields_no_card_not_uniform_fallback(self):
        """整个池被停发 → 保守地"无卡可发"，绝不悄悄均匀退回。"""
        with _synthetic_root("lt_card_all_zero_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "study", task_type="free")
            harness.add_task(2, "goal-card", "study", task_type="goal")
            harness.publish({"card_type:free": 0.0, "card_type:goal": 0.0})
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

    def test_unapproved_draft_and_illegal_keys_keep_old_behaviour(self):
        """未批准草案 / 非法键 / 越界值都不得激活，旧抽卡逐位保留。"""
        cases = {
            "draft_not_approved": ({"card_type:goal": 0.01}, False),
            "out_of_range_value": ({"card_type:goal": 1e9}, True),
            "above_one_value": ({"card_type:goal": 5.0}, True),
            "negative_value": ({"card_type:goal": -1.0}, True),
            "non_numeric_value": ({"card_type:goal": "high"}, True),
            "unknown_card_type_suffix": ({"card_type:study": 0.01}, True),
            "uppercase_suffix": ({"card_type:FREE": 0.01}, True),
            "content_category_key": ({"category:goal": 0.01}, True),
        }
        for label, (weights, approved) in cases.items():
            with self.subTest(case=label), _synthetic_root(
                "lt_card_neg_"
            ) as temp:
                harness = _Harness(temp)
                # priority 差异让旧权重可区分：高档任务先、低档任务后。
                harness.add_task(
                    1, "high-priority-free", "study", task_type="free", priority=10
                )
                harness.add_task(
                    2, "low-priority-goal", "study", task_type="goal", priority=1
                )

                # 基线：完全没有策略时 rng=0.999 必须抽到权重最低的那张。
                with _patched_rng(0.999):
                    response, baseline = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, baseline)
                self.assertEqual(baseline["task"]["id"], 2, baseline)

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

    def test_old_policy_without_card_type_keys_keeps_sampling_unchanged(self):
        """旧策略（只有 category:）的抽样结果 **逐位不变**。"""
        with _synthetic_root("lt_card_old_policy_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-card", "study", task_type="free", priority=10)
            harness.add_task(2, "goal-card", "study", task_type="goal", priority=1)

            harness.publish({"category:study": 1.0})
            with _patched_rng(0.999):
                response, with_policy = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, with_policy)

            # 同一策略再抽一次，结果必须可复现（旧行为零漂移）。
            with _patched_rng(0.999):
                response, again = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, again)
            self.assertEqual(
                with_policy["task"]["id"], again["task"]["id"], (with_policy, again)
            )

    def test_module_coefficient_domain_matches_publisher(self):
        """卡类型系数域必须与 Publisher 完全一致（否则又是接口冲突）。"""
        self.assertEqual(
            gacha_module.MIN_CARD_TYPE_COEFFICIENT, PUBLISHER_MIN_WEIGHT
        )
        self.assertEqual(
            gacha_module.MAX_CARD_TYPE_COEFFICIENT, PUBLISHER_MAX_WEIGHT
        )
        self.assertLessEqual(gacha_module.MAX_CARD_TYPE_COEFFICIENT, 1.0)
        # G01 的类别系数域不得被本轮改动。
        self.assertEqual(
            gacha_module.MIN_CATEGORY_COEFFICIENT, PUBLISHER_MIN_WEIGHT
        )
        self.assertEqual(
            gacha_module.MAX_CATEGORY_COEFFICIENT, PUBLISHER_MAX_WEIGHT
        )


# ===========================================================================
# 3. 正交性：category: 与 card_type: 互不混淆、可共同作用
# ===========================================================================


class CategoryAndCardTypeOrthogonalityTests(unittest.TestCase):
    """两个维度必须语义独立、互不覆盖、共同作用。"""

    def test_category_and_card_type_coefficients_are_independent(self):
        """同一策略里两个前缀可同时作用，且各自只影响自己的维度。"""
        with _synthetic_root("lt_ortho_") as temp:
            harness = _Harness(temp)
            # 4 张卡：2 个内容类别 × 2 个卡类型。
            harness.add_task(1, "study-free", "study", task_type="free")
            harness.add_task(2, "study-goal", "study", task_type="goal")
            harness.add_task(3, "work-free", "work", task_type="free")
            harness.add_task(4, "work-goal", "work", task_type="goal")

            # 只压低内容类别 work → work 的两张卡都不该被抽到。
            harness.publish({"category:work": 0.0}, policy={"free_task_time_strategy": {"options": [25]}})
            for step in range(101):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(body["task"]["category"], "study", body)

            # 只压低卡类型 goal → study 的两张 goal 卡都不该被抽到。
            harness.publish({"card_type:goal": 0.0}, policy={"free_task_time_strategy": {"options": [25]}})
            for step in range(101):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertNotEqual(body["task"]["task_type"], "goal", body)

            # 两个维度同时生效（相乘）：
            #   category:work=0 → 停发 work 的两张卡；
            #   card_type:goal=0 → 停发 goal 的两张卡；
            #   两者取交集后只剩 study/free 这一张 —— 它仍然照发。
            harness.publish(
                {"category:work": 0.0, "card_type:goal": 0.0},
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            for step in range(101):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(body["task"]["id"], 1, body)
                self.assertEqual(body["task"]["category"], "study", body)
                self.assertEqual(body["task"]["task_type"], "free", body)

            # 再把 study 也停发 → 全池清零 → 404（绝不均匀回退）。
            harness.publish(
                {
                    "category:work": 0.0,
                    "category:study": 0.0,
                    "card_type:goal": 0.0,
                },
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            with _patched_rng(0.5):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)

    def test_both_dimensions_multiply_on_the_same_card(self):
        """两个系数在同一张卡上相乘（0.5 × 0.5 = 0.25）。"""
        base = [{"category": "study", "task_type": "goal"}, {"id": 2}]
        weights, tasks, applied = gacha_module._policy_weighted_weights(
            [1.0, 1.0],
            base,
            {"study": 0.5},
            {"goal": 0.5},
        )
        self.assertTrue(applied)
        self.assertEqual(len(weights), len(tasks))
        self.assertAlmostEqual(weights[0], 0.25, places=6)

    def test_category_key_never_leaks_into_card_type_dimension(self):
        """``category:free`` 绝不生效（free 是卡类型，不是内容类别）。"""
        with _synthetic_root("lt_ortho_leak_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "free", task_type="free", priority=10
            )
            harness.add_task(
                2, "goal-card", "goal", task_type="goal", priority=1
            )
            # 这份策略在"内容类别"维度上确实命中了 free/goal 两个字面值，
            # 因此 **按 category 语义** 应当压低 category=goal 的那张卡。
            harness.publish({"category:goal": 0.0}, policy={"free_task_time_strategy": {"options": [25]}})
            for step in range(101):
                with _patched_rng(step / 100.0):
                    response, body = harness.drawn_id(pool="tomato")
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(body["task"]["category"], "free", body)
                # 但它 **绝不是** 一次卡类型策略：free 那张卡仍然照发。
                self.assertEqual(body["task"]["task_type"], "free", body)


# ===========================================================================
# 4. Bootstrap 423 + 四条抽卡路径共用同一条接线
# ===========================================================================


class BootstrapGateAndSharedPathTests(unittest.TestCase):
    """闸门 fail closed + 四路抽卡共用 card_type: 接线。"""

    def test_bootstrap_gate_still_blocks_writes_without_approved_policy(self):
        """无有效策略时，正式抽卡写请求仍由既有服务端闸门 fail closed。"""
        with _synthetic_root("lt_card_gate_") as temp:
            harness = _Harness(temp, enforce_bootstrap_gate=True)
            harness.add_task(1, "free-card", "study", task_type="free")
            harness.write_raw_latest(
                _draft_document({"card_type:free": 0.0}, approved=False)
            )
            response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 423, body)
            self.assertEqual(body["error"], "bootstrap-locked", body)

            # Bootstrap 解锁不等于自由卡可以绕过获批时长策略。
            harness.publish(
                {"card_type:free": 1.0},
                policy={"free_task_time_strategy": {"options": [25]}},
            )
            with _patched_rng(0.5):
                response, body = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["id"], 1, body)

    def test_four_draw_paths_share_the_card_type_wiring(self):
        """draw / care-draw / replace / multi-draw 同一条 card_type: 接线。"""
        with _synthetic_root("lt_card_paths_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-1", "study", task_type="free")
            harness.add_task(2, "free-2", "study", task_type="free")
            harness.add_task(3, "goal-1", "study", task_type="goal")
            harness.add_task(4, "goal-2", "study", task_type="goal")
            harness.add_task(
                5, "free-long", "study", task_type="free", estimated_time=90
            )
            # 停发 free → 四条路径都只能发 goal。
            harness.publish({"card_type:free": 0.0, "card_type:goal": 1.0})

            with _patched_rng(0.5):
                response, drawn = harness.drawn_id(pool="tomato")
            self.assertEqual(response.status_code, 200, drawn)
            self.assertEqual(drawn["task"]["task_type"], "goal", drawn)

            with _patched_rng(0.5):
                care = harness.client.post(
                    "/api/gacha/care-draw", json={"pool": "tomato"}
                ).get_json()
            self.assertEqual(care["task"]["task_type"], "goal", care)

            with _patched_rng(0.5):
                replaced = harness.client.post(
                    "/api/gacha/replace",
                    json={"task_id": 1, "pool": "tomato", "reason": "other"},
                ).get_json()
            self.assertEqual(replaced["task"]["task_type"], "goal", replaced)
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM task_rejection_log WHERE task_id=1"
                ),
                1,
            )

            with _patched_rng(0.5):
                multi = harness.client.post(
                    "/api/gacha/multi-draw",
                    json={"available_time": 60, "count": 3},
                ).get_json()
            self.assertGreaterEqual(len(multi["tasks"]), 1, multi)
            self.assertEqual(
                [task["task_type"] for task in multi["tasks"]],
                ["goal"] * len(multi["tasks"]),
                multi,
            )
            # 时间预算仍然生效。
            self.assertLessEqual(multi["total_minutes"], 60, multi)
            self.assertTrue(
                all(task["estimated_time"] <= 60 for task in multi["tasks"]), multi
            )
            # 发行记录仍然每次落一行（refusal_reason IS NULL）。
            # draw 1 行 + replace 1 行（care-draw 不走时间预算路径，按既有
            # 行为不写发行行）+ multi-draw 每张卡 1 行。
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM gacha_records WHERE refusal_reason IS NULL"
                ),
                2 + len(multi["tasks"]),
            )

    def test_time_budget_still_holds_with_card_type_weights(self):
        """时间预算与发行记录在 card_type: 策略下不回退。"""
        with _synthetic_root("lt_card_budget_") as temp:
            harness = _Harness(temp)
            harness.add_task(1, "free-1", "study", task_type="free")
            harness.add_task(2, "goal-1", "study", task_type="goal")
            harness.add_task(
                3, "too-long-goal", "study", task_type="goal", estimated_time=90
            )
            harness.publish({"card_type:free": 0.2, "card_type:goal": 1.0})
            response = harness.client.post(
                "/api/gacha/draw", json={"pool": "tomato", "available_time": 25}
            )
            body = response.get_json()
            self.assertEqual(response.status_code, 200, body)
            self.assertLessEqual(body["task"]["estimated_time"], 25, body)
            # 走时间预算路径 → 恰好一行发行记录。
            self.assertEqual(
                harness.counts(
                    "SELECT COUNT(*) FROM gacha_records WHERE refusal_reason IS NULL"
                ),
                1,
            )
            # 超出预算的长卡即使策略允许也绝不会被发出来。
            self.assertNotEqual(body["task"]["id"], 3, body)


# ===========================================================================
# 5. POST / PUT /api/tasks 的 task_type 写入面
# ===========================================================================


class TaskTypeWriteSurfaceTests(unittest.TestCase):
    """任务 CRUD 显式接受合法卡类型、拒绝非法值、不自动改型。"""

    def _create(self, harness, payload):
        return harness.client.post("/api/tasks", json=payload)

    def test_post_accepts_every_official_card_type(self):
        """四种正式卡类型都必须能被显式写入。"""
        with _synthetic_root("lt_task_create_") as temp:
            harness = _Harness(temp)
            for index, card_type in enumerate(tasks_module.CARD_TYPES):
                with self.subTest(card_type=card_type):
                    response = self._create(
                        harness,
                        {
                            "name": f"synthetic-{card_type}-{index}",
                            "category": "study",
                            "task_type": card_type,
                        },
                    )
                    self.assertEqual(response.status_code, 201, response.get_json())
                    task_id = response.get_json()["id"]
                    row = harness.task_row(task_id)
                    self.assertEqual(row["task_type"], card_type, row)

    def test_post_rejects_invalid_task_type_without_partial_write(self):
        """非法值 → 400，且 **不可部分写入**（任务根本没被创建）。"""
        invalid_values = [
            "FREE",          # 大小写变体
            "study",         # 内容类别不是卡类型
            "unknown_kind",  # 未知拼写
            "",              # 空串
            "   ",           # 纯空白
            123,             # 数字
            True,            # 布尔
            None,            # null
            ["free"],        # 列表
            {"card": "free"} # 对象
        ]
        with _synthetic_root("lt_task_invalid_") as temp:
            harness = _Harness(temp)
            for index, value in enumerate(invalid_values):
                with self.subTest(value=repr(value)):
                    before = harness.counts("SELECT COUNT(*) FROM tasks")
                    response = self._create(
                        harness,
                        {
                            "name": f"synthetic-invalid-{index}",
                            "category": "study",
                            "task_type": value,
                        },
                    )
                    self.assertEqual(response.status_code, 400, response.get_json())
                    self.assertIn("task_type", response.get_json()["error"])
                    after = harness.counts("SELECT COUNT(*) FROM tasks")
                    self.assertEqual(after, before, "must not partially write")

    def test_post_without_task_type_keeps_legacy_behaviour(self):
        """省略 task_type → 保持既有旧行为（写 "normal"）。"""
        with _synthetic_root("lt_task_legacy_") as temp:
            harness = _Harness(temp)
            response = self._create(
                harness, {"name": "synthetic-no-type", "category": "study"}
            )
            self.assertEqual(response.status_code, 201, response.get_json())
            row = harness.task_row(response.get_json()["id"])
            self.assertEqual(row["task_type"], "normal", row)
            # 归一后它就是 standard（旧卡绝不变成自由卡）。
            self.assertEqual(
                gacha_module.normalize_card_type(row["task_type"]), "standard"
            )

    def test_put_updates_task_type_only_when_explicitly_given(self):
        """PUT 显式给出 → 改型；省略 → **绝不** 自动给已有任务改型。"""
        with _synthetic_root("lt_task_put_") as temp:
            harness = _Harness(temp)
            response = self._create(
                harness,
                {
                    "name": "synthetic-put-target",
                    "category": "study",
                    "task_type": "standard",
                },
            )
            task_id = response.get_json()["id"]

            # 省略 task_type 的普通更新 → 该列保持不变。
            response = harness.client.put(
                f"/api/tasks/{task_id}", json={"name": "synthetic-renamed"}
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            row = harness.task_row(task_id)
            self.assertEqual(row["task_type"], "standard", row)
            self.assertEqual(row["name"], "synthetic-renamed", row)

            # 显式给出 → 改型。
            response = harness.client.put(
                f"/api/tasks/{task_id}", json={"task_type": "free"}
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(harness.task_row(task_id)["task_type"], "free")

    def test_put_rejects_invalid_task_type_without_partial_write(self):
        """PUT 非法值 → 400，且其它字段也一并不写（不可部分写入）。"""
        with _synthetic_root("lt_task_put_invalid_") as temp:
            harness = _Harness(temp)
            response = self._create(
                harness,
                {
                    "name": "synthetic-put-invalid",
                    "category": "study",
                    "task_type": "standard",
                },
            )
            task_id = response.get_json()["id"]

            response = harness.client.put(
                f"/api/tasks/{task_id}",
                json={"name": "synthetic-should-not-persist", "task_type": "bogus"},
            )
            self.assertEqual(response.status_code, 400, response.get_json())
            row = harness.task_row(task_id)
            self.assertEqual(row["name"], "synthetic-put-invalid", row)
            self.assertEqual(row["task_type"], "standard", row)

    def test_list_and_get_keep_existing_response_fields(self):
        """list/get 保留原响应字段（新增字段只是附加）。"""
        with _synthetic_root("lt_task_list_") as temp:
            harness = _Harness(temp)
            response = self._create(
                harness,
                {
                    "name": "synthetic-listed",
                    "category": "study",
                    "task_type": "micro",
                },
            )
            task_id = response.get_json()["id"]

            listed = harness.client.get("/api/tasks").get_json()
            self.assertTrue(any(item["id"] == task_id for item in listed))
            fetched = harness.client.get(f"/api/tasks/{task_id}").get_json()
            for field in ("id", "name", "category", "task_type", "estimated_time"):
                self.assertIn(field, fetched)
            self.assertEqual(fetched["task_type"], "micro", fetched)


if __name__ == "__main__":
    unittest.main()
