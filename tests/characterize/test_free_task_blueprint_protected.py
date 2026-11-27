"""**受保护** 自由任务 Blueprint（``create_protected_free_task_blueprint``）的
合成刻画测试。

范围（``LT_RETENTION_FREE_TASK_AUTH_SYNTH_20261022_F``）：

  G. 工厂 fail closed
     - 缺失 ``authorizer``（关键字形式 / 位置形式）、``None``、非 callable
       → 在 **Blueprint 注册前** 抛 :class:`TypeError`；
     - 拒绝发生在触碰 store 之前（探针 store 的调用计数必须为 0）；
     - 绝不提供任何默认放行、默认 token 或“无授权也能构造”的形态；
     - 工厂在构造期 / import 期不读配置、不碰文件、不联网。

  H. 未授权 → 401，且不接触账本
     - 无 ``Authorization``、错误凭据 → POST 与 GET 都是 401
       ``free_task_unauthorized``；
     - 被拒请求 **绝不** 接触 store：事件列表 / summary 计数 **不变**；
     - 401 响应是固定 JSON 形状，且 **绝不** 回显任何凭据内容。

  I. 正确授权 → 业务合同完全不变
     - started → completed → GET summary 全链路 200；
     - 415 / 400 / 409 等既有分类在受保护蓝图中 **一字不变**。

  J. 授权器抛异常 → fail closed 503，且不泄漏敏感内容
     - 401 与 503 被 **明确区分**；
     - 503 响应 **绝不** 含异常文本、异常类型名或任何 secret；
     - 账本 **不变**。

  K. 边界与不回退
     - E 组 ``register_free_task_preview_errors`` opt-in 行为不回退；
     - 旧的未保护工厂仍保留既有合成合同，且测试显式断言它 **无认证**
       （同时声明 **禁止生产使用**）；
     - 受保护蓝图 **没有** 绕过保护的备用路径。

本文件是 **纯合成** 测试：只用独立 ``Flask(__name__)``、
``tempfile.TemporaryDirectory`` 与注入的 ``FreeTaskEventStore`` /
测试替身；绝不触碰 ``data/task_publisher.db``、``config/config.json``、
``src/notes/**``；不启动真实 Web 服务、不监听端口；fake 凭据是 **固定测试
常量**，**绝不使用** 任何真实用户机密。
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

flask = pytest.importorskip("flask")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask  # noqa: E402
from werkzeug.datastructures import Headers  # noqa: E402

from server.blueprints import free_task_bp  # noqa: E402
from server.blueprints.free_task_bp import (  # noqa: E402
    AUTHORIZATION_UNAVAILABLE_CODE,
    LEGACY_PREVIEW_BLUEPRINT_NAME,
    PREVIEW_URL_PREFIX,
    PROTECTED_PREVIEW_BLUEPRINT_NAME,
    REGISTRATION_CONFLICT_CODE,
    REGISTRATION_CONFLICT_CONFIG_KEY,
    UNAUTHORIZED_CODE,
    create_free_task_blueprint,
    create_protected_free_task_blueprint,
    register_free_task_preview_errors,
)
from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_events import FreeTaskEventStore  # noqa: E402

URL_PREFIX = "/api/free-tasks"

TS0 = "2026-10-22T09:00:00Z"
TS1 = "2026-10-22T09:10:00Z"
TS2 = "2026-10-22T09:25:00Z"

#: **固定测试常量**，仅用于 synthetic 沙箱；与任何真实机密无关。
FAKE_AUTHORIZATION_HEADER = "Bearer SYNTHETIC-NOT-A-REAL-SECRET"
FAKE_BAD_AUTHORIZATION_HEADER = "Bearer SYNTHETIC-WRONG-VALUE"


# ---------------------------------------------------------------------------
# 辅助：假的 authorizer（显式注入的可注入凭据校验）
# ---------------------------------------------------------------------------

def make_constant_header_authorizer(expected_header: str):
    """返回一个 ``authorizer(request) -> bool``：Authorization header 常量比较。

    这就是本轮允许的“synthetic 测试假凭据/假 verifier”。它 **不** 是生产
    授权模型，只是让本轮能在隔离沙箱里刻画受保护端点的行为。
    """

    def _authorizer(request) -> bool:
        return request.headers.get("Authorization") == expected_header

    return _authorizer


def make_raising_authorizer(exc: Exception):
    """返回一个必定抛异常的 authorizer（用于 fail closed 路径）。"""

    def _authorizer(request) -> bool:
        raise exc

    return _authorizer


def auth_headers(value: str = FAKE_AUTHORIZATION_HEADER) -> dict:
    return {"Authorization": value}


# ---------------------------------------------------------------------------
# 合成请求体
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
        "action": "append",
        "session_id": session_id,
        "event_id": event_id,
        "event_payload": payload,
    }


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_bp_protected_") as temp:
        yield Path(temp)


@pytest.fixture()
def store(sandbox):
    return FreeTaskEventStore(str(sandbox / "synthetic_protected.sqlite3"))


@pytest.fixture()
def authorizer():
    return make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)


def build_protected_app(store, authorizer, *, opt_in_errors: bool = False):
    """隔离 synthetic app：只注册受保护 Blueprint（手动注册）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer)
    )
    if opt_in_errors:
        register_free_task_preview_errors(app)
    return app


@pytest.fixture()
def client(store, authorizer):
    """受保护 app 的 test client（默认带正确凭据的辅助函数）。"""
    return build_protected_app(store, authorizer).test_client()


def post(client, body, content_type="application/json", headers=None):
    return client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        content_type=content_type,
        headers=headers or {},
    )


def authed_post(client, body, content_type="application/json"):
    return post(client, body, content_type, headers=auth_headers())


def authed_get(client, session_id):
    return client.get(
        f"{URL_PREFIX}/sessions/{session_id}/summary", headers=auth_headers()
    )


def get_summary(client, session_id, headers=None):
    return client.get(f"{URL_PREFIX}/sessions/{session_id}/summary", headers=headers)


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
# G. 工厂 fail closed
# ---------------------------------------------------------------------------

def test_protected_factory_rejects_missing_authorizer(store):
    """缺失 authorizer → TypeError（不是 TypeError 缺省放行）。"""
    with pytest.raises(TypeError):
        create_protected_free_task_blueprint(store)  # 完全不给第二个参数


def test_protected_factory_rejects_none_authorizer(store):
    with pytest.raises(TypeError):
        create_protected_free_task_blueprint(store, None)


@pytest.mark.parametrize(
    "bad_authorizer",
    [
        "Bearer token",        # 字符串（可调用对象的反面：非 callable）
        42,                    # 整数
        True,                  # 布尔
        {"token": "x"},        # 字典
        ["token"],             # 列表
        object(),              # 普通对象
    ],
)
def test_protected_factory_rejects_non_callable_authorizer(store, bad_authorizer):
    with pytest.raises(TypeError):
        create_protected_free_task_blueprint(store, bad_authorizer)


def test_authorizer_validation_happens_before_touching_store():
    """拒绝必须发生在触碰 store **之前**（探针 store 零调用）。"""

    class ProbeStore:
        """任何被调用都会让 ``touched`` 变真（这里必须永不变真）。"""

        def __init__(self):
            self.touched = False

        def append_event(self, session_id, event_id, event_payload):
            self.touched = True
            return {}

        def get_summary(self, session_id):
            self.touched = True
            return {}

    probe = ProbeStore()
    with pytest.raises(TypeError):
        create_protected_free_task_blueprint(probe, None)
    assert probe.touched is False

    with pytest.raises(TypeError):
        create_protected_free_task_blueprint(probe, "not-callable")
    assert probe.touched is False


def test_protected_factory_has_no_optional_authorizer_kwarg():
    """不得存在“默认 authorizer”这种悄悄放行的签名。"""
    sig = inspect.signature(create_protected_free_task_blueprint)
    params = list(sig.parameters.values())
    # 两个参数都是必须的位置参数（POSITIONAL_OR_KEYWORD），没有默认值。
    assert [p.name for p in params] == ["store", "authorizer"]
    assert all(p.default is inspect.Parameter.empty for p in params)
    # 没有 keyword-only 的“跳过授权”开关。
    assert not any(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params)


def test_protected_factory_has_no_bypass_flag():
    """不得有 skip_auth / disable_auth / open 之类的旁路参数。"""
    sig = inspect.signature(create_protected_free_task_blueprint)
    names = {p.name.lower() for p in sig.parameters.values()}
    forbidden_tokens = ("skip", "bypass", "disable", "no_auth", "open", "insecure")
    for token in forbidden_tokens:
        assert not any(token in name for name in names), (
            f"受保护工厂不应包含疑似旁路参数: {token}"
        )


def test_protected_blueprint_name_is_distinct(store, authorizer):
    """受保护蓝图名固定且与旧的未保护蓝图不同。"""
    bp = create_protected_free_task_blueprint(store, authorizer)
    assert bp.name == "free_task_protected_preview"
    assert bp.url_prefix == URL_PREFIX


# ---------------------------------------------------------------------------
# H. 未授权 → 401，且不接触账本
# ---------------------------------------------------------------------------

def test_post_without_authorization_is_401_and_writes_nothing(client, store):
    """POST 完全不带 Authorization → 401，事件列表不变。"""
    response = post(client, post_body("sess-h", "h-1", start_payload()))
    assert response.status_code == 401
    assert error_of(response) == UNAUTHORIZED_CODE
    assert store.list_events("sess-h") == []
    assert store.get_summary("sess-h")["event_count"] == 0


def test_post_with_wrong_credential_is_401_and_writes_nothing(client, store):
    """错误凭据 → 401，事件列表不变。"""
    response = post(
        client,
        post_body("sess-h", "h-2", start_payload()),
        headers=auth_headers(FAKE_BAD_AUTHORIZATION_HEADER),
    )
    assert response.status_code == 401
    assert error_of(response) == UNAUTHORIZED_CODE
    assert store.list_events("sess-h") == []


def test_get_summary_without_authorization_is_401(client, store):
    """GET summary 未授权 → 401（读路径同样受保护）。"""
    response = get_summary(client, "sess-h")
    assert response.status_code == 401
    assert error_of(response) == UNAUTHORIZED_CODE


def test_get_summary_with_wrong_credential_is_401(client, store):
    response = get_summary(client, "sess-h", headers=auth_headers(FAKE_BAD_AUTHORIZATION_HEADER))
    assert response.status_code == 401
    assert error_of(response) == UNAUTHORIZED_CODE


def test_get_summary_unauthorized_does_not_expose_summary(client, store):
    """未授权 GET 绝不泄漏 summary 内容。"""
    # 先用授权通道写入一条事件，确保账本里确实有数据。
    assert authed_post(client, post_body("sess-h", "h-1", start_payload())).status_code == 200
    # 未授权 GET 拿不到 summary。
    response = get_summary(client, "sess-h")
    assert response.status_code == 401
    body = response.get_json()
    assert "summary" not in body
    assert set(body) == {"ok", "error"}


def test_unauthorized_never_returns_200(client):
    """未授权路径上的任何请求都不得返回 200。"""
    assert post(client, post_body("sess-x", "x-1", start_payload())).status_code == 401
    assert post(
        client,
        post_body("sess-x", "x-1", start_payload()),
        headers=auth_headers(FAKE_BAD_AUTHORIZATION_HEADER),
    ).status_code == 401
    assert get_summary(client, "sess-x").status_code == 401
    assert get_summary(
        client, "sess-x", headers=auth_headers(FAKE_BAD_AUTHORIZATION_HEADER)
    ).status_code == 401


def test_unauthorized_response_does_not_echo_credential(client):
    """401 文案不得回显任何凭据内容（含“正确”凭据也绝不回显）。"""
    wrong = post(
        client,
        post_body("sess-x", "x-1", start_payload()),
        headers=auth_headers(FAKE_BAD_AUTHORIZATION_HEADER),
    )
    raw = wrong.get_data(as_text=True)
    assert FAKE_BAD_AUTHORIZATION_HEADER not in raw
    assert "SYNTHETIC" not in raw
    assert "Bearer" not in raw
    # 也没有把请求头整体反射出来。
    assert "Authorization" not in raw


def test_401_json_shape_is_the_fixed_contract(client):
    response = get_summary(client, "sess-shape")
    body = response.get_json()
    assert set(body) == {"ok", "error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == UNAUTHORIZED_CODE


# ---------------------------------------------------------------------------
# I. 正确授权 → 业务合同完全不变
# ---------------------------------------------------------------------------

def test_authorized_full_session_flow(client, store):
    """正确授权：started → completed → GET summary 全链路。"""
    r1 = authed_post(client, post_body("sess-1", "evt-1", start_payload()))
    assert r1.status_code == 200, r1.get_data(as_text=True)
    b1 = r1.get_json()
    assert b1["ok"] is True and b1["action"] == "append"
    assert b1["summary"]["event_count"] == 1

    r2 = authed_post(client, post_body("sess-1", "evt-2", completion_payload()))
    assert r2.status_code == 200
    assert r2.get_json()["summary"]["successful_tasks"] == 1

    r3 = authed_get(client, "sess-1")
    assert r3.status_code == 200
    b3 = r3.get_json()
    assert b3["action"] == "summary"
    assert b3["summary"]["event_count"] == 2
    assert b3["summary"]["effective_study_minutes"] == 25
    assert len(store.list_events("sess-1")) == 2


def test_authorized_summary_marks_user_report(client):
    """授权 GET 保留既有“用户自报”标注。"""
    assert authed_post(client, post_body("sess-u", "u-1", start_payload())).status_code == 200
    r = authed_get(client, "sess-u")
    assert r.status_code == 200
    assert r.get_json()["summary"]["verification"] == "user_reported_not_independently_verified"


def test_authorized_error_classification_unchanged(client, store):
    """受保护蓝图中 415 / 400 / 409 分类与旧的未保护合同一致。"""
    # 415：非 JSON 内容类型
    r415 = client.post(
        f"{URL_PREFIX}/events",
        data=b"action=append",
        content_type="application/x-www-form-urlencoded",
        headers=auth_headers(),
    )
    assert r415.status_code == 415 and error_of(r415) == "unsupported_media_type"

    # 400：action 非 append
    r400 = authed_post(client, {"action": "summary", "session_id": "s"})
    assert r400.status_code == 400 and error_of(r400) == "action_not_append"

    # 409：未 started 就完成
    r409 = authed_post(client, post_body("sess-nostart", "n-1", completion_payload()))
    assert r409.status_code == 409 and error_of(r409) == "session_not_started"

    # 上述失败都没写库。
    assert store.list_events("sess-nostart") == []


def test_malformed_body_with_valid_auth_maps_to_existing_codes(client, store):
    """请求体畸形但授权通过 → 仍走既有 4xx 分类（不被授权闸门改写）。"""
    bad_json = client.post(
        f"{URL_PREFIX}/events", data=b"{not json", content_type="application/json",
        headers=auth_headers(),
    )
    assert bad_json.status_code == 400 and error_of(bad_json) == "invalid_json"

    not_object = client.post(
        f"{URL_PREFIX}/events", data=b"[]", content_type="application/json",
        headers=auth_headers(),
    )
    assert not_object.status_code == 400 and error_of(not_object) == "body_not_object"

    unknown_field = authed_post(
        client, {**post_body("sess-m", "m-1", start_payload()), "force": True}
    )
    assert unknown_field.status_code == 400
    assert error_of(unknown_field) == "adapter_request_unknown_field"
    assert store.list_events("sess-m") == []


# ---------------------------------------------------------------------------
# J. 授权器抛异常 → fail closed 503，且不泄漏敏感内容
# ---------------------------------------------------------------------------

@pytest.fixture()
def raising_client(store):
    exc = RuntimeError("secret-token-abc123 db-password=hunter2")
    return build_protected_app(store, make_raising_authorizer(exc)).test_client()


def test_authorizer_exception_is_503_not_200(raising_client, store):
    r = post(raising_client, post_body("sess-j", "j-1", start_payload()))
    assert r.status_code == 503
    assert error_of(r) == AUTHORIZATION_UNAVAILABLE_CODE
    assert store.list_events("sess-j") == []


def test_authorizer_exception_on_get_is_503(raising_client):
    r = get_summary(raising_client, "sess-j")
    assert r.status_code == 503
    assert error_of(r) == AUTHORIZATION_UNAVAILABLE_CODE


def test_authorizer_exception_does_not_leak_sensitive_content(raising_client):
    """503 响应绝不回显异常文本、异常类型名或任何 secret。"""
    r = post(raising_client, post_body("sess-j", "j-1", start_payload()))
    raw = r.get_data(as_text=True)
    for forbidden in ("secret-token", "abc123", "hunter2", "db-password", "RuntimeError"):
        assert forbidden not in raw, f"503 响应泄漏了敏感内容: {forbidden}"
    # 通用文案，不含异常类型名。
    assert "RuntimeError" not in raw
    assert error_of(r) == AUTHORIZATION_UNAVAILABLE_CODE


def test_false_and_exception_are_distinguished(store):
    """明确区分：返回 False → 401；抛异常 → 503。"""
    false_client = build_protected_app(
        store, make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)
    ).test_client()
    r_false = get_summary(false_client, "s")  # 无凭据 → authorizer 返回 False
    assert r_false.status_code == 401

    raising_client = build_protected_app(
        store, make_raising_authorizer(ValueError("boom"))
    ).test_client()
    r_exc = get_summary(raising_client, "s")
    assert r_exc.status_code == 503
    # 两个 code 不同，明确区分。
    assert error_of(r_false) == UNAUTHORIZED_CODE
    assert error_of(r_exc) == AUTHORIZATION_UNAVAILABLE_CODE
    assert UNAUTHORIZED_CODE != AUTHORIZATION_UNAVAILABLE_CODE


def test_ledger_unchanged_after_rejected_then_authorized(client, store):
    """被拒请求不改账本；随后授权请求正常写入（账本保持一致）。"""
    # 一串被拒请求（无凭据 / 错凭据）
    for _ in range(3):
        assert post(client, post_body("sess-k", "k-1", start_payload())).status_code == 401
        assert get_summary(client, "sess-k").status_code == 401
    assert store.get_summary("sess-k")["event_count"] == 0

    # 正确授权 → 写入成功，账本只包含这一条（没有重复/幽灵事件）。
    r = authed_post(client, post_body("sess-k", "k-1", start_payload()))
    assert r.status_code == 200
    events = store.list_events("sess-k")
    assert len(events) == 1
    assert events[0]["event_id"] == "k-1"


# ---------------------------------------------------------------------------
# K. 边界与不回退
# ---------------------------------------------------------------------------

def test_e_group_opt_in_still_works_with_protected_blueprint(store, authorizer):
    """E 组 opt-in 行为在受保护蓝图上不回退。"""
    app = build_protected_app(store, authorizer, opt_in_errors=True)
    client = app.test_client()
    # preview 前缀下匹配阶段 404 → 统一 JSON。
    r404 = client.get(f"{URL_PREFIX}/nope")
    assert r404.status_code == 404 and error_of(r404) == "not_found"
    # preview 前缀下匹配阶段 405 → 统一 JSON（授权闸门不介入匹配阶段）。
    r405 = client.get(f"{URL_PREFIX}/events")
    assert r405.status_code == 405 and error_of(r405) == "method_not_allowed"
    # 正常授权路径仍工作。
    assert authed_post(client, post_body("sess-e", "e-1", start_payload())).status_code == 200


def test_protected_blueprint_405_and_404_without_opt_in(store, authorizer):
    """默认（不 opt-in）：状态码仍是 404 / 405（授权不改状态码语义）。"""
    client = build_protected_app(store, authorizer, opt_in_errors=False).test_client()
    assert client.get(f"{URL_PREFIX}/nope").status_code == 404
    assert client.get(f"{URL_PREFIX}/events").status_code == 405


def test_old_unprotected_factory_still_has_no_auth(store):
    """旧的未保护工厂保留既有合成合同，且 **明确无认证**（禁止生产）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_free_task_blueprint(store))
    client = app.test_client()

    # 无任何 Authorization 头依然 200 —— 证明它确实无认证（合成预览用）。
    r = client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(post_body("sess-old", "o-1", start_payload())).encode("utf-8"),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert client.get(f"{URL_PREFIX}/sessions/sess-old/summary").status_code == 200


def test_protected_and_unprotected_cannot_coexist_in_one_app(store, authorizer):
    """**取代**旧主张 ``test_protected_and_unprotected_can_coexist`` 的安全契约。

    旧契约声称“同一 app 可同时注册无认证版与受保护版，前缀冲突交给 Flask
    裁决”。F Review 已实际复现：先注册无认证版再注册受保护版时，无凭证
    ``POST /api/free-tasks/events`` 仍返回 200 且 ``FakeStore`` 被写入 1 条
    事件 —— 即严重授权绕过。G 已在
    ``server/blueprints/free_task_bp.py`` 加入 **注册阶段** fail-closed
    冲突检测，本测试改为刻画该安全契约：

      1. ``unprotected -> protected``：第二次注册 **立刻** 抛
         :class:`RuntimeError`；
      2. ``protected -> unprotected``：顺序不是安全模型，同样抛
         :class:`RuntimeError`；
      3. 先注册的那个蓝图 **不** 使二者共同正常提供服务；
      4. 冲突已发生时，无凭证 POST **不** 返回成功，且 **不** 新增任何
         store 事件。冲突态下该 app 整个 free-task 前缀返回 503 属
         **预期** fail-closed，本测试 **不** 要求该 app 继续可用；
      5. 各自 **独立** 的正常 app 中，旧的合成 preview 仍按 D/E 组
         synthetic-only 合同运行，独立受保护 preview 仍 401/503/200 规范。
    """
    # -- 顺序一：unprotected -> protected ------------------------------------
    app_legacy_first = Flask(__name__)
    app_legacy_first.config["TESTING"] = True
    app_legacy_first.register_blueprint(create_free_task_blueprint(store))
    legacy_names = {b.name for b in app_legacy_first.blueprints.values()}
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in legacy_names

    with pytest.raises(RuntimeError) as exc_legacy_first:
        app_legacy_first.register_blueprint(
            create_protected_free_task_blueprint(store, authorizer)
        )

    # 被拒的受保护蓝图没有落进 app；不存在两个蓝图共同正常服务的形态。
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME not in app_legacy_first.blueprints
    assert app_legacy_first.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is True
    conflict_message = str(exc_legacy_first.value)
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in conflict_message
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME in conflict_message
    # 冲突文案不得泄漏凭据。
    assert FAKE_AUTHORIZATION_HEADER not in conflict_message
    assert "Bearer" not in conflict_message
    assert "SYNTHETIC" not in conflict_message

    # -- 顺序二：protected -> unprotected ------------------------------------
    app_protected_first = Flask(__name__)
    app_protected_first.config["TESTING"] = True
    app_protected_first.register_blueprint(
        create_protected_free_task_blueprint(store, authorizer)
    )

    with pytest.raises(RuntimeError) as exc_protected_first:
        app_protected_first.register_blueprint(create_free_task_blueprint(store))

    assert LEGACY_PREVIEW_BLUEPRINT_NAME not in app_protected_first.blueprints
    assert app_protected_first.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is True
    reverse_message = str(exc_protected_first.value)
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in reverse_message
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME in reverse_message
    assert FAKE_AUTHORIZATION_HEADER not in reverse_message

    # -- 冲突态：无凭证 POST 既不成功，也不写库 ------------------------------
    for conflicted_app, session in (
        (app_legacy_first, "sess-coexist-legacy-first"),
        (app_protected_first, "sess-coexist-protected-first"),
    ):
        client = conflicted_app.test_client()
        response = post(
            client, post_body(session, "cf-1", start_payload())
        )  # 无任何 Authorization 头
        assert response.status_code != 200, "冲突态 app 不得把未授权 POST 放行为 200"
        assert response.status_code == 503
        assert error_of(response) == REGISTRATION_CONFLICT_CODE
        assert store.list_events(session) == []
        assert store.get_summary(session)["event_count"] == 0

    # -- 各自独立 app：旧合成 preview 合同（D/E synthetic-only）不回退 ------
    legacy_only = Flask(__name__)
    legacy_only.config["TESTING"] = True
    legacy_only.register_blueprint(create_free_task_blueprint(store))
    legacy_client = legacy_only.test_client()
    assert legacy_client.post(
        f"{URL_PREFIX}/events",
        data=json.dumps(
            post_body("sess-standalone-legacy", "l-1", start_payload())
        ).encode("utf-8"),
        content_type="application/json",
    ).status_code == 200  # 明确无认证的旧合成预览
    assert len(store.list_events("sess-standalone-legacy")) == 1

    # -- 各自独立 app：受保护 preview 的 401 / 503 / 200 规范不回退 --------
    protected_only_client = build_protected_app(store, authorizer).test_client()
    assert post(
        protected_only_client, post_body("sess-standalone-protected", "p-1", start_payload())
    ).status_code == 401
    assert error_of(
        get_summary(protected_only_client, "sess-standalone-protected")
    ) == UNAUTHORIZED_CODE

    raising_only_client = build_protected_app(
        store, make_raising_authorizer(RuntimeError("synthetic-boom"))
    ).test_client()
    raising_response = post(
        raising_only_client, post_body("sess-standalone-protected", "p-2", start_payload())
    )
    assert raising_response.status_code == 503
    assert error_of(raising_response) == AUTHORIZATION_UNAVAILABLE_CODE

    assert authed_post(
        protected_only_client, post_body("sess-standalone-protected", "p-3", start_payload())
    ).status_code == 200


def test_module_does_not_import_production_wiring():
    """模块绝不 import 真实 app_factory / backend_api（不自动接生产）。"""
    tree = ast.parse(Path(free_task_bp.__file__).read_text(encoding="utf-8"))
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


def _code_string_constants(tree) -> list:
    """所有 **非 docstring** 的字符串常量（真正会进入运行的字面量）。"""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_module_contains_no_real_secret_or_default_token():
    """模块不含真实秘钥 / 默认 token / 硬编码凭据常量。

    只看会真正运行的字符串字面量（docstring 是说明文字，不是凭据）。
    """
    tree = ast.parse(Path(free_task_bp.__file__).read_text(encoding="utf-8"))
    literals = _code_string_constants(tree)
    # 断言用的探针本身必须有效：先证明该提取方式不是空转。
    assert literals, "提取逻辑失效：不应返回空字面量列表"
    for literal in literals:
        low = literal.lower()
        for token in ("bearer ", "sk-", "api_key", "apikey", "password", "token="):
            assert token not in low, f"模块疑似含默认凭据/秘密: {literal!r}"


def test_module_never_reads_credentials_itself():
    """授权判定完全交给调用方：模块自身 **绝不** 读 Authorization 头。

    这条保证“凭据来源不在本模块定义”，也保证工厂不可能自带默认放行逻辑。
    """
    tree = ast.parse(Path(free_task_bp.__file__).read_text(encoding="utf-8"))
    header_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "headers"
    ]
    assert header_reads == [], "模块不应直接读取 request.headers（授权必须完全注入）"
    # 允许出现的只有本模块 **自己声明** 的公开常量（名字或其取值）；
    # 任何其它含 "authorization" 的字面量（例如硬编码 header 名或凭据）都拒绝。
    allowed_names = set(getattr(free_task_bp, "__all__", ()))
    allowed_values = {
        value
        for value in (
            getattr(free_task_bp, name, None) for name in allowed_names
        )
        if isinstance(value, str)
    }
    offenders = [
        literal
        for literal in _code_string_constants(tree)
        if "authorization" in literal.lower()
        and literal not in allowed_names
        and literal not in allowed_values
    ]
    assert offenders == [], f"模块含疑似凭据来源字面量: {offenders!r}"


def test_protected_factory_does_not_touch_files_or_network_at_construction(
    store, authorizer, monkeypatch, sandbox
):
    """构造期/import 期：不读配置、不碰文件、不联网（全部依赖注入）。"""
    # 让任何 socket 连接直接失败，证明构造过程不联网。
    import socket as socket_module

    def _no_net(*_a, **_k):
        raise AssertionError("构造受保护蓝图时不得联网")

    monkeypatch.setattr(socket_module.socket, "connect", _no_net)
    # 构造蓝图本身不得创建任何文件。
    before_files = sorted(p.name for p in sandbox.iterdir())
    bp = create_protected_free_task_blueprint(store, authorizer)
    assert bp is not None
    after_files = sorted(p.name for p in sandbox.iterdir())
    assert before_files == after_files


def test_request_object_is_passed_to_authorizer(store):
    """authorizer 收到的确实是当前 Flask request（契约固定）。"""
    seen = {}

    def _spy(request):
        seen["path"] = request.path
        seen["method"] = request.method
        return True

    client = build_protected_app(store, _spy).test_client()
    r = client.get(f"{URL_PREFIX}/sessions/sess-q/summary")
    assert r.status_code == 200
    assert seen["path"] == f"{URL_PREFIX}/sessions/sess-q/summary"
    assert seen["method"] == "GET"


def test_authorizer_sees_request_before_any_ledger_work(store):
    """授权闸门在账本之前：授权器看到请求，且 store 尚未被写。"""
    order = []

    def _spy(request):
        order.append("authorize")
        return True

    client = build_protected_app(store, _spy).test_client()
    authed_post(client, post_body("sess-o", "o-1", start_payload()))
    assert order == ["authorize"]  # 只授权了一次，先于后续写入


def test_headers_helper_is_werkzeug_compatible():
    """小自检：测试用的 header 构造与 Flask 兼容（防测试自身假绿）。"""
    headers = Headers({"Authorization": FAKE_AUTHORIZATION_HEADER})
    assert headers.get("Authorization") == FAKE_AUTHORIZATION_HEADER


def test_preview_url_prefix_constant_unchanged():
    assert PREVIEW_URL_PREFIX == URL_PREFIX


def test_unauthenticated_options_is_also_gated(store, authorizer):
    """未授权的 OPTIONS 同样被授权闸门拦住（fail closed，绝不放行）。

    ``before_request`` 早于 Flask 的自动 OPTIONS 应答，因此自动应答也
    **不构成** 绕过保护的旁路。
    """
    client = build_protected_app(store, authorizer).test_client()
    response = client.options(f"{URL_PREFIX}/events")
    assert response.status_code == 401
    assert error_of(response) == UNAUTHORIZED_CODE

    # 带正确凭据时才恢复 Flask 原生的自动 OPTIONS 语义（200 + Allow）。
    authorized = client.options(
        f"{URL_PREFIX}/events", headers=auth_headers()
    )
    assert authorized.status_code == 200
    assert authorized.headers.get("Allow")