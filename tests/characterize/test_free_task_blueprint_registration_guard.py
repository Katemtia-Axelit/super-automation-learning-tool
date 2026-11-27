"""自由任务预览 **双 Blueprint 注册守卫** 的合成刻画测试。

范围（``LT_RETENTION_FREE_TASK_REGISTRATION_GUARD_20261023_G``）：

  L. 互斥契约：两种注册顺序都 fail closed
     - ``unprotected -> protected``：第二次注册抛
       :class:`RuntimeError`；
     - ``protected -> unprotected``：第二次注册抛
       :class:`RuntimeError`；
     - 报错文案 **不泄漏** 任何凭据；
     - 冲突之后该 app **不可服务**：自由任务前缀下的任何请求都拿不到
       200，**没有事件写入**，且 **没有** 重复的
       ``/api/free-tasks/events`` 路由完成注册；
     - 注册失败 **不得** 返回一个 “已装好可服务” 的 app。

  M. 单工厂兼容
     - 只注册受保护工厂：未授权 GET / POST / OPTIONS 都 **不写库**；
       授权器异常 → 503；正确授权 → 200；
     - 只注册旧的无认证工厂：保留原合成合同（无认证仍 200）。

  N. 边界与不回退
     - **相似 URL 前缀**（``/api/free-tasks-old`` 等）**不** 触发守卫；
     - E 组 opt-in ``register_free_task_preview_errors`` 的 JSON 404 / 405
       行为不回退；
     - 守卫 **不依赖** 请求到达才被触发（注册即判定）；
     - 不引入 “按 Flask Debug 模式分支” 或任何 allowlist 绕过。

本文件是 **纯合成** 测试：只用独立 ``Flask(__name__)``、
``tempfile.TemporaryDirectory`` 与注入的 ``FreeTaskEventStore`` / 测试替身；
绝不触碰 ``data/task_publisher.db``、``config/config.json``、
``src/notes/**``；**不启动真实 Web 服务、不监听端口、不连 socket**；假凭据
是 **固定测试常量**，**绝不使用** 任何真实用户机密。
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

flask = pytest.importorskip("flask")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Blueprint, Flask  # noqa: E402

from server.blueprints.free_task_bp import (  # noqa: E402
    LEGACY_PREVIEW_BLUEPRINT_NAME,
    PROTECTED_PREVIEW_BLUEPRINT_NAME,
    REGISTRATION_CONFLICT_CODE,
    REGISTRATION_CONFLICT_CONFIG_KEY,
    REQUIRED_ACTION,
    ROLE_LEGACY_UNPROTECTED,
    ROLE_PROTECTED,
    create_free_task_blueprint,
    create_protected_free_task_blueprint,
    register_free_task_preview_errors,
)
from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_events import FreeTaskEventStore  # noqa: E402

URL_PREFIX = "/api/free-tasks"
EVENTS_URL = f"{URL_PREFIX}/events"

TS0 = "2026-10-23T02:00:00Z"

#: **固定测试常量**，仅用于 synthetic 沙箱；与任何真实机密无关。
FAKE_AUTHORIZATION_HEADER = "Bearer SYNTHETIC-NOT-A-REAL-SECRET"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def make_constant_header_authorizer(expected_header: str):
    """``authorizer(request) -> bool``：Authorization header 常量比较。"""

    def _authorizer(request) -> bool:
        return request.headers.get("Authorization") == expected_header

    return _authorizer


def make_raising_authorizer(exc: Exception):
    """必定抛异常的 authorizer（用于 fail closed 路径）。"""

    def _authorizer(request) -> bool:
        raise exc

    return _authorizer


def start_payload():
    return {
        "event_type": domain.EVENT_STARTED,
        "activity": "复习线性代数",
        "category": "学习",
        "planned_minutes": 25,
        "occurred_at": TS0,
        "reason": domain.DEFAULT_FREE_TASK_REASON,
    }


def post_body(session_id, event_id, payload):
    return {
        "action": REQUIRED_ACTION,
        "session_id": session_id,
        "event_id": event_id,
        "event_payload": payload,
    }


def post(client, body, headers=None):
    return client.post(
        EVENTS_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        headers=headers or {},
    )


def authed_post(client, body):
    return post(client, body, headers={"Authorization": FAKE_AUTHORIZATION_HEADER})


def get_summary(client, session_id, headers=None):
    return client.get(f"{URL_PREFIX}/sessions/{session_id}/summary", headers=headers or {})


def error_of(response):
    body = response.get_json()
    assert body is not None and isinstance(body, dict)
    assert body["ok"] is False
    error = body["error"]
    assert set(error) == {"code", "message"}
    return error["code"]


def events_rule_count(app) -> int:
    """app 的 url_map 中指向 ``/api/free-tasks/events`` 的规则条数。"""
    return sum(
        1
        for rule in app.url_map.iter_rules()
        if rule.rule == EVENTS_URL
    )


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_reg_guard_") as temp:
        yield Path(temp)


@pytest.fixture()
def store(sandbox):
    return FreeTaskEventStore(str(sandbox / "synthetic_reg_guard.sqlite3"))


@pytest.fixture()
def authorizer():
    return make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)


@pytest.fixture()
def socket_ledger(monkeypatch):
    """记录所有被创建 / 监听的 socket —— 本组测试必须 **一个都没有**。"""
    created: list = []

    class _RecordingSocket(socket.socket):
        def __init__(self, *args, **kwargs):
            created.append(self)
            super().__init__(*args, **kwargs)

        def bind(self, *args, **kwargs):
            created.append("bind")
            return super().bind(*args, **kwargs)

        def listen(self, *args, **kwargs):
            created.append("listen")
            return super().listen(*args, **kwargs)

        def connect(self, *args, **kwargs):
            created.append("connect")
            return super().connect(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _RecordingSocket)

    def _deny_connect(*_a, **_k):
        created.append("connect")
        raise AssertionError("本组测试不得建立任何 socket 连接")

    monkeypatch.setattr(socket, "create_connection", _deny_connect)
    return created


# ---------------------------------------------------------------------------
# L. 互斥契约：两种注册顺序都 fail closed
# ---------------------------------------------------------------------------

def test_registration_unprotected_then_protected_is_rejected(store, authorizer):
    """unprotected -> protected：第二次注册必须被拒绝（不再无认证 200 写库）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))

    with pytest.raises(RuntimeError) as excinfo:
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )

    message = str(excinfo.value)
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in message
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME in message
    # 不泄漏任何凭据。
    assert FAKE_AUTHORIZATION_HEADER not in message
    assert "Bearer" not in message
    assert "SYNTHETIC" not in message


def test_registration_protected_then_unprotected_is_rejected(store, authorizer):
    """protected -> unprotected：第二次注册同样必须被拒绝（顺序不是安全模型）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer)
    )

    with pytest.raises(RuntimeError) as excinfo:
        app.register_blueprint(create_free_task_blueprint(store))

    message = str(excinfo.value)
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in message
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME in message
    assert FAKE_AUTHORIZATION_HEADER not in message


def test_rejected_dual_registration_leaves_no_duplicate_events_route(store, authorizer):
    """双注册被拒后：不存在重复的 ``/api/free-tasks/events`` 路由完成注册。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    before = events_rule_count(app)

    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )

    # 受保护版本 **没有** 成功完成注册 → 规则数不变，且 url_map 里
    # 不存在 “受保护” 前缀的 events 路由。
    assert events_rule_count(app) == before
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert not any(
        endpoint.startswith(f"{PROTECTED_PREVIEW_BLUEPRINT_NAME}.")
        and endpoint.endswith("append_free_task_event")
        for endpoint in endpoints
    )


def test_rejected_dual_registration_app_cannot_serve_unauthenticated_write(
    store, authorizer
):
    """冲突后该 app **不可服务**：未认证 POST 不得 200，也不得写库。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )

    # 该 app 被标记为配置冲突。
    assert app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is True

    client = app.test_client()
    response = post(client, post_body("sess-x", "x-1", start_payload()))
    assert response.status_code != 200
    assert error_of(response) == REGISTRATION_CONFLICT_CODE
    # 没有事件写入。
    assert store.list_events("sess-x") == []
    assert store.get_summary("sess-x")["event_count"] == 0


def test_rejected_dual_registration_protected_first_also_blocks_writes(
    store, authorizer
):
    """protected -> unprotected 被拒后，同样不得出现未授权 200 写入。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer)
    )
    with pytest.raises(RuntimeError):
        app.register_blueprint(create_free_task_blueprint(store))

    client = app.test_client()
    response = post(client, post_body("sess-y", "y-1", start_payload()))
    assert response.status_code != 200
    assert store.list_events("sess-y") == []


def test_conflict_response_does_not_leak_credentials(store, authorizer):
    """冲突闸门返回的 503 不含任何凭据 / 内部细节。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )

    raw = app.test_client().post(
        EVENTS_URL,
        data=json.dumps(post_body("sess-z", "z-1", start_payload())).encode("utf-8"),
        content_type="application/json",
    ).get_data(as_text=True)
    for forbidden in (FAKE_AUTHORIZATION_HEADER, "Bearer", "SYNTHETIC", "Authorization"):
        assert forbidden not in raw


def test_guard_is_detected_at_registration_not_at_request_time(store, authorizer):
    """守卫在 **注册期** 判定：不依赖请求到达（没有任何请求也能拦下）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )
    # 整个过程 **零请求**：上面没有 test_client() 调用。
    assert len(store.list_events("sess-none")) == 0


def test_guard_detects_conflict_even_with_renamed_registration(store, authorizer):
    """即使受保护蓝图用 ``name=`` 改名注册，也照样被识别为冲突。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))

    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer),
            name="some_other_name",
        )
    assert store.list_events("sess-r") == []


def test_guard_detects_conflict_when_protected_registered_under_custom_name(
    store, authorizer
):
    """受保护蓝图改名注册后，再注册无认证版本仍被拒（按角色而非名字判定）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer),
        name="renamed_protected",
    )
    with pytest.raises(RuntimeError):
        app.register_blueprint(create_free_task_blueprint(store))


def test_role_marker_is_not_name_based(store, authorizer):
    """解释：为什么 “Blueprint 名字不同” 不会导致漏检。

    检测依据是 **角色标记**（``free_task_role``），而不是名字相等性。
    """
    legacy = create_free_task_blueprint(store)
    protected = create_protected_free_task_blueprint(store, authorizer)

    assert legacy.name != protected.name  # 名字确实不同
    assert legacy.free_task_role == ROLE_LEGACY_UNPROTECTED
    assert protected.free_task_role == ROLE_PROTECTED
    # 名字不同，但角色互斥 → 命中守卫。
    assert legacy.free_task_role != protected.free_task_role


def test_guard_falls_back_to_canonical_blueprint_name(store, authorizer):
    """兜底：手工构造的 **规范同名** Blueprint 也会被识别为冲突。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    # 手工构造一个同名（但非本模块工厂）的受保护蓝图。
    manual = Blueprint(PROTECTED_PREVIEW_BLUEPRINT_NAME, __name__)
    app.register_blueprint(manual)

    with pytest.raises(RuntimeError):
        app.register_blueprint(create_free_task_blueprint(store))


def test_same_blueprint_object_registered_twice_is_not_a_conflict(store, authorizer):
    """同一个受保护蓝图对象换名重复注册 **不** 属于互斥冲突（不误报）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    bp = create_protected_free_task_blueprint(store, authorizer)
    app.register_blueprint(bp)
    app.register_blueprint(bp, name="protected_again")  # 不抛错

    assert app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is None


def test_no_socket_listener_during_guard_checks(store, authorizer, socket_ledger):
    """整个守卫路径 **不建立任何 socket**，即没有服务端监听。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )
    # 没有 socket 被创建 / 监听 / 连接。
    assert socket_ledger == []


# ---------------------------------------------------------------------------
# M. 单工厂兼容
# ---------------------------------------------------------------------------

def test_only_protected_factory_still_blocks_unauthorized(store, authorizer):
    """只注册受保护工厂：未授权 GET / POST / OPTIONS 全被拒，且不写库。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer)
    )
    client = app.test_client()

    assert post(client, post_body("sess-p", "p-1", start_payload())).status_code == 401
    assert get_summary(client, "sess-p").status_code == 401
    assert client.options(EVENTS_URL).status_code == 401
    assert store.list_events("sess-p") == []
    assert store.get_summary("sess-p")["event_count"] == 0

    # 授权后才放行。
    assert authed_post(client, post_body("sess-p", "p-1", start_payload())).status_code == 200
    assert len(store.list_events("sess-p")) == 1


def test_only_protected_factory_authorizer_exception_is_503(store):
    """只注册受保护工厂：授权器异常 → 503，且不写库。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(
            store, make_raising_authorizer(RuntimeError("secret-token-abc123"))
        )
    )
    client = app.test_client()
    response = post(client, post_body("sess-q", "q-1", start_payload()))
    assert response.status_code == 503
    assert store.list_events("sess-q") == []
    raw = response.get_data(as_text=True)
    for forbidden in ("secret-token", "abc123", "RuntimeError"):
        assert forbidden not in raw


def test_only_legacy_factory_keeps_original_contract(store):
    """只注册旧的无认证工厂：保留原合成合同（无认证仍 200 / 可写）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    client = app.test_client()

    response = post(client, post_body("sess-old", "o-1", start_payload()))
    assert response.status_code == 200
    assert len(store.list_events("sess-old")) == 1
    assert get_summary(client, "sess-old").status_code == 200
    # 单注册不受守卫影响：app 不被标记为冲突。
    assert app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is None


def test_legacy_factory_public_signature_unchanged():
    """旧工厂的公共签名 **不变**（store 一个必需位置参数，无新增开关）。"""
    import inspect

    sig = inspect.signature(create_free_task_blueprint)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["store"]
    assert all(p.default is inspect.Parameter.empty for p in params)
    # 不得新增任何 allowlist / 跳过守卫的参数。
    for param in params:
        for token in ("skip", "bypass", "allow", "debug", "force", "unsafe"):
            assert token not in param.name.lower()


# ---------------------------------------------------------------------------
# N. 边界与不回退
# ---------------------------------------------------------------------------

def test_similar_url_prefix_blueprint_is_not_treated_as_conflict(store, authorizer):
    """相似 URL 前缀 **不** 触发守卫（不得误伤无关蓝图）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))

    similar = Blueprint("free_tasks_old_preview", __name__, url_prefix="/api/free-tasks-old")
    app.register_blueprint(similar)  # 不抛错

    assert app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is None
    # 旧的无认证路由仍然可用（未被守卫误伤）。
    client = app.test_client()
    assert post(client, post_body("sess-s", "s-1", start_payload())).status_code == 200


def test_similar_prefix_paths_are_not_blocked_by_conflict_guard(store, authorizer):
    """冲突闸门 **前缀精确**：形似路径不受 503 影响。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )

    client = app.test_client()
    # 形似但不是同一前缀的路径 → 不受冲突闸门影响（仍是原生 404）。
    for similar in ("/api/free-tasks-old", "/api/free-tasksXYZ"):
        assert client.get(similar).status_code == 404


def test_e_group_opt_in_json_404_405_not_regressed(store):
    """E 组 opt-in 的 JSON 404 / 405 行为在守卫之后 **不回退**。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    register_free_task_preview_errors(app)
    client = app.test_client()

    r404 = client.get(f"{URL_PREFIX}/nope")
    assert r404.status_code == 404 and error_of(r404) == "not_found"
    r405 = client.get(EVENTS_URL)
    assert r405.status_code == 405 and error_of(r405) == "method_not_allowed"


def test_e_group_opt_in_404_405_not_regressed_with_protected_only(store, authorizer):
    """只注册受保护工厂时，E 组 opt-in 语义同样不回退。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer)
    )
    register_free_task_preview_errors(app)
    client = app.test_client()

    r404 = client.get(f"{URL_PREFIX}/nope")
    assert r404.status_code == 404 and error_of(r404) == "not_found"
    r405 = client.get(EVENTS_URL)
    assert r405.status_code == 405 and error_of(r405) == "method_not_allowed"


def test_guard_has_no_debug_mode_branch(store, authorizer):
    """守卫 **不得** 依据 Flask Debug 模式分支（Debug 不放行）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )
    assert app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is True


def test_guard_is_not_bypassed_by_direct_blueprint_register(store, authorizer):
    """即便直接调用 Flask 的 ``Blueprint.register``，守卫依然 fail closed。

    这里刻意调用 **Flask 基类** 的 ``register``，绕开本模块对 ``register``
    的覆盖，以验证第二层 ``record_once`` 钩子确实独立生效。
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))

    bp = create_protected_free_task_blueprint(store, authorizer)
    with pytest.raises(RuntimeError):
        flask.Blueprint.register(bp, app, {})
    assert store.list_events("sess-b") == []


def test_record_once_hook_is_the_second_independent_layer(store, authorizer):
    """``record_once`` 钩子确实被安装在蓝图上（Flask 官方钩子）。"""
    bp = create_protected_free_task_blueprint(store, authorizer)
    # ``record_once`` 的回调进入 ``deferred_functions``，并在注册时执行。
    assert any(
        getattr(fn, "__name__", "") == "_assert_no_conflicting_free_task_blueprint_hook"
        for fn in bp.deferred_functions
    )


def test_rejected_registration_leaves_protected_blueprint_unregistered(
    store, authorizer
):
    """被拒的注册 **没有** 在 app 上留下受保护蓝图的注册记录。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError):
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME not in app.blueprints
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in app.blueprints


def test_guard_does_not_leak_credentials_in_runtime_error(store, authorizer):
    """RuntimeError 文案不含凭据、异常类型名或内部路径。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    with pytest.raises(RuntimeError) as excinfo:
        app.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )
    message = str(excinfo.value)
    assert "Traceback" not in message
    assert str(sandbox_path_of(store)) not in message
    assert FAKE_AUTHORIZATION_HEADER not in message


def sandbox_path_of(store):
    """尽力取出 store 的路径（仅用于断言错误信息不泄漏内部路径）。"""
    for attr in ("_path", "path", "db_path"):
        value = getattr(store, attr, None)
        if isinstance(value, str):
            return value
    return "<unknown-path>"
