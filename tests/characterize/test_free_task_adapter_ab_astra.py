"""``free_task_adapter_ab_astra`` 的合成特征测试（TASK LT-MODEL-AB-A）。

范围
----
1. ``dispatch`` 的 append / summary 主路径：
   - append 真实落库、返回 ``{'ok','action','summary'}`` 三键结构；
   - summary 只读、返回同结构且 ``action='summary'``；
   - summary 的来源就是注入的 store（mock/double 证据）。
2. 入参闸门 fail-closed：额外键、缺失键、非字符串 ID、``bool`` ID、
   非 dict payload、未知 action → 一律拒绝且 **不产生任何写入**。
3. 底层 ``FreeTaskEventError`` 的 ``code`` **不被吞并**。
4. 幂等完全来自底层：同一 ``event_id`` 重复 append 只产生一行，
   适配层不伪造、不重放事件。
5. 娱乐完成 **不增加学习分钟**；流逝分钟不冒充已学分钟。
6. ``validate_synthetic_db_path``：只验证不创建、可用路径通过、
   越界 / ``..`` / root 本身 / 生产库名 / 符号链接 / junction /
   目录链接 / 硬链接 / 缺 root 一律拒绝。
7. Windows 无权限创建 symlink 时 **明确 skip**，绝不伪称通过。

本文件是 **纯合成** 测试：所有 SQLite 都建在
``tempfile.TemporaryDirectory()`` 里，路径校验只发生在临时目录；
绝不触碰 ``data/task_publisher.db``、``config/config.json``、
``src/notes/**``，不 import Flask、不启动真实服务、不连接生产数据库。
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_adapter_ab_astra import (  # noqa: E402
    FreeTaskAdapter,
    FreeTaskAdapterError,
    validate_synthetic_db_path,
)
from server.services.free_task_events import (  # noqa: E402
    FreeTaskEventError,
    FreeTaskEventStore,
)

TS0 = "2026-10-22T09:00:00Z"
TS1 = "2026-10-22T09:10:00Z"
TS2 = "2026-10-22T09:25:00Z"


# ---------------------------------------------------------------------------
# 辅助：payload / store / double
# ---------------------------------------------------------------------------

def start_payload(activity="复习线性代数", category="学习", minutes=25):
    return {
        "event_type": domain.EVENT_STARTED,
        "activity": activity,
        "category": category,
        "planned_minutes": minutes,
        "occurred_at": TS0,
        "reason": domain.DEFAULT_FREE_TASK_REASON,
    }


def completion_payload(reported=25, elapsed=25):
    return {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": elapsed,
        "reported_study_minutes": reported,
        "occurred_at": TS2,
    }


def make_store(root: Path, name="synthetic_ab_astra.sqlite3") -> FreeTaskEventStore:
    return FreeTaskEventStore(str(Path(root) / name))


class RecordingStore:
    """极简 double：记录调用，**不接触任何真实数据库**。

    用于证明“校验失败发生在触碰 store 之前”。
    """

    def __init__(self, summary=None, raises=None):
        self.append_calls = []
        self.summary_calls = []
        self._summary = summary if summary is not None else {"successful_tasks": 0}
        self._raises = raises

    def append_event(self, session_id, event_id, event_payload):
        self.append_calls.append((session_id, event_id, event_payload))
        if self._raises is not None:
            raise self._raises
        return {"stored": True, "duplicate": False}

    def get_summary(self, session_id):
        self.summary_calls.append(session_id)
        if self._raises is not None:
            raise self._raises
        return self._summary


@pytest.fixture()
def tmp_root():
    with TemporaryDirectory(prefix="lt_adapter_ab_astra_") as temp:
        yield Path(temp)


def count_rows(store: FreeTaskEventStore, session_id: str) -> int:
    conn = sqlite3.connect(store.db_path)
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM free_task_events WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1) append / summary 主路径
# ---------------------------------------------------------------------------

def test_append_returns_exact_envelope_with_summary(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)

    result = adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-1",
            "event_id": "ab-evt-1",
            "event_payload": start_payload(),
        }
    )

    assert set(result) == {"ok", "action", "summary"}
    assert result["ok"] is True
    assert result["action"] == "append"
    assert isinstance(result["summary"], dict)
    # summary 是底层 store 的原样结果（不重新推导）
    assert result["summary"] == store.get_summary("ab-sess-1")
    assert result["summary"]["session_id"] == "ab-sess-1"
    assert result["summary"]["event_count"] == 1
    assert result["summary"]["verification"] == "user_reported_not_independently_verified"
    assert count_rows(store, "ab-sess-1") == 1


def test_summary_action_returns_same_envelope_and_writes_nothing(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-2",
            "event_id": "ab-evt-2a",
            "event_payload": start_payload(),
        }
    )
    before = count_rows(store, "ab-sess-2")

    result = adapter.dispatch({"action": "summary", "session_id": "ab-sess-2"})

    assert set(result) == {"ok", "action", "summary"}
    assert result["ok"] is True
    assert result["action"] == "summary"
    assert result["summary"] == store.get_summary("ab-sess-2")
    assert count_rows(store, "ab-sess-2") == before


def test_summary_of_unknown_session_is_zero_not_error(tmp_root):
    store = make_store(tmp_root)
    result = FreeTaskAdapter(store).dispatch(
        {"action": "summary", "session_id": "never-seen"}
    )
    assert result["summary"]["event_count"] == 0
    assert result["summary"]["successful_tasks"] == 0
    assert result["summary"]["effective_study_minutes"] == 0


def test_adapter_requires_injected_store_and_never_builds_one():
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(None)
    assert excinfo.value.code == "store_required"

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(object())
    assert excinfo.value.code == "store_invalid"


def test_adapter_exposes_injected_store_untouched(tmp_root):
    store = make_store(tmp_root)
    assert FreeTaskAdapter(store).store is store


def test_summary_comes_from_injected_double():
    """mock/double 证据：summary 确实来自注入的 store，不是自造。"""
    double = RecordingStore(summary={"successful_tasks": 7, "marker": "double"})
    result = FreeTaskAdapter(double).dispatch(
        {"action": "summary", "session_id": "ab-sess-d"}
    )
    assert result["summary"] == {"successful_tasks": 7, "marker": "double"}
    assert double.append_calls == []
    assert double.summary_calls == ["ab-sess-d"]


# ---------------------------------------------------------------------------
# 2) 入参闸门：拒绝且不产生写入
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "request_obj, expected_code",
    [
        # 额外键
        (
            {
                "action": "append",
                "session_id": "s",
                "event_id": "e",
                "event_payload": {},
                "force": True,
            },
            "unexpected_key",
        ),
        (
            {
                "action": "append",
                "session_id": "s",
                "event_id": "e",
                "event_payload": {},
                "db_path": "data/task_publisher.db",
            },
            "unexpected_key",
        ),
        (
            {"action": "summary", "session_id": "s", "event_id": "e"},
            "unexpected_key",
        ),
        (
            {"action": "summary", "session_id": "s", "event_payload": {}},
            "unexpected_key",
        ),
        # 缺失键
        (
            {"action": "append", "session_id": "s", "event_id": "e"},
            "field_required",
        ),
        (
            {"action": "append", "session_id": "s", "event_payload": {}},
            "field_required",
        ),
        (
            {"action": "summary"},
            "field_required",
        ),
        # 未知 / 非法 action
        ({"action": "delete", "session_id": "s"}, "action_unsupported"),
        ({"action": "update", "session_id": "s"}, "action_unsupported"),
        ({"session_id": "s"}, "action_unsupported"),
        ({"action": True, "session_id": "s"}, "action_unsupported"),
        ({"action": "", "session_id": "s"}, "action_unsupported"),
        ({"action": 5, "session_id": "s"}, "action_unsupported"),
        # 请求本身不是 dict
        ("not-a-dict", "request_invalid"),
        (None, "request_invalid"),
        (["append"], "request_invalid"),
    ],
)
def test_bad_requests_are_rejected_without_touching_store(request_obj, expected_code):
    double = RecordingStore()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(double).dispatch(request_obj)
    assert excinfo.value.code == expected_code
    assert double.append_calls == []
    assert double.summary_calls == []


@pytest.mark.parametrize(
    "request_obj, expected_code",
    [
        (
            {"action": "summary", "session_id": ""},
            "session_id_required",
        ),
        (
            {"action": "summary", "session_id": "   "},
            "session_id_required",
        ),
        (
            {"action": "summary", "session_id": None},
            "session_id_required",
        ),
        (
            {"action": "summary", "session_id": 42},
            "session_id_required",
        ),
        (
            {"action": "summary", "session_id": True},
            "session_id_required",
        ),
        (
            {"action": "summary", "session_id": ["s"]},
            "session_id_required",
        ),
    ],
)
def test_non_string_session_ids_are_rejected(request_obj, expected_code):
    double = RecordingStore()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(double).dispatch(request_obj)
    assert excinfo.value.code == expected_code
    assert double.append_calls == [] and double.summary_calls == []


@pytest.mark.parametrize(
    "session_id, event_id, event_payload, expected_field",
    [
        ("s", "", start_payload(), "event_id_required"),
        ("s", None, start_payload(), "event_id_required"),
        ("s", 7, start_payload(), "event_id_required"),
        ("s", False, start_payload(), "event_id_required"),
        ("s", "  ", start_payload(), "event_id_required"),
        ("", "e", start_payload(), "session_id_required"),
        (True, "e", start_payload(), "session_id_required"),
        ("s", "e", None, "event_payload_invalid"),
        ("s", "e", [], "event_payload_invalid"),
        ("s", "e", "payload", "event_payload_invalid"),
        ("s", "e", True, "event_payload_invalid"),
    ],
)
def test_append_field_validation_rejects_bad_values(
    session_id, event_id, event_payload, expected_field
):
    double = RecordingStore()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(double).dispatch(
            {
                "action": "append",
                "session_id": session_id,
                "event_id": event_id,
                "event_payload": event_payload,
            }
        )
    assert excinfo.value.code == expected_field
    assert double.append_calls == [] and double.summary_calls == []


def test_rejected_request_creates_no_event_rows(tmp_root):
    """真实库视角：非法请求不留下任何事件行。"""
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)

    with pytest.raises(FreeTaskAdapterError):
        adapter.dispatch(
            {
                "action": "append",
                "session_id": "ab-sess-x",
                "event_id": "ab-evt-x",
                "event_payload": start_payload(),
                "is_admin": True,
            }
        )
    assert count_rows(store, "ab-sess-x") == 0
    assert store.get_summary("ab-sess-x")["event_count"] == 0


# ---------------------------------------------------------------------------
# 3) 底层 code 不被吞并
# ---------------------------------------------------------------------------

def test_underlying_event_error_code_is_propagated_unchanged(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)

    # 先落一个 started 事件，使会话进入 running 状态
    adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-3",
            "event_id": "ab-evt-3a",
            "event_payload": start_payload(),
        }
    )
    # 学习会话的完成事件缺少用户报告分钟 → 底层 study_minutes_required
    with pytest.raises(FreeTaskEventError) as excinfo:
        adapter.dispatch(
            {
                "action": "append",
                "session_id": "ab-sess-3",
                "event_id": "ab-evt-3b",
                "event_payload": {
                    "event_type": domain.EVENT_COMPLETED,
                    "actual_minutes": 25,
                    "occurred_at": TS2,
                },
            }
        )
    # 底层 code 原样抛出，未被改写成适配层 code
    assert excinfo.value.code == "study_minutes_required"
    assert isinstance(excinfo.value, FreeTaskEventError)
    assert not isinstance(excinfo.value, FreeTaskAdapterError)
    # 失败的事件没有落库
    assert count_rows(store, "ab-sess-3") == 1
    assert store.get_summary("ab-sess-3")["successful_tasks"] == 0


def test_underlying_error_code_is_never_rewritten_to_adapter_error(tmp_root):
    double = RecordingStore(raises=FreeTaskEventError("event_conflict", "底层冲突"))
    with pytest.raises(FreeTaskEventError) as excinfo:
        FreeTaskAdapter(double).dispatch(
            {
                "action": "append",
                "session_id": "s",
                "event_id": "e",
                "event_payload": start_payload(),
            }
        )
    assert excinfo.value.code == "event_conflict"


def test_payload_domain_errors_keep_their_own_codes(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    with pytest.raises(FreeTaskEventError) as excinfo:
        adapter.dispatch(
            {
                "action": "append",
                "session_id": "ab-sess-4",
                "event_id": "ab-evt-4a",
                "event_payload": {
                    "event_type": domain.EVENT_STARTED,
                    "activity": "x",
                    "category": "睡觉",
                    "planned_minutes": 25,
                    "occurred_at": TS0,
                },
            }
        )
    assert excinfo.value.code == "category_invalid"


# ---------------------------------------------------------------------------
# 4) 幂等来自底层，不伪造事件
# ---------------------------------------------------------------------------

def test_same_event_id_is_idempotent_via_underlying_store(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    request = {
        "action": "append",
        "session_id": "ab-sess-5",
        "event_id": "ab-evt-5a",
        "event_payload": start_payload(),
    }
    first = adapter.dispatch(dict(request))
    second = adapter.dispatch(dict(request))

    assert count_rows(store, "ab-sess-5") == 1
    assert first["summary"] == second["summary"]
    assert second["summary"]["event_count"] == 1


def test_conflicting_payload_for_same_event_id_keeps_event_conflict(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    base = {
        "action": "append",
        "session_id": "ab-sess-6",
        "event_id": "ab-evt-6a",
    }
    adapter.dispatch({**base, "event_payload": start_payload()})
    with pytest.raises(FreeTaskEventError) as excinfo:
        adapter.dispatch({**base, "event_payload": start_payload(activity="别的活动")})
    assert excinfo.value.code == "event_conflict"
    assert count_rows(store, "ab-sess-6") == 1


def test_adapter_never_invents_event_ids(tmp_root):
    """适配层不得补默认 event_id：缺失即拒绝。"""
    store = make_store(tmp_root)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(store).dispatch(
            {
                "action": "append",
                "session_id": "ab-sess-7",
                "event_payload": start_payload(),
            }
        )
    assert excinfo.value.code == "field_required"
    assert count_rows(store, "ab-sess-7") == 0


# ---------------------------------------------------------------------------
# 5) 娱乐不增加学习分钟；流逝分钟不冒充已学分钟
# ---------------------------------------------------------------------------

def test_entertainment_completion_adds_no_study_minutes(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-8",
            "event_id": "ab-evt-8a",
            "event_payload": start_payload(
                activity="打游戏", category="娱乐", minutes=55
            ),
        }
    )
    # 即便调用方谎报 40 分钟学习，娱乐会话也不得折算
    result = adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-8",
            "event_id": "ab-evt-8b",
            "event_payload": completion_payload(reported=40, elapsed=55),
        }
    )
    summary = result["summary"]
    assert summary["successful_tasks"] == 1
    assert summary["entertainment_completions"] == 1
    assert summary["study_completions"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0


def test_timer_elapsed_never_counts_as_learned_minutes(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-9",
            "event_id": "ab-evt-9a",
            "event_payload": start_payload(minutes=25),
        }
    )
    result = adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-9",
            "event_id": "ab-evt-9b",
            "event_payload": {
                "event_type": domain.EVENT_TIMER_ELAPSED,
                "actual_minutes": 25,
                "occurred_at": TS1,
            },
        }
    )
    summary = result["summary"]
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["timer_elapsed_events"] == 1
    assert summary["auto_completed"] is False
    assert summary["completion_source"] == "explicit_user_report"


def test_study_completion_summary_is_pure_passthrough(tmp_root):
    store = make_store(tmp_root)
    adapter = FreeTaskAdapter(store)
    adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-10",
            "event_id": "ab-evt-10a",
            "event_payload": start_payload(minutes=25),
        }
    )
    result = adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-10",
            "event_id": "ab-evt-10b",
            "event_payload": completion_payload(reported=30, elapsed=25),
        }
    )
    summary = result["summary"]
    assert summary == store.get_summary("ab-sess-10")
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 30


# ---------------------------------------------------------------------------
# 6) validate_synthetic_db_path：可用路径
# ---------------------------------------------------------------------------

def test_fresh_db_path_inside_sandbox_is_allowed(tmp_root):
    resolved = validate_synthetic_db_path(
        str(tmp_root / "new_synthetic.db"), str(tmp_root)
    )
    assert os.path.isabs(resolved)
    assert os.path.normcase(os.path.dirname(resolved)) == os.path.normcase(
        os.path.realpath(str(tmp_root))
    )
    assert os.path.basename(resolved).lower().endswith(".db")


def test_relative_candidate_is_resolved_under_root(tmp_root):
    resolved = validate_synthetic_db_path("sub/new.sqlite3", str(tmp_root))
    assert os.path.normcase(resolved) == os.path.normcase(
        os.path.realpath(str(tmp_root / "sub" / "new.sqlite3"))
    )


def test_existing_regular_single_link_file_is_allowed(tmp_root):
    target = tmp_root / "existing.sqlite3"
    target.write_bytes(b"")
    resolved = validate_synthetic_db_path(str(target), str(tmp_root))
    assert os.path.normcase(resolved) == os.path.normcase(os.path.realpath(str(target)))


def test_validation_creates_nothing_on_disk(tmp_root):
    before = sorted(p.name for p in tmp_root.iterdir())
    validate_synthetic_db_path(str(tmp_root / "never_created.db"), str(tmp_root))
    validate_synthetic_db_path("nested/deep/also_never.db", str(tmp_root))
    after = sorted(p.name for p in tmp_root.iterdir())
    assert before == after
    assert not (tmp_root / "never_created.db").exists()


def test_trailing_separator_on_root_is_tolerated(tmp_root):
    resolved = validate_synthetic_db_path(
        str(tmp_root / "ok.db"), str(tmp_root) + os.sep
    )
    assert os.path.basename(resolved) == "ok.db"


# ---------------------------------------------------------------------------
# 7) validate_synthetic_db_path：拒绝
# ---------------------------------------------------------------------------

def test_missing_or_non_directory_root_is_rejected(tmp_root):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(tmp_root / "a.db"), str(tmp_root / "no_such_dir"))
    assert excinfo.value.code == "root_missing"

    plain_file = tmp_root / "plain.txt"
    plain_file.write_text("x", encoding="utf-8")
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(tmp_root / "a.db"), str(plain_file))
    assert excinfo.value.code == "root_missing"

    for bad_root in ("", "   ", None, 7):
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(str(tmp_root / "a.db"), bad_root)
        assert excinfo.value.code == "root_required"


def test_candidate_equal_to_root_is_rejected(tmp_root):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(tmp_root), str(tmp_root))
    assert excinfo.value.code == "candidate_is_root"


def test_dotdot_escape_is_rejected_without_normalisation(tmp_root):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path("../escaped.db", str(tmp_root))
    assert excinfo.value.code == "path_escape"

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(tmp_root / ".." / "escaped.db"), str(tmp_root))
    assert excinfo.value.code == "path_escape"


def test_absolute_path_outside_root_is_rejected(tmp_root):
    with TemporaryDirectory(prefix="lt_adapter_ab_astra_out_") as outside:
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(
                os.path.join(outside, "foreign.db"), str(tmp_root)
            )
        assert excinfo.value.code == "path_escape"


def test_traversal_that_would_still_land_inside_is_still_rejected(tmp_root):
    """`a/../b.db` 归一化后仍在 root 内，但 `..` 一律拒绝（不猜测）。"""
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path("nested/../b.db", str(tmp_root))
    assert excinfo.value.code == "path_escape"


def test_sibling_directory_prefix_is_not_inside_root(tmp_root):
    """`/tmp/x_sandbox_evil` 不是 `/tmp/x_sandbox` 的子目录（前缀陷阱）。"""
    parent = tmp_root
    root = parent / "sandbox"
    root.mkdir()
    sibling = parent / "sandbox_evil"
    sibling.mkdir()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(sibling / "x.db"), str(root))
    assert excinfo.value.code == "path_escape"


@pytest.mark.parametrize(
    "name",
    [
        "task_publisher.db",
        "TASK_PUBLISHER.DB",
        "Task_Publisher.Db",
        "task_publisher.db-wal",
        "task_publisher.db-shm",
        "TASK_PUBLISHER.DB-WAL",
        "task_publisher.DB-Shm",
    ],
)
def test_production_database_names_are_rejected(tmp_root, name):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(tmp_root / name), str(tmp_root))
    assert excinfo.value.code == "production_db_name"


def test_production_data_dir_is_rejected(tmp_root):
    data_dir = PROJECT_ROOT / "data"
    assert data_dir.is_dir()  # 只读检查目录存在，不读取任何文件
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(
            str(data_dir / "anything_synthetic.db"), str(data_dir)
        )
    assert excinfo.value.code == "production_data_dir"


def test_existing_directory_candidate_is_rejected(tmp_root):
    sub = tmp_root / "sub"
    sub.mkdir()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(sub), str(tmp_root))
    assert excinfo.value.code == "candidate_is_directory"


def test_non_directory_path_middle_segment_is_rejected(tmp_root):
    blocker = tmp_root / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(blocker / "under.db"), str(tmp_root))
    assert excinfo.value.code == "path_contains_file"


def test_blank_candidate_is_rejected(tmp_root):
    for bad in ("", "   ", None, 42):
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(bad, str(tmp_root))
        assert excinfo.value.code == "candidate_required"


# ---------------------------------------------------------------------------
# 8) 硬链接
# ---------------------------------------------------------------------------

def test_existing_hard_link_alias_is_rejected(tmp_root):
    target = tmp_root / "hardlinked.db"
    target.write_bytes(b"payload")
    # 建立别名之前：普通单链接文件 → 通过
    assert validate_synthetic_db_path(str(target), str(tmp_root))

    alias = tmp_root / "alias.db"
    try:
        os.link(str(target), str(alias))
    except (OSError, NotImplementedError) as exc:  # pragma: no cover
        pytest.skip(f"当前平台不支持创建硬链接: {exc}")

    st = os.stat(str(alias))
    if getattr(st, "st_nlink", 1) <= 1:  # pragma: no cover - 异常文件系统
        pytest.skip("文件系统未报告 st_nlink > 1，无法构造硬链接别名")

    # 别名 → 拒绝（存在硬链接别名）
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(alias), str(tmp_root))
    assert excinfo.value.code == "hard_link_alias"

    # 原始路径同样被拒：os.stat 跟随链接，两条路径的 st_nlink 都是 2。
    # 这正是契约要的行为 —— 目标文件已存在硬链接别名即视为不可靠。
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(str(target), str(tmp_root))
    assert excinfo.value.code == "hard_link_alias"


def test_single_link_file_passes_after_alias_is_removed(tmp_root):
    target = tmp_root / "solo.db"
    target.write_bytes(b"payload")
    alias = tmp_root / "solo_alias.db"
    try:
        os.link(str(target), str(alias))
    except (OSError, NotImplementedError) as exc:  # pragma: no cover
        pytest.skip(f"当前平台不支持创建硬链接: {exc}")
    alias.unlink()

    st = os.stat(str(target))
    if getattr(st, "st_nlink", 1) != 1:  # pragma: no cover - 异常文件系统
        pytest.skip("文件系统未在删除别名后恢复 st_nlink == 1")

    assert validate_synthetic_db_path(str(target), str(tmp_root))


# ---------------------------------------------------------------------------
# 9) 符号链接 / junction / 目录链接
# ---------------------------------------------------------------------------

IS_WINDOWS = os.name == "nt"


def _can_symlink(base: Path, link: Path, target_is_dir: bool) -> bool:
    """真实探测当前进程是否有权限创建符号链接 / junction。"""
    try:
        if target_is_dir:
            os.symlink(str(base), str(link), target_is_directory=True)
        else:
            os.symlink(str(base), str(link))
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


def test_symlinked_target_inside_sandbox_is_rejected(tmp_root):
    real_dir = tmp_root / "real_target"
    real_dir.mkdir()
    real_file = real_dir / "target.db"
    real_file.write_bytes(b"")
    link_file = tmp_root / "linked_file.db"
    if not _can_symlink(real_file, link_file, target_is_dir=False):
        pytest.skip("当前平台/权限不允许创建文件符号链接（Windows 需管理员或开发者模式）")
    try:
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(str(link_file), str(tmp_root))
        assert excinfo.value.code == "path_contains_link"
    finally:
        link_file.unlink()


def test_symlinked_directory_inside_sandbox_is_rejected(tmp_root):
    real_dir = tmp_root / "real_dir"
    real_dir.mkdir()
    link_dir = tmp_root / "link_dir"
    if not _can_symlink(real_dir, link_dir, target_is_dir=True):
        pytest.skip("当前平台/权限不允许创建目录符号链接")
    try:
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(str(link_dir / "under.db"), str(tmp_root))
        assert excinfo.value.code == "path_contains_link"
    finally:
        link_dir.unlink()


def test_symlink_pointing_outside_sandbox_is_rejected(tmp_root):
    """即使 realpath 归一化后**看起来**落在别处，也必须拒绝（不靠 realpath 猜）。"""
    with TemporaryDirectory(prefix="lt_adapter_ab_astra_tgt_") as outside:
        outside_file = Path(outside) / "outside.db"
        outside_file.write_bytes(b"")
        link = tmp_root / "escape.db"
        if not _can_symlink(outside_file, link, target_is_dir=False):
            pytest.skip("当前平台/权限不允许创建文件符号链接")
        try:
            with pytest.raises(FreeTaskAdapterError) as excinfo:
                validate_synthetic_db_path(str(link), str(tmp_root))
            assert excinfo.value.code == "path_contains_link"
        finally:
            link.unlink()


@pytest.mark.skipif(not IS_WINDOWS, reason="Windows junction 专属用例")
def test_windows_junction_resolves_to_real_target_inside_root(tmp_root):
    """经由 junction 指向 sandbox 内部的路径：realpath 后仍在 root 内 → 通过。

    文档化当前契约：契约只要求 **拒绝越界 / root 本身 / 根经由链接**，
    不要求拒绝指向 root 内部的链接路径（那会误伤合法写入）。
    """
    real_dir = tmp_root / "junction_target"
    real_dir.mkdir()
    junction = tmp_root / "junction_ok"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(real_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not junction.exists():
        pytest.skip(f"当前环境无法创建 junction（需要 NTFS 权限）: {result.stdout}{result.stderr}")
    try:
        resolved = validate_synthetic_db_path(str(junction / "synthetic.db"), str(tmp_root))
        assert os.path.normcase(resolved) == os.path.normcase(
            os.path.realpath(str(junction / "synthetic.db"))
        )
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)


@pytest.mark.skipif(not IS_WINDOWS, reason="Windows junction 专属用例")
def test_windows_junction_candidate_pointing_outside_is_rejected(tmp_root):
    """candidate 经由 junction 指向 sandbox **之外** → 越界，拒绝。"""
    with TemporaryDirectory(prefix="lt_adapter_ab_astra_out2_") as outside:
        outside_dir = Path(outside) / "target"
        outside_dir.mkdir()
        junction = tmp_root / "junction_escape"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not junction.exists():
            pytest.skip(f"当前环境无法创建 junction: {result.stdout}{result.stderr}")
        try:
            with pytest.raises(FreeTaskAdapterError) as excinfo:
                validate_synthetic_db_path(str(junction / "synthetic.db"), str(tmp_root))
            assert excinfo.value.code == "path_escape"
        finally:
            subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)


# ---------------------------------------------------------------------------
# 10) 端到端：store 路径必须先过闸门
# ---------------------------------------------------------------------------

def test_store_built_from_validated_synthetic_path_works(tmp_root):
    resolved = validate_synthetic_db_path(
        str(tmp_root / "end_to_end.db"), str(tmp_root)
    )
    adapter = FreeTaskAdapter(FreeTaskEventStore(resolved))
    result = adapter.dispatch(
        {
            "action": "append",
            "session_id": "ab-sess-e2e",
            "event_id": "ab-evt-e2e",
            "event_payload": start_payload(),
        }
    )
    assert result["ok"] is True
    assert result["summary"]["event_count"] == 1
    assert os.path.exists(resolved)