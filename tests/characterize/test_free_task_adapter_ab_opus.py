"""自由任务 **synthetic 适配层** (free_task_adapter_ab_opus) 的合成单元测试。

范围（LT_MODEL_AB_B_20261022_B，第 2 轮 A/B 工程评价）：

  A. 适配器形状契约
     - 只接受注入的 store；``None`` / 缺方法 → 拒绝
     - ``append`` 真实追加 + 返回同结构结果
     - ``summary`` 只读返回同结构结果
     - 多余参数（额外键）失败 **且不写库**
     - 非法 action / 缺失键 / 非字符串 ID / 布尔 ID / 非 dict payload 全部拒绝
     - 底层 ``FreeTaskEventError`` 的 code **不被吞并**（原样传播）
     - ``event_id`` 幂等由底层保证，且 **不伪造事件**（行数不增）
     - 娱乐完成 **不** 增加已学分钟；流逝分钟 **不** 变成已学分钟
     - summary 是原样透传（引用同一来源字段集合）

  B. 沙箱路径校验
     - root 内全新 ``.db`` 路径允许通过，且 **不创建任何文件**
     - 越界（绝对 / ``..`` / 等于 root / root 本身）拒绝
     - root 不存在 / 不是目录 / 是链接 → 拒绝
     - 文件链接 / 目录链接 / junction 作为中转 → 拒绝
     - 硬链接目标（``st_nlink > 1``）→ 拒绝
     - ``task_publisher.db`` / ``-wal`` / ``-shm``（大小写变体）→ 拒绝
     - 生产 ``data/`` 目录 → 拒绝

平台说明
--------
创建符号链接在 Windows 上需要权限（开发者模式 / 管理员）。无权限时
相关用例 **必须** 明确 ``skip``，绝不伪称通过。

本文件是 **纯合成** 测试：所有 SQLite 与被测路径都建在
``tempfile.TemporaryDirectory()`` 里；绝不触碰 ``data/task_publisher.db``、
``config/config.json``、``src/notes/**``，不 import Flask、不启动真实服务。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_adapter_ab_opus import (  # noqa: E402
    APPEND_ALLOWED_KEYS,
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
# 辅助：synthetic 账本 / 请求 / 测试替身
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


def completion_payload(actual_minutes=25, reported=25):
    payload = {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": actual_minutes,
        "occurred_at": TS2,
    }
    if reported is not None:
        payload["reported_study_minutes"] = reported
    return payload


@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_adapter_") as temp:
        yield Path(temp)


def make_store(root: Path, name: str = "synthetic_events.sqlite3") -> FreeTaskEventStore:
    return FreeTaskEventStore(str(Path(root) / name))


def make_adapter(root: Path, name: str = "synthetic_events.sqlite3") -> FreeTaskAdapter:
    return FreeTaskAdapter(make_store(root, name))


class CountingStore:
    """测试替身：只记录调用，不触碰任何数据库。"""

    def __init__(self) -> None:
        self.append_calls = []
        self.summary_calls = []

    def append_event(self, session_id, event_id, event_payload):
        self.append_calls.append((session_id, event_id, event_payload))
        return {"stored": True, "duplicate": False}

    def get_summary(self, session_id):
        self.summary_calls.append(session_id)
        return {"session_id": session_id, "successful_tasks": 0}


class ExplodingStore:
    """测试替身：底层错误必须原样传播（不被吞并 / 不被包装）。"""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def append_event(self, session_id, event_id, event_payload):
        raise self._error

    def get_summary(self, session_id):  # pragma: no cover - 不应被触达
        raise AssertionError("append 失败后不得读取 summary")


# ---------------------------------------------------------------------------
# A. 注入契约：绝不隐式创建或连接数据库
# ---------------------------------------------------------------------------

def test_store_must_be_injected():
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(None)
    assert excinfo.value.code == "adapter_store_required"


def test_injected_store_must_expose_the_ledger_protocol():
    class NotAStore:
        pass

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(NotAStore())
    assert excinfo.value.code == "adapter_store_invalid"


def test_adapter_exposes_the_injected_store_without_replacing_it(sandbox):
    store = make_store(sandbox)
    adapter = FreeTaskAdapter(store)
    assert adapter.store is store


def test_adapter_construction_creates_nothing_beyond_the_injected_store(sandbox):
    """适配层自身不落任何文件：构造前后目录内容完全一致。

    注意：``FreeTaskEventStore`` 构造函数本就会按底层设计创建 schema 文件，
    那是注入方（store）的既有行为，不是适配层的副作用。因此这里比较的是
    “store 就绪之后 → 构造适配器之后 / dispatch 之后”的目录快照。
    """
    store = make_store(sandbox)
    baseline = sorted(p.name for p in sandbox.iterdir())
    assert "synthetic_events.sqlite3" in baseline  # 来自底层 store，非适配层

    adapter = FreeTaskAdapter(store)
    assert sorted(p.name for p in sandbox.iterdir()) == baseline

    adapter.dispatch({
        "action": "append",
        "session_id": "sess-nf",
        "event_id": "nf-1",
        "event_payload": start_payload(),
    })
    after = sorted(p.name for p in sandbox.iterdir())
    assert set(after) <= set(baseline) | {"synthetic_events.sqlite3-wal",
                                          "synthetic_events.sqlite3-shm"}
    assert not any(
        name.endswith(".json") or name.startswith("task_publisher") for name in after
    )


# ---------------------------------------------------------------------------
# B. append：真实写入 + 结果结构
# ---------------------------------------------------------------------------

def test_append_returns_expected_structure_and_persists(sandbox):
    adapter = make_adapter(sandbox)
    result = adapter.dispatch({
        "action": "append",
        "session_id": "sess-1",
        "event_id": "evt-1",
        "event_payload": start_payload(),
    })

    assert result["ok"] is True
    assert result["action"] == "append"
    assert set(result) == {"ok", "action", "summary"}
    assert isinstance(result["summary"], dict)

    store = adapter.store
    events = store.list_events("sess-1")
    assert len(events) == 1
    assert events[0]["event_id"] == "evt-1"
    assert events[0]["event_type"] == domain.EVENT_STARTED
    assert events[0]["activity"] == "复习线性代数"
    assert events[0]["category"] == domain.CATEGORY_STUDY


def test_summary_action_returns_same_shape(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-2",
        "event_id": "evt-a",
        "event_payload": start_payload(),
    })

    result = adapter.dispatch({"action": "summary", "session_id": "sess-2"})
    assert result["ok"] is True
    assert result["action"] == "summary"
    assert set(result) == {"ok", "action", "summary"}
    assert result["summary"]["event_count"] == 1
    assert result["summary"]["successful_tasks"] == 0


def test_summary_passthrough_matches_ledger_verbatim(sandbox):
    """summary 是原样透传：不复制、不新增、不折算。"""
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-p",
        "event_id": "p-1",
        "event_payload": start_payload(),
    })
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-p",
        "event_id": "p-2",
        "event_payload": completion_payload(actual_minutes=25, reported=25),
    })

    result = adapter.dispatch({"action": "summary", "session_id": "sess-p"})
    ledger = adapter.store.get_summary("sess-p")
    assert result["summary"] == ledger
    assert result["summary"]["effective_study_minutes"] == 25
    assert result["summary"]["verification"] == "user_reported_not_independently_verified"


def test_summary_on_unknown_session_does_not_write(sandbox):
    adapter = make_adapter(sandbox)
    before = sorted(p.name for p in sandbox.iterdir())
    result = adapter.dispatch({"action": "summary", "session_id": "never-seen"})
    assert result["summary"]["event_count"] == 0
    assert result["summary"]["successful_tasks"] == 0
    assert adapter.store.list_events("never-seen") == []


# ---------------------------------------------------------------------------
# C. 幂等：由底层保证，本层不伪造事件
# ---------------------------------------------------------------------------

def test_duplicate_event_id_is_idempotent_via_ledger(sandbox):
    adapter = make_adapter(sandbox)
    request = {
        "action": "append",
        "session_id": "sess-dup",
        "event_id": "evt-dup",
        "event_payload": start_payload(),
    }
    first = adapter.dispatch(dict(request))
    second = adapter.dispatch(dict(request))

    assert first["ok"] is True and second["ok"] is True
    events = adapter.store.list_events("sess-dup")
    assert len(events) == 1                      # 没有伪造第二条事件
    assert first["summary"]["event_count"] == second["summary"]["event_count"] == 1


def test_completion_double_click_counts_once(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-dc",
        "event_id": "dc-1",
        "event_payload": start_payload(),
    })
    done = {
        "action": "append",
        "session_id": "sess-dc",
        "event_id": "dc-2",
        "event_payload": completion_payload(actual_minutes=25, reported=25),
    }
    adapter.dispatch(dict(done))
    again = adapter.dispatch(dict(done))

    summary = again["summary"]
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25
    assert len(adapter.store.list_events("sess-dc")) == 2


# ---------------------------------------------------------------------------
# D. 娱乐不增加已学分钟；流逝分钟不冒充已学分钟
# ---------------------------------------------------------------------------

def test_entertainment_completion_adds_no_study_minutes(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-e",
        "event_id": "e-1",
        "event_payload": start_payload(
            activity="打游戏", category="娱乐", minutes=55
        ),
    })
    result = adapter.dispatch({
        "action": "append",
        "session_id": "sess-e",
        "event_id": "e-2",
        # 即便调用方谎报学习分钟，娱乐会话也不得产生已学分钟
        "event_payload": completion_payload(actual_minutes=55, reported=40),
    })

    summary = result["summary"]
    assert summary["successful_tasks"] == 1
    assert summary["entertainment_completions"] == 1
    assert summary["study_completions"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0


def test_timer_elapsed_minutes_are_not_study_minutes(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-t",
        "event_id": "t-1",
        "event_payload": start_payload(minutes=25),
    })
    result = adapter.dispatch({
        "action": "append",
        "session_id": "sess-t",
        "event_id": "t-2",
        "event_payload": {
            "event_type": domain.EVENT_TIMER_ELAPSED,
            "actual_minutes": 25,
            "occurred_at": TS1,
        },
    })

    summary = result["summary"]
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0
    assert summary["timer_elapsed_events"] == 1
    assert summary["auto_completed"] is False


# ---------------------------------------------------------------------------
# E. 拒绝面：额外参数 / 非法输入 → 拒绝且绝不写入
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "extra_key, extra_value",
    [
        ("force", True),
        ("study_minutes", 999),
        ("note", "绕过校验"),
        ("db_path", "data/task_publisher.db"),
    ],
)
def test_append_with_extra_keys_is_rejected_without_writing(
    sandbox, extra_key, extra_value
):
    adapter = make_adapter(sandbox)
    request = {
        "action": "append",
        "session_id": "sess-x",
        "event_id": "x-1",
        "event_payload": start_payload(),
        extra_key: extra_value,
    }
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch(request)
    assert excinfo.value.code == "adapter_request_unknown_field"

    assert adapter.store.list_events("sess-x") == []
    assert adapter.store.get_summary("sess-x")["event_count"] == 0


def test_summary_with_extra_keys_is_rejected_without_writing(sandbox):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({
            "action": "summary",
            "session_id": "sess-y",
            "event_id": "y-1",
        })
    assert excinfo.value.code == "adapter_request_unknown_field"
    assert adapter.store.list_events("sess-y") == []


@pytest.mark.parametrize(
    "bad_action",
    ["delete", "reset", "APPEND", "", "  ", "summary; DROP TABLE x", 7, True, None],
)
def test_unsupported_or_invalid_actions_are_rejected(sandbox, bad_action):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({"action": bad_action, "session_id": "sess-a"})
    assert excinfo.value.code in ("adapter_action_invalid", "adapter_action_required")
    assert adapter.store.list_events("sess-a") == []


def test_missing_action_is_rejected(sandbox):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({"session_id": "sess-a"})
    assert excinfo.value.code == "adapter_action_required"


def test_request_must_be_a_dict(sandbox):
    adapter = make_adapter(sandbox)
    for bad in (None, ["append"], "append", 42, True):
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            adapter.dispatch(bad)
        assert excinfo.value.code == "adapter_request_invalid"


@pytest.mark.parametrize("bad_id", ["", "   ", None, 123, 1.5, True, False, b"x", ["s"]])
def test_invalid_session_id_is_rejected_without_writing(sandbox, bad_id):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({"action": "summary", "session_id": bad_id})
    assert excinfo.value.code in (
        "adapter_session_id_invalid",
        "adapter_session_id_required",
    )
    assert adapter.store.list_events("sess-ok") == []


@pytest.mark.parametrize("bad_id", ["", "  ", None, 5, True, False, {"id": 1}])
def test_invalid_event_id_is_rejected_without_writing(sandbox, bad_id):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({
            "action": "append",
            "session_id": "sess-b",
            "event_id": bad_id,
            "event_payload": start_payload(),
        })
    assert excinfo.value.code in (
        "adapter_event_id_invalid",
        "adapter_event_id_required",
    )
    assert adapter.store.list_events("sess-b") == []


@pytest.mark.parametrize("bad_payload", [None, [], "x", 7, True, ("a",)])
def test_non_dict_event_payload_is_rejected_without_writing(sandbox, bad_payload):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({
            "action": "append",
            "session_id": "sess-c",
            "event_id": "c-1",
            "event_payload": bad_payload,
        })
    assert excinfo.value.code == "adapter_event_payload_invalid"
    assert adapter.store.list_events("sess-c") == []


def test_missing_event_payload_key_is_rejected(sandbox):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({
            "action": "append",
            "session_id": "sess-d",
            "event_id": "d-1",
        })
    assert excinfo.value.code == "adapter_event_payload_required"
    assert adapter.store.list_events("sess-d") == []


def test_rejection_happens_before_any_store_call():
    """形状校验必须在调用 store 之前完成（调用计数为 0）。"""
    spy = CountingStore()
    adapter = FreeTaskAdapter(spy)
    for request in (
        {"action": "append", "session_id": "s", "event_id": "e", "extra": 1},
        {"action": "nope", "session_id": "s"},
        {"action": "append", "session_id": "", "event_id": "e",
         "event_payload": {}},
    ):
        with pytest.raises(FreeTaskAdapterError):
            adapter.dispatch(request)
    assert spy.append_calls == []
    assert spy.summary_calls == []


# ---------------------------------------------------------------------------
# F. 底层错误 code 不被吞并
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ledger_code",
    [
        "event_conflict",
        "session_not_started",
        "illegal_state_order",
        "study_minutes_required",
        "event_type_invalid",
        "payload_unknown_field",
        "duplicate_completion",
    ],
)
def test_ledger_error_codes_propagate_unchanged(ledger_code):
    error = FreeTaskEventError(ledger_code, "底层裁决")
    adapter = FreeTaskAdapter(ExplodingStore(error))

    with pytest.raises(FreeTaskEventError) as excinfo:
        adapter.dispatch({
            "action": "append",
            "session_id": "s",
            "event_id": "e",
            "event_payload": start_payload(),
        })

    assert excinfo.value.code == ledger_code          # 原样保留，未被吞并
    assert excinfo.value is error                     # 未被包装成新异常
    assert not isinstance(excinfo.value, FreeTaskAdapterError)


def test_real_conflict_from_ledger_surfaces_its_own_code(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-k",
        "event_id": "k-1",
        "event_payload": start_payload(),
    })
    with pytest.raises(FreeTaskEventError) as excinfo:
        adapter.dispatch({
            "action": "append",
            "session_id": "sess-k",
            "event_id": "k-1",
            "event_payload": start_payload(activity="换了活动"),
        })
    assert excinfo.value.code == "event_conflict"
    assert len(adapter.store.list_events("sess-k")) == 1


# ---------------------------------------------------------------------------
# G. 沙箱路径校验：可用路径
# ---------------------------------------------------------------------------

def test_fresh_db_path_inside_sandbox_is_accepted_and_creates_nothing(sandbox):
    candidate = sandbox / "fresh_events.db"
    resolved = validate_synthetic_db_path(candidate, sandbox)

    assert os.path.isabs(resolved)
    assert os.path.normcase(resolved).startswith(
        os.path.normcase(str(sandbox))
    ) and os.path.normcase(resolved) != os.path.normcase(str(sandbox))
    assert not candidate.exists()                       # 只验证，不创建
    assert sorted(p.name for p in sandbox.iterdir()) == []


def test_relative_candidate_is_joined_to_sandbox_root(sandbox):
    resolved = validate_synthetic_db_path("nested/dir/ok.db", sandbox)
    assert os.path.isfile(os.path.dirname(resolved)) is False   # 仍然不创建
    assert resolved == os.path.abspath(str(sandbox / "nested" / "dir" / "ok.db"))


def test_string_arguments_are_accepted(sandbox):
    resolved = validate_synthetic_db_path(str(sandbox / "plain.db"), str(sandbox))
    assert os.path.isabs(resolved)


def test_accepted_path_can_actually_host_a_synthetic_store(sandbox):
    """验证通过后，路径确实可用于 synthetic 账本（接线前的正向闭环）。"""
    resolved = validate_synthetic_db_path(sandbox / "usable.db", sandbox)
    store = FreeTaskEventStore(resolved)
    store.append_event("sess-u", "u-1", start_payload())
    assert len(store.list_events("sess-u")) == 1
    assert store.get_summary("sess-u")["event_count"] == 1


# ---------------------------------------------------------------------------
# H. 沙箱路径校验：越界 / 缺根 / 生产库
# ---------------------------------------------------------------------------

def test_root_itself_is_rejected(sandbox):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(sandbox, sandbox)
    assert excinfo.value.code == "adapter_db_path_outside_sandbox"


def test_absolute_path_outside_sandbox_is_rejected(sandbox):
    with TemporaryDirectory(prefix="lt_ft_outside_") as other:
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(Path(other) / "evil.db", sandbox)
        assert excinfo.value.code == "adapter_db_path_outside_sandbox"


@pytest.mark.parametrize(
    "candidate", ["../escape.db", "sub/../../escape.db", "..\\escape.db"]
)
def test_parent_traversal_is_rejected(sandbox, candidate):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(candidate, sandbox)
    assert excinfo.value.code == "adapter_db_path_escape"


def test_missing_sandbox_root_is_rejected(sandbox):
    ghost = sandbox / "no_such_dir"
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(ghost / "x.db", ghost)
    assert excinfo.value.code == "adapter_sandbox_root_missing"


def test_sandbox_root_that_is_a_file_is_rejected(sandbox):
    target = sandbox / "not_a_dir"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(target / "x.db", target)
    assert excinfo.value.code == "adapter_sandbox_root_missing"


@pytest.mark.parametrize("bad_root", [None, "", "   ", 7, True])
def test_invalid_sandbox_root_types_are_rejected(sandbox, bad_root):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(sandbox / "x.db", bad_root)
    assert excinfo.value.code == "adapter_sandbox_root_invalid"


@pytest.mark.parametrize("bad_candidate", [None, "", "   ", 7, True, b"bytes"])
def test_invalid_candidate_types_are_rejected(sandbox, bad_candidate):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(bad_candidate, sandbox)
    assert excinfo.value.code == "adapter_db_path_invalid"


@pytest.mark.parametrize(
    "name",
    [
        "task_publisher.db",
        "task_publisher.db-wal",
        "task_publisher.db-shm",
        "Task_Publisher.DB",
        "TASK_PUBLISHER.DB-WAL",
        "Task_Publisher.Db-Shm",
    ],
)
def test_production_db_basenames_are_rejected(sandbox, name):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(sandbox / name, sandbox)
    assert excinfo.value.code == "adapter_db_path_forbidden"
    assert not (sandbox / name).exists()      # 拒绝时不得创建


def test_project_production_data_dir_is_refused_without_io(sandbox):
    """生产 data/ 目录必须被拒绝；本用例只做字符串比较，不遍历目录。"""
    real_data = PROJECT_ROOT / "data"
    if not real_data.is_dir():  # pragma: no cover - 项目结构异常
        pytest.skip("项目 data/ 目录不存在")
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(
            PROJECT_ROOT / "data" / "synthetic_probe.db", sandbox
        )
    assert excinfo.value.code in (
        "adapter_db_path_outside_sandbox",
        "adapter_db_path_forbidden",
    )
    assert not (PROJECT_ROOT / "data" / "synthetic_probe.db").exists()


def test_existing_directory_target_is_rejected(sandbox):
    target = sandbox / "already_dir"
    target.mkdir()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(target, sandbox)
    assert excinfo.value.code == "adapter_db_path_is_directory"


# ---------------------------------------------------------------------------
# I. 硬链接目标 → 拒绝
# ---------------------------------------------------------------------------

def test_existing_hardlinked_target_is_rejected(sandbox):
    original = sandbox / "original.db"
    original.write_bytes(b"synthetic")
    alias = sandbox / "alias.db"
    try:
        os.link(str(original), str(alias))
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"本平台/文件系统无法创建硬链接: {exc}")

    assert os.lstat(str(original)).st_nlink > 1
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(alias, sandbox)
    assert excinfo.value.code == "adapter_db_path_hardlinked"


def test_single_link_existing_file_is_allowed(sandbox):
    """对照组：``st_nlink == 1`` 的普通文件不应被硬链接规则误伤。"""
    target = sandbox / "normal.db"
    target.write_bytes(b"synthetic")
    if os.lstat(str(target)).st_nlink != 1:  # pragma: no cover - 极端文件系统
        pytest.skip("文件系统报告了非预期的链接计数")
    resolved = validate_synthetic_db_path(target, sandbox)
    assert os.path.normcase(resolved) == os.path.normcase(str(target.resolve()))


# ---------------------------------------------------------------------------
# J. 符号链接 / junction 中转 → 拒绝（无权限时明确 skip）
# ---------------------------------------------------------------------------

def _skip_reason(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def test_file_symlink_target_is_rejected(sandbox):
    """目标本身是指向别处的文件链接 → 拒绝。"""
    real_file = sandbox / "real.db"
    real_file.write_bytes(b"synthetic")
    link = sandbox / "link.db"
    try:
        os.symlink(str(real_file), str(link))
    except (OSError, NotImplementedError, AttributeError) as exc:
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in (1, 1314):
            pytest.skip("Windows 未授予创建符号链接的权限（需开发者模式/管理员）")
        pytest.skip("无法创建符号链接: " + _skip_reason(exc))

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(link, sandbox)
    assert excinfo.value.code in (
        "adapter_db_path_link_intermediate",
        "adapter_db_path_unverifiable",
    )


def test_file_symlink_intermediate_directory_is_rejected(sandbox):
    """链接目录作为中转（``sandbox/linkdir/x.db``）→ 拒绝。"""
    outside = sandbox / "outside"
    outside.mkdir()
    link_dir = sandbox / "linkdir"
    try:
        os.symlink(str(outside), str(link_dir), target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError) as exc:
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in (1, 1314):
            pytest.skip("Windows 未授予创建符号链接的权限（需开发者模式/管理员）")
        pytest.skip("无法创建目录符号链接: " + _skip_reason(exc))

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(link_dir / "x.db", sandbox)
    assert excinfo.value.code == "adapter_db_path_link_intermediate"
    assert not (outside / "x.db").exists()


def test_sandbox_root_being_a_symlink_is_rejected(sandbox):
    real_root = sandbox / "real_root"
    real_root.mkdir()
    link_root = sandbox / "link_root"
    try:
        os.symlink(str(real_root), str(link_root), target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError) as exc:
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in (1, 1314):
            pytest.skip("Windows 未授予创建符号链接的权限（需开发者模式/管理员）")
        pytest.skip("无法创建目录符号链接: " + _skip_reason(exc))

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(link_root / "x.db", link_root)
    assert excinfo.value.code == "adapter_sandbox_root_not_real"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction 专属用例")
def test_junction_intermediate_directory_is_rejected(sandbox):
    """Windows junction（reparse point）中转 → 拒绝。

    ``mklink /J`` 不需要管理员权限，可在普通权限下创建；因此这里用
    ``cmd`` 创建 junction，并要求失败时必须明确 skip。
    """
    import subprocess

    outside = sandbox / "junction_target"
    outside.mkdir()
    link_dir = sandbox / "junction_link"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_dir), str(outside)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.skip("无法创建 junction（mklink /J 失败）: " + proc.stderr.strip())

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(link_dir / "x.db", sandbox)
    assert excinfo.value.code == "adapter_db_path_link_intermediate"
    assert not (outside / "x.db").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction 专属用例")
def test_sandbox_root_being_a_junction_is_rejected(sandbox):
    import subprocess

    real_root = sandbox / "jreal"
    real_root.mkdir()
    link_root = sandbox / "jlink"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_root), str(real_root)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.skip("无法创建 junction（mklink /J 失败）: " + proc.stderr.strip())

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(link_root / "x.db", link_root)
    assert excinfo.value.code == "adapter_sandbox_root_not_real"


# ---------------------------------------------------------------------------
# K. 契约常量自检 + 适配层不触碰生产路径
# ---------------------------------------------------------------------------

def test_allowed_key_constants_are_exact():
    assert APPEND_ALLOWED_KEYS == frozenset(
        {"action", "session_id", "event_id", "event_payload"}
    )
    from server.services.free_task_adapter_ab_opus import (
        SUMMARY_ALLOWED_KEYS,
        SUPPORTED_ACTIONS,
    )

    assert SUMMARY_ALLOWED_KEYS == frozenset({"action", "session_id"})
    assert set(SUPPORTED_ACTIONS) == {"append", "summary"}


def test_adapter_never_touches_project_data_dir(sandbox, monkeypatch):
    """在临时目录跑完整会话，项目 data/ 不得被写入任何东西。"""
    monkeypatch.chdir(sandbox)
    data_dir = PROJECT_ROOT / "data"
    before = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []

    adapter = make_adapter(sandbox, "no_project_data.db")
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-n",
        "event_id": "n-1",
        "event_payload": start_payload(),
    })
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-n",
        "event_id": "n-2",
        "event_payload": completion_payload(actual_minutes=25, reported=25),
    })
    adapter.dispatch({"action": "summary", "session_id": "sess-n"})

    after = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []
    assert before == after