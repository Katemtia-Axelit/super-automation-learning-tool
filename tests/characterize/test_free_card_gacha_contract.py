"""M02-S02-G01-W05: 正式单抽路径 (``POST /api/gacha/draw``) 的自由卡时长合同。

唯一可独立验收目标
------------------
用 **真实 Flask 路由** 在 **完全合成隔离目录** 内验证：只有 **已批准** 的
自由卡时长才决定实际可派发卡片的 ``effective_minutes`` 与可用时间筛选；
**没有合法批准时长的自由卡不应真正发行**。

本文件 **只写测试**：不实现、不修改任何生产代码。若真实路由不符合合同，
应保留失败用例并上报 ``BLOCKED_CONTRACT``，绝不降低安全预期、绝不伪造 PASS。

范围与红线
----------
- 只打真实 ``server.blueprints.gacha_bp`` 的 ``POST /api/gacha/draw``
  （经 Flask ``test_client``）。**不** 打 care-draw / replace / multi-draw /
  suggestion，**不** 验证 UI，**不** 触碰 Publisher 实现或 Factory 注册。
- 全部状态在 ``tempfile`` 临时目录内：合成 SQLite + 合成策略目录。
  **绝不** 读写真实 ``data/task_publisher.db``(±wal/shm)、``config/config.json``、
  ``src/notes/**``、``data/agent-policy/latest.json``。
- "已批准"策略一律经 **真实受控 Publisher**（``scripts.agent_policy_publisher``）
  在合成目录里发布（合成批准证据）；本文件 **从不** 自己伪造
  ``approved_by_user`` / ``approved_at``。
- 只 ``import`` 生产模块并 **只读** 调用其 helper（``_build_free_card_context`` /
  ``_fits_minutes`` / ``_filter_pool``）做刻画；**绝不** 写任何生产文件。

Controller 已裁决的设计不变量（本文档只刻画，不自行重新规划）
------------------------------------------------------------
1. 自由卡时长 **只** 来自已批准策略的 ``free_task_time_strategy.options``
   （合法值严格是 25 / 55 的整数）。
2. 自由卡 **不按行内 ``estimated_time``** 分池 / 过滤：它按 **本次发行抽定** 的
   合法时长参与时间预算（因此 25 分钟的自由卡不会被行内的 80 分钟误过滤，
   55 分钟的自由卡也绝不会被发给只有 30 分钟的用户）。
3. ``tasks.estimated_time`` **绝不** 被改写（非 free 路径逐位不变）。
4. 没有合法已批准时长 → 该自由卡 **不可派发**；在 **带预算** 的请求里它被
   **移出候选集**（404），**绝不** 回落 ``tasks.estimated_time``。
5. 抽卡响应里自由卡额外带 ``effective_minutes`` / ``free_card_dispatchable`` /
   ``free_card_reason``；其它卡类型的响应字段 **逐字不变**。

最低场景（仅单抽，不验证 care/replace/multi/suggestion）
----------------------------------------------------------
S1  已批准 25；候选只有一张自由卡，行内 ``estimated_time=80``；
    ``available_time=30`` → 200、``effective_minutes=25``、
    ``free_card_dispatchable=true``、行内 80 **不变**、正常发行记录 **恰一行**，
    且该行记录的是 **原请求的可用预算 30**（不是伪装成存储时长 25）。
S2  已批准 55（唯一合法值）；``available_time=30`` → 404 且 **不发行**；
    ``available_time=60`` → 200 且 ``effective_minutes=55``。
S3  策略 **只批准权重**、**没有获批自由卡时长**，候选池只有 free →
    ``available_time=30`` → 404、**不发行**、**绝不** 从行内 ``estimated_time``
    回退（此用例刻意让行内时长 ≤ 预算，这样一旦发生回退就一定会被发行）。
S4  策略缺失时 / 混合含一张非自由卡时 → 既有非自由卡仍按 **原时长** 发出，
    **仅** free 被排除；不改类别 / 卡类型权重，使用原始接口与确定性随机。

本次修复目标与新事实（M02-S02-G01-W06）
----------------------------------------
W05 验收时发现的 **生产残留** 已被本轮裁决并修复：``/draw`` **不带**
``available_time`` 且候选池 **只有** 自由卡、策略没有获批 25/55 时长时，
``_filter_pool`` 的末段兜底 ``pool = tasks`` 会把 **已被排除** 的非法自由卡
重新放回候选集，于是返回 HTTP 200 与一张 **不能执行** 的自由卡
（``free_card_dispatchable=false`` / ``effective_minutes=null``），并仍然写
一行 ``gacha_records``（``available_time=NULL``）——与"带预算 404"和"混合池
剔除 free" **不一致**。

W06 的目标合同（Controller 已裁决，**不是** 本文件自行设计）：

1. **无预算 + 候选池只有自由卡 + 用户没有已批准的有效自由卡时长**
   → HTTP 404（``{"error":"No tasks available"}``），
   **不写任何** ``gacha_records``、**不增加** ``draw_count_today``；
   **绝不** 出现 HTTP 200 的"不能执行却已经发行"的自由卡。
2. **用户确实批准了 25 或 55** 时，free-only 池即使 **不带**
   ``available_time`` 也 **仍可** 按合法时长发行，响应带
   ``effective_minutes`` 且 ``free_card_dispatchable=true``。
3. **混合池** 仍照发非自由卡（free 被完全排除），非自由卡历史行为不变。
4. 非 free 路径的候选过滤兜底 **逐位不变**（只有"存在不可派发自由卡且合法
   base 为空"这一种情形不再回退到原始未过滤的 ``tasks``）。

本文件把上述事实 **显式断言** 出来（见
``NoBudgetFreeOnlyPoolSafetyTests`` 与
``NoBudgetFreeOnlyPoolCharacterizationTests``）。
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import importlib
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

# `server.blueprints.gacha_bp` 在包级别被 Blueprint 实例遮蔽，必须按
# 真实子模块路径取模块，才能同时拿到路由与内部 helper。
gacha_module = importlib.import_module("server.blueprints.gacha_bp")
publisher = importlib.import_module("agent_policy_publisher")
from server.services import free_card_policy  # noqa: E402

#: 自由卡合法时长（唯一权威来自生产领域模块，本文件不另立一套）。
LEGAL_FREE_MINUTES = tuple(free_card_policy.FREE_CARD_MINUTES_OPTIONS)

# 与 tests/characterize/test_card_type_pool.py 相同的合成 schema
# （只建本文件用到的表；``task_type`` 是自由卡判定的核心列）。
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


# ---------------------------------------------------------------------------
# 合成脚手架（全部在 tempfile 内）
# ---------------------------------------------------------------------------


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
    """确定性 rng 替身：同一请求在相同策略下抽到同一张卡。"""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value

    def randrange(self, n: int) -> int:
        return min(n - 1, int(self.value * n))


@contextlib.contextmanager
def _patched_rng(value: float):
    """把 gacha_bp 使用的 random 换成确定性替身（只在本测试进程内）。"""
    with mock.patch.object(gacha_module, "random", _FixedRng(value)):
        yield


class _Harness:
    """一次性的合成 app + 合成 DB + 合成策略目录（全部在临时目录内）。"""

    def __init__(self, root: Path) -> None:
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
        self.app.register_blueprint(gacha_module.gacha_bp)
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
    def publish(self, weights=None, *, policy=None) -> dict:
        self._published += 1
        proposal = {
            "schema_version": 1,
            "version": f"2099-01-01.{self._published}",
            "effect_summary": (
                "synthetic effect summary for free card gacha contract test"
            ),
            "weights": dict(weights or {}),
            "policy": dict(policy or {}),
        }
        return publisher.publish(
            str(self.policy_dir),
            proposal,
            proposal_digest_expected=publisher.proposal_digest(proposal),
            approval_evidence={
                "approved_by": "synthetic-reviewer",
                "approval_text": (
                    "synthetic approval for free card gacha contract test only"
                ),
                "session_id": "lt-m02-s02-g01-w05-synthetic",
                "approved_at": _dt.datetime.now(_dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            },
            authorize=True,
            authorization_note=(
                "synthetic free card gacha contract test publication"
            ),
            create_policy_dir=True,
        )

    # --- 断言辅助 ---------------------------------------------------------
    def draw(self, **payload):
        """真实 ``POST /api/gacha/draw``；返回 ``(response, body)``。"""
        response = self.client.post("/api/gacha/draw", json=payload)
        return response, (response.get_json() or {})

    def issuance_rows(self):
        """正常发行记录（``refusal_reason IS NULL``）的全部行。"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM gacha_records WHERE refusal_reason IS NULL "
                "ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def issuance_count(self) -> int:
        return len(self.issuance_rows())


# ===========================================================================
# S1. 已批准 25 分钟 → effective_minutes / 可派发 / 行内不变 / 发行记录
# ===========================================================================


class ApprovedDurationSingleDrawTests(unittest.TestCase):
    """已批准的自由卡时长必须真正决定本次发行的时长与可派发性。"""

    def test_approved_25_minutes_drives_effective_minutes_and_issuance(self):
        """S1：行内 80 + 已批准 25 + 预算 30 → 200 / effective 25 / 行内不变。"""
        with _synthetic_root("lt_fg_s1_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)

            self.assertEqual(response.status_code, 200, body)
            task = body["task"]
            self.assertEqual(task["id"], 1, body)
            self.assertEqual(task["task_type"], "free", body)

            # --- 已批准时长决定 effective_minutes -------------------------
            self.assertEqual(task["effective_minutes"], 25, body)
            self.assertIn(25, LEGAL_FREE_MINUTES)
            # --- 可派发标记 -----------------------------------------------
            self.assertIs(task["free_card_dispatchable"], True, body)
            self.assertIsNone(task["free_card_reason"], body)

            # --- 行内 estimated_time 绝不被改写，也绝不当成自由卡时长 ------
            self.assertEqual(task["estimated_time"], 80, body)
            row = harness.task_row(1)
            self.assertEqual(row["estimated_time"], 80, row)
            self.assertNotEqual(task["effective_minutes"], row["estimated_time"])

            # --- 正常发行记录恰一行，且记录的是原请求的可用预算 30 --------
            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["task_id"], 1, rows)
            self.assertEqual(rows[0]["available_time"], 30, rows)
            # 绝不能把"存储时长 25"伪装成"可用预算"。
            self.assertNotEqual(rows[0]["available_time"], 25, rows)

    def test_approved_duration_is_not_derived_from_inline_estimated_time(self):
        """S1 变体：行内 80 绝不被当成时长，也绝不参与筛选（25 仍能发出）。"""
        with _synthetic_root("lt_fg_s1b_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )

            # 预算 30：行内 80 放不下，但已批准的 25 放得下 → 必须发出。
            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["effective_minutes"], 25, body)
            self.assertEqual(body["task"]["estimated_time"], 80, body)

            # 预算 20：已批准的 25 放不下 → 绝不发（行内 80 也不该救它）。
            with _patched_rng(0.5):
                response, body = harness.draw(available_time=20)
            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            self.assertEqual(harness.issuance_count(), 1, "404 不得写发行记录")


# ===========================================================================
# S2. 已批准 55 分钟 → 预算不足不发行，预算充足按 55 发出
# ===========================================================================


class ApprovedLongDurationBudgetTests(unittest.TestCase):
    """55 分钟的自由卡绝不被发给只有 30 分钟的用户。"""

    def test_55_minute_free_card_is_not_issued_within_30_minute_budget(self):
        """S2 前半：预算 30 → 404，绝不发行。"""
        with _synthetic_root("lt_fg_s2a_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [55]}}
            )

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)

            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 不得发行、不得留下任何副作用。
            self.assertEqual(harness.issuance_rows(), [])
            row = harness.task_row(1)
            self.assertEqual(row["draw_count_today"], 0, row)

    def test_55_minute_free_card_is_issued_within_60_minute_budget(self):
        """S2 后半：预算 60 → 200，effective_minutes=55。"""
        with _synthetic_root("lt_fg_s2b_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [55]}}
            )

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=60)

            self.assertEqual(response.status_code, 200, body)
            task = body["task"]
            self.assertEqual(task["id"], 1, body)
            self.assertEqual(task["effective_minutes"], 55, body)
            self.assertIs(task["free_card_dispatchable"], True, body)
            self.assertEqual(task["estimated_time"], 80, body)
            self.assertEqual(harness.task_row(1)["estimated_time"], 80)

            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["available_time"], 60, rows)


# ===========================================================================
# S3. 只批准权重、没有获批自由卡时长 → 自由卡不发行、绝不回退行内时长
# ===========================================================================


class MissingApprovedDurationFailsClosedTests(unittest.TestCase):
    """没有合法已批准时长 → 自由卡不可派发，且绝不回退任何默认值。"""

    def test_weights_only_policy_free_only_pool_returns_404(self):
        """S3：只批准权重 + 候选只有 free + 预算 30 → 404 且不发行。"""
        with _synthetic_root("lt_fg_s3_") as temp:
            harness = _Harness(temp)
            # 行内 25 ≤ 预算 30：一旦发生"回退行内时长"，这张卡一定会被发出来，
            # 因此本用例对回退是**尖锐**的。
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)

            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 不得发行、不得留下副作用。
            self.assertEqual(harness.issuance_rows(), [])
            row = harness.task_row(1)
            self.assertEqual(row["draw_count_today"], 0, row)
            self.assertEqual(row["estimated_time"], 25, row)

    def test_missing_approved_duration_never_falls_back_to_inline_minutes(self):
        """S3 变体：helper 层同样绝不回退行内 ``estimated_time``。"""
        with _synthetic_root("lt_fg_s3b_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.publish(weights={"card_type:free": 1.0})
            task = harness.task_row(1)

            with harness.app.app_context():
                ctx = gacha_module._build_free_card_context(
                    [task], require_approved_duration=True
                )
                # 没有合法已批准时长 → 有效时长为 None（不是 25 / 30 / 55）。
                self.assertIsNone(ctx.effective_minutes(task))
                self.assertIsNone(ctx.minutes_for(task))
                self.assertFalse(ctx.is_dispatchable(task))
                # 绝不"放得下"（即使行内 25 ≤ 30）。
                self.assertFalse(gacha_module._fits_minutes(task, 30, ctx))
                self.assertFalse(gacha_module._fits_minutes(task, 60, ctx))
                # 候选过滤的兜底 **绝不** 把不可派发的自由卡放回候选集
                # （M02-S02-G01-W06：``_filter_pool`` 在合法 base 为空且存在
                # 不可派发自由卡时 **不再** 回退到原始未过滤的 ``tasks``）。
                pool = gacha_module._filter_pool(
                    [task], "tomato", free_card_context=ctx
                )
                self.assertEqual(pool, [], pool)

    def test_unapproved_policy_has_no_free_duration_either(self):
        """S3 变体：策略 **缺失** 时同样没有可用自由卡时长。"""
        with _synthetic_root("lt_fg_s3c_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            # 策略目录存在但没有 latest.json（策略缺失）。
            task = harness.task_row(1)

            with harness.app.app_context():
                ctx = gacha_module._build_free_card_context(
                    [task], require_approved_duration=True
                )
                self.assertIsNone(ctx.effective_minutes(task))
                self.assertFalse(ctx.is_dispatchable(task))
                self.assertFalse(gacha_module._fits_minutes(task, 30, ctx))

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)
            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(harness.issuance_rows(), [])


# ===========================================================================
# S4. 非自由卡的既有行为逐位不变；仅 free 被排除
# ===========================================================================


class NonFreeCardBehaviourPreservedTests(unittest.TestCase):
    """混合池里非自由卡仍按原时长发出；仅自由卡被排除。"""

    def test_missing_policy_keeps_non_free_card_issuable_at_its_own_duration(self):
        """S4a：策略缺失 + 混合池 → 非自由卡按原时长发出，仅 free 被排除。"""
        with _synthetic_root("lt_fg_s4a_") as temp:
            harness = _Harness(temp)
            # 两张卡的行内时长都 ≤ 预算：free 被排除 **只可能** 因为没有
            # 获批时长（而不是因为"放不下"）。
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=20
            )
            harness.add_task(
                2, "standard-card", "study", task_type="standard",
                estimated_time=20,
            )
            # 策略缺失：不发布任何策略。

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)

            self.assertEqual(response.status_code, 200, body)
            task = body["task"]
            self.assertEqual(task["id"], 2, body)
            # 非自由卡的响应字段逐字不变（没有自由卡专属字段）。
            self.assertNotIn("effective_minutes", task)
            self.assertNotIn("free_card_dispatchable", task)
            self.assertNotIn("free_card_reason", task)
            self.assertEqual(task["estimated_time"], 20, body)

            # 仅 free 被排除：它既没被发行也没留下副作用。
            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["task_id"], 2, rows)
            self.assertEqual(rows[0]["available_time"], 30, rows)
            free_row = harness.task_row(1)
            self.assertEqual(free_row["draw_count_today"], 0, free_row)

    def test_approved_duration_larger_than_budget_excludes_only_the_free_card(self):
        """S4b：已批准 55 + 预算 30 + 混合池 → 仅 free 被排除，其余照发。"""
        with _synthetic_root("lt_fg_s4b_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=20
            )
            harness.add_task(
                2, "standard-card", "study", task_type="standard",
                estimated_time=20,
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [55]}}
            )

            with _patched_rng(0.5):
                response, body = harness.draw(available_time=30)

            self.assertEqual(response.status_code, 200, body)
            task = body["task"]
            self.assertEqual(task["id"], 2, body)
            self.assertEqual(task["estimated_time"], 20, body)
            self.assertNotIn("effective_minutes", task)

            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["task_id"], 2, rows)
            self.assertEqual(harness.task_row(1)["draw_count_today"], 0)


# ===========================================================================
# 无预算路径：fail-closed 安全合同（M02-S02-G01-W06）
# ===========================================================================


class NoBudgetFreeOnlyPoolSafetyTests(unittest.TestCase):
    """不带预算时，绝不产生 **可执行** 的自由卡发行，也绝不发行它。"""

    def test_no_budget_draw_never_yields_a_dispatchable_free_card(self):
        """无预算 + 无获批时长 → 必须是 404，且 **零发行**、零计数副作用。

        M02-S02-G01-W06：这里 **不再** 接受"200 + 不可派发标记"作为 PASS
        （那正是本轮修掉的"不能执行却已经发行"残留）。安全预期被 **收紧** 为
        "根本不发行"。
        """
        with _synthetic_root("lt_fg_nb_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.draw(pool="tomato")

            # 目标安全合同：404 + 明确的错误码。
            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # **零发行**：不得留下任何 gacha_records 行。
            self.assertEqual(harness.issuance_rows(), [])
            # **零计数副作用**：抽卡计数不得增加。
            self.assertEqual(harness.task_row(1)["draw_count_today"], 0)

    def test_no_budget_free_only_pool_issues_nothing_without_approved_duration(self):
        """无预算 + free-only + 无获批时长 → 404 / 0 记录 / 抽卡计数不变。

        这是本工单的 **唯一验收目标**（Controller 已裁决的安全合同）。
        """
        with _synthetic_root("lt_fg_nb2_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            # 只批准权重、**没有** 获批自由卡时长（25 / 55 都不可用）。
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.draw(pool="tomato")

            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 不得发行（连"不可派发"的那种发行都不允许）。
            self.assertEqual(harness.issuance_rows(), [])
            # 抽卡计数逐位不变。
            self.assertEqual(harness.task_row(1)["draw_count_today"], 0)
            # 行内 estimated_time 绝不被改写。
            self.assertEqual(harness.task_row(1)["estimated_time"], 25)

    def test_no_budget_free_only_pool_still_issues_with_approved_duration(self):
        """无预算 + free-only + **确实获批** 时长 → 仍可合法发行。

        W06 修复只收窄"**没有** 获批时长"的兜底；用户 **确实** 批准 25 或 55
        时，free-only 池即使不带 ``available_time`` 也必须照发，并带
        ``effective_minutes`` 与 ``free_card_dispatchable=true``。
        """
        for minutes in LEGAL_FREE_MINUTES:
            with self.subTest(minutes=minutes), _synthetic_root(
                "lt_fg_nb3_"
            ) as temp:
                harness = _Harness(temp)
                harness.add_task(
                    1, "free-card", "study", task_type="free", estimated_time=25
                )
                harness.publish(
                    policy={"free_task_time_strategy": {"options": [minutes]}}
                )

                with _patched_rng(0.5):
                    response, body = harness.draw(pool="tomato")

                self.assertEqual(response.status_code, 200, body)
                task = body["task"]
                self.assertEqual(task["id"], 1, body)
                self.assertEqual(task["task_type"], "free", body)
                self.assertEqual(task["effective_minutes"], minutes, body)
                self.assertIs(task["free_card_dispatchable"], True, body)
                self.assertIsNone(task["free_card_reason"], body)
                # 行内 estimated_time 绝不被改写，也绝不当成自由卡时长。
                self.assertEqual(task["estimated_time"], 25, body)
                self.assertEqual(harness.task_row(1)["estimated_time"], 25)
                # 合法发行 → 恰有一行发行记录。
                rows = harness.issuance_rows()
                self.assertEqual(len(rows), 1, rows)
                self.assertEqual(rows[0]["task_id"], 1, rows)


class NoBudgetFreeOnlyPoolCharacterizationTests(unittest.TestCase):
    """无预算 free-only 池的 **目标安全合同**（M02-S02-G01-W06）。

    历史行为（200 + 一条 ``gacha_records`` 发行记录）已被 Controller 裁决
    为 **必须修掉的残留**：``_filter_pool`` 的末段兜底曾把 **已被排除** 的
    不可派发自由卡重新放回候选集，导致一张 **不能执行** 的自由卡被真实发行。

    本类现在 **刻画目标合同**（而非历史残留）：

    1. 无预算 + free-only + 无获批时长 → 404、**零发行记录**、
       **抽卡计数不变**；
    2. 混合池里同一份策略下自由卡被完全排除，非自由卡照发。
    """

    def test_no_budget_free_only_pool_fails_closed_without_approved_duration(self):
        """目标合同：404 + 0 记录 + 抽卡计数不变。"""
        with _synthetic_root("lt_fg_nbc_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.draw(pool="tomato")

            # 目标合同 1：404 + 明确错误码。
            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 目标合同 2：零发行记录（绝不写 available_time=NULL 的发行行）。
            rows = harness.issuance_rows()
            self.assertEqual(rows, [])
            # 目标合同 3：抽卡计数逐位不变。
            row = harness.task_row(1)
            self.assertEqual(row["draw_count_today"], 0, row)
            self.assertEqual(row["estimated_time"], 25, row)

    def test_mixed_pool_excludes_the_free_card_entirely(self):
        """对照：混合池里同一份策略下自由卡被完全排除（仅发非 free）。"""
        with _synthetic_root("lt_fg_nbc2_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.add_task(
                2, "standard-card", "study", task_type="standard",
                estimated_time=25,
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.draw(pool="tomato")

            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["id"], 2, body)
            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["task_id"], 2, rows)
            # 混合池下非自由卡照发、free 零副作用。
            self.assertEqual(harness.task_row(1)["draw_count_today"], 0)


# ===========================================================================
# GET /api/gacha/free-card/suggestion："帮我选" 的只读数据入口
# （M02-S02-G02）
# ===========================================================================


class FreeCardSuggestionRouteTests(unittest.TestCase):
    """"帮我选" 的只读入口：**恰好一条**合法建议，或明确失败。

    - 有效获批候选 → 200，返回 **其中一条**（不是编造的、不是占位）；
    - 无合法获批候选 → 422 + 稳定错误码，**绝不** 返回任何活动；
    - 该入口 **不写库**、**不发行**（绝不产生 ``gacha_records`` 行）。
    """

    def _suggest(self, harness):
        response = harness.client.get("/api/gacha/free-card/suggestion")
        return response, (response.get_json() or {})

    def test_approved_candidates_return_one_of_them(self):
        """有效获批候选 → 200 + 候选池中的 **一条**。"""
        with _synthetic_root("lt_fg_sug_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            candidates = [
                {"activity": "看一集纪录片", "category": "娱乐"},
                {"activity": "读十页书", "category": "学习"},
            ]
            harness.publish(
                policy={
                    "free_task_time_strategy": {"options": [25]},
                    "free_task_activity_candidates": candidates,
                }
            )

            with _patched_rng(0.5):
                response, body = self._suggest(harness)

            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["candidate_count"], len(candidates), body)
            suggestion = body["suggestion"]
            self.assertIn("suggestion", body, body)
            self.assertIsInstance(suggestion, dict, body)
            self.assertIn(
                suggestion["activity"],
                [c["activity"] for c in candidates],
                "the suggestion must come from the approved candidate pool",
            )
            # 只读入口：绝不发行、绝不写库。
            self.assertEqual(harness.issuance_rows(), [])

    def test_no_approved_candidates_fails_explicitly_without_inventing(self):
        """没有获批候选 → 422 + 稳定错误码，**绝不** 编造活动。"""
        with _synthetic_root("lt_fg_sug_none_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            # 只批准时长，**没有** 活动候选。
            harness.publish(policy={"free_task_time_strategy": {"options": [25]}})

            response, body = self._suggest(harness)

            self.assertEqual(response.status_code, 422, body)
            self.assertEqual(
                body["error"],
                free_card_policy.REASON_CANDIDATES_MISSING,
                body,
            )
            self.assertNotIn("suggestion", body, body)
            self.assertNotIn("activity", body, body)
            self.assertEqual(harness.issuance_rows(), [])

    def test_all_candidates_illegal_fails_explicitly_without_inventing(self):
        """候选存在但全部非法 → 422 + 稳定错误码，**绝不** 编造活动。

        注：后端把"候选全部非法"与"没有候选"同样归一化为 **一个** 空的
        合法候选池，因此路由层返回的是 ``..._missing``（``..._invalid``
        只出现在策略读取层）。此处断言的是 **稳定错误码 + 不编造**。
        """
        with _synthetic_root("lt_fg_sug_bad_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={
                    "free_task_activity_candidates": [
                        {"activity": "<script>alert(1)</script>"},
                        {"activity": "   "},
                        {"activity": "x" * 201},
                        {"activity": "已撤下", "approved": False},
                    ]
                }
            )

            response, body = self._suggest(harness)

            self.assertEqual(response.status_code, 422, body)
            self.assertIn(
                body["error"],
                (
                    free_card_policy.REASON_CANDIDATES_MISSING,
                    free_card_policy.REASON_CANDIDATES_INVALID,
                ),
                body,
            )
            self.assertNotIn("suggestion", body, body)
            self.assertNotIn("activity", body, body)
            self.assertEqual(harness.issuance_rows(), [])

    def test_missing_policy_fails_explicitly_without_inventing(self):
        """策略缺失（未获批准）→ 422 + 稳定错误码，**绝不** 编造活动。"""
        with _synthetic_root("lt_fg_sug_nopolicy_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            # 不发布任何策略。

            response, body = self._suggest(harness)

            self.assertEqual(response.status_code, 422, body)
            self.assertIn(
                body["error"],
                (
                    free_card_policy.REASON_POLICY_NOT_INITIALIZED,
                    free_card_policy.REASON_POLICY_DIR_MISSING,
                ),
                body,
            )
            self.assertNotIn("suggestion", body, body)


# ===========================================================================
# 隔离性：本文件绝不触碰真实用户数据
# ===========================================================================


class SyntheticIsolationTests(unittest.TestCase):
    """所有状态都在合成临时目录内，真实红线目录零写入。"""

    def test_everything_stays_inside_the_synthetic_root(self):
        """合成 DB 与合成策略目录都在临时目录内，且 latest.json 只在合成目录。"""
        with _synthetic_root("lt_fg_iso_") as temp:
            harness = _Harness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            root = Path(temp).resolve()
            self.assertTrue(str(harness.db_path.resolve()).startswith(str(root)))
            self.assertTrue(
                str(harness.policy_dir.resolve()).startswith(str(root))
            )
            latest = harness.policy_dir / "latest.json"
            self.assertTrue(latest.is_file())
            self.assertTrue(str(latest.resolve()).startswith(str(root)))
            # 项目真实红线文件绝不在合成根内被引用。
            self.assertNotIn(
                "task_publisher.db",
                str(harness.app.config["_db_path"]),
            )


if __name__ == "__main__":
    unittest.main()
