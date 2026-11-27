"""自由任务 (free task) 领域逻辑的合成单元测试。

范围（LT_RETENTION_FREE_TASK_DOMAIN_20261022_A）：
  - 时间策略自动选择 25 / 55（注入确定性随机源）
  - 缺失 / 非法时间策略 → 明确报错
  - 原因缺省文本与非法原因
  - 活动内容必填
  - 显式完成 → 完成任务数 +1；计时结束不自动完成
  - 娱乐活动学习番茄钟贡献为零；学习活动依据真实报告学习时间
  - 异常输入（暂停 / 中断 / 失败 / 建议）
  - “帮我选”返回具体建议；无合法候选时明确拒绝
  - 无副作用：不写文件、不碰数据库 / 配置 / 笔记

本文件是 **纯合成** 测试：不读取也不写入 ``data/task_publisher.db``、
``config/config.json``、``src/notes/**``、``data/agent-policy/``。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import free_task_domain as free_task  # noqa: E402  公共入口
from server.services.free_task_domain import FreeTaskError  # noqa: E402
from server.services import free_task as legacy_free_task  # noqa: E402  旧模块兼容


class FixedRandom:
    """确定性随机源：始终返回同一个 ``[0, 1)`` 数值。"""

    def __init__(self, value: float) -> None:
        self.value = value
        self.calls = 0

    def random(self) -> float:
        self.calls += 1
        return self.value


def make_task(**overrides):
    """构造一个合法的“进行中”自由任务视图。"""
    task = {
        "task_id": "ft-1",
        "activity": "复习线性代数",
        "category": free_task.CATEGORY_STUDY,
        "planned_minutes": 25,
        "reason": free_task.DEFAULT_FREE_TASK_REASON,
        "status": free_task.STATUS_RUNNING,
        "elapsed_minutes": 0,
    }
    task.update(overrides)
    return task


# ---------------------------------------------------------------------------
# 1) 时长策略 → 25 / 55
# ---------------------------------------------------------------------------

def test_fixed_policy_returns_its_minutes_without_random():
    assert free_task.select_free_task_minutes({"free_task_minutes": 55}) == 55
    assert free_task.select_free_task_minutes({"free_task_minutes": 25}) == 25


def test_two_option_policy_selects_25_or_55_deterministically():
    policy = {"free_task_minutes": [25, 55]}
    assert free_task.select_free_task_minutes(policy, FixedRandom(0.0)) == 25
    assert free_task.select_free_task_minutes(policy, FixedRandom(0.6)) == 55
    assert free_task.select_free_task_minutes(policy, FixedRandom(0.999)) == 55


def test_two_option_policy_with_strategy_object():
    policy = {"free_task_time_strategy": {"options": [55, 25]}}
    assert free_task.select_free_task_minutes(policy, FixedRandom(0.0)) == 55
    assert free_task.select_free_task_minutes(policy, FixedRandom(0.9)) == 25


def test_nested_policy_document_is_supported():
    policy = {"policy": {"free_task_minutes": [25, 55]}}
    assert free_task.select_free_task_minutes(policy, FixedRandom(0.2)) == 25


@pytest.mark.parametrize(
    "policy",
    [
        None,
        {},
        [],
        "25",
        {"free_task_minutes": 30},
        {"free_task_minutes": [25, 40]},
        {"free_task_minutes": [25, "55"]},
        {"free_task_minutes": []},
        {"free_task_minutes": True},
        {"free_task_minutes": 25.0},
    ],
)
def test_invalid_or_missing_time_policy_raises(policy):
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.select_free_task_minutes(policy)
    assert excinfo.value.code.startswith("time_policy_")


def test_random_source_returning_garbage_is_rejected():
    policy = {"free_task_minutes": [25, 55]}
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.select_free_task_minutes(policy, FixedRandom("x"))
    assert excinfo.value.code == "random_source_invalid"


# ---------------------------------------------------------------------------
# 2) 原因与活动内容
# ---------------------------------------------------------------------------

def test_missing_reason_uses_default_text():
    assert free_task.normalize_reason(None) == "没有什么理由，我就是想。"
    assert free_task.normalize_reason("") == "没有什么理由，我就是想。"
    assert free_task.normalize_reason("   ") == "没有什么理由，我就是想。"


def test_explicit_reason_is_preserved_and_stripped():
    assert free_task.normalize_reason("  想静一静  ") == "想静一静"


@pytest.mark.parametrize("reason", [123, ["x"], {"a": 1}, "带\n换行", "x" * 500])
def test_invalid_reason_raises(reason):
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.normalize_reason(reason)
    assert excinfo.value.code == "reason_invalid"


@pytest.mark.parametrize("activity", [None, "", "   ", 42, "含\x00控制符", "x" * 500])
def test_activity_is_required_and_validated(activity):
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.validate_activity(activity)
    assert excinfo.value.code in ("activity_required", "activity_invalid")


def test_activity_is_trimmed():
    assert free_task.validate_activity("  写代码  ") == "写代码"


# ---------------------------------------------------------------------------
# 3) 开始自由任务
# ---------------------------------------------------------------------------

def test_start_free_task_returns_structured_started_event():
    event = free_task.start_free_task(
        activity="读论文",
        category="学习",
        minutes=55,
        task_id="ft-9",
        occurred_at="2026-10-22T09:00:00Z",
    )
    assert event["event_type"] == free_task.EVENT_STARTED
    assert event["occurred_at"] == "2026-10-22T09:00:00Z"
    task = event["task"]
    assert task["task_id"] == "ft-9"
    assert task["activity"] == "读论文"
    assert task["category"] == free_task.CATEGORY_STUDY
    assert task["planned_minutes"] == 55
    assert task["reason"] == free_task.DEFAULT_FREE_TASK_REASON
    assert task["status"] == free_task.STATUS_RUNNING
    assert task["elapsed_minutes"] == 0


def test_start_free_task_with_entertainment_category():
    event = free_task.start_free_task(
        activity="打游戏",
        category="娱乐",
        minutes=25,
    )
    assert event["task"]["category"] == free_task.CATEGORY_ENTERTAINMENT


@pytest.mark.parametrize(
    "kwargs",
    [
        {"activity": "", "category": "学习", "minutes": 25},
        {"activity": "看书", "category": "未知", "minutes": 25},
        {"activity": "看书", "category": "学习", "minutes": 30},
        {"activity": "看书", "category": "学习", "minutes": None},
        {"activity": "看书", "category": "学习", "minutes": 25, "reason": 5},
    ],
)
def test_start_free_task_rejects_invalid_input(kwargs):
    with pytest.raises(FreeTaskError):
        free_task.start_free_task(**kwargs)


# ---------------------------------------------------------------------------
# 4) 暂停 / 中断 / 失败 / 计时结束
# ---------------------------------------------------------------------------

def test_pause_returns_structured_event_without_completion():
    event = free_task.pause_free_task(make_task(), elapsed_minutes=7)
    assert event["event_type"] == free_task.EVENT_PAUSED
    assert event["task"]["status"] == free_task.STATUS_PAUSED
    assert event["task"]["elapsed_minutes"] == 7
    assert event["completed_count_delta"] == 0


def test_interrupt_returns_structured_event_without_completion():
    event = free_task.interrupt_free_task(make_task(), elapsed_minutes=3)
    assert event["event_type"] == free_task.EVENT_INTERRUPTED
    assert event["task"]["status"] == free_task.STATUS_INTERRUPTED
    assert event["completed_count_delta"] == 0


def test_fail_returns_structured_event_with_reason():
    event = free_task.fail_free_task(
        make_task(), elapsed_minutes=2, reason="状态不好"
    )
    assert event["event_type"] == free_task.EVENT_FAILED
    assert event["task"]["status"] == free_task.STATUS_FAILED
    assert event["reason"] == "状态不好"
    assert event["completed_count_delta"] == 0


def test_fail_without_reason_uses_default_text():
    event = free_task.fail_free_task(make_task())
    assert event["reason"] == free_task.DEFAULT_FREE_TASK_REASON


@pytest.mark.parametrize("bad", [-1, 1.5, "10", True, None])
def test_invalid_elapsed_minutes_raise(bad):
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.pause_free_task(make_task(), elapsed_minutes=bad)
    assert excinfo.value.code == "elapsed_minutes_invalid"


# ---------------------------------------------------------------------------
# 5) 计时结束不得自动完成
# ---------------------------------------------------------------------------

def test_timer_elapsed_does_not_complete_automatically():
    event = free_task.on_timer_elapsed(make_task(planned_minutes=25), elapsed_minutes=25)
    assert event["event_type"] == free_task.EVENT_TIMER_ELAPSED
    assert event["completed_count_delta"] == 0
    assert event["study_pomodoros"] == 0
    assert event["study_minutes"] == 0
    assert event["auto_completed"] is False
    assert event["task"]["status"] == free_task.STATUS_RUNNING


# ---------------------------------------------------------------------------
# 6) 显式完成
# ---------------------------------------------------------------------------

def test_explicit_completion_increments_completed_count():
    event = free_task.complete_free_task(
        make_task(planned_minutes=25),
        reported_study_minutes=25,
        elapsed_minutes=25,
        occurred_at="2026-10-22T10:00:00Z",
    )
    assert event["event_type"] == free_task.EVENT_COMPLETED
    assert event["completed_count_delta"] == 1
    assert event["task"]["status"] == free_task.STATUS_COMPLETED
    assert event["study_minutes"] == 25
    assert event["study_pomodoros"] == 1
    assert event["explicitly_reported"] is True
    assert event["auto_completed"] is False
    assert event["occurred_at"] == "2026-10-22T10:00:00Z"


def test_entertainment_completion_has_zero_study_contribution():
    event = free_task.complete_free_task(
        make_task(category=free_task.CATEGORY_ENTERTAINMENT, planned_minutes=55),
        reported_study_minutes=40,
        elapsed_minutes=55,
    )
    assert event["completed_count_delta"] == 1
    assert event["study_minutes"] == 0
    assert event["study_pomodoros"] == 0


def test_study_completion_requires_reported_study_minutes():
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.complete_free_task(make_task(), elapsed_minutes=25)
    assert excinfo.value.code == "study_minutes_required"


@pytest.mark.parametrize("bad", [0, -5, 12.5, "20", True])
def test_study_completion_rejects_invalid_reported_minutes(bad):
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.complete_free_task(make_task(), reported_study_minutes=bad)
    assert excinfo.value.code == "study_minutes_invalid"


def test_completion_rejects_unknown_category():
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.complete_free_task(make_task(category="other"))
    assert excinfo.value.code == "category_invalid"


def test_completion_rejects_invalid_planned_minutes():
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.complete_free_task(make_task(planned_minutes=40))
    assert excinfo.value.code == "minutes_invalid"


def test_completion_pomodoro_count_uses_reported_minutes():
    event = free_task.complete_free_task(
        make_task(planned_minutes=55), reported_study_minutes=110
    )
    assert event["study_minutes"] == 110
    assert event["study_pomodoros"] == 2


# ---------------------------------------------------------------------------
# 7) “帮我选”
# ---------------------------------------------------------------------------

def test_suggest_returns_one_concrete_approved_candidate():
    candidates = [
        {"approved": True, "activity": "整理错题本", "category": "学习"},
        {"approved": True, "activity": "散步", "category": "娱乐"},
    ]
    event = free_task.suggest_activity(candidates, FixedRandom(0.0))
    assert event["event_type"] == free_task.EVENT_ACTIVITY_SUGGESTED
    assert event["suggestion"]["activity"] == "整理错题本"
    assert event["suggestion"]["category"] == free_task.CATEGORY_STUDY
    assert event["suggestion"]["reason"] == free_task.DEFAULT_FREE_TASK_REASON
    assert event["candidate_count"] == 2

    event = free_task.suggest_activity(candidates, FixedRandom(0.99))
    assert event["suggestion"]["activity"] == "散步"


def test_suggest_ignores_unapproved_and_invalid_candidates():
    candidates = [
        {"approved": False, "activity": "未批准", "category": "学习"},
        {"approved": True, "activity": "", "category": "学习"},
        {"approved": True, "activity": "合法", "category": "学习"},
    ]
    event = free_task.suggest_activity(candidates, FixedRandom(0.0))
    assert event["suggestion"]["activity"] == "合法"
    assert event["candidate_count"] == 1


@pytest.mark.parametrize(
    "candidates",
    [None, [], (), [{"approved": False, "activity": "x", "category": "学习"}]],
)
def test_suggest_without_legal_candidate_is_refused(candidates):
    with pytest.raises(FreeTaskError) as excinfo:
        free_task.suggest_activity(candidates)
    assert excinfo.value.code == "no_candidate_available"


# ---------------------------------------------------------------------------
# 8) 无副作用
# ---------------------------------------------------------------------------

def test_domain_functions_do_not_touch_protected_paths(tmp_path, monkeypatch):
    """把 CWD 指向临时目录后调用全部入口，断言没有任何文件被创建。"""
    monkeypatch.chdir(tmp_path)
    policy = {"free_task_minutes": [25, 55]}
    minutes = free_task.select_free_task_minutes(policy, FixedRandom(0.0))
    task = free_task.start_free_task(
        activity="写测试", category="学习", minutes=minutes
    )["task"]
    free_task.pause_free_task(task, elapsed_minutes=1)
    free_task.interrupt_free_task(task, elapsed_minutes=2)
    free_task.fail_free_task(task, elapsed_minutes=3)
    free_task.on_timer_elapsed(task, elapsed_minutes=4)
    free_task.complete_free_task(task, reported_study_minutes=25)
    free_task.suggest_activity(
        [{"approved": True, "activity": "读一章", "category": "学习"}],
        FixedRandom(0.0),
    )
    assert list(tmp_path.iterdir()) == []


def test_legacy_module_and_public_entry_point_agree():
    """旧模块 `free_task` 与公共入口 `free_task_domain` 必须是同一实现。"""
    assert legacy_free_task is free_task.implementation
    assert legacy_free_task.select_free_task_minutes is free_task.select_free_task_minutes
    assert legacy_free_task.FreeTaskError is free_task.FreeTaskError
    # 公共入口不得复制实现：新名字也应由同一实现体提供
    assert free_task.MAX_ACTIVITY_LENGTH == legacy_free_task.MAX_ACTIVITY_LENGTH
    # 公共入口的兜底转发：实现体新名也能被公共入口取到
    assert free_task.EVENT_TIMER_ELAPSED == legacy_free_task.EVENT_TIMER_ELAPSED


def test_returned_task_view_does_not_alias_caller_state():
    task = make_task()
    event = free_task.pause_free_task(task, elapsed_minutes=4)
    event["task"]["activity"] = "被篡改"
    assert task["activity"] == "复习线性代数"
    assert task["status"] == free_task.STATUS_RUNNING
