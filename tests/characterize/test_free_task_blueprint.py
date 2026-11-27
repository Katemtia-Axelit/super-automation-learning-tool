"""自由任务 **隔离预览 HTTP API** (``free_task_bp``) 的合成刻画测试。

范围（LT_RETENTION_FREE_TASK_FACTORY_SYNTH_20261022_D）：

  A. 隔离与工厂契约
     - 只用 ``Flask(__name__)`` 建立 **隔离** synthetic app 并 **手动**
       注册新 Blueprint；绝不 import / 调用真实 ``app_factory``；
     - store 由测试注入 ``TemporaryDirectory`` 内的
       ``FreeTaskEventStore``；
     - 工厂拒绝 ``None`` / 行为不完整的 store；
     - 路由前缀 ``/api/free-tasks``；生产 Factory **默认不装配** 自由任务
       （默认关闭 + 显式 opt-in 的新合同，详见 A.5 一节的修订说明）。

  B. POST /events 正例
     - started → completed 成功；响应形状 ``{ok, action, summary}``；
     - 娱乐完成 **不** 记有效学习分钟；``timer_elapsed`` **不** 算完成；
     - ``occurred_at`` 等字段形状以真实领域层为准。

  C. POST /events 反例
     - 非 JSON 内容类型 → 415 ``unsupported_media_type``；
     - 非法 JSON / 非对象 → 400 ``invalid_json`` / ``body_not_object``；
     - ``action`` 非 ``append`` → 400 ``action_not_append``；
     - 多余字段 → 400 ``adapter_request_unknown_field``（且不写库）；
     - 缺失 / 空白 ID → 400 ``adapter_*_required`` / ``adapter_*_invalid``；
     - 重复 ``event_id`` 幂等（事件数不增）；
     - ``event_conflict`` → 409；``session_not_started`` / 非法状态 → 409；
     - 缺失 payload 字段 → 400（**不隐式创建事件**）。

  D. GET summary
     - 只读、不写库；``verification`` 标注用户自报；
     - 未知会话返回 0 计数而不是 404；
     - 空白 / 非法会话 ID → 400。

  E. HTTP 语义
     - 未知路由 → 404；方法不允许 → 405；
     - 所有 **视图内** 失败响应都是 JSON 且带稳定 ``error.code``；
     - **默认（未 opt-in）** 匹配阶段的 404 / 405 只保证 **状态码**，
       body 仍是 werkzeug 默认 HTML —— 断言 JSON **不是** 契约；
     - **opt-in**（``register_free_task_preview_errors``）之后，preview 前缀
       下匹配阶段的 404 / 405 才是统一 JSON，且状态码不变；
     - opt-in 绝不波及非 preview 路径与其它 Blueprint。

本文件是 **纯合成** 测试：所有 SQLite 都建在
``tempfile.TemporaryDirectory()`` 里；绝不触碰 ``data/task_publisher.db``、
``config/config.json``、``src/notes/**``；不启动真实 Web 服务。
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

flask = pytest.importorskip("flask")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask  # noqa: E402

from server.blueprints.free_task_bp import (  # noqa: E402
    ALLOWED_POST_KEYS,
    PREVIEW_URL_PREFIX,
    REQUIRED_ACTION,
    create_free_task_blueprint,
    register_free_task_preview_errors,
)
from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_adapter import FreeTaskAdapterError  # noqa: E402
from server.services.free_task_events import FreeTaskEventStore  # noqa: E402

URL_PREFIX = "/api/free-tasks"

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


def post_body(session_id, event_id, payload):
    return {
        "action": REQUIRED_ACTION,
        "session_id": session_id,
        "event_id": event_id,
        "event_payload": payload,
    }


@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_bp_") as temp:
        yield Path(temp)


@pytest.fixture()
def store(sandbox):
    """注入的 synthetic 账本（临时目录，绝不是生产库）。"""
    return FreeTaskEventStore(str(sandbox / "synthetic_events.sqlite3"))


@pytest.fixture()
def client(store):
    """隔离的 synthetic app：``Flask(__name__)`` + 手动注册本 Blueprint。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    return app.test_client()


def post(client, body, content_type="application/json"):
    return client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        content_type=content_type,
    )


def get_summary(client, session_id):
    return client.get(f"{URL_PREFIX}/sessions/{session_id}/summary")


def start_session(client, session_id="sess-1", event_id="evt-1", **kwargs):
    response = post(client, post_body(session_id, event_id, start_payload(**kwargs)))
    assert response.status_code == 200, response.get_data(as_text=True)
    return response


def error_of(response):
    body = response.get_json()
    assert body is not None and isinstance(body, dict)
    assert body["ok"] is False
    error = body["error"]
    assert set(error) == {"code", "message"}
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    return error["code"]


# ---------------------------------------------------------------------------
# A. 隔离与工厂契约
# ---------------------------------------------------------------------------

def test_factory_requires_an_injected_store():
    with pytest.raises(FreeTaskAdapterError) as excinfo:
        create_free_task_blueprint(None)
    assert excinfo.value.code == "adapter_store_required"

    class NotAStore:
        pass

    with pytest.raises(FreeTaskAdapterError) as excinfo:
        create_free_task_blueprint(NotAStore())
    assert excinfo.value.code == "adapter_store_invalid"


def test_blueprint_uses_the_declared_url_prefix():
    class FakeStore:
        def append_event(self, session_id, event_id, event_payload):
            return {}

        def get_summary(self, session_id):
            return {}

    bp = create_free_task_blueprint(FakeStore())
    assert bp.url_prefix == URL_PREFIX
    assert bp.name == "free_task_preview"


def test_route_table_matches_contract(store):
    app = Flask(__name__)
    app.register_blueprint(create_free_task_blueprint(store))
    rules = {
        rule.endpoint: sorted(rule.methods - {"HEAD", "OPTIONS"})
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith(URL_PREFIX)
    }
    assert rules == {
        "free_task_preview.append_free_task_event": ["POST"],
        "free_task_preview.free_task_session_summary": ["GET"],
    }


def test_allowed_post_keys_and_action_are_declared_consistently():
    assert ALLOWED_POST_KEYS == frozenset(
        {"action", "session_id", "event_id", "event_payload"}
    )
    assert REQUIRED_ACTION == "append"


def test_free_task_preview_is_wired_only_by_explicit_factory_opt_in(
    sandbox, store, monkeypatch
):
    """自由任务接口 **只** 可能经由 Factory 的显式 opt-in 装配（默认关闭）。

    合同修订说明
    ------------
    本函数原先断言 ``"free_task_bp" not in text_factory``（对 Factory 源文本
    做 **字符串** 包含判断），那刻画的是“Factory **全面禁止** 装配自由任务”
    的旧合同。I 组（``LT_RETENTION_FACTORY_OPTIN_SYNTH_20261023_I``）引入的
    新合同是 **默认完全关闭 + 仅显式 opt-in 才装配受保护蓝图**，两者互斥，
    因此旧断言必须被替换 —— 而不是被删除。

    新合同的四条安全约束（本函数逐条静态 + 动态验证）：

    A. ``server.blueprints.free_task_bp`` **自身** 仍不得 import
       ``app_factory`` / ``backend_api`` / ``load_config`` / ``create_app``
       （反向依赖隔离，保留原 D 组约束）；
    B. 旧生产入口 ``server/backend_api.py`` 仍 **不装配** 自由任务接口
       —— 用 **AST** 检查真实 import / ``register_blueprint`` 调参，
       而不是查注释字符串；
    C. Factory 的 ``create_app`` 仍保有 **keyword-only** 的
       ``free_task_preview=None`` 默认参数，默认路径 **不** import /
       register 自由任务蓝图；仅在显式 opt-in 时 **延迟** import
       **受保护** 的 ``create_protected_free_task_blueprint``，
       **绝不** import/注册无认证的 ``create_free_task_blueprint``，
       且自由任务模块 **绝不** 在 Factory 模块顶层被 import；
    D. 动态证据（复用 I 组现有 synthetic fixture，**不** 自建真实配置、
       **不** 触发 ``create_app()`` 的 ``load_config()`` 默认读取）：
       默认 app 的 url_map 中没有任何 ``/api/free-tasks`` 路由，
       而 opt-in app 只出现 **受保护** 蓝图（未授权请求 401），
       无认证旧蓝图名始终缺席。

    正反可区分性：若新 Factory **默认开启** 自由任务，D 的默认 app 断言
    必然失败；若新 Factory **导入/注册无认证旧工厂**，C 的 import 名字
    断言与 D 的蓝图角色断言必然失败。本函数不会因“删掉断言”而变绿。
    """
    # -- A. 反向依赖隔离（保留原 D 组约束） ------------------------------
    source = sys.modules[create_free_task_blueprint.__module__].__file__
    tree = ast.parse(Path(source).read_text(encoding="utf-8"))
    imported: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for forbidden in ("app_factory", "backend_api", "load_config", "create_app"):
        assert not any(forbidden in name for name in imported), (
            f"不得 import 生产装配符号 {forbidden}"
        )

    # -- B. legacy 生产入口 backend_api.py 绝不装配自由任务（AST） --------
    backend_path = PROJECT_ROOT / "server" / "backend_api.py"
    backend_tree = ast.parse(backend_path.read_text(encoding="utf-8"))

    backend_modules: set = set()
    for node in ast.walk(backend_tree):
        if isinstance(node, ast.Import):
            backend_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            backend_modules.add(node.module)
    assert not any("free_task" in name for name in backend_modules), (
        f"backend_api 不得 import 自由任务模块：{sorted(backend_modules)}"
    )

    # 任何标识符（函数 / 变量 / 属性）都不得提到自由任务装配符号。
    backend_symbols = {
        node.id for node in ast.walk(backend_tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(backend_tree) if isinstance(node, ast.Attribute)
    }
    assert not any("free_task" in symbol for symbol in backend_symbols), (
        "backend_api 不得引用自由任务装配符号"
    )

    # 蓝图注册参数必须与自由任务无关。
    for node in ast.walk(backend_tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "register_blueprint":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Name):
                label = arg.id
            elif isinstance(arg, ast.Attribute):
                label = arg.attr
            else:
                continue
            assert "free_task" not in label.lower(), (
                f"backend_api 不得注册自由任务蓝图：{label}"
            )

    # 路由前缀字符串也不得出现（AST 常量，不是注释文本）。
    backend_constants = {
        node.value
        for node in ast.walk(backend_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any(value.startswith("/api/free-tasks") for value in backend_constants), (
        "backend_api 不得出现自由任务路由前缀"
    )

    # -- C. Factory 静态合同 ----------------------------------------------
    import inspect

    from server.app import app_factory as factory_module
    from server.app.app_factory import create_app as factory_create_app

    signature = inspect.signature(factory_create_app)
    preview_param = signature.parameters["free_task_preview"]
    assert preview_param.kind is inspect.Parameter.KEYWORD_ONLY
    assert preview_param.default is None
    assert [
        p.name
        for p in signature.parameters.values()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ] == ["config"]

    factory_tree = ast.parse(
        Path(factory_module.__file__).read_text(encoding="utf-8")
    )

    # C1. 自由任务模块绝不在 Factory 顶层被 import（默认路径不得加载它）。
    module_level_modules: set = set()
    for node in factory_tree.body:
        if isinstance(node, ast.Import):
            module_level_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_level_modules.add(node.module)
    assert not any("free_task" in name for name in module_level_modules), (
        f"Factory 顶层不得 import 自由任务模块：{sorted(module_level_modules)}"
    )

    # C2. 全文件里唯一的自由任务 import 只允许是“受保护工厂”的延迟 import。
    free_task_imports = [
        node
        for node in ast.walk(factory_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and "free_task" in node.module
    ]
    assert len(free_task_imports) == 1, [
        (node.module, [a.name for a in node.names]) for node in free_task_imports
    ]
    deferred = free_task_imports[0]
    assert deferred.module == "server.blueprints.free_task_bp"
    assert {alias.name for alias in deferred.names} == {
        "create_protected_free_task_blueprint"
    }, [alias.name for alias in deferred.names]

    # C3. 该延迟 import 必须位于 create_app 的条件分支内部。
    parents: dict = {}
    for parent in ast.walk(factory_tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    chain = []
    cursor = deferred
    while cursor in parents:
        cursor = parents[cursor]
        chain.append(cursor)
    assert any(isinstance(node, ast.If) for node in chain), (
        "自由任务 import 必须在条件分支内（默认路径不得触发）"
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "create_app"
        for node in chain
    ), "自由任务 import 必须发生在 create_app 内部"

    # C4. 无认证旧工厂在 Factory 中 **绝不** 被引用（导入或调用）。
    legacy_refs = {
        node.id
        for node in ast.walk(factory_tree)
        if isinstance(node, ast.Name) and node.id == "create_free_task_blueprint"
    } | {
        node.attr
        for node in ast.walk(factory_tree)
        if isinstance(node, ast.Attribute) and node.attr == "create_free_task_blueprint"
    } | {
        alias.name
        for node in ast.walk(factory_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == "create_free_task_blueprint"
    }
    assert not legacy_refs, "Factory 绝不允许引用无认证的旧自由任务工厂"

    # -- D. 动态证据（复用 I 组现有 synthetic fixture） --------------------
    import importlib.util

    i_group_path = (
        PROJECT_ROOT / "tests" / "characterize" / "test_free_task_factory_optin.py"
    )
    spec = importlib.util.spec_from_file_location(
        "lt_i_group_factory_optin", i_group_path
    )
    assert spec is not None and spec.loader is not None
    i_group = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(i_group)

    # AR03-P2 / Stage 7：兼容桥已从装配流程整体移除 —— 合成接缝
    # **零次** 被调用。替身保留以证明"没被调用"是真事实。
    #
    # AR03-P5：兼容桥文件已归档到 ``_archive/``（零路由 / 零副作用 /
    # 零运行时引用）。此时 **没有可替换的模块** —— 但断言的 **不变量**
    # （零次调用）依然成立，且更强：模块 **根本不存在**，不可能被调用。
    # 因此这里在归档后返回 **空列表**，并额外断言 ``server/**`` 无任何
    # 对它的引用，确保归档是安全的。
    legacy_calls: list = []

    def _legacy_recorder(app, config):
        legacy_calls.append(config.get("_db_path"))
        return 0

    try:
        monkeypatch.setattr(
            "server.app.legacy_compat.register_legacy_compat", _legacy_recorder
        )
    except (ImportError, AttributeError):
        # 已归档：模块不存在 → 不可能有调用。
        # 额外校验「server/** 无运行时引用」，确保归档是安全的。
        server_dir = PROJECT_ROOT / "server"
        offenders = []
        for path in server_dir.rglob("*.py"):
            if path.name == "legacy_compat.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.endswith("legacy_compat"):
                            offenders.append(path.name)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    if base.endswith("legacy_compat"):
                        offenders.append(path.name)
                    for alias in node.names:
                        if alias.name == "register_legacy_compat":
                            offenders.append(path.name)
        assert not offenders, (
            "兼容桥归档后仍存在运行时引用: " + ", ".join(sorted(set(offenders)))
        )

    synthetic_cfg = i_group.build_synthetic_config(Path(sandbox) / "synthetic_root")

    def _rules(app):
        return {
            (rule.rule, method)
            for rule in app.url_map.iter_rules()
            for method in rule.methods
            if method not in {"HEAD", "OPTIONS"}
        }

    # D1. 默认路径：完全关闭。
    default_app = factory_create_app(synthetic_cfg)
    assert not any(
        rule.startswith("/api/free-tasks") for rule, _ in _rules(default_app)
    ), "默认 app 绝不允许出现自由任务路由"
    assert "free_task_preview" not in default_app.blueprints
    assert "free_task_protected_preview" not in default_app.blueprints
    assert default_app.config.get("LT_FREE_TASK_PREVIEW_OPT_IN") is None
    assert default_app.test_client().get("/api/free-tasks/events").status_code == 404

    # D2. 显式 opt-in：只装配 **受保护** 蓝图（未授权 401，而非放行）。
    authorizer = i_group.make_constant_header_authorizer(
        "Bearer SYNTHETIC-NOT-A-REAL-SECRET"
    )
    opted_app = factory_create_app(
        synthetic_cfg,
        free_task_preview={
            "enabled": True,
            "store": store,
            "authorizer": authorizer,
        },
    )
    opted_rules = _rules(opted_app)
    assert ("/api/free-tasks/events", "POST") in opted_rules
    assert ("/api/free-tasks/sessions/<session_id>/summary", "GET") in opted_rules
    assert "free_task_protected_preview" in opted_app.blueprints
    assert "free_task_preview" not in opted_app.blueprints
    assert opted_app.test_client().get(
        "/api/free-tasks/sessions/sess-1/summary"
    ).status_code == 401

    # 合成接缝未被静默跳过 —— AR03-P2 / Stage 7 起兼容桥不再参与装配，
    # 因此这里是 **零次调用**（不是被静默跳过，而是根本不在流程里）。
    assert len(legacy_calls) == 0


def test_isolated_app_does_not_touch_project_data_dir(sandbox, monkeypatch):
    """在临时目录跑完整会话，项目 data/ 不得被写入任何东西。"""
    monkeypatch.chdir(sandbox)
    data_dir = PROJECT_ROOT / "data"
    before = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []

    app = Flask(__name__)
    app.register_blueprint(
        create_free_task_blueprint(FreeTaskEventStore(str(sandbox / "no_project.db")))
    )
    local = app.test_client()
    start_session(local, "sess-n", "n-1")
    assert post(local, post_body("sess-n", "n-2", completion_payload())).status_code == 200
    assert get_summary(local, "sess-n").status_code == 200

    after = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []
    assert before == after


# ---------------------------------------------------------------------------
# B. POST /events 正例
# ---------------------------------------------------------------------------

def test_append_started_returns_ok_and_summary(client, store):
    response = start_session(client)
    body = response.get_json()
    assert body["ok"] is True
    assert body["action"] == "append"
    assert set(body) == {"ok", "action", "summary"}
    assert body["summary"]["event_count"] == 1
    assert body["summary"]["successful_tasks"] == 0
    assert len(store.list_events("sess-1")) == 1


def test_study_completion_records_user_reported_minutes(client):
    start_session(client)
    response = post(client, post_body("sess-1", "evt-2", completion_payload(25, 25)))
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["successful_tasks"] == 1
    assert summary["study_completions"] == 1
    assert summary["effective_study_minutes"] == 25
    assert summary["study_pomodoros"] == 1


def test_entertainment_completion_never_counts_study_minutes(client):
    start_session(client, "sess-e", "e-1", activity="打游戏", category="娱乐", minutes=55)
    response = post(
        client,
        post_body("sess-e", "e-2", completion_payload(actual_minutes=55, reported=40)),
    )
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["successful_tasks"] == 1
    assert summary["entertainment_completions"] == 1
    assert summary["study_completions"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["study_pomodoros"] == 0


def test_timer_elapsed_is_not_completion(client):
    start_session(client, "sess-t", "t-1")
    response = post(client, post_body("sess-t", "t-2", {
        "event_type": domain.EVENT_TIMER_ELAPSED,
        "actual_minutes": 25,
        "occurred_at": TS1,
    }))
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0
    assert summary["timer_elapsed_events"] == 1
    assert summary["auto_completed"] is False


def test_append_does_not_implicitly_start_a_session(client, store):
    """没有 started 事件就不能完成：绝不隐式创建事件。"""
    response = post(client, post_body("sess-x", "x-1", completion_payload()))
    assert response.status_code == 409
    assert error_of(response) == "session_not_started"
    assert store.list_events("sess-x") == []


def test_completion_without_reported_study_minutes_is_rejected(client, store):
    start_session(client, "sess-m", "m-1")
    response = post(client, post_body("sess-m", "m-2", {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": 25,
        "occurred_at": TS2,
    }))
    assert response.status_code == 400
    assert error_of(response) == "study_minutes_required"
    assert store.get_summary("sess-m")["successful_tasks"] == 0


# ---------------------------------------------------------------------------
# C. POST /events 反例
# ---------------------------------------------------------------------------

def test_wrong_content_type_is_415(client, store):
    response = client.post(
        f"{URL_PREFIX}/events",
        data=b"action=append",
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 415
    assert error_of(response) == "unsupported_media_type"
    assert store.get_summary("sess-1")["event_count"] == 0


def test_missing_content_type_is_415(client):
    response = client.post(f"{URL_PREFIX}/events", data=b"{}")
    assert response.status_code == 415
    assert error_of(response) == "unsupported_media_type"


def test_malformed_json_is_400(client):
    response = client.post(
        f"{URL_PREFIX}/events", data=b"{not json", content_type="application/json"
    )
    assert response.status_code == 400
    assert error_of(response) == "invalid_json"


@pytest.mark.parametrize("raw", [b"[]", b'"append"', b"7", b"null", b"true"])
def test_non_object_body_is_400(client, raw):
    response = client.post(
        f"{URL_PREFIX}/events", data=raw, content_type="application/json"
    )
    assert response.status_code == 400
    assert error_of(response) == "body_not_object"


@pytest.mark.parametrize("bad_action", ["summary", "", "  ", "APPEND", 7, None])
def test_non_append_action_is_400(client, store, bad_action):
    body = post_body("sess-a", "a-1", start_payload())
    if bad_action is None:
        body.pop("action")
    else:
        body["action"] = bad_action
    response = post(client, body)
    assert response.status_code == 400
    assert error_of(response) == "action_not_append"
    assert store.list_events("sess-a") == []


@pytest.mark.parametrize(
    "extra_key, extra_value",
    [
        ("force", True),
        ("study_minutes", 999),
        ("db_path", "data/task_publisher.db"),
        ("status", "running"),
    ],
)
def test_extra_fields_are_400_and_never_written(client, store, extra_key, extra_value):
    body = post_body("sess-x", "x-1", start_payload())
    body[extra_key] = extra_value
    response = post(client, body)
    assert response.status_code == 400
    assert error_of(response) == "adapter_request_unknown_field"
    assert store.list_events("sess-x") == []


@pytest.mark.parametrize("field", ["session_id", "event_id"])
@pytest.mark.parametrize("bad_value", ["", "   ", None, 7, True])
def test_blank_or_missing_ids_are_400_without_writing(client, store, field, bad_value):
    body = post_body("sess-b", "b-1", start_payload())
    body[field] = bad_value
    response = post(client, body)
    assert response.status_code == 400
    code = error_of(response)
    assert code in (
        f"adapter_{field}_invalid",
        f"adapter_{field}_required",
    )
    assert store.list_events("sess-b") == []


@pytest.mark.parametrize("field", ["session_id", "event_id", "event_payload"])
def test_missing_required_keys_are_400_without_writing(client, store, field):
    body = post_body("sess-c", "c-1", start_payload())
    body.pop(field)
    response = post(client, body)
    assert response.status_code == 400
    assert error_of(response) == f"adapter_{field}_required"
    assert store.list_events("sess-c") == []


def test_duplicate_event_id_is_idempotent(client, store):
    body = post_body("sess-dup", "evt-dup", start_payload())
    first = post(client, dict(body))
    second = post(client, dict(body))
    assert first.status_code == 200 and second.status_code == 200
    assert second.get_json()["summary"]["event_count"] == 1
    assert len(store.list_events("sess-dup")) == 1        # 没有伪造第二条


def test_same_event_id_with_different_payload_is_409(client, store):
    post(client, post_body("sess-k", "evt-k", start_payload()))
    response = post(client, post_body("sess-k", "evt-k", start_payload(activity="换了活动")))
    assert response.status_code == 409
    assert error_of(response) == "event_conflict"
    assert len(store.list_events("sess-k")) == 1


def test_second_completion_event_is_409(client, store):
    start_session(client, "sess-dc", "dc-1")
    assert post(
        client, post_body("sess-dc", "dc-2", completion_payload())
    ).status_code == 200
    response = post(client, post_body("sess-dc", "dc-3", completion_payload()))
    assert response.status_code == 409
    assert error_of(response) in ("duplicate_completion", "illegal_state_order")
    summary = store.get_summary("sess-dc")
    assert summary["successful_tasks"] == 1


def test_illegal_state_order_is_409(client, store):
    """没有 started 事件就 paused：会话顺序非法 → 409，且不写入。"""
    response = post(client, post_body("sess-i", "i-2", {
        "event_type": domain.EVENT_PAUSED,
        "actual_minutes": 25,
        "occurred_at": TS2,
    }))
    assert response.status_code == 409
    assert error_of(response) in ("session_not_started", "illegal_state_order")
    assert len(store.list_events("sess-i")) == 0


def test_completion_after_timer_elapsed_is_illegal(client, store):
    """``timer_elapsed`` 不改变状态机语义：随后直接完成仍被账本裁决。"""
    start_session(client, "sess-o", "o-1")
    paused = post(client, post_body("sess-o", "o-2", {
        "event_type": domain.EVENT_PAUSED,
        "actual_minutes": 25,
        "occurred_at": TS1,
    }))
    assert paused.status_code == 200
    completed = post(client, post_body("sess-o", "o-3", completion_payload()))
    assert completed.status_code == 200
    summary = completed.get_json()["summary"]
    assert summary["timer_elapsed_events"] == 0
    assert summary["successful_tasks"] == 1
    assert summary["auto_completed"] is False
    assert len(store.list_events("sess-o")) == 3


def test_ledger_input_errors_surface_as_400(client, store):
    response = post(client, post_body("sess-p", "p-1", {
        "event_type": "free_task.does_not_exist",
        "occurred_at": TS0,
    }))
    assert response.status_code == 400
    assert error_of(response) == "event_type_invalid"
    assert store.list_events("sess-p") == []


def test_payload_unknown_field_is_400(client, store):
    payload = start_payload()
    payload["smuggle"] = "x"
    response = post(client, post_body("sess-u", "u-1", payload))
    assert response.status_code == 400
    assert error_of(response) == "payload_unknown_field"


def test_missing_occurred_at_is_400(client, store):
    payload = start_payload()
    payload.pop("occurred_at")
    response = post(client, post_body("sess-o", "o-1", payload))
    assert response.status_code == 400
    assert error_of(response) == "occurred_at_required"
    assert store.list_events("sess-o") == []


# ---------------------------------------------------------------------------
# D. GET /sessions/<session_id>/summary
# ---------------------------------------------------------------------------

def test_summary_is_read_only_and_marks_user_report(client, store):
    start_session(client)
    post(client, post_body("sess-1", "evt-2", completion_payload()))
    before = len(store.list_events("sess-1"))

    response = get_summary(client, "sess-1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["action"] == "summary"
    summary = body["summary"]
    assert summary["session_id"] == "sess-1"
    assert summary["event_count"] == 2
    assert summary["successful_tasks"] == 1
    assert summary["effective_study_minutes"] == 25
    assert summary["verification"] == "user_reported_not_independently_verified"
    assert summary["auto_completed"] is False
    assert len(store.list_events("sess-1")) == before       # 只读


def test_summary_of_unknown_session_is_zero_not_404(client):
    response = get_summary(client, "never-seen")
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["event_count"] == 0
    assert summary["successful_tasks"] == 0
    assert summary["effective_study_minutes"] == 0


def test_summary_is_session_isolated(client):
    start_session(client, "sess-1", "e1")
    response = get_summary(client, "sess-2")
    assert response.get_json()["summary"]["event_count"] == 0


@pytest.mark.parametrize(
    "session_id, expected_codes",
    [
        ("%20%20", {"adapter_session_id_invalid"}),        # 空白
        ("a" * 200, {"session_id_too_long"}),             # 账本层长度上限
        ("a" * 5 + "%00", {"session_id_invalid"}),         # 控制字符
    ],
)
def test_summary_rejects_invalid_session_ids_with_400(client, session_id, expected_codes):
    response = get_summary(client, session_id)
    assert response.status_code == 400
    assert error_of(response) in expected_codes


# ---------------------------------------------------------------------------
# E. HTTP 语义：404 / 405 / 错误形状
# ---------------------------------------------------------------------------

def test_unknown_route_is_404(client):
    """未知路由 → 标准 404。

    本模块刻意不安装 app 级 handler（那会污染生产应用的既有行为），
    因此匹配阶段的 404 保留 Flask 默认响应体，但状态码语义正确。
    """
    response = client.get(f"{URL_PREFIX}/nope")
    assert response.status_code == 404


def test_get_on_events_endpoint_is_405(client):
    response = client.get(f"{URL_PREFIX}/events")
    assert response.status_code == 405


def test_post_on_summary_endpoint_is_405(client):
    response = client.post(
        f"{URL_PREFIX}/sessions/sess-1/summary",
        data=b"{}",
        content_type="application/json",
    )
    assert response.status_code == 405


def test_error_handlers_do_not_leak_to_other_blueprints(store):
    """Blueprint 级 handler 不改变同一 app 上其它路由的 404 / 405 行为。"""
    from flask import Blueprint, jsonify

    app = Flask(__name__)
    app.register_blueprint(create_free_task_blueprint(store))

    other = Blueprint("other_routes", __name__)

    @other.route("/other")
    def _other():
        return jsonify({"ok": True})

    app.register_blueprint(other)

    assert app.test_client().get("/other").status_code == 200
    # 其它路由的 404 仍然是标准 HTML 404（未被本 Blueprint 劫持成 JSON）
    assert app.test_client().get("/does-not-exist").status_code == 404


def test_every_failure_body_has_the_same_shape(client, store):
    responses = [
        post(client, {"action": "summary", "session_id": "s"}),
        post(client, post_body("sess-z", "z-1", {"event_type": "nope",
                                                "occurred_at": TS0})),
        post(client, post_body("sess-y", "y-1", {"event_type": "nope"})),
    ]
    for response in responses:
        assert response.status_code >= 400
        body = response.get_json()
        assert body["ok"] is False
        assert set(body) == {"ok", "error"}
        assert set(body["error"]) == {"code", "message"}
    assert store.list_events("sess-z") == []
    assert store.list_events("sess-y") == []


def test_sandbox_db_is_created_inside_temp_dir_only(client, sandbox, store):
    start_session(client)
    names = sorted(os.listdir(sandbox))
    assert names
    assert all(not name.startswith("task_publisher") for name in names)
    assert Path(store.db_path).parent == sandbox.resolve() or os.path.samefile(
        Path(store.db_path).parent, sandbox
    )


# ---------------------------------------------------------------------------
# F. 匹配阶段 404 / 405 的 JSON 收口（显式 opt-in，生产禁用）
# ---------------------------------------------------------------------------
#
# 关键区分点：状态码 404 **不等于** JSON 契约。
#   - 默认（未 opt-in）：状态码正确，body 是 werkzeug 默认 HTML；
#   - opt-in 后：preview 前缀下才是统一 JSON，且状态码一字不变。
# 因此下面的测试都 **显式** 检查 Content-Type / ``get_json()``，
# 绝不以 ``status_code == 404`` 冒充 JSON 断言。

#: 一个“形似但不是同一路径”的前缀 —— opt-in 绝不能误伤它。
SIMILAR_PREFIXES = [
    "/api/free-tasksXYZ",
    "/api/free-tasks-old",
    "/api/free-tasksfoo/events",
]


def _build_app(store, *, opt_in: bool):
    """建一个隔离 synthetic app，可选择是否 opt-in 预览错误收口。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    if opt_in:
        register_free_task_preview_errors(app)
    return app


@pytest.fixture()
def other_blueprint_app(store):
    """同一个 synthetic app 上再挂一个无关 Blueprint（负向对照）。"""
    from flask import Blueprint, jsonify

    app = _build_app(store, opt_in=True)

    other = Blueprint("unrelated_routes", __name__)

    @other.route("/unrelated")
    def _unrelated():
        return jsonify({"ok": True})

    @other.route("/unrelated-write", methods=["POST"])
    def _unrelated_write():
        return jsonify({"ok": True})

    app.register_blueprint(other)
    return app.test_client()


# -- F.1 默认行为：opt-in 之前不变（先证明问题真实存在） -------------------

def test_default_app_does_not_return_json_for_matching_stage_404(store):
    """未 opt-in：匹配阶段 404 状态码正确，但 **不是** JSON（本模块的原问题）。"""
    client = _build_app(store, opt_in=False).test_client()
    response = client.get(f"{URL_PREFIX}/nope")

    # 状态码语义：必须正确
    assert response.status_code == 404
    # JSON 契约：**不** 成立 —— 显式证明它确实是默认 HTML
    assert response.get_json(silent=True) is None
    assert "text/html" in response.headers["Content-Type"]
    assert PREVIEW_URL_PREFIX == URL_PREFIX


def test_default_app_does_not_return_json_for_matching_stage_405(store):
    """未 opt-in：匹配阶段 405 同样只有状态码契约，没有 JSON 契约。"""
    client = _build_app(store, opt_in=False).test_client()
    response = client.get(f"{URL_PREFIX}/events")

    assert response.status_code == 405
    assert response.get_json(silent=True) is None
    assert "text/html" in response.headers["Content-Type"]


def test_factory_alone_never_opt_in(store):
    """默认工厂 ``create_free_task_blueprint`` 不注册任何 app 级 handler。"""
    app = _build_app(store, opt_in=False)
    # app 级 404/405 handler 只可能来自 opt-in helper；默认必须是空的。
    handlers = dict(app.error_handler_spec[None][None]) if app.error_handler_spec.get(
        None
    ) else {}
    assert 404 not in handlers
    assert 405 not in handlers


# -- F.2 opt-in 之后：preview 404 / 405 是统一 JSON，状态码不变 ------------

def test_opt_in_makes_preview_404_a_unified_json_body(store):
    client = _build_app(store, opt_in=True).test_client()
    response = client.get(f"{URL_PREFIX}/nope")

    assert response.status_code == 404
    assert "application/json" in response.headers["Content-Type"]
    assert error_of(response) == "not_found"


def test_opt_in_makes_preview_405_a_unified_json_body(store):
    client = _build_app(store, opt_in=True).test_client()
    response = client.get(f"{URL_PREFIX}/events")

    assert response.status_code == 405
    assert "application/json" in response.headers["Content-Type"]
    assert error_of(response) == "method_not_allowed"


def test_opt_in_preserves_status_codes_against_default_app(store):
    """收口只改 body：状态码必须与未 opt-in 时 **逐一相同**。"""
    for path, method in [
        (f"{URL_PREFIX}/nope", "GET"),
        (f"{URL_PREFIX}/events", "GET"),
        (f"{URL_PREFIX}/sessions/s1/summary", "POST"),
    ]:
        default_resp = _build_app(store, opt_in=False).test_client().open(
            path, method=method
        )
        opted_resp = _build_app(store, opt_in=True).test_client().open(
            path, method=method
        )
        assert default_resp.status_code == opted_resp.status_code, path


# -- F.3 opt-in 绝不误伤非 preview 路径 -------------------------------------

@pytest.mark.parametrize("path", SIMILAR_PREFIXES)
def test_opt_in_leaves_similar_but_different_prefixes_native(store, path):
    """前缀相似但不是同一路径 → 保持原生 HTML 404，状态码不变。"""
    opted = _build_app(store, opt_in=True).test_client()
    default = _build_app(store, opt_in=False).test_client()

    opted_resp = opted.get(path)
    default_resp = default.get(path)

    assert opted_resp.status_code == default_resp.status_code == 404
    assert opted_resp.get_json(silent=True) is None
    assert "text/html" in opted_resp.headers["Content-Type"]


@pytest.mark.parametrize("path", ["/", "/other", "/api/other", "/api/free-task/summary"])
def test_opt_in_leaves_unrelated_paths_native(store, path):
    """无关路径的 404 必须逐字保持原生行为（body 完全一致）。"""
    opted_resp = _build_app(store, opt_in=True).test_client().get(path)
    default_resp = _build_app(store, opt_in=False).test_client().get(path)

    assert opted_resp.status_code == 404
    assert opted_resp.get_json(silent=True) is None
    assert opted_resp.get_data() == default_resp.get_data()


def test_opt_in_leaves_other_blueprint_404_and_405_native(other_blueprint_app):
    """同 app 上其它 Blueprint 的 404 / 405 完全不受影响。"""
    # 其它 Blueprint 自身的 405：PUT 到只允许 POST 的路由
    resp405 = other_blueprint_app.put("/unrelated-write")
    assert resp405.status_code == 405
    assert resp405.get_json(silent=True) is None

    # 其它 Blueprint 自身的 404
    resp404 = other_blueprint_app.get("/unrelated/missing")
    assert resp404.status_code == 404
    assert resp404.get_json(silent=True) is None

    # 正常路由不受影响
    assert other_blueprint_app.get("/unrelated").status_code == 200


def test_opt_in_keeps_allow_header_on_non_preview_405(other_blueprint_app):
    """非 preview 的 405 原生透传：``Allow`` 头仍在（不做无脑 JSON 化）。"""
    response = other_blueprint_app.put("/unrelated-write")
    assert response.status_code == 405
    assert response.headers.get("Allow")


# -- F.4 Flask 自动方法语义（HEAD / OPTIONS / PUT） --------------------------

def test_opt_in_head_on_preview_get_route_is_405_json(store):
    """HEAD 落到只允许 POST 的路由 → 405。

    这条锁死“收口不改变 Flask 的方法匹配语义”。注意 HTTP **规定** HEAD
    响应不得带 body，所以这里断言状态码与 Content-Type 是 JSON，而
    body 被剥空是正确行为（不是 JSON 契约失败）。
    """
    default_resp = _build_app(store, opt_in=False).test_client().head(
        f"{URL_PREFIX}/events"
    )
    opted_resp = _build_app(store, opt_in=True).test_client().head(
        f"{URL_PREFIX}/events"
    )
    assert default_resp.status_code == opted_resp.status_code == 405
    # 默认是 HTML，opt-in 后 Content-Type 变成 JSON（body 因 HEAD 被剥空）
    assert "text/html" in default_resp.headers["Content-Type"]
    assert "application/json" in opted_resp.headers["Content-Type"]
    assert opted_resp.get_data() == b""


def test_opt_in_options_on_preview_route_still_200(store):
    """OPTIONS 自动应答仍是 200（未被 404/405 收口误伤）。"""
    response = _build_app(store, opt_in=True).test_client().options(
        f"{URL_PREFIX}/events"
    )
    assert response.status_code == 200
    assert response.headers.get("Allow")


def test_opt_in_put_on_preview_post_route_is_405_json(store):
    client = _build_app(store, opt_in=True).test_client()
    response = client.put(f"{URL_PREFIX}/events", data=b"{}", content_type="application/json")
    assert response.status_code == 405
    assert error_of(response) == "method_not_allowed"


def test_opt_in_head_on_summary_route_is_served_with_405_free_semantics(store):
    """GET 路由的 HEAD 被 Flask 自动允许 → 200 且不写库。"""
    client = _build_app(store, opt_in=True).test_client()
    response = client.head(f"{URL_PREFIX}/sessions/sess-h/summary")
    assert response.status_code == 200
    # HEAD 无 body
    assert response.get_data() == b""


# -- F.5 opt-in 之后业务合同不回退 ------------------------------------------

def test_opt_in_keeps_post_and_get_business_contract(store, client):
    """opt-in app 上 200 / 400 / 409 / 415 分类完全不变。"""
    assert start_session(client, "sess-k", "k-1").status_code == 200
    assert post(client, post_body("sess-k", "k-2", completion_payload())).status_code == 200
    summary = get_summary(client, "sess-k")
    assert summary.status_code == 200
    assert summary.get_json()["summary"]["successful_tasks"] == 1

    # 400
    assert error_of(post(client, {"action": "summary"})) == "action_not_append"
    # 415
    resp415 = client.post(
        f"{URL_PREFIX}/events", data=b"a=1", content_type="application/x-www-form-urlencoded"
    )
    assert resp415.status_code == 415 and error_of(resp415) == "unsupported_media_type"
    # 409
    resp409 = post(client, post_body("sess-nostart", "n-1", completion_payload()))
    assert resp409.status_code == 409 and error_of(resp409) == "session_not_started"


def test_opt_in_does_not_change_ledger_contents(store):
    """opt-in 不影响写入：事件数与未 opt-in 的 app 完全一致。"""
    opted = _build_app(store, opt_in=True).test_client()
    start_session(opted, "sess-z", "z-1")
    post(opted, post_body("sess-z", "z-2", completion_payload()))
    assert len(store.list_events("sess-z")) == 2
    assert store.get_summary("sess-z")["successful_tasks"] == 1


def test_register_helper_returns_the_app_and_is_idempotent(store):
    """辅助函数返回同一 app；重复调用不改变结果。"""
    app = Flask(__name__)
    assert register_free_task_preview_errors(app) is app
    app.register_blueprint(create_free_task_blueprint(store))
    register_free_task_preview_errors(app)  # 幂等

    client = app.test_client()
    assert client.get(f"{URL_PREFIX}/nope").status_code == 404
    assert error_of(client.get(f"{URL_PREFIX}/nope")) == "not_found"


def test_helper_is_not_invoked_at_import_time(store):
    """模块 import 不产生注册副作用：默认工厂路径仍然原生。"""
    app = _build_app(store, opt_in=False)
    resp = app.test_client().get(f"{URL_PREFIX}/nope")
    assert resp.status_code == 404
    assert resp.get_json(silent=True) is None