"""自由任务 **恢复（resumed）契约** 的合成刻画测试。

范围（``LT_RETENTION_FREE_TASK_RESUME_CONTRACT_20261023_L``）：

本文件只刻画“领域层 + 事件账本层”的 *严格状态机* 增量契约：
``free_task.resumed`` 事件让 K 组 UX 的 “暂停 → 继续 → 再次暂停” 在
synthetic 后端有唯一合法语义，同时证明恢复 **绝不** 产生完成数 /
已验证学习分钟 / 番茄钟。

  A. 领域层：paused → running 是唯一合法恢复
     - 合法：``paused`` 任务恢复为 ``running``，事件类型为
       ``free_task.resumed``；
     - 不变量：活动 / 分类 / 计划时长 / 已有时长 **不被重置**；
     - 统计：``completed_count_delta`` / ``study_minutes`` /
       ``study_pomodoros`` 恒为 ``0``；
     - 非法初态：``running`` / ``interrupted`` / ``failed`` /
       ``completed`` / ``None`` / 非 dict → 抛既有
       :class:`FreeTaskError`（稳定 code ``resume_not_allowed``）；
     - 纯函数：绝不修改调用方传入的任务视图。

  B. 公共入口（facade / export）对应
     - ``free_task_domain`` 显式导出 + ``__all__`` 与实现体一致；
     - 旧导入路径 ``server.services.free_task`` 仍然可用。

  C. 账本层：恢复只允许从 paused，且不污染统计
     - 完整链路 ``started → paused → resumed → paused → resumed →
       completed`` 全部写入，状态逐条正确；
     - ``reported_study_minutes`` 被拒绝；
     - 非法迁移（running 重复恢复 / 终态恢复 / 未 started 就恢复）被
       拒绝且 **账本零变化**；
     - ``event_id`` 幂等与 payload 冲突；
     - entertainment / study 两种分类都不因恢复产生学习分钟；
     - 自由任务秒数（``actual_minutes``）绝不灌入有效学习分钟。

  D. 受保护 Blueprint 合成 app
     - 独立 ``Flask(__name__)`` + 授权 fake：POST append / GET summary
       能反映 ``resumed``；
     - 未授权请求始终 401 且 **绝不** 写事件。

本文件是 **纯合成** 测试：只用 ``tempfile.TemporaryDirectory`` 内的
SQLite、独立 ``Flask(__name__)`` 与固定测试常量假凭据；绝不触碰
``data/task_publisher.db``、``config/config.json``、``src/notes/**``；
不启动真实 Web 服务、不监听端口、不连接主程序。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

flask = pytest.importorskip("flask")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask  # noqa: E402

from server.services import free_task as legacy_free_task  # noqa: E402
from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_events import (  # noqa: E402
    ALLOWED_EVENT_TYPES,
    TABLE_NAME,
    FreeTaskEventError,
    FreeTaskEventStore,
)

URL_PREFIX = "/api/free-tasks"

TS0 = "2026-10-23T09:00:00Z"
TS1 = "2026-10-23T09:10:00Z"
TS2 = "2026-10-23T09:20:00Z"
TS3 = "2026-10-23T09:30:00Z"
TS4 = "2026-10-23T09:40:00Z"
TS5 = "2026-10-23T10:00:00Z"

#: **固定测试常量**，仅用于 synthetic 沙箱；与任何真实机密无关。
FAKE_AUTHORIZATION_HEADER = "Bearer SYNTHETIC-RESUME-NOT-A-REAL-SECRET"

#: 非法恢复的稳定错误码（fail closed）。
RESUME_REFUSED_CODE = "resume_not_allowed"


# ---------------------------------------------------------------------------
# 合成辅助
# ---------------------------------------------------------------------------

def make_task(status: str = domain.STATUS_RUNNING, *, elapsed: int = 0,
              minutes: int = 25, activity: str = "复习线性代数",
              category: str = domain.CATEGORY_STUDY) -> dict:
    return {
        "task_id": "sess-synth",
        "activity": activity,
        "category": category,
        "planned_minutes": minutes,
        "reason": domain.DEFAULT_FREE_TASK_REASON,
        "status": status,
        "elapsed_minutes": elapsed,
    }


def make_paused_task(*, elapsed: int = 7, minutes: int = 25,
                     activity: str = "复习线性代数",
                     category: str = domain.CATEGORY_STUDY) -> dict:
    """走真实领域链：started → paused，保证前态是 *账本真实产出的* paused。"""
    started = domain.start_free_task(
        activity=activity, category=category, minutes=minutes, task_id="sess-synth"
    )["task"]
    return domain.pause_free_task(started, elapsed_minutes=elapsed)["task"]


@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_resume_") as temp:
        yield Path(temp)


@pytest.fixture()
def store(sandbox):
    return FreeTaskEventStore(str(sandbox / "synthetic_resume.sqlite3"))


def start_payload(activity="复习线性代数", category="学习", minutes=25, occurred_at=TS0):
    return {
        "event_type": domain.EVENT_STARTED,
        "activity": activity,
        "category": category,
        "planned_minutes": minutes,
        "occurred_at": occurred_at,
        "reason": domain.DEFAULT_FREE_TASK_REASON,
    }


def resumed_payload(actual_minutes=7, occurred_at=TS1, **extra):
    payload = {
        "event_type": domain.EVENT_RESUMED,
        "actual_minutes": actual_minutes,
        "occurred_at": occurred_at,
    }
    payload.update(extra)
    return payload


def count_rows(store: FreeTaskEventStore, session_id: str) -> int:
    """直接查 SQLite 行数（不经由 store API，避免“读路径即写入”的错觉）。"""
    conn = sqlite3.connect(store.db_path)
    try:
        return int(
            conn.execute(
                f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# A. 领域层：paused → running 是唯一合法恢复
# ---------------------------------------------------------------------------

def test_resumed_event_constant_is_the_frontend_contract():
    """前端使用的 ``free_task.resumed`` 必须存在且被正式导出。"""
    assert domain.EVENT_RESUMED == "free_task.resumed"
    assert "EVENT_RESUMED" in domain.__all__
    assert domain.EVENT_RESUMED in ALLOWED_EVENT_TYPES


def test_resume_from_paused_returns_running_without_metrics():
    """合法恢复：paused → running，三项统计恒为 0。"""
    task = make_paused_task(elapsed=7)
    event = domain.resume_free_task(task, occurred_at=TS1)

    assert event["event_type"] == domain.EVENT_RESUMED
    assert event["occurred_at"] == TS1
    assert event["task"]["status"] == domain.STATUS_RUNNING
    assert event["completed_count_delta"] == 0
    assert event["study_minutes"] == 0
    assert event["study_pomodoros"] == 0
    assert event["auto_completed"] is False


def test_resume_preserves_activity_category_and_planned_minutes():
    """恢复 **不** 重置活动、分类、计划时长（也不得偷偷换时长）。"""
    task = make_paused_task(elapsed=7, minutes=55, activity="看纪录片",
                            category=domain.CATEGORY_ENTERTAINMENT)
    resumed = domain.resume_free_task(task)["task"]

    assert resumed["activity"] == "看纪录片"
    assert resumed["category"] == domain.CATEGORY_ENTERTAINMENT
    assert resumed["planned_minutes"] == 55
    assert resumed["reason"] == domain.DEFAULT_FREE_TASK_REASON
    assert resumed["task_id"] == "sess-synth"


def test_resume_keeps_existing_elapsed_minutes_by_default():
    """缺省不传 elapsed_minutes 时沿用已有时长（不归零、不重算）。"""
    task = make_paused_task(elapsed=12)
    assert task["elapsed_minutes"] == 12
    assert domain.resume_free_task(task)["task"]["elapsed_minutes"] == 12
    # 显式传入时以调用方给的为准，且仍是合法非负整数。
    assert domain.resume_free_task(
        task, elapsed_minutes=20
    )["task"]["elapsed_minutes"] == 20


def test_resume_is_pure_and_does_not_mutate_caller_task():
    """纯函数：绝不就地修改调用方传入的暂停视图。"""
    task = make_paused_task(elapsed=7)
    snapshot = dict(task)
    domain.resume_free_task(task)
    assert task == snapshot
    assert task["status"] == domain.STATUS_PAUSED


def test_resume_pause_cycle_is_repeatable():
    """暂停 → 恢复 → 再次暂停 → 再次恢复：K 组 UX 的完整闭环。"""
    task = make_paused_task(elapsed=3)
    running = domain.resume_free_task(task)["task"]
    assert running["status"] == domain.STATUS_RUNNING

    paused_again = domain.pause_free_task(running, elapsed_minutes=9)["task"]
    assert paused_again["status"] == domain.STATUS_PAUSED
    assert paused_again["elapsed_minutes"] == 9

    running_again = domain.resume_free_task(paused_again)["task"]
    assert running_again["status"] == domain.STATUS_RUNNING
    assert running_again["elapsed_minutes"] == 9


@pytest.mark.parametrize(
    "bad_status",
    [
        domain.STATUS_RUNNING,
        domain.STATUS_INTERRUPTED,
        domain.STATUS_FAILED,
        domain.STATUS_COMPLETED,
        None,
        "not_a_status",
    ],
)
def test_resume_from_illegal_state_is_refused(bad_status):
    """非 paused 前态 → 抛既有 FreeTaskError（稳定 code），绝不静默放行。"""
    task = make_task(status=bad_status, elapsed=5)
    with pytest.raises(domain.FreeTaskError) as excinfo:
        domain.resume_free_task(task)
    assert excinfo.value.code == RESUME_REFUSED_CODE
    assert isinstance(excinfo.value.message, str) and excinfo.value.message


def test_resume_rejects_non_dict_task():
    for bad in (None, [], "paused", 42):
        with pytest.raises(domain.FreeTaskError) as excinfo:
            domain.resume_free_task(bad)
        assert excinfo.value.code == "task_invalid"


def test_resume_with_illegal_planned_minutes_is_refused():
    """暂停视���的时长非法 → 复用既有 minutes_invalid（不新增错误码家族）。"""
    task = make_paused_task()
    task["planned_minutes"] = 30
    with pytest.raises(domain.FreeTaskError) as excinfo:
        domain.resume_free_task(task)
    assert excinfo.value.code == "minutes_invalid"


@pytest.mark.parametrize("bad_elapsed", [-1, "5", 5.0, True])
def test_resume_with_invalid_elapsed_is_refused(bad_elapsed):
    with pytest.raises(domain.FreeTaskError) as excinfo:
        domain.resume_free_task(make_paused_task(), elapsed_minutes=bad_elapsed)
    assert excinfo.value.code == "elapsed_minutes_invalid"


def test_completion_still_requires_user_reported_study_minutes():
    """恢复不得让完成变成 “自动折算”：学习类完成仍必须自报分钟。"""
    running = domain.resume_free_task(make_paused_task())["task"]
    with pytest.raises(domain.FreeTaskError) as excinfo:
        domain.complete_free_task(running, elapsed_minutes=25)
    assert excinfo.value.code == "study_minutes_required"

    completed = domain.complete_free_task(
        running, reported_study_minutes=25, elapsed_minutes=25
    )
    assert completed["completed_count_delta"] == 1
    assert completed["study_minutes"] == 25
    assert completed["study_pomodoros"] == 1


def test_entertainment_completion_after_resume_still_zero_study_minutes():
    """娱乐类：暂停→恢复→完成，学习分钟仍恒为 0。"""
    paused = make_paused_task(category=domain.CATEGORY_ENTERTAINMENT,
                              activity="看电影", elapsed=5)
    running = domain.resume_free_task(paused)["task"]
    completed = domain.complete_free_task(running, elapsed_minutes=25)
    assert completed["completed_count_delta"] == 1
    assert completed["study_minutes"] == 0
    assert completed["study_pomodoros"] == 0


# ---------------------------------------------------------------------------
# B. 公共入口（facade / export）对应
# ---------------------------------------------------------------------------

def test_public_entry_exports_resume_api():
    assert callable(domain.resume_free_task)
    assert "resume_free_task" in domain.__all__
    assert "EVENT_RESUMED" in domain.__all__


def test_public_entry_is_the_same_implementation_object():
    """facade 只转发：公共入口就是实现体的同一对象（不是副本）。"""
    assert domain.implementation is legacy_free_task
    assert domain.resume_free_task is legacy_free_task.resume_free_task
    assert domain.EVENT_RESUMED is legacy_free_task.EVENT_RESUMED


def test_domain_all_and_implementation_all_stay_in_sync():
    """facade 的 ``__all__`` 覆盖实现体 ``__all__``（不遗漏新 API）。"""
    missing = set(legacy_free_task.__all__) - set(domain.__all__)
    assert missing == set(), f"公共入口遗漏了实现体的公共名: {sorted(missing)}"
    # 兜底转发（__getattr__）未被破坏。
    assert domain.__getattr__("EVENT_RESUMED") == "free_task.resumed"
    with pytest.raises(AttributeError):
        domain.__getattr__("_private_missing")


# ---------------------------------------------------------------------------
# C. 账本层：恢复只允许从 paused，且不污染统计
# ---------------------------------------------------------------------------

def test_ledger_start_pause_resume_pause_resume_complete(store):
    """完整链路写入成功，状态逐条正确，总统计只认那一次明确完成。"""
    store.append_event("sess-1", "e1", start_payload())
    store.append_event("sess-1", "e2", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 5, "occurred_at": TS1})
    store.append_event("sess-1", "e3", resumed_payload(5, TS2))
    store.append_event("sess-1", "e4", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 15, "occurred_at": TS3})
    store.append_event("sess-1", "e5", resumed_payload(15, TS4))
    store.append_event("sess-1", "e6", {"event_type": domain.EVENT_COMPLETED,
                                       "actual_minutes": 25,
                                       "reported_study_minutes": 25,
                                       "occurred_at": TS5})

    events = store.list_events("sess-1")
    assert [e["event_type"] for e in events] == [
        domain.EVENT_STARTED,
        domain.EVENT_PAUSED,
        domain.EVENT_RESUMED,
        domain.EVENT_PAUSED,
        domain.EVENT_RESUMED,
        domain.EVENT_COMPLETED,
    ]
    assert [e["status"] for e in events] == [
        domain.STATUS_RUNNING,
        domain.STATUS_PAUSED,
        domain.STATUS_RUNNING,
        domain.STATUS_PAUSED,
        domain.STATUS_RUNNING,
        domain.STATUS_COMPLETED,
    ]
    # 恢复事件本身不带任何统计贡献。
    for resumed in (events[2], events[4]):
        assert resumed["completed_count_delta"] == 0
        assert resumed["study_minutes"] == 0
        assert resumed["study_pomodoros"] == 0
        assert resumed["reported_study_minutes"] is None
        assert resumed["activity"] == "复习线性代数"
        assert resumed["category"] == domain.CATEGORY_STUDY
        assert resumed["planned_minutes"] == 25

    summary = store.get_summary("sess-1")
    assert summary["event_count"] == 6
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25
    assert summary["study_pomodoros"] == 1
    assert summary["auto_completed"] is False
    assert summary["verification"] == "user_reported_not_independently_verified"


def test_pause_and_resume_alone_never_add_study_minutes(store):
    """只有暂停/恢复（没有完成）时：完成数与学习分钟都必须为 0。"""
    store.append_event("sess-2", "p1", start_payload())
    for index, payload in enumerate(
        (
            {"event_type": domain.EVENT_PAUSED, "actual_minutes": 4, "occurred_at": TS1},
            resumed_payload(4, TS2),
            {"event_type": domain.EVENT_PAUSED, "actual_minutes": 8, "occurred_at": TS3},
            resumed_payload(8, TS4),
        ),
        start=2,
    ):
        store.append_event("sess-2", f"p{index}", payload)

    summary = store.get_summary("sess-2")
    assert summary["event_count"] == 5
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0
    # 自由任务秒数绝不灌入有效学习分钟。
    assert sum(int(e["actual_minutes"]) for e in store.list_events("sess-2")) == 24
    assert summary["effective_study_minutes"] == 0


def test_resume_actual_minutes_do_not_leak_into_verified_study_metrics(store):
    """整段会话的 ``actual_minutes`` 之和远大于已验证学习分钟（守恒）。"""
    store.append_event("sess-3", "c1", start_payload())
    store.append_event("sess-3", "c2", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 30, "occurred_at": TS1})
    store.append_event("sess-3", "c3", resumed_payload(30, TS2))
    store.append_event("sess-3", "c4", {"event_type": domain.EVENT_TIMER_ELAPSED,
                                       "actual_minutes": 55, "occurred_at": TS3})
    store.append_event("sess-3", "c5", {"event_type": domain.EVENT_COMPLETED,
                                       "actual_minutes": 55,
                                       "reported_study_minutes": 10,
                                       "occurred_at": TS4})

    summary = store.get_summary("sess-3")
    assert summary["effective_study_minutes"] == 10
    assert summary["study_pomodoros"] == 0  # 10 // 25 = 0
    assert summary["timer_elapsed_events"] == 1
    assert summary["successful_tasks"] == 1


def test_resume_rejects_reported_study_minutes(store):
    """恢复事件不得携带用户报告的学习分钟（否则等于恢复即计学习）。"""
    store.append_event("sess-4", "r1", start_payload())
    store.append_event("sess-4", "r2", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 6, "occurred_at": TS1})
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-4", "r3",
                           resumed_payload(6, TS2, reported_study_minutes=25))
    assert excinfo.value.code == "reported_study_minutes_invalid"
    assert count_rows(store, "sess-4") == 2


def test_resume_before_start_is_rejected_and_writes_nothing(store):
    """非法初态：会话尚未 started 就恢复 → session_not_started，账本零变化。"""
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-5", "x1", resumed_payload(0, TS1))
    assert excinfo.value.code == "session_not_started"
    assert count_rows(store, "sess-5") == 0


def test_resume_while_running_is_rejected_and_writes_nothing(store):
    """running 状态下重复恢复 → 非法迁移，账本零变化。"""
    store.append_event("sess-6", "y1", start_payload())
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-6", "y2", resumed_payload(2, TS1))
    assert excinfo.value.code == "illegal_state_order"
    assert count_rows(store, "sess-6") == 1
    assert store.list_events("sess-6")[-1]["status"] == domain.STATUS_RUNNING


@pytest.mark.parametrize(
    "terminal_event",
    [
        domain.EVENT_INTERRUPTED,
        domain.EVENT_FAILED,
    ],
)
def test_resume_from_terminal_state_is_rejected_and_writes_nothing(
    store, terminal_event
):
    """终态（interrupted / failed / completed）之后恢复一律被拒。"""
    store.append_event("sess-7", "z1", start_payload())
    store.append_event("sess-7", "z2", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 5, "occurred_at": TS1})
    store.append_event("sess-7", "z3", {"event_type": terminal_event,
                                       "actual_minutes": 6, "occurred_at": TS2})
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-7", "z4", resumed_payload(6, TS3))
    assert excinfo.value.code == "illegal_state_order"
    assert count_rows(store, "sess-7") == 3


def test_resume_after_completion_is_rejected_and_writes_nothing(store):
    """完成之后恢复被拒；且完成事件仍然只被计入一次。"""
    store.append_event("sess-8", "w1", start_payload())
    store.append_event("sess-8", "w3", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 10, "occurred_at": TS1})
    store.append_event("sess-8", "w4", resumed_payload(10, TS2))
    store.append_event("sess-8", "w5", {"event_type": domain.EVENT_COMPLETED,
                                       "actual_minutes": 25,
                                       "reported_study_minutes": 25,
                                       "occurred_at": TS3})
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-8", "w6", resumed_payload(25, TS4))
    assert excinfo.value.code == "illegal_state_order"
    assert count_rows(store, "sess-8") == 4
    assert store.get_summary("sess-8")["successful_tasks"] == 1


def test_resume_is_idempotent_per_event_id(store):
    """同一 ``event_id`` + 相同 payload → 幂等；账本行数不增加。"""
    store.append_event("sess-9", "i1", start_payload())
    store.append_event("sess-9", "i2", {"event_type": domain.EVENT_PAUSED,
                                       "actual_minutes": 5, "occurred_at": TS1})
    first = store.append_event("sess-9", "i3", resumed_payload(5, TS2))
    second = store.append_event("sess-9", "i3", resumed_payload(5, TS2))

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["row_id"] == first["row_id"]
    assert count_rows(store, "sess-9") == 3
    assert store.get_summary("sess-9")["successful_tasks"] == 0


def test_resume_with_same_event_id_but_different_payload_conflicts(store):
    store.append_event("sess-10", "d1", start_payload())
    store.append_event("sess-10", "d2", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 5, "occurred_at": TS1})
    store.append_event("sess-10", "d3", resumed_payload(5, TS2))
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-10", "d3", resumed_payload(9, TS2))
    assert excinfo.value.code == "event_conflict"
    assert count_rows(store, "sess-10") == 3


def test_resume_declared_status_must_match_running(store):
    """声明 ``status`` 与恢复后实际状态不一致 → status_mismatch。"""
    store.append_event("sess-11", "m1", start_payload())
    store.append_event("sess-11", "m2", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 5, "occurred_at": TS1})
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-11", "m3", resumed_payload(
            5, TS2, status=domain.STATUS_PAUSED))
    assert excinfo.value.code == "status_mismatch"
    assert count_rows(store, "sess-11") == 2

    # 显式声明 running 则一致，接受。
    store.append_event("sess-11", "m4", resumed_payload(
        5, TS3, status=domain.STATUS_RUNNING))
    assert store.list_events("sess-11")[-1]["status"] == domain.STATUS_RUNNING


def test_resume_cannot_rewrite_activity_category_or_planned_minutes(store):
    """恢复不得改写会话已登记的活动 / 分类 / 时长（信任边界不回退）。"""
    store.append_event("sess-12", "n1", start_payload())
    store.append_event("sess-12", "n2", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 5, "occurred_at": TS1})
    for field, value in (
        ("activity", "看电影"),
        ("category", domain.CATEGORY_ENTERTAINMENT),
        ("planned_minutes", 55),
    ):
        with pytest.raises(FreeTaskEventError) as excinfo:
            store.append_event("sess-12", f"n-{field}",
                               resumed_payload(5, TS2, **{field: value}))
        assert excinfo.value.code.endswith("_mismatch"), excinfo.value.code
    assert count_rows(store, "sess-12") == 2


def test_entertainment_session_resume_keeps_zero_study_minutes(store):
    """娱乐会话：暂停→恢复→完成，成功任务 +1 但有效学习分钟恒为 0。"""
    store.append_event("sess-13", "f1", start_payload(
        activity="看电影", category="娱乐"))
    store.append_event("sess-13", "f2", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 11, "occurred_at": TS1})
    store.append_event("sess-13", "f3", resumed_payload(11, TS2))
    store.append_event("sess-13", "f4", {"event_type": domain.EVENT_COMPLETED,
                                        "actual_minutes": 25,
                                        "reported_study_minutes": 25,
                                        "occurred_at": TS3})

    summary = store.get_summary("sess-13")
    assert summary["successful_tasks"] == 1
    assert summary["entertainment_completions"] == 1
    assert summary["study_completions"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0


def test_study_session_resume_does_not_double_count_completion(store):
    """恢复不产生额外完成：同一会话的完成事件仍只允许一个。"""
    store.append_event("sess-14", "g1", start_payload())
    store.append_event("sess-14", "g2", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 3, "occurred_at": TS1})
    store.append_event("sess-14", "g3", resumed_payload(3, TS2))
    store.append_event("sess-14", "g4", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 20, "occurred_at": TS3})
    store.append_event("sess-14", "g5", resumed_payload(20, TS4))
    store.append_event("sess-14", "g6", {"event_type": domain.EVENT_COMPLETED,
                                        "actual_minutes": 25,
                                        "reported_study_minutes": 50,
                                        "occurred_at": TS5})
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-14", "g7", {"event_type": domain.EVENT_COMPLETED,
                                             "actual_minutes": 25,
                                             "reported_study_minutes": 50,
                                             "occurred_at": TS5})
    assert excinfo.value.code in ("illegal_state_order", "duplicate_completion")

    summary = store.get_summary("sess-14")
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 50
    assert summary["study_pomodoros"] == 2


def test_ledger_is_still_append_only_after_resume(store):
    """恢复事件同样受追加语义保护：UPDATE / DELETE 被数据库层拒绝。"""
    store.append_event("sess-15", "a1", start_payload())
    store.append_event("sess-15", "a2", {"event_type": domain.EVENT_PAUSED,
                                        "actual_minutes": 5, "occurred_at": TS1})
    store.append_event("sess-15", "a3", resumed_payload(5, TS2))

    conn = sqlite3.connect(store.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE {TABLE_NAME} SET status = 'completed'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"DELETE FROM {TABLE_NAME}")
    finally:
        conn.close()
    assert count_rows(store, "sess-15") == 3


def test_store_still_refuses_production_database_path(sandbox):
    """恢复改动不得放宽“禁止写生产库”的红线条。"""
    with pytest.raises(FreeTaskEventError) as excinfo:
        FreeTaskEventStore(str(sandbox / "task_publisher.db"))
    assert excinfo.value.code == "db_path_forbidden"


# ---------------------------------------------------------------------------
# D. 受保护 Blueprint 合成 app
# ---------------------------------------------------------------------------

def make_constant_header_authorizer(expected_header: str):
    def _authorizer(request) -> bool:
        return request.headers.get("Authorization") == expected_header

    return _authorizer


def post_body(session_id, event_id, payload):
    return {
        "action": "append",
        "session_id": session_id,
        "event_id": event_id,
        "event_payload": payload,
    }


@pytest.fixture()
def protected_client(store):
    from server.blueprints.free_task_bp import (
        UNAUTHORIZED_CODE,
        create_protected_free_task_blueprint,
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(
            store, make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)
        )
    )
    client = app.test_client()
    client.free_task_unauthorized_code = UNAUTHORIZED_CODE  # type: ignore[attr-defined]
    return client


def http_post(client, body, *, authed: bool = False):
    headers = {"Authorization": FAKE_AUTHORIZATION_HEADER} if authed else {}
    return client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        headers=headers,
    )


def http_summary(client, session_id, *, authed: bool = False):
    headers = {"Authorization": FAKE_AUTHORIZATION_HEADER} if authed else {}
    return client.get(f"{URL_PREFIX}/sessions/{session_id}/summary", headers=headers)


def test_protected_http_session_reflects_resumed(protected_client, store):
    """授权 POST append / GET summary 全链路反映 resumed，且只完成一次。"""
    assert http_post(protected_client, post_body("h-1", "b1", start_payload()),
                     authed=True).status_code == 200
    assert http_post(protected_client,
                     post_body("h-1", "b2", {"event_type": domain.EVENT_PAUSED,
                                             "actual_minutes": 8,
                                             "occurred_at": TS1}),
                     authed=True).status_code == 200
    resumed = http_post(protected_client,
                        post_body("h-1", "b3", resumed_payload(8, TS2)),
                        authed=True)
    assert resumed.status_code == 200, resumed.get_data(as_text=True)
    body = resumed.get_json()
    assert body["ok"] is True
    assert body["summary"]["successful_tasks"] == 0
    assert body["summary"]["effective_study_minutes"] == 0

    assert http_post(protected_client,
                     post_body("h-1", "b4", {"event_type": domain.EVENT_COMPLETED,
                                             "actual_minutes": 25,
                                             "reported_study_minutes": 25,
                                             "occurred_at": TS3}),
                     authed=True).status_code == 200

    summary_response = http_summary(protected_client, "h-1", authed=True)
    assert summary_response.status_code == 200
    summary = summary_response.get_json()["summary"]
    assert summary["event_count"] == 4
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25

    types = [e["event_type"] for e in store.list_events("h-1")]
    assert domain.EVENT_RESUMED in types
    assert types.count(domain.EVENT_COMPLETED) == 1


def test_protected_http_illegal_resume_is_409(protected_client, store):
    """running 状态重复恢复 → HTTP 409（illegal_state_order），不写库。"""
    assert http_post(protected_client, post_body("h-2", "c1", start_payload()),
                     authed=True).status_code == 200
    response = http_post(protected_client,
                         post_body("h-2", "c2", resumed_payload(2, TS1)),
                         authed=True)
    assert response.status_code == 409
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "illegal_state_order"
    assert count_rows(store, "h-2") == 1


def test_protected_http_unauthorized_resume_never_writes(store, protected_client):
    """未授权的恢复请求始终 401，且绝不写任何事件（含只读 summary）。"""
    from server.blueprints.free_task_bp import (
        UNAUTHORIZED_CODE,
        create_protected_free_task_blueprint,
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(
            store, make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)
        )
    )
    client = app.test_client()

    unauthorized = client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(post_body("h-3", "d1", resumed_payload(0, TS1)),
                        ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )
    assert unauthorized.status_code == 401
    assert unauthorized.get_json()["error"]["code"] == UNAUTHORIZED_CODE
    assert count_rows(store, "h-3") == 0

    bad = client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(post_body("h-3", "d1", start_payload()),
                        ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        headers={"Authorization": "Bearer SYNTHETIC-WRONG-VALUE"},
    )
    assert bad.status_code == 401
    assert count_rows(store, "h-3") == 0

    read = client.get(f"{URL_PREFIX}/sessions/h-3/summary")
    assert read.status_code == 401
    assert "summary" not in read.get_json()
    assert count_rows(store, "h-3") == 0
    # 同一 store 上授权读取仍可用，且反映 “账本里没有任何事件”。
    authorized = http_summary(protected_client, "h-3", authed=True)
    assert authorized.status_code == 200
    assert authorized.get_json()["summary"]["event_count"] == 0