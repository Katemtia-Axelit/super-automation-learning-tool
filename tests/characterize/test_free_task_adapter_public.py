"""``server.services.free_task_adapter`` 稳定公共入口的合成刻画测试。

范围（LT_RETENTION_FREE_TASK_FACTORY_SYNTH_20261022_D）：

  A. 稳定公共导入接口
     - 三个必须显式提供的名字存在且可用；
     - ``__all__`` 精确，且与实现体一致；
     - **源实现唯一**：公共入口对象 **就是** opus 实现体的同一对象
       （不是副本、不是子类、不是包装）；
     - 绝不 import Astra 原型（已知 junction 绕过缺陷）。

  B. 无隐式建库 / 无生产接线
     - 导入本模块不创建任何文件（项目 ``data/`` 目录不变）；
     - 适配器只接受注入的 store，``None`` / 缺方法 → 拒绝；
     - 构造适配器本身不落任何额外文件；
     - 拒绝路径在任何账本调用之前发生（spy 调用计数为 0）。

  C. 基本校验与底层事件错误码透传
     - append / summary 正常形状；
     - 多余字段、缺失 / 空白 ID、非 dict payload → 适配层 code；
     - 底层 ``FreeTaskEventError`` 的 code 原样传播、不被吞并。

  D. 安全路径复验
     - sandbox 内新路径通过且 **不创建任何文件**；
     - 越界 / ``..`` / 等于 root / 生产库文件名 → 拒绝；
     - 硬链接别名 → 拒绝；
     - Windows junction 作为中转 → 拒绝（无权限时明确 ``skip``）。

平台说明
--------
创建符号链接在 Windows 上需要权限（开发者模式 / 管理员），``mklink /J``
通常不需要。权限不足时相关用例 **必须** 明确 ``skip``，绝不伪称通过。

本文件是 **纯合成** 测试：所有 SQLite 与被测路径都建在
``tempfile.TemporaryDirectory()`` 里；绝不触碰 ``data/task_publisher.db``、
``config/config.json``、``src/notes/**``，不 import Flask、不启动真实服务。
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import free_task_adapter as public  # noqa: E402
from server.services.free_task_adapter import (  # noqa: E402
    APPEND_ALLOWED_KEYS,
    SUMMARY_ALLOWED_KEYS,
    SUPPORTED_ACTIONS,
    FreeTaskAdapter,
    FreeTaskAdapterError,
    validate_synthetic_db_path,
)
from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_events import (  # noqa: E402
    FreeTaskEventError,
    FreeTaskEventStore,
)

TS0 = "2026-10-22T09:00:00Z"
TS1 = "2026-10-22T09:10:00Z"
TS2 = "2026-10-22T09:25:00Z"


# ---------------------------------------------------------------------------
# 辅助
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
    return {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": actual_minutes,
        "occurred_at": TS2,
        "reported_study_minutes": reported,
    }


@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_adapter_public_") as temp:
        yield Path(temp)


def make_adapter(root: Path, name: str = "synthetic_events.sqlite3") -> FreeTaskAdapter:
    return FreeTaskAdapter(FreeTaskEventStore(str(Path(root) / name)))


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
# A. 稳定公共导入接口
# ---------------------------------------------------------------------------

def test_three_required_public_names_are_importable():
    """必须显式提供：FreeTaskAdapter / FreeTaskAdapterError /
    validate_synthetic_db_path。"""
    assert callable(public.FreeTaskAdapter)
    assert issubclass(public.FreeTaskAdapterError, Exception)
    assert callable(public.validate_synthetic_db_path)
    for name in ("FreeTaskAdapter", "FreeTaskAdapterError", "validate_synthetic_db_path"):
        assert name in public.__all__, f"{name} 必须出现在 __all__ 中"


def test_dunder_all_is_exact():
    assert set(public.__all__) == {
        "APPEND_ALLOWED_KEYS",
        "FORBIDDEN_DB_BASENAMES",
        "SUMMARY_ALLOWED_KEYS",
        "SUPPORTED_ACTIONS",
        "FreeTaskAdapter",
        "FreeTaskAdapterError",
        "implementation",
        "validate_synthetic_db_path",
    }


def _module_imports(module) -> set:
    """模块 **真实代码** 里 import 的模块名集合（AST 精确，不受文档串干扰）。

    相对 import（level>0）会被还原成相对包名的短名，因此
    ``from .free_task_adapter_ab_opus import ...`` 记录为
    ``free_task_adapter_ab_opus``。
    """
    module_dir = Path(module.__file__).resolve().parent
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            tail = (node.module or "").split(".")[-1] if node.module else ""
            if node.level:
                if tail:
                    names.add(tail)
            elif node.module:
                names.add(node.module.split(".")[0])
    assert module_dir.name            # 保留：确认路径解析可用
    return names


def test_source_implementation_is_unique_not_a_copy():
    """公共入口必须 **就是** 已验收实现体的同一对象（不是副本 / 子类）。"""
    impl = public.implementation
    assert impl is not None
    assert public.FreeTaskAdapter is impl.FreeTaskAdapter
    assert public.FreeTaskAdapterError is impl.FreeTaskAdapterError
    assert public.validate_synthetic_db_path is impl.validate_synthetic_db_path
    assert public.APPEND_ALLOWED_KEYS is impl.APPEND_ALLOWED_KEYS

    # 公共入口自己的源码体必须非常薄：模块层 **不定义** 任何 class/def，
    # 只有导入与转发（AST 精确，不受文档字符串措辞干扰）。
    tree = ast.parse(Path(public.__file__).read_text(encoding="utf-8"))
    defined = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    ]
    assert defined == ["__getattr__"] if defined else True
    assert "FreeTaskAdapter" not in defined
    assert "validate_synthetic_db_path" not in defined


def test_adapter_module_never_depends_on_the_astra_prototype():
    """Astra 原型存在已知 Windows 内部 junction 绕过缺陷，不得被依赖。

    注意：``sys.modules`` 可能因 **其它** 测试文件而含有 Astra，所以这里只
    断言本公共入口的真实 import 关系。
    """
    imports = _module_imports(public)
    assert "free_task_adapter_ab_astra" not in imports
    assert "free_task_adapter_ab_opus" in imports   # 唯一实现体是已复验的 opus


def test_contract_constants_match_the_implementation():
    assert APPEND_ALLOWED_KEYS == frozenset(
        {"action", "session_id", "event_id", "event_payload"}
    )
    assert SUMMARY_ALLOWED_KEYS == frozenset({"action", "session_id"})
    assert set(SUPPORTED_ACTIONS) == {"append", "summary"}


def test_public_entry_imports_no_framework_no_db_no_wiring():
    """公共入口 **不** import Flask / sqlite3，也不 import 任何生产装配模块。"""
    imports = _module_imports(public)
    for forbidden in (
        "flask",
        "sqlite3",
        "app_factory",
        "backend_api",
        "free_task_adapter_ab_astra",
    ):
        assert forbidden not in imports, f"公共入口不得 import {forbidden}"
    # 不读配置、不建库：模块里没有 load_config / create_app 等符号引用。
    assert not hasattr(public, "load_config")
    assert not hasattr(public, "create_app")


def test_adapter_has_no_db_path_parameter_and_no_implicit_database():
    """``FreeTaskAdapter`` 只能注入 store：没有 db_path、没有默认路径。"""
    signature = inspect.signature(FreeTaskAdapter.__init__)
    params = [p for p in signature.parameters if p != "self"]
    assert params == ["store"]
    assert signature.parameters["store"].default is inspect.Parameter.empty


# ---------------------------------------------------------------------------
# B. 不隐式建库 / 只接受注入
# ---------------------------------------------------------------------------

def test_importing_public_entry_creates_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = PROJECT_ROOT / "data"
    before = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []
    module = importlib.import_module("server.services.free_task_adapter")
    assert module is public
    after = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []
    assert before == after
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_store_must_be_injected_and_protocol_checked():
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(None)
    assert excinfo.value.code == "adapter_store_required"

    class NotAStore:
        pass

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        FreeTaskAdapter(NotAStore())
    assert excinfo.value.code == "adapter_store_invalid"


def test_adapter_exposes_injected_store_without_replacing_it(sandbox):
    store = FreeTaskEventStore(str(sandbox / "synthetic_events.sqlite3"))
    adapter = FreeTaskAdapter(store)
    assert adapter.store is store


def test_adapter_construction_creates_no_extra_files(sandbox):
    store = FreeTaskEventStore(str(sandbox / "synthetic_events.sqlite3"))
    baseline = set(os.listdir(sandbox))
    adapter = FreeTaskAdapter(store)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-nf",
        "event_id": "nf-1",
        "event_payload": start_payload(),
    })
    after = set(os.listdir(sandbox))
    assert after <= baseline | {
        "synthetic_events.sqlite3-wal",
        "synthetic_events.sqlite3-shm",
    }
    assert not any(n.endswith(".json") or n.startswith("task_publisher") for n in after)


def test_rejection_happens_before_any_store_call():
    spy = CountingStore()
    adapter = FreeTaskAdapter(spy)
    for request in (
        {"action": "append", "session_id": "s", "event_id": "e", "extra": 1},
        {"action": "nope", "session_id": "s"},
        {"action": "append", "session_id": "  ", "event_id": "e",
         "event_payload": {}},
        {"action": "append", "session_id": "s", "event_id": "e",
         "event_payload": []},
    ):
        with pytest.raises(FreeTaskAdapterError):
            adapter.dispatch(request)
    assert spy.append_calls == []
    assert spy.summary_calls == []


# ---------------------------------------------------------------------------
# C. 基本校验 + 底层错误码透传
# ---------------------------------------------------------------------------

def test_append_and_summary_round_trip(sandbox):
    adapter = make_adapter(sandbox)
    appended = adapter.dispatch({
        "action": "append",
        "session_id": "sess-1",
        "event_id": "evt-1",
        "event_payload": start_payload(),
    })
    assert appended["ok"] is True
    assert set(appended) == {"ok", "action", "summary"}
    assert appended["summary"]["event_count"] == 1
    assert appended["summary"]["successful_tasks"] == 0

    summarized = adapter.dispatch({"action": "summary", "session_id": "sess-1"})
    assert summarized["summary"] == adapter.store.get_summary("sess-1")
    assert summarized["summary"]["verification"] == "user_reported_not_independently_verified"


def test_entertainment_completion_adds_no_study_minutes(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-e",
        "event_id": "e-1",
        "event_payload": start_payload(activity="打游戏", category="娱乐", minutes=55),
    })
    result = adapter.dispatch({
        "action": "append",
        "session_id": "sess-e",
        "event_id": "e-2",
        "event_payload": completion_payload(actual_minutes=55, reported=40),
    })
    summary = result["summary"]
    assert summary["successful_tasks"] == 1
    assert summary["entertainment_completions"] == 1
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0


def test_timer_elapsed_is_not_completion(sandbox):
    adapter = make_adapter(sandbox)
    adapter.dispatch({
        "action": "append",
        "session_id": "sess-t",
        "event_id": "t-1",
        "event_payload": start_payload(),
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
    assert summary["timer_elapsed_events"] == 1
    assert summary["auto_completed"] is False


@pytest.mark.parametrize(
    "extra_key, extra_value",
    [("force", True), ("study_minutes", 999), ("db_path", "data/task_publisher.db")],
)
def test_extra_keys_are_rejected_without_writing(sandbox, extra_key, extra_value):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({
            "action": "append",
            "session_id": "sess-x",
            "event_id": "x-1",
            "event_payload": start_payload(),
            extra_key: extra_value,
        })
    assert excinfo.value.code == "adapter_request_unknown_field"
    assert adapter.store.list_events("sess-x") == []


@pytest.mark.parametrize("bad_id", ["", "   ", None, 7, True, False, ["s"]])
def test_blank_or_non_string_ids_are_rejected_without_writing(sandbox, bad_id):
    adapter = make_adapter(sandbox)
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        adapter.dispatch({"action": "summary", "session_id": bad_id})
    assert excinfo.value.code in (
        "adapter_session_id_invalid",
        "adapter_session_id_required",
    )

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


@pytest.mark.parametrize("bad_payload", [None, [], "x", 7, True])
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
    assert excinfo.value.code == ledger_code          # 原样保留
    assert excinfo.value is error                     # 未被包装成新异常
    assert not isinstance(excinfo.value, FreeTaskAdapterError)


def test_real_conflict_from_ledger_surfaces_event_conflict(sandbox):
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
# D. 安全路径复验（symlink / junction / hardlink）
# ---------------------------------------------------------------------------

def _skip_reason(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def test_fresh_path_inside_sandbox_is_accepted_and_creates_nothing(sandbox):
    candidate = sandbox / "fresh_events.db"
    resolved = validate_synthetic_db_path(candidate, sandbox)
    assert os.path.isabs(resolved)
    assert not candidate.exists()
    assert sorted(p.name for p in sandbox.iterdir()) == []


def test_accepted_path_can_host_a_synthetic_store(sandbox):
    resolved = validate_synthetic_db_path(sandbox / "usable.db", sandbox)
    store = FreeTaskEventStore(resolved)
    store.append_event("sess-u", "u-1", start_payload())
    assert len(store.list_events("sess-u")) == 1


def test_root_itself_and_parent_traversal_are_rejected(sandbox):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(sandbox, sandbox)
    assert excinfo.value.code == "adapter_db_path_outside_sandbox"

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path("../escape.db", sandbox)
    assert excinfo.value.code == "adapter_db_path_escape"


def test_absolute_path_outside_sandbox_is_rejected(sandbox):
    with TemporaryDirectory(prefix="lt_ft_public_outside_") as other:
        with pytest.raises(FreeTaskAdapterError) as excinfo:
            validate_synthetic_db_path(Path(other) / "evil.db", sandbox)
        assert excinfo.value.code == "adapter_db_path_outside_sandbox"


@pytest.mark.parametrize(
    "name",
    ["task_publisher.db", "Task_Publisher.DB-WAL", "Task_Publisher.Db-Shm"],
)
def test_production_db_basenames_are_rejected(sandbox, name):
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(sandbox / name, sandbox)
    assert excinfo.value.code == "adapter_db_path_forbidden"
    assert not (sandbox / name).exists()


def test_existing_directory_target_is_rejected(sandbox):
    target = sandbox / "already_dir"
    target.mkdir()
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(target, sandbox)
    assert excinfo.value.code == "adapter_db_path_is_directory"


def test_existing_hardlinked_target_is_rejected(sandbox):
    original = sandbox / "original.db"
    original.write_bytes(b"synthetic")
    alias = sandbox / "alias.db"
    try:
        os.link(str(original), str(alias))
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"本平台/文件系统无法创建硬链接: {_skip_reason(exc)}")

    assert os.lstat(str(original)).st_nlink > 1
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(alias, sandbox)
    assert excinfo.value.code == "adapter_db_path_hardlinked"


def test_single_link_existing_file_is_allowed(sandbox):
    target = sandbox / "normal.db"
    target.write_bytes(b"synthetic")
    if os.lstat(str(target)).st_nlink != 1:  # pragma: no cover - 极端文件系统
        pytest.skip("文件系统报告了非预期的链接计数")
    resolved = validate_synthetic_db_path(target, sandbox)
    assert os.path.normcase(resolved) == os.path.normcase(str(target.resolve()))


def test_file_symlink_target_is_rejected_or_skipped(sandbox):
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


@pytest.mark.skipif(os.name != "nt", reason="Windows junction 专属用例")
def test_junction_intermediate_directory_is_rejected(sandbox):
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
def test_junction_deep_inside_sandbox_is_rejected(sandbox):
    """回归 LT_MODEL_AB_B_20261022_B：junction 作为 **内部** 中转也必须被拒。

    Astra 原型正是漏掉了内部 junction，导致 realpath 解析到别处仍放行；
    这里用 opus 实现体复验该场景。
    """
    outside = sandbox / "inside_junction_target"
    outside.mkdir()
    middle = sandbox / "level1"
    middle.mkdir()
    link_dir = middle / "junction_link"          # 位于 sandbox **内部**
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


def test_project_data_dir_is_refused_without_creating_anything(sandbox):
    real_data = PROJECT_ROOT / "data"
    if not real_data.is_dir():  # pragma: no cover - 项目结构异常
        pytest.skip("项目 data/ 目录不存在")
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        validate_synthetic_db_path(
            real_data / "synthetic_probe_public.db", sandbox
        )
    assert excinfo.value.code in (
        "adapter_db_path_outside_sandbox",
        "adapter_db_path_forbidden",
    )
    assert not (real_data / "synthetic_probe_public.db").exists()