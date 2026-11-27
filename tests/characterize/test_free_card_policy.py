"""M02-S02-G01-W04: 自由卡策略读取器的合成特征测试（只读刻画，不改生产代码）。

范围与红线
----------
- 只刻画已存在的 ``server.services.free_card_policy``（W02 保留代码，本轮
  **不** 实现新功能、**不** 修生产文件）：
  ``read_free_card_policy`` / ``select_free_card_minutes`` /
  ``suggest_free_card_activity`` 的公开返回结构。
- 全部状态在 ``tempfile`` 临时目录内：合成策略目录 + 合成 ``latest.json``。
  **绝不** 读写真实 ``data/task_publisher.db``、``config/config.json``、
  ``src/notes/**``、``data/agent-policy/latest.json``。
- "已批准"策略一律经 **真实受控 Publisher**（``scripts.agent_policy_publisher``）
  在合成目录里发布（公开合成发布协议 + 合成批准证据），绝不手写
  ``approved_by_user`` 伪造用户批准；负向用例只写"未批准草案 / 损坏文件"。
- 形状参考 ``tests/characterize/test_card_type_pool.py`` 的 ``_Harness.publish``：
  真实 Publisher + 合成目录 + 合成批准证据，不混淆批准字段。

Controller 已裁决的行为（本轮只做刻画，不自行重新规划）
--------------------------------------------------------
1. 无策略目录 / 无 latest / 损坏 / 未批准 → ``read_free_card_policy`` 的
   ``ok=false``，无可用分钟与候选，且 **不创建** 策略目录。
2. 合法合成已批准策略的 ``free_task_time_strategy: {"options":[25,55]}`` →
   时长集合严格是 25 与 55；注入伪随机分别选到 25 与 55；固定 25 策略
   稳定选择 25。
3. 只批准权重、没有时长 → ``minutes_options=[]``，
   ``select_free_card_minutes`` 不回落任何默认数值；权重里的数字
   （含形似时长的键）绝不能成为自由卡时长。
4. 非法策略时长（bool、float、字符串、0、30、56、混合列表）全部
   fail closed，无部分容错。
5. 活动建议只能从 **同一份已批准** ``free_task_activity_candidates`` 的合法
   候选池返回恰好 1 条；空候选明确报错；无内置建议、不自动标记学习分钟；
   含 HTML 标签的非法候选不得被选中。
"""

from __future__ import annotations

import builtins
import contextlib
import datetime as _dt
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SOURCE_ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(SOURCE_ROOT), str(SOURCE_ROOT / "scripts")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

publisher = importlib.import_module("agent_policy_publisher")
from server.services import free_card_policy  # noqa: E402


# ---------------------------------------------------------------------------
# 合成脚手架（全部在 tempfile 内）
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _synthetic_root(prefix: str):
    """合成工作目录（Windows 上临时目录清理失败不应算测试失败）。"""
    with tempfile.TemporaryDirectory(
        prefix=prefix, ignore_cleanup_errors=True
    ) as temp:
        yield Path(temp)


class _FixedRng:
    """确定性随机源替身：``rng`` 只需提供 ``.random() -> float``。"""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


class _SyntheticPolicyHarness:
    """合成策略目录 + **真实受控 Publisher**（只写 tempfile 内）。

    ``publish`` 走 Publisher 的公开合成发布协议：提案 → 摘要 → 合成批准证据
    → ``authorize=True``；Publisher 负责生成 ``approved_by_user`` /
    ``approved_at``，本文件 **从不** 自己伪造批准字段。
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.policy_dir = root / "agent-policy"
        self._published = 0

    def publish(self, *, weights=None, policy=None) -> dict:
        """在合成目录发布一份已批准策略（``policy`` 袋会被 Publisher 展平）。"""
        self._published += 1
        proposal = {
            "schema_version": 1,
            "version": f"2099-01-01.{self._published}",
            "effect_summary": (
                "synthetic effect summary for free card policy reader test"
            ),
            "weights": dict(weights or {}),
            "policy": dict(policy or {}),
        }
        result = publisher.publish(
            str(self.policy_dir),
            proposal,
            proposal_digest_expected=publisher.proposal_digest(proposal),
            approval_evidence={
                "approved_by": "synthetic-reviewer",
                "approval_text": (
                    "synthetic approval for free card policy test only"
                ),
                "session_id": "lt-m02-s02-g01-w04-synthetic",
                "approved_at": _dt.datetime.now(_dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            },
            authorize=True,
            authorization_note=(
                "synthetic free card policy reader test publication"
            ),
            create_policy_dir=True,
        )
        assert result.get("ok") is True, result
        return result

    def read(self) -> dict:
        """经正式读取器读取合成策略。"""
        return free_card_policy.read_free_card_policy(str(self.policy_dir))

    def write_raw_latest(self, raw_text: str) -> None:
        """直接写一份 ``latest.json``（仅用于损坏 / 未批准这类负向用例）。"""
        self.policy_dir.mkdir(parents=True, exist_ok=True)
        (self.policy_dir / "latest.json").write_text(
            raw_text, encoding="utf-8"
        )


# ===========================================================================
# 1. 无策略 / 损坏 / 未批准 → fail closed，且不创建策略目录
# ===========================================================================


class MissingOrUnapprovedPolicyTests(unittest.TestCase):
    """读取器在没有任何可用策略时必须 fail closed。"""

    def test_absent_policy_dir_is_fail_closed_and_never_created(self):
        """策略目录不存在 → ok=false，且读取 **绝不** 创建该目录。"""
        with _synthetic_root("lt_fcp_missing_") as temp:
            target = Path(temp) / "never-created"
            result = free_card_policy.read_free_card_policy(str(target))
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["minutes_options"], [])
            self.assertEqual(result["activity_candidates"], [])
            self.assertFalse(
                target.exists(), "read must never create the policy directory"
            )

    def test_empty_policy_dir_argument_is_fail_closed(self):
        """空路径 → 稳定的 ``policy_dir_not_configured``，无任何可用数据。"""
        result = free_card_policy.read_free_card_policy("")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], free_card_policy.REASON_POLICY_DIR_MISSING)
        self.assertEqual(result["minutes_options"], [])
        self.assertEqual(result["activity_candidates"], [])

    def test_absent_latest_in_existing_dir_is_fail_closed(self):
        """目录存在但没有 latest.json → ok=false，无时长、无候选。"""
        with _synthetic_root("lt_fcp_no_latest_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.policy_dir.mkdir(parents=True, exist_ok=True)
            result = harness.read()
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["reason"], free_card_policy.REASON_POLICY_NOT_INITIALIZED
            )
            self.assertEqual(result["minutes_options"], [])
            self.assertEqual(result["activity_candidates"], [])

    def test_corrupted_latest_is_fail_closed(self):
        """latest.json 损坏（坏 JSON）→ ok=false，无时长、无候选。"""
        with _synthetic_root("lt_fcp_corrupt_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.write_raw_latest("{ this is not valid json ")
            result = harness.read()
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["reason"], free_card_policy.REASON_POLICY_NOT_INITIALIZED
            )
            self.assertEqual(result["policy_status"], "invalid_json")
            self.assertEqual(result["minutes_options"], [])
            self.assertEqual(result["activity_candidates"], [])

    def test_unapproved_draft_latest_is_fail_closed(self):
        """未批准草案 → ok=false；草案自称的批准字段绝不生效。"""
        with _synthetic_root("lt_fcp_draft_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            draft = {
                "schema_version": 1,
                "version": "2099-01-01.99",
                "approved_by_user": False,
                # 时间戳必须"看似可信"，否则读侧会先因"批准时间不可信"
                # 而 fail closed，测不到"未获批准"这一条理由。
                "approved_at": "2026-01-01T00:00:00+00:00",
                "effect_summary": "synthetic unapproved draft",
                "weights": {"card_type:free": 1.0},
                "free_task_time_strategy": {"options": [25, 55]},
                "free_task_activity_candidates": [
                    {"activity": "synthetic draft activity"}
                ],
            }
            harness.write_raw_latest(json.dumps(draft, ensure_ascii=False))
            result = harness.read()
            self.assertFalse(result["ok"])
            self.assertEqual(result["policy_status"], "not_approved")
            self.assertEqual(result["minutes_options"], [])
            self.assertEqual(result["activity_candidates"], [])
            self.assertIsNone(
                free_card_policy.select_free_card_minutes(result)
            )
            with self.assertRaises(free_card_policy.FreeCardPolicyError):
                free_card_policy.suggest_free_card_activity(result)


# ===========================================================================
# 2. 合法已批准策略：时长集合严格 25 / 55，随机源可注入
# ===========================================================================


class ApprovedDurationPolicyTests(unittest.TestCase):
    """已批准的 ``free_task_time_strategy`` 必须真正决定自由卡时长。"""

    def test_approved_options_expose_exactly_25_and_55(self):
        """``options=[25,55]`` → 时长集合严格是这两个值。"""
        with _synthetic_root("lt_fcp_options_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25, 55]}}
            )
            result = harness.read()
            self.assertTrue(result["ok"])
            self.assertEqual(len(result["minutes_options"]), 2)
            self.assertEqual(set(result["minutes_options"]), {25, 55})
            self.assertEqual(
                result["minutes_reason"], free_card_policy.REASON_OK
            )

    def test_injected_rng_selects_each_approved_option(self):
        """注入伪随机 → 分别选到 25 与 55（不是固定值、不是默认值）。"""
        with _synthetic_root("lt_fcp_rng_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25, 55]}}
            )
            result = harness.read()
            self.assertEqual(
                free_card_policy.select_free_card_minutes(
                    result, _FixedRng(0.0)
                ),
                25,
            )
            self.assertEqual(
                free_card_policy.select_free_card_minutes(
                    result, _FixedRng(0.99)
                ),
                55,
            )

    def test_fixed_25_policy_is_stable(self):
        """固定 25 策略 → 无论随机源取值都稳定选 25。"""
        with _synthetic_root("lt_fcp_fixed_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            result = harness.read()
            self.assertEqual(result["minutes_options"], [25])
            for draw in (0.0, 0.5, 0.99):
                with self.subTest(draw=draw):
                    self.assertEqual(
                        free_card_policy.select_free_card_minutes(
                            result, _FixedRng(draw)
                        ),
                        25,
                    )


# ===========================================================================
# 3. 只批准权重 → 绝不回落任何默认时长
# ===========================================================================


class WeightsOnlyPolicyTests(unittest.TestCase):
    """只有权重、没有批准时长时，必须没有任何可用自由卡时长。"""

    def test_weights_only_policy_has_no_minutes_and_no_fallback(self):
        """只批准权重 → minutes_options=[]，抽取返回 None（不回落默认值）。"""
        with _synthetic_root("lt_fcp_weights_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                weights={"card_type:free": 0.75, "focus": 1.0},
            )
            result = harness.read()
            self.assertTrue(result["ok"], "策略本身已批准")
            self.assertEqual(result["minutes_options"], [])
            self.assertEqual(
                result["minutes_reason"], free_card_policy.REASON_MINUTES_MISSING
            )
            self.assertIsNone(free_card_policy.select_free_card_minutes(result))
            self.assertIsNone(
                free_card_policy.select_free_card_minutes(
                    result, _FixedRng(0.5)
                )
            )

    def test_numbers_in_weights_never_become_free_card_minutes(self):
        """权重里的数字（连形似时长的键）绝不成为自由卡时长。"""
        with _synthetic_root("lt_fcp_weights_keys_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                weights={"25": 0.5, "55": 0.5, "card_type:free": 0.25},
            )
            result = harness.read()
            self.assertTrue(result["ok"])
            self.assertEqual(result["minutes_options"], [])
            self.assertIsNone(free_card_policy.select_free_card_minutes(result))


# ===========================================================================
# 4. 非法时长 → 全部 fail closed，无部分容错
# ===========================================================================


class IllegalDurationFailsClosedTests(unittest.TestCase):
    """非法时长值一律整体拒绝，绝不部分接受。"""

    def _publish_and_read(self, harness, options):
        harness.publish(
            policy={"free_task_time_strategy": {"options": options}}
        )
        return harness.read()

    def test_illegal_scalar_durations_fail_closed(self):
        """bool / float / 字符串 / 0 / 30 / 56 全部 fail closed。"""
        cases = {
            "bool_true": True,
            "bool_false": False,
            "float": 25.0,
            "string": "25",
            "zero": 0,
            "negative": -25,
            "thirty": 30,
            "fifty_six": 56,
            "empty_list": [],
        }
        with _synthetic_root("lt_fcp_illegal_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            for label, options in cases.items():
                with self.subTest(case=label):
                    result = self._publish_and_read(harness, options)
                    self.assertTrue(
                        result["ok"], "文档本身是已批准的，失败的是时长"
                    )
                    self.assertEqual(result["minutes_options"], [])
                    self.assertEqual(
                        result["minutes_reason"],
                        free_card_policy.REASON_MINUTES_INVALID,
                    )
                    self.assertIsNone(
                        free_card_policy.select_free_card_minutes(result)
                    )

    def test_mixed_option_lists_are_rejected_wholesale(self):
        """混合列表（含合法项）→ 整体拒绝，绝不部分容错。"""
        cases = {
            "legal_plus_out_of_range": [25, 30],
            "legal_plus_string": [25, "55"],
            "legal_plus_bool": [25, True],
            "legal_plus_float": [25, 55.0],
            "bool_plus_legal": [False, 55],
        }
        with _synthetic_root("lt_fcp_mixed_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            for label, options in cases.items():
                with self.subTest(case=label):
                    result = self._publish_and_read(harness, options)
                    self.assertEqual(
                        result["minutes_options"],
                        [],
                        "混合列表必须整体拒绝，绝不保留合法项",
                    )
                    self.assertEqual(
                        result["minutes_reason"],
                        free_card_policy.REASON_MINUTES_INVALID,
                    )
                    self.assertIsNone(
                        free_card_policy.select_free_card_minutes(result)
                    )


# ===========================================================================
# 5. 活动建议：只来自同份已批准候选池，恰好 1 条
# ===========================================================================


class ActivitySuggestionTests(unittest.TestCase):
    """"帮我选" 的建议必须来自已批准策略的合法候选池。"""

    def test_suggestion_comes_from_approved_pool_and_returns_exactly_one(self):
        """合法候选池 → 恰好返回 1 条建议，且建议来自该池。"""
        with _synthetic_root("lt_fcp_suggest_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={
                    "free_task_time_strategy": {"options": [25, 55]},
                    "free_task_activity_candidates": [
                        {"activity": "看一集纪录片", "category": "娱乐"},
                        {"activity": "读十页书", "category": "学习"},
                    ],
                }
            )
            result = harness.read()
            self.assertTrue(result["ok"])
            self.assertEqual(
                result["candidates_reason"], free_card_policy.REASON_OK
            )
            self.assertEqual(len(result["activity_candidates"]), 2)
            for draw, expected in ((0.0, "看一集纪录片"), (0.99, "读十页书")):
                with self.subTest(draw=draw):
                    suggestion = free_card_policy.suggest_free_card_activity(
                        result, _FixedRng(draw)
                    )
                    self.assertEqual(
                        set(suggestion.keys()),
                        {"suggestion", "candidate_count"},
                    )
                    self.assertEqual(suggestion["candidate_count"], 2)
                    self.assertEqual(
                        suggestion["suggestion"]["activity"], expected
                    )

    def test_illegal_candidates_are_excluded_and_pool_errors_explicitly(self):
        """非法候选全部被剔除；池空 → 明确报错（无内置建议）。"""
        candidates = [
            {"activity": "<script>alert(1)</script>", "category": "娱乐"},
            {"activity": "<b>粗体</b>"},
            {"activity": "   "},
            {"activity": "x" * 201},
            {"activity": "带控制字符\x01"},
            {"activity": "已撤下的候选", "approved": False},
            {"activity": "分钟非法", "minutes": 30},
            123,
        ]
        with _synthetic_root("lt_fcp_bad_candidates_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_activity_candidates": candidates}
            )
            result = harness.read()
            self.assertTrue(result["ok"])
            self.assertEqual(result["activity_candidates"], [])
            self.assertEqual(
                result["candidates_reason"],
                free_card_policy.REASON_CANDIDATES_INVALID,
            )
            with self.assertRaises(
                free_card_policy.FreeCardPolicyError
            ) as ctx:
                free_card_policy.suggest_free_card_activity(
                    result, _FixedRng(0.0)
                )
            self.assertTrue(
                ctx.exception.code.startswith("free_card_activity_candidates"),
                ctx.exception.code,
            )

    def test_html_candidate_is_never_the_suggestion(self):
        """含 HTML 标签的候选不得被选中（任何随机取值都不行）。"""
        with _synthetic_root("lt_fcp_html_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={
                    "free_task_activity_candidates": [
                        {
                            "activity": "<script>alert('x')</script>",
                            "category": "娱乐",
                        },
                        {"activity": "整理桌面", "category": "娱乐"},
                    ]
                }
            )
            result = harness.read()
            self.assertEqual(len(result["activity_candidates"]), 1)
            for draw in (0.0, 0.5, 0.99):
                with self.subTest(draw=draw):
                    suggestion = free_card_policy.suggest_free_card_activity(
                        result, _FixedRng(draw)
                    )
                    self.assertEqual(
                        suggestion["suggestion"]["activity"], "整理桌面"
                    )
                    self.assertEqual(suggestion["candidate_count"], 1)
                    self.assertNotIn("<", suggestion["suggestion"]["activity"])
                    self.assertNotIn(">", suggestion["suggestion"]["activity"])

    def test_empty_candidate_pool_errors_explicitly(self):
        """空候选池 → 明确报错，绝不返回内置 / 占位建议。"""
        with _synthetic_root("lt_fcp_empty_pool_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_activity_candidates": []}
            )
            result = harness.read()
            self.assertTrue(result["ok"])
            self.assertEqual(result["activity_candidates"], [])
            with self.assertRaises(
                free_card_policy.FreeCardPolicyError
            ) as ctx:
                free_card_policy.suggest_free_card_activity(
                    result, _FixedRng(0.0)
                )
            self.assertTrue(
                ctx.exception.code.startswith("free_card_activity_candidates"),
                ctx.exception.code,
            )

    def test_missing_candidate_key_errors_explicitly(self):
        """已批准策略但没有候选键 → 明确报错，绝不内置建议。"""
        with _synthetic_root("lt_fcp_no_candidates_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            result = harness.read()
            self.assertTrue(result["ok"])
            self.assertEqual(
                result["candidates_reason"],
                free_card_policy.REASON_CANDIDATES_MISSING,
            )
            with self.assertRaises(
                free_card_policy.FreeCardPolicyError
            ) as ctx:
                free_card_policy.suggest_free_card_activity(
                    result, _FixedRng(0.0)
                )
            self.assertTrue(
                ctx.exception.code.startswith("free_card_activity_candidates"),
                ctx.exception.code,
            )

    def test_suggestion_never_invents_category_or_study_minutes(self):
        """建议不替用户编造分类，也不自动标记任何学习分钟。"""
        with _synthetic_root("lt_fcp_no_invent_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={
                    "free_task_activity_candidates": [
                        {"activity": "散步十分钟"}
                    ]
                }
            )
            result = harness.read()
            suggestion = free_card_policy.suggest_free_card_activity(
                result, _FixedRng(0.0)
            )["suggestion"]
            self.assertEqual(suggestion, {"activity": "散步十分钟"})
            for forbidden in (
                "category",
                "study_minutes",
                "study_pomodoros",
                "completed_count_delta",
                "auto_completed",
            ):
                self.assertNotIn(forbidden, suggestion)


# ===========================================================================
# 6. 公开返回结构 + 读取隔离（绝不触碰真实用户数据）
# ===========================================================================


class PublicShapeAndIsolationTests(unittest.TestCase):
    """公开返回结构稳定；读取过程只读、只在给定策略目录内发生。"""

    def test_public_return_shape_is_stable(self):
        """已批准策略 → 返回结构固定，字段值与文档一致。"""
        with _synthetic_root("lt_fcp_shape_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={
                    "free_task_time_strategy": {"options": [25, 55]},
                    "free_task_activity_candidates": [
                        {"activity": "整理桌面", "category": "娱乐"}
                    ],
                }
            )
            result = harness.read()
            self.assertEqual(
                set(result.keys()),
                {
                    "ok",
                    "status",
                    "reason",
                    "policy_status",
                    "policy_reason",
                    "version",
                    "minutes_options",
                    "minutes_reason",
                    "activity_candidates",
                    "candidates_reason",
                },
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["reason"], free_card_policy.REASON_OK)
            self.assertEqual(result["policy_status"], "ok")
            self.assertEqual(result["policy_reason"], "approved")
            self.assertEqual(result["version"], "2099-01-01.1")
            self.assertEqual(result["minutes_options"], [25, 55])
            self.assertEqual(
                result["minutes_reason"], free_card_policy.REASON_OK
            )
            self.assertEqual(
                result["activity_candidates"],
                [{"activity": "整理桌面", "category": "娱乐"}],
            )
            self.assertEqual(
                result["candidates_reason"], free_card_policy.REASON_OK
            )
            # 返回结构必须可 JSON 序列化（供 HTTP 层直接使用）。
            json.dumps(result, ensure_ascii=False)

    def test_reader_only_reads_inside_the_given_policy_dir(self):
        """读取器只以只读方式打开给定策略目录内的文件，绝不建目录 / 写文件。"""
        with _synthetic_root("lt_fcp_isolation_") as temp:
            harness = _SyntheticPolicyHarness(Path(temp))
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            opened: list = []
            real_open = builtins.open

            def spy_open(file, mode="r", *args, **kwargs):
                try:
                    resolved = os.path.abspath(os.fspath(file))
                except TypeError:
                    resolved = repr(file)
                opened.append((resolved, mode))
                if any(flag in mode for flag in ("w", "a", "x", "+")):
                    raise AssertionError(
                        "read_free_card_policy must never write files"
                    )
                return real_open(file, mode, *args, **kwargs)

            def forbidden_mkdir(*_args, **_kwargs):
                raise AssertionError(
                    "read_free_card_policy must never create directories"
                )

            with mock.patch("builtins.open", new=spy_open), mock.patch(
                "os.makedirs", new=forbidden_mkdir
            ), mock.patch("os.mkdir", new=forbidden_mkdir):
                result = harness.read()

            self.assertTrue(result["ok"], result)
            self.assertTrue(opened, "the reader should have opened latest.json")
            root = os.path.abspath(str(harness.policy_dir))
            for resolved, _mode in opened:
                self.assertTrue(
                    resolved.startswith(root + os.sep),
                    f"unexpected path accessed by the reader: {resolved}",
                )


if __name__ == "__main__":
    unittest.main()
