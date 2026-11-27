"""自由任务事件账本 (free_task_events) 的合成单元测试。

范围（LT_RETENTION_FREE_TASK_EVENT_LEDGER_20261022_B）：
  - 必须显式传入 SQLite 路径；拒绝生产库文件名；无默认路径
  - 重启持久性（重新打开同一个 synthetic DB 仍能读到事件）
  - 重复点击幂等（同一 event_id + 相同 payload）
  - 相同 event_id 但 payload 冲突 → 明确报错
  - 会话隔离
  - 娱乐 / 学习分账
  - 暂停 / 中断 / 失败
  - 时间结束不算完成
  - 非法状态顺序
  - 损坏 payload 安全拒绝
  - SQL 参数化安全（注入串被当作普通文本）
  - 并发 / 锁行为合理
  - 追加语义：旧行不可修改 / 不可删除

本文件是 **纯合成** 测试：所有 SQLite 都建在
``tempfile.TemporaryDirectory()`` 里；绝不触碰 ``data/task_publisher.db``、
``config/config.json``、``src/notes/**``、``data/agent-policy/``，
也不 import Flask、不启动真实服务。
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_events import (  # noqa: E402
    ALLOWED_PAYLOAD_FIELDS,
    FreeTaskEventError,
    FreeTaskEventStore,
    new_event_id,
)

TS0 = "2026-10-22T09:00:00Z"
TS1 = "2026-10-22T09:10:00Z"
TS2 = "2026-10-22T09:25:00Z"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def start_payload(activity="复习线性代数", category="学习", minutes=25, **extra):
    payload = {
        "event_type": domain.EVENT_STARTED,
        "activity": activity,
        "category": category,
        "planned_minutes": minutes,
        "occurred_at": TS0,
        "reason": domain.DEFAULT_FREE_TASK_REASON,
    }
    payload.update(extra)
    return payload


def make_store(root, name="synthetic_events.sqlite3") -> FreeTaskEventStore:
    return FreeTaskEventStore(str(Path(root) / name))


@pytest.fixture()
def tmp_db_dir():
    with TemporaryDirectory(prefix="lt_free_task_events_") as temp:
        yield Path(temp)


# ---------------------------------------------------------------------------
# 1) 路径必须显式传入；不得落到生产库
# ---------------------------------------------------------------------------

def test_db_path_is_required():
    with pytest.raises(FreeTaskEventError) as excinfo:
        FreeTaskEventStore(None)
    assert excinfo.value.code == "db_path_required"


def test_blank_db_path_is_rejected():
    with pytest.raises(FreeTaskEventError) as excinfo:
        FreeTaskEventStore("   ")
    assert excinfo.value.code == "db_path_required"


def test_production_database_path_is_refused(tmp_db_dir):
    with pytest.raises(FreeTaskEventError) as excinfo:
        FreeTaskEventStore(str(tmp_db_dir / "task_publisher.db"))
    assert excinfo.value.code == "db_path_forbidden"


def test_production_database_file_is_not_created(tmp_db_dir):
    target = tmp_db_dir / "task_publisher.db"
    with pytest.raises(FreeTaskEventError):
        FreeTaskEventStore(str(target))
    assert not target.exists()


def test_store_never_touches_project_data_dir(tmp_db_dir, monkeypatch):
    """在临时目录里跑一次完整会话，项目 data/ 不得被写入任何东西。"""
    monkeypatch.chdir(tmp_db_dir)
    store = make_store(tmp_db_dir)
    store.append_event("s1", "e1", start_payload())
    data_dir = PROJECT_ROOT / "data"
    before = sorted(p.name for p in data_dir.iterdir()) if data_dir.exists() else []
    store.append_event("s1", "e2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "reported_study_minutes": 25,
        "occurred_at": TS2,
    })
    after = sorted(p.name for p in data_dir.iterdir()) if data_dir.exists() else []
    assert before == after


# ---------------------------------------------------------------------------
# 2) 基本写入 / 读取 / 持久性
# ---------------------------------------------------------------------------

def test_append_started_event_and_read_back(tmp_db_dir):
    store = make_store(tmp_db_dir)
    result = store.append_event("sess-1", "evt-1", start_payload())
    assert result["stored"] is True
    assert result["duplicate"] is False
    assert result["status"] == domain.STATUS_RUNNING

    events = store.list_events("sess-1")
    assert len(events) == 1
    event = events[0]
    assert event["event_id"] == "evt-1"
    assert event["session_id"] == "sess-1"
    assert event["event_type"] == domain.EVENT_STARTED
    assert event["activity"] == "复习线性代数"
    assert event["category"] == domain.CATEGORY_STUDY
    assert event["reason"] == domain.DEFAULT_FREE_TASK_REASON
    assert event["status"] == domain.STATUS_RUNNING
    assert event["actual_minutes"] == 0
    assert event["occurred_at"] == TS0
    assert event["reported_study_minutes"] is None


def test_event_id_may_be_generated_uuid(tmp_db_dir):
    store = make_store(tmp_db_dir)
    eid = new_event_id()
    assert uuid.UUID(eid)  # 合法 UUID
    store.append_event("sess-uuid", eid, start_payload())
    assert len(store.list_events("sess-uuid")) == 1


def test_events_survive_restart(tmp_db_dir):
    db_path = str(tmp_db_dir / "restart.sqlite3")
    store = FreeTaskEventStore(db_path)
    store.append_event("sess-r", "evt-r", start_payload())

    # 模拟进程重启：全新 store 实例读同一个文件
    reopened = FreeTaskEventStore(db_path)
    events = reopened.list_events("sess-r")
    assert len(events) == 1
    assert events[0]["activity"] == "复习线性代数"
    assert reopened.get_summary("sess-r")["event_count"] == 1


def test_policy_version_is_stored_when_present(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-p", "evt-p", start_payload(policy_version="v1.2.3"))
    event = store.list_events("sess-p")[0]
    assert event["policy_version"] == "v1.2.3"


# ---------------------------------------------------------------------------
# 3) 幂等 / 冲突
# ---------------------------------------------------------------------------

def test_duplicate_event_id_with_same_payload_is_idempotent(tmp_db_dir):
    store = make_store(tmp_db_dir)
    payload = start_payload()
    first = store.append_event("sess-2", "evt-dup", payload)
    second = store.append_event("sess-2", "evt-dup", payload)

    assert second["duplicate"] is True
    assert second["row_id"] == first["row_id"]
    assert len(store.list_events("sess-2")) == 1


def test_duplicate_event_id_with_different_payload_conflicts(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-3", "evt-x", start_payload())
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-3", "evt-x", start_payload(activity="改成别的活动"))
    assert excinfo.value.code == "event_conflict"
    assert len(store.list_events("sess-3")) == 1


def test_completion_event_is_idempotent_on_double_click(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-4", "evt-s", start_payload())
    completion = {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "reported_study_minutes": 25,
        "occurred_at": TS2,
    }
    store.append_event("sess-4", "evt-c", completion)
    again = store.append_event("sess-4", "evt-c", completion)
    assert again["duplicate"] is True

    summary = store.get_summary("sess-4")
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25


# ---------------------------------------------------------------------------
# 4) 会话隔离
# ---------------------------------------------------------------------------

def test_sessions_are_isolated(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-a", "a-1", start_payload(activity="学习 A"))
    store.append_event("sess-b", "b-1", start_payload(activity="学习 B"))

    assert len(store.list_events("sess-a")) == 1
    assert len(store.list_events("sess-b")) == 1
    assert store.list_events("sess-a")[0]["activity"] == "学习 A"
    assert store.get_summary("sess-a")["event_count"] == 1
    assert store.get_summary("sess-b")["event_count"] == 1


def test_unknown_session_returns_empty(tmp_db_dir):
    store = make_store(tmp_db_dir)
    assert store.list_events("never-seen") == []
    summary = store.get_summary("never-seen")
    assert summary["event_count"] == 0
    assert summary["successful_tasks"] == 0


# ---------------------------------------------------------------------------
# 5) 娱乐 / 学习分账
# ---------------------------------------------------------------------------

def test_entertainment_completion_counts_one_task_and_zero_study_minutes(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-e", "e-1", start_payload(
        activity="打游戏", category="娱乐", minutes=55))
    store.append_event("sess-e", "e-2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 55,
        "reported_study_minutes": 40,
        "occurred_at": TS2,
    })

    summary = store.get_summary("sess-e")
    assert summary["successful_tasks"] == 1
    assert summary["entertainment_completions"] == 1
    assert summary["study_completions"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0


def test_study_completion_uses_reported_actual_minutes(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-s", "s-1", start_payload(minutes=55))
    store.append_event("sess-s", "s-2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 55,
        "reported_study_minutes": 110,
        "occurred_at": TS2,
    })

    summary = store.get_summary("sess-s")
    assert summary["successful_tasks"] == 1
    assert summary["study_completions"] == 1
    assert summary["effective_study_minutes"] == 110
    assert summary["study_pomodoros"] == 2


def test_study_completion_without_reported_minutes_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-s2", "s2-1", start_payload())
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-s2", "s2-2", {
            "event_type": domain.EVENT_COMPLETED,
            "actual_minutes": 25,
            "occurred_at": TS2,
        })
    assert excinfo.value.code == "study_minutes_required"
    assert store.get_summary("sess-s2")["successful_tasks"] == 0


def test_non_completion_event_cannot_carry_reported_minutes(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-s3", "s3-1", start_payload())
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-s3", "s3-2", {
            "event_type": domain.EVENT_PAUSED,
            "actual_minutes": 10,
            "reported_study_minutes": 10,
            "occurred_at": TS1,
        })
    assert excinfo.value.code == "reported_study_minutes_invalid"


def test_caller_cannot_fake_entertainment_as_study_via_event_type(tmp_db_dir):
    """娱乐会话即便在后续事件里声明 “学习” 也不能产生学习分钟。"""
    store = make_store(tmp_db_dir)
    store.append_event("sess-fake", "f-1", start_payload(
        activity="看电影", category="娱乐"))
    with pytest.raises(FreeTaskEventError):
        store.append_event("sess-fake", "f-2", {
            "event_type": domain.EVENT_COMPLETED,
            "actual_minutes": 25,
            "reported_study_minutes": 25,
            "category": domain.CATEGORY_STUDY,
            "occurred_at": TS2,
        })
    summary = store.get_summary("sess-fake")
    assert summary["effective_study_minutes"] == 0


def test_unknown_category_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-cat", "c-1", start_payload(category="睡觉"))
    assert excinfo.value.code == "category_invalid"


def test_unknown_event_type_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-type", "t-1", {
            "event_type": "free_task.hacked",
            "occurred_at": TS0,
        })
    assert excinfo.value.code == "event_type_invalid"


def test_unknown_payload_field_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-unk", "u-1", start_payload(secret_token="x"))
    assert excinfo.value.code == "payload_unknown_field"


def test_allowed_payload_fields_contract():
    assert "event_type" in ALLOWED_PAYLOAD_FIELDS
    assert "reported_study_minutes" in ALLOWED_PAYLOAD_FIELDS
    assert "secret_token" not in ALLOWED_PAYLOAD_FIELDS


# ---------------------------------------------------------------------------
# 6) 暂停 / 中断 / 失败 / 时间结束
# ---------------------------------------------------------------------------

def test_pause_does_not_complete(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-p1", "p1-1", start_payload())
    store.append_event("sess-p1", "p1-2", {
        "event_type": domain.EVENT_PAUSED,
        "actual_minutes": 10,
        "occurred_at": TS1,
    })
    summary = store.get_summary("sess-p1")
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0
    assert store.list_events("sess-p1")[-1]["status"] == domain.STATUS_PAUSED


def test_interrupt_does_not_complete(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-i1", "i1-1", start_payload())
    store.append_event("sess-i1", "i1-2", {
        "event_type": domain.EVENT_INTERRUPTED,
        "actual_minutes": 5,
        "occurred_at": TS1,
    })
    summary = store.get_summary("sess-i1")
    assert summary["successful_tasks"] == 0
    assert store.list_events("sess-i1")[-1]["status"] == domain.STATUS_INTERRUPTED


def test_failure_does_not_complete(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-f1", "f1-1", start_payload())
    store.append_event("sess-f1", "f1-2", {
        "event_type": domain.EVENT_FAILED,
        "actual_minutes": 3,
        "reason": "状态不好",
        "occurred_at": TS1,
    })
    summary = store.get_summary("sess-f1")
    assert summary["successful_tasks"] == 0
    assert store.list_events("sess-f1")[-1]["status"] == domain.STATUS_FAILED


def test_timer_elapsed_is_not_a_completion(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-t1", "t1-1", start_payload(minutes=25))
    store.append_event("sess-t1", "t1-2", {
        "event_type": domain.EVENT_TIMER_ELAPSED,
        "actual_minutes": 25,
        "occurred_at": TS1,
    })
    summary = store.get_summary("sess-t1")
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0
    assert summary["timer_elapsed_events"] == 1
    assert summary["auto_completed"] is False
    assert store.list_events("sess-t1")[-1]["status"] == domain.STATUS_RUNNING


def test_timer_elapsed_then_explicit_completion_counts_once(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-t2", "t2-1", start_payload(minutes=25))
    store.append_event("sess-t2", "t2-2", {
        "event_type": domain.EVENT_TIMER_ELAPSED,
        "actual_minutes": 25,
        "occurred_at": TS1,
    })
    store.append_event("sess-t2", "t2-3", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "reported_study_minutes": 25,
        "occurred_at": TS2,
    })
    summary = store.get_summary("sess-t2")
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25
    assert summary["timer_elapsed_events"] == 1


# ---------------------------------------------------------------------------
# 7) 非法状态顺序 / 重复完成
# ---------------------------------------------------------------------------

def test_event_before_start_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-o", "o-1", {
            "event_type": domain.EVENT_PAUSED,
            "actual_minutes": 1,
            "occurred_at": TS1,
        })
    assert excinfo.value.code == "session_not_started"


def test_completion_after_completion_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-dc", "dc-1", start_payload())
    store.append_event("sess-dc", "dc-2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "reported_study_minutes": 25,
        "occurred_at": TS2,
    })
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-dc", "dc-3", {
            "event_type": domain.EVENT_COMPLETED,
            "actual_minutes": 25,
            "reported_study_minutes": 25,
            "occurred_at": TS2,
        })
    assert excinfo.value.code in ("illegal_state_order", "duplicate_completion")
    summary = store.get_summary("sess-dc")
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25


def test_pause_after_completion_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-pc", "pc-1", start_payload())
    store.append_event("sess-pc", "pc-2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "reported_study_minutes": 25,
        "occurred_at": TS2,
    })
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-pc", "pc-3", {
            "event_type": domain.EVENT_PAUSED,
            "actual_minutes": 26,
            "occurred_at": TS2,
        })
    assert excinfo.value.code == "illegal_state_order"


def test_declared_status_mismatch_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-sm", "sm-1", start_payload())
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-sm", "sm-2", {
            "event_type": domain.EVENT_PAUSED,
            "actual_minutes": 5,
            "status": domain.STATUS_COMPLETED,
            "occurred_at": TS1,
        })
    assert excinfo.value.code == "status_mismatch"


def test_invalid_minutes_are_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-min", "min-1", start_payload(minutes=30))
    assert excinfo.value.code == "minutes_invalid"


def test_missing_occurred_at_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    payload = start_payload()
    payload.pop("occurred_at")
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-ts", "ts-1", payload)
    assert excinfo.value.code == "occurred_at_required"


def test_invalid_occurred_at_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-ts2", "ts2-1", start_payload(occurred_at="昨天"))
    assert excinfo.value.code == "occurred_at_invalid"


# ---------------------------------------------------------------------------
# 8) 损坏 payload 安全拒绝
# ---------------------------------------------------------------------------

def test_corrupt_payload_json_is_rejected_safely(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-cr", "cr-1", start_payload())
    conn = sqlite3.connect(store.db_path)
    try:
        # 先摘掉追加保护触发器，模拟外部篡改 / 磁盘损坏
        conn.execute("DROP TRIGGER trg_free_task_events_no_update")
        conn.execute(
            "UPDATE free_task_events SET payload_json = ? WHERE event_id = ?",
            ("{not-json", "cr-1"),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(FreeTaskEventError) as excinfo:
        store.list_events("sess-cr")
    assert excinfo.value.code == "payload_corrupt"


def test_non_dict_payload_json_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-cr3", "cr3-1", start_payload())
    conn = sqlite3.connect(store.db_path)
    try:
        conn.execute("DROP TRIGGER trg_free_task_events_no_update")
        conn.execute(
            "UPDATE free_task_events SET payload_json = ? WHERE event_id = ?",
            ("[1,2,3]", "cr3-1"),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(FreeTaskEventError) as excinfo:
        store.list_events("sess-cr3")
    assert excinfo.value.code == "payload_corrupt"


def test_payload_must_be_dict(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-cr4", "cr4-1", ["not", "a", "dict"])
    assert excinfo.value.code == "payload_invalid"


# ---------------------------------------------------------------------------
# 9) 追加语义
# ---------------------------------------------------------------------------

def test_existing_rows_cannot_be_updated(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-au", "au-1", start_payload())
    conn = sqlite3.connect(store.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE free_task_events SET activity = '篡改' "
                "WHERE event_id = 'au-1'"
            )
    finally:
        conn.close()
    assert store.list_events("sess-au")[0]["activity"] == "复习线性代数"


def test_existing_rows_cannot_be_deleted(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-ad", "ad-1", start_payload())
    conn = sqlite3.connect(store.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM free_task_events WHERE event_id = 'ad-1'")
    finally:
        conn.close()
    assert len(store.list_events("sess-ad")) == 1


# ---------------------------------------------------------------------------
# 10) SQL 参数化安全
# ---------------------------------------------------------------------------

def test_sql_injection_in_session_id_is_treated_as_text(tmp_db_dir):
    store = make_store(tmp_db_dir)
    nasty = "sess'; DROP TABLE free_task_events; --"
    store.append_event(nasty, "inj-1", start_payload())
    assert len(store.list_events(nasty)) == 1
    # 表仍然存在
    assert len(store.list_events("sess-a")) == 0
    store.append_event("sess-a", "inj-2", start_payload())
    assert len(store.list_events("sess-a")) == 1


def test_sql_injection_in_activity_is_stored_as_text(tmp_db_dir):
    store = make_store(tmp_db_dir)
    payload = start_payload(activity="'); DROP TABLE free_task_events; --")
    store.append_event("sess-inj2", "inj2-1", payload)
    event = store.list_events("sess-inj2")[0]
    assert event["activity"] == "'); DROP TABLE free_task_events; --"
    assert len(store.list_events("sess-inj2")) == 1


def test_event_id_injection_string_is_stored_as_literal_text(tmp_db_dir):
    """参数化查询：注入串只会被当作普通文本，绝不执行 SQL。"""
    store = make_store(tmp_db_dir)
    nasty = "'; DELETE FROM free_task_events; --"
    store.append_event("sess-inj3", nasty, start_payload())
    events = store.list_events("sess-inj3")
    assert len(events) == 1
    assert events[0]["event_id"] == nasty
    # 表仍然健在
    store.append_event("sess-inj3-2", "ok-1", start_payload())
    assert len(store.list_events("sess-inj3-2")) == 1


def test_event_id_with_control_characters_is_rejected(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.append_event("sess-inj4", "evt\x00bad", start_payload())
    assert excinfo.value.code == "event_id_invalid"


# ---------------------------------------------------------------------------
# 11) 并发 / 锁
# ---------------------------------------------------------------------------

def test_concurrent_appends_keep_all_events(tmp_db_dir):
    store = make_store(tmp_db_dir)
    errors = []

    def worker(index: int) -> None:
        try:
            local = FreeTaskEventStore(store.db_path)
            local.append_event(
                f"sess-c{index}", f"c-{index}-1",
                start_payload(activity=f"活动 {index}"),
            )
        except Exception as exc:  # pragma: no cover - 失败即记录
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    total = sum(len(store.list_events(f"sess-c{i}")) for i in range(8))
    assert total == 8


def test_concurrent_same_event_id_yields_single_row(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-race", "race-1", start_payload())
    outcomes = []

    def worker() -> None:
        try:
            local = FreeTaskEventStore(store.db_path)
            res = local.append_event("sess-race", "race-1", start_payload())
            outcomes.append(("ok", res["duplicate"]))
        except FreeTaskEventError as exc:
            outcomes.append(("err", exc.code))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(store.list_events("sess-race")) == 1
    # 要么幂等成功，要么明确冲突 / 锁忙；绝不产生第二行
    for kind, payload in outcomes:
        if kind == "ok":
            assert payload is True
        else:
            assert payload in ("event_conflict", "db_busy")


def test_busy_timeout_is_reported_as_db_busy(tmp_db_dir):
    store = make_store(tmp_db_dir, "busy.sqlite3")
    store.busy_timeout_ms = 100
    blocker = sqlite3.connect(store.db_path, isolation_level=None)
    try:
        blocker.execute("BEGIN EXCLUSIVE")
        with pytest.raises(FreeTaskEventError) as excinfo:
            store.append_event("sess-lock", "lock-1", start_payload())
        assert excinfo.value.code == "db_busy"
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


# ---------------------------------------------------------------------------
# 12) summary 语义：用户自报，而非客观验证
# ---------------------------------------------------------------------------

def test_summary_declares_user_reported_not_verified(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-sum", "sum-1", start_payload())
    store.append_event("sess-sum", "sum-2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "reported_study_minutes": 25,
        "occurred_at": TS2,
    })
    summary = store.get_summary("sess-sum")
    assert summary["completion_source"] == "explicit_user_report"
    assert summary["verification"] == "user_reported_not_independently_verified"
    assert "用户自报" in summary["note"]


def test_summary_json_serialisable(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-j", "j-1", start_payload())
    summary = store.get_summary("sess-j")
    dumped = json.loads(json.dumps(summary, ensure_ascii=False))
    assert dumped["session_id"] == "sess-j"


def test_summary_rejects_bad_session_id(tmp_db_dir):
    store = make_store(tmp_db_dir)
    with pytest.raises(FreeTaskEventError) as excinfo:
        store.get_summary("")
    assert excinfo.value.code == "session_id_required"


def test_only_sqlite_files_are_created_in_synthetic_dir(tmp_db_dir):
    store = make_store(tmp_db_dir)
    store.append_event("sess-files", "fl-1", start_payload())
    names = sorted(p.name for p in tmp_db_dir.iterdir())
    assert all(name.startswith("synthetic_events.sqlite3") for name in names)
    assert os.path.exists(store.db_path)
