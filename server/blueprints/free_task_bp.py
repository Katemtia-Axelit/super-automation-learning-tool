"""server.blueprints.free_task_bp - 自由任务的 **隔离预览** HTTP API。

定位
----
这是一个 **工厂函数** 形态的独立 Blueprint：调用方必须显式注入一个
既有的 :class:`~server.services.free_task_events.FreeTaskEventStore`，
工厂才会产出一个可注册到 **任意** Flask app 的 Blueprint。

    from flask import Flask
    from server.blueprints.free_task_bp import create_free_task_blueprint
    from server.services.free_task_events import FreeTaskEventStore

    app = Flask(__name__)
    app.register_blueprint(
        create_free_task_blueprint(FreeTaskEventStore(r"/tmp/sandbox/events.db"))
    )

生产程序 **不会** 自动接线
--------------------------
- 本模块 **不读** ``config/config.json``、**不** 发现数据库、**不**
  import :mod:`server.app.app_factory`、**不** import
  :mod:`server.backend_api`、**不** 注册到任何既有生产 Blueprint；
- :func:`server.app.app_factory.create_app` **未被修改**，因此本 Blueprint
  **绝对不自动** 出现在真实应用里；
- 该接口 **没有** 认证、没有 CSRF、没有速率限制，**仅用于 synthetic
  测试 / 隔离预览**，**不得** 向生产公开。

路由（``url_prefix = /api/free-tasks``）
--------------------------------------
- ``POST /events`` —— 追加一个事件；
- ``GET  /sessions/<session_id>/summary`` —— 只读汇总。

受保护工厂（显式 opt-in 的授权入口）
------------------------------------
:func:`create_protected_free_task_blueprint` 是 **第二个、显式命名** 的工厂：
调用方 **必须** 同时注入 store 与 ``authorizer``，本模块对 ``authorizer``
做 **Blueprint 注册前 fail closed** 校验（缺失 / ``None`` / 非 callable →
直接抛 :class:`TypeError`）。因此“忘记注入授权规则” **不可能** 悄悄退化成
开放写入端点 —— 忘记注入的表现是 **启动即崩**，而不是静默放行。

``authorizer`` 契约
~~~~~~~~~~~~~~~~~~
``authorizer(request) -> bool`` —— 接收当前 Flask ``request``；返回
**真值** 表示放行，返回 ``False`` 表示拒绝。**异常 = 拒绝**（fail
closed），且异常内容 **绝不** 回显给客户端。

- 未授权 → HTTP 401 ``free_task_unauthorized``；
- ``authorizer`` 抛异常 → HTTP 503 ``free_task_authorization_unavailable``
  （通用文案，不泄漏异常体或任何秘密）。

两个工厂的关系
~~~~~~~~~~~~~~
- :func:`create_free_task_blueprint` —— **旧合成合同，无认证**，仅限
  synthetic 预览，语义保持不变以维持既有测试；
- :func:`create_protected_free_task_blueprint` —— **本轮新入口**，用于后续
  安全 Factory opt-in 接线时 **强制** 注入授权规则。

两者 Blueprint **名** 不同（``free_task_protected_preview``），但 **同一个
Flask app 上必须只存在其中一个**。

互斥契约（注册期 fail closed）
------------------------------
两个蓝图共用同一 ``url_prefix``（``/api/free-tasks``），而 Flask 的 URL
匹配是 **first-match 优先**。因此 “无认证版本先注册 + 受保护版本后注册”
的组合会让 **未认证** 的 ``POST /api/free-tasks/events`` 返回 200 并真的
写入事件 —— 授权闸门被完全绕过。

注册顺序 **不得** 成为安全模型，因此本模块在 **Blueprint 注册阶段**
（早于任何请求、且早于路由写入 ``url_map``）就 fail closed：

- 检测依据是 Blueprint 自身携带的 **角色标记**（``free_task_role``），
  **不是** “注册名是否相同”。两个工厂名字本来就不同，按名字相等检测必然
  漏检；按角色检测则 **名字不同也照样命中**；
- 兜底再查 ``app.blueprints``（按对象 ``name`` 与注册键）与
  ``app.url_map``（按 endpoint 前缀），覆盖 ``name=`` 改名与手工同名
  Blueprint 等形态；
- 命中即抛 :class:`RuntimeError`，**绝不** 只警告后继续；错误文案 **不**
  泄漏任何凭据；
- 同时把该 app 标记为配置冲突，并安装一道 **前缀精确** 的 503 闸门，
  使这个 “半装配” 的 app **无法再提供任何自由任务写入**（未认证写入彻底
  不可能，事件不可能落库）；
- 守卫同时挂在 :meth:`flask.Blueprint.register` 覆盖与 Flask 官方
  ``record_once`` 钩子上，两层都在 **路由生效之前** 触发，**不依赖请求到达**
  才被检查。

请求契约（POST /events）
-----------------------
请求体必须是 ``Content-Type: application/json`` 的 **JSON 对象**，其键
**恰好** 为 ``{action, session_id, event_id, event_payload}``，全部必需；
``action`` 必须严格等于 ``"append"``。

    {
      "action": "append",
      "session_id": "sess-1",
      "event_id": "evt-1",
      "event_payload": {"event_type": "free_task.started", ...}
    }

``event_payload`` 的字段形状以真实领域层
(:mod:`server.services.free_task_domain` /
:mod:`server.services.free_task_events`) 为准，本模块 **不** 复制那套
校验规则，只做 HTTP 形状校验 + 错误分类。

响应契约
--------
成功（HTTP 200）—— 适配层返回值 **原样透传**::

    {"ok": true, "action": "append", "summary": { ... 账本 summary ... }}

失败（4xx/5xx）—— 固定形状::

    {"ok": false, "error": {"code": "<稳定 code>", "message": "<中文说明>"}}

错误码与状态码
--------------
=  ==========================  ==========================================
    状态                      触发条件 / code
=  ==========================  ==========================================
400                        ``empty_body`` / ``invalid_json`` /
                               ``body_not_object`` / ``action_not_append`` /
                               ``adapter_*``（形状校验）/
                               账本 ``*_invalid`` / ``*_required`` 等
    404                        未知路由（``not_found``；**默认**只有本 Blueprint
                               视图抛出时才是 JSON）
   405                        方法不允许（``method_not_allowed``；**默认**同上）
   409                        ``event_conflict`` / ``illegal_state_order`` /
                               ``duplicate_completion`` /
                               ``session_not_started``
   415                        非 JSON 内容类型（``unsupported_media_type``）
   503                        ``db_busy``（数据库被占用，可重试）
   500                        任何未预期异常（``internal_error`` /
                               ``internal_sqlite_error``，细节只进日志，
                               绝不伪报成功）
=  ==========================  ==========================================

404 / 405 语义
-------------
**默认（什么都不做）**：本模块 **刻意不安装 app 级错误处理器** —— 那会改变
生产应用既有的全局行为。因此 URL 匹配阶段（路由不存在 / 方法不允许）由
Flask/werkzeug 处理，保留 **标准状态码** 404 / 405 与其 **默认 HTML 响应体**；
由本 Blueprint 视图显式抛出的 404 / 405 则被 ``bp.errorhandler`` 转成统一
JSON 形状。注意 Flask 3.1 起 Blueprint 级 errorhandler **不会** 捕获 URL
匹配阶段的 404/405 —— 这正是默认行为 “状态码正确、body 不是 JSON” 的原因。

**显式 opt-in（仅限 synthetic app）**：隔离预览若需要“匹配阶段也返回统一
JSON”，必须由调用方在自己的 **独立 synthetic Flask app** 上显式调用
:func:`register_free_task_preview_errors`。默认的
:func:`create_free_task_blueprint` **绝不** 注册它。

行为红线
--------
- **不隐式创建事件**：GET 只读；POST 必须携带完整 payload，缺字段 → 400。
- **不因定时器结束自动完成**：``free_task.timer_elapsed`` 由账本裁决，
  本模块 不 折算任何数字。
- **异常不被吞掉**：``sqlite3`` / ``OSError`` / 未知异常一律 → 500
  ``internal_error`` 并记录日志，绝不返回“成功”。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Tuple

from flask import Blueprint, current_app, jsonify, request

from server.services.free_task_adapter import (
    APPEND_ALLOWED_KEYS,
    FreeTaskAdapter,
    FreeTaskAdapterError,
)

#: 唯一受支持的 POST 动作（端点本身就是 append，summary 走 GET）。
REQUIRED_ACTION = "append"

#: POST /events 允许的键集（与稳定公共适配器契约同源，绝不在此处另立一份）。
ALLOWED_POST_KEYS = APPEND_ALLOWED_KEYS

#: 会话级冲突类账本错误码 → HTTP 409。
_CONFLICT_CODES = frozenset(
    {
        "event_conflict",
        "illegal_state_order",
        "duplicate_completion",
        "session_not_started",
    }
)

#: 可重试的账本错误码 → HTTP 503。
_RETRYABLE_CODES = frozenset({"db_busy"})


# ---------------------------------------------------------------------------
# 双工厂互斥契约（注册期 fail closed）
# ---------------------------------------------------------------------------
#
# 契约（不可协商）
# ~~~~~~~~~~~~~~~~
# **同一个 Flask app 绝对不得同时拥有** “旧的无认证预览”与 “受保护预览”
# 两个工厂的实例。两个 Blueprint 共用同一 ``url_prefix``（``/api/free-tasks``），
# 而 Flask 的 URL 匹配是 **first-match 优先**：先注册的那份路由会先被匹配，
# 于是 “无认证版本在前 + 受保护版本在后” 的组合会让 **未认证** 的
# ``POST /api/free-tasks/events`` 返回 200 并真的写入事件 —— 授权闸门被
# 完全绕过。注册顺序 **不得** 成为安全模型，因此两种顺序都必须 fail closed。
#
# 检测方式
# ~~~~~~~~
# 在 **Blueprint 注册阶段**（即 Flask 把路由写入 ``app.url_map``、把
# ``before_request`` 合并进 app **之前**）判定：
#
# - 判定依据是 Blueprint 自身携带的 **角色标记**（``free_task_role``），
#   而不是“注册名是否相同”。两个工厂的 Blueprint **名字本来就不同**
#   （``free_task_preview`` vs ``free_task_protected_preview``），若只按
#   “同一个名字” 检测就会漏检；按角色检测则 **名字不同也照样命中**；
# - 同时兜底检查 ``app.blueprints`` 与 ``app.url_map``（按规范名匹配），
#   以覆盖 “手工构造了同名 Blueprint” 与 “用 ``name=`` 改了注册名” 的情形；
# - 命中即抛 :class:`RuntimeError`，**绝不** 只警告后继续；
# - 抛错前把该 app 标记为 **配置冲突** 并安装一道 **只覆盖
#   ``/api/free-tasks`` 前缀** 的 503 闸门，使这个“半装配”的 app 无法再
#   提供任何自由任务写入（未认证写入彻底不可能）。

#: 旧的无认证工厂的规范蓝图名。
LEGACY_PREVIEW_BLUEPRINT_NAME = "free_task_preview"

#: 受保护工厂的规范蓝图名。
PROTECTED_PREVIEW_BLUEPRINT_NAME = "free_task_protected_preview"

#: 角色标记：旧的无认证预览（**禁止生产使用**）。
ROLE_LEGACY_UNPROTECTED = "legacy_unprotected"

#: 角色标记：受保护预览。
ROLE_PROTECTED = "protected"

#: 规范蓝图名 → 角色标记。
_ROLE_BY_CANONICAL_NAME = {
    LEGACY_PREVIEW_BLUEPRINT_NAME: ROLE_LEGACY_UNPROTECTED,
    PROTECTED_PREVIEW_BLUEPRINT_NAME: ROLE_PROTECTED,
}

#: 角色标记 → 规范蓝图名。
_CANONICAL_NAME_BY_ROLE = {v: k for k, v in _ROLE_BY_CANONICAL_NAME.items()}

#: 冲突被拒后，该 app 上自由任务前缀请求的稳定 code（HTTP 503）。
REGISTRATION_CONFLICT_CODE = "free_task_registration_conflict"

#: 冲突被拒后返回给客户端的 **通用** 文案（不含任何凭据 / 内部细节）。
REGISTRATION_CONFLICT_MESSAGE = "自由任务预览注册冲突，该请求已被拒绝"

#: app.config 中标记“本 app 曾发生注册冲突”的键。
REGISTRATION_CONFLICT_CONFIG_KEY = "LT_FREE_TASK_REGISTRATION_CONFLICT"

#: 注册冲突闸门函数的固定名字（用于幂等去重）。
_CONFLICT_GUARD_NAME = "_free_task_registration_conflict_guard"


# ---------------------------------------------------------------------------
# 响应构造
# ---------------------------------------------------------------------------

def _fail(code: str, message: str, status: int) -> Tuple[Any, int]:
    """统一失败形状：``{"ok": False, "error": {"code", "message"}}``。"""
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status


def _ledger_status(code: str) -> int:
    """账本错误码 → HTTP 状态。

    - 冲突 / 状态机 / 会话顺序 → 409；
    - 库被占用 → 503（可重试）；
    - 其余（输入非法、payload 损坏等）→ 400。
    """
    if code in _CONFLICT_CODES:
        return 409
    if code in _RETRYABLE_CODES:
        return 503
    return 400


# ---------------------------------------------------------------------------
# 授权：未授权 / 授权检查故障（两者都 **绝不** 接触账本）
# ---------------------------------------------------------------------------

#: 未授权时的稳定 code（HTTP 401）。
UNAUTHORIZED_CODE = "free_task_unauthorized"

#: ``authorizer`` 自身故障时的稳定 code（HTTP 503，fail closed）。
AUTHORIZATION_UNAVAILABLE_CODE = "free_task_authorization_unavailable"

#: 客户端可见的 **通用** 文案。刻意 **不含** 异常类型名、异常文本、请求内容
#: 或任何凭据 —— 异常细节只写服务端日志。
UNAUTHORIZED_MESSAGE = "缺少或无效的授权凭据，请求已被拒绝"
AUTHORIZATION_UNAVAILABLE_MESSAGE = "授权检查暂时不可用，请求已被拒绝"


def _authorize_or_reject(authorizer: Any):
    """执行授权判定；放行返回 ``None``，拒绝返回待返回的失败响应。

    三态被 **明确区分**（绝不混淆）：

    - 返回 **真值** → 放行（``None``）；
    - 返回 **假值**（``False`` / ``None`` / ``0`` …）→ HTTP 401
      ``free_task_unauthorized`` —— 是调用方没通过授权；
    - **抛异常** → HTTP 503 ``free_task_authorization_unavailable`` ——
      是授权检查本身坏了，因此 **fail closed** 拒绝。

    任何一种拒绝都在触碰 :class:`FreeTaskAdapter` / 账本 **之前** 返回，
    所以被拒请求 **不会** 创建事件、**不会** 改变既有账本。
    """
    try:
        allowed = authorizer(request)
    except Exception as exc:  # 授权器故障：fail closed，且绝不回显异常内容
        current_app.logger.exception(
            "free-task 授权检查异常（已 fail closed）: %s: %s",
            type(exc).__name__,
            exc,
        )
        return _fail(
            AUTHORIZATION_UNAVAILABLE_CODE,
            AUTHORIZATION_UNAVAILABLE_MESSAGE,
            503,
        )

    if not allowed:
        return _fail(UNAUTHORIZED_CODE, UNAUTHORIZED_MESSAGE, 401)
    return None


# ---------------------------------------------------------------------------
# 双工厂互斥：注册期检测
# ---------------------------------------------------------------------------

def _role_of_blueprint(bp: Any) -> str | None:
    """判定一个 Blueprint 属于哪个自由任务预览角色。

    优先使用 Blueprint 自身携带的角色标记（:func:`_build_free_task_blueprint`
    在构造时写入），回退到 **规范蓝图名** 映射。两者都拿不到 → ``None``
    （不是自由任务预览蓝图，与本守卫无关）。
    """
    role = getattr(bp, "free_task_role", None)
    if role in (ROLE_LEGACY_UNPROTECTED, ROLE_PROTECTED):
        return role
    name = getattr(bp, "name", None)
    return _ROLE_BY_CANONICAL_NAME.get(name)


def _find_conflicting_role(app: Any, role: str) -> str | None:
    """在 ``app`` 上找出与 ``role`` **互斥** 的自由任务预览蓝图。

    返回冲突方的角色标记；没有冲突 → ``None``。

    检查面（刻意冗余，避免任何一种注册形态漏检）：

    1. ``app.blueprints`` 的 **值**（Blueprint 对象）——用 ``bp.name`` 判定，
       因此即使用 ``name=`` 改了注册名也照样命中；
    2. ``app.blueprints`` 的 **键**（注册名）——覆盖 “手工构造同名
       Blueprint” 的情形；
    3. ``app.url_map`` 中已有规则的 endpoint 前缀 —— 覆盖 “路由已生效但
       Blueprint 记录被绕过” 的情形。

    **只看角色，不看名字是否相同**：两个工厂的名字本来就不同
    （``free_task_preview`` vs ``free_task_protected_preview``），按名字相等
    检测必然漏检；按角色检测则名字不同也照样命中。
    """
    blueprints = getattr(app, "blueprints", None) or {}
    for bp in blueprints.values():
        if bp is None:
            continue
        other = _role_of_blueprint(bp)
        if other is not None and other != role:
            return other
    for key in blueprints:
        other = _ROLE_BY_CANONICAL_NAME.get(key)
        if other is not None and other != role:
            return other

    url_map = getattr(app, "url_map", None)
    if url_map is not None:
        try:
            rules = list(url_map.iter_rules())
        except Exception:  # pragma: no cover - url_map 异常时不做判定
            rules = []
        for rule in rules:
            endpoint = getattr(rule, "endpoint", "") or ""
            if "." not in endpoint:
                continue
            blueprint_name = endpoint.rsplit(".", 1)[0]
            other = _ROLE_BY_CANONICAL_NAME.get(blueprint_name)
            if other is not None and other != role:
                return other
    return None


def _install_registration_conflict_block(app: Any) -> None:
    """把发生注册冲突的 app 变成 **不可服务** 状态。

    冲突发生时，先注册的蓝图可能已经把 “无认证” 路由写进了 ``url_map``。
    为了保证 “未认证 POST 绝不 200、绝不写库”，这里安装一道 **前缀精确**
    的闸门：冲突发生后，该 app 上落在 ``/api/free-tasks``（及其子路径）下的
    请求一律返回 HTTP 503 固定 JSON。

    - 闸门挂在 **app 级** ``before_request``，早于任何蓝图级闸门；
    - 响应是固定形状 ``{"ok": false, "error": {...}}``，**不含** 任何凭据、
      异常文本或内部路径；
    - **前缀精确**：``/api/free-tasks-old``、``/api/free-tasksXYZ`` 等
      **形似但不是同一路径** 的前缀不受影响（与 :func:`_is_preview_request`
      的判定保持一致）；
    - 幂等：重复安装不会叠加多道闸门。
    """
    config = getattr(app, "config", None)
    if isinstance(config, dict):
        config[REGISTRATION_CONFLICT_CONFIG_KEY] = True

    def _free_task_registration_conflict_guard():
        # 只拦截 **精确** 的自由任务预览前缀；其它路径原样放行。
        if not _is_preview_request(request):
            return None
        return (
            jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": REGISTRATION_CONFLICT_CODE,
                        "message": REGISTRATION_CONFLICT_MESSAGE,
                    },
                }
            ),
            503,
        )

    existing = getattr(app, "before_request_funcs", None)
    if isinstance(existing, dict):
        guards = existing.get(None) or []
        for guard in guards:
            if getattr(guard, "__name__", "") == _CONFLICT_GUARD_NAME:
                return  # 已安装过 → 幂等
    try:
        app.before_request(_free_task_registration_conflict_guard)
        return
    except Exception:
        # setup 已结束（app 已处理过请求）时 setupmethod 会拒绝；
        # 退回到直接写入 ``before_request_funcs``，保证闸门一定装上。
        pass
    try:
        app.before_request_funcs.setdefault(None, []).append(
            _free_task_registration_conflict_guard
        )
    except Exception:  # pragma: no cover - 极端情况下至少 RuntimeError 仍会抛出
        pass


def _assert_no_conflicting_free_task_blueprint(app: Any, role: str) -> None:
    """注册期 fail closed：同一 app 不得同时拥有两个互斥的自由任务蓝图。

    命中冲突时：

    1. 先把该 app 标记为配置冲突并安装 503 闸门（使其不可服务）；
    2. 再抛 :class:`RuntimeError`，错误文案 **不泄漏任何凭据**。
    """
    conflict = _find_conflicting_role(app, role)
    if conflict is None:
        return
    _install_registration_conflict_block(app)
    ours = _CANONICAL_NAME_BY_ROLE.get(role, role)
    theirs = _CANONICAL_NAME_BY_ROLE.get(conflict, conflict)
    raise RuntimeError(
        "同一个 Flask app 不得同时注册自由任务预览的受保护版本与无认证版本："
        f"检测到已注册角色 {theirs!r}，又尝试注册 {ours!r}。"
        "两个蓝图共用同一 URL 前缀且 Flask 按先匹配优先，"
        "组合后未认证请求会绕过授权闸门并写入事件，因此本次注册被拒绝。"
        "请为每个 app 只选择其中一个工厂。"
    )


class _FreeTaskPreviewBlueprint(Blueprint):
    """携带 **角色标记** 的自由任务预览 Blueprint。

    角色标记（``free_task_role``）是检测互斥的 **主依据**：它与 Blueprint
    **名字** 无关，因此 “两个工厂名字不同” 不会导致漏检。
    """

    def register(self, app, options):  # noqa: D102 - 覆盖 Flask 行为
        # 第一层闸门：在 Flask 把任何路由 / before_request 合并进 app
        # **之前** 判定，冲突则完全不改 app 状态并抛 RuntimeError。
        role = getattr(self, "free_task_role", None)
        if role is not None:
            _assert_no_conflicting_free_task_blueprint(app, role)
        return super().register(app, options)


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------

def create_free_task_blueprint(store: Any) -> Blueprint:
    """构造一个隔离的自由任务 Blueprint（**无认证**，仅限 synthetic 预览）。

    参数
    ----
    store:
        **必须由调用方显式注入** 的既有
        :class:`~server.services.free_task_events.FreeTaskEventStore`。
        本工厂 **绝不** 构造 store、**绝不** 提供默认路径、**绝不**
        发现数据库；``None`` 或行为不完整的对象 → 直接抛
        :class:`~server.services.free_task_adapter.FreeTaskAdapterError`。

    返回
    ----
    ``Blueprint('free_task_preview', url_prefix='/api/free-tasks')``。

    注意：Blueprint 名固定，因此 **同一个 app** 只能注册一次（重复注册会
    被 Flask 拒绝）。这是刻意设计：避免真实应用不小心注册两份。

    生产禁用（重要）
    ----------------
    本工厂产出的 Blueprint **没有任何认证**。凡是注册了真实用户的 app、
    共享 app 或任何非一次性合成 app，都 **禁止** 使用它：本轮 F 之后，
    面向生产的接线 **必须** 改用
    :func:`create_protected_free_task_blueprint`（强制注入 ``authorizer``）。
    """
    return _build_free_task_blueprint(store, blueprint_name="free_task_preview")


def create_protected_free_task_blueprint(store: Any, authorizer: Any) -> Blueprint:
    """构造 **强制受授权保护** 的自由任务 Blueprint。

    与 :func:`create_free_task_blueprint` 的唯一区别：``authorizer`` 是
    **必需** 的第二个参数，并且 **不存在任何“无授权也能构造”的形态**。

    参数
    ----
    store:
        同 :func:`create_free_task_blueprint`：必须显式注入既有 store。

    authorizer:
        **显式注入** 的 callable，契约固定为 ``authorizer(request) -> bool``。
        - 缺失 / ``None`` / 非 callable → **注册前** 直接抛
          :class:`TypeError`（fail closed）；**绝不**退化成“默认放行”；
        - 返回真值 → 放行；返回假值 → HTTP 401；
        - 抛异常 → HTTP 503 ``free_task_authorization_unavailable``。

        本模块 **绝不** 提供任何默认 ``authorizer``、**绝不** 内置真实
        秘钥或默认 token、**绝不** 自行读取凭据来源。synthetic 测试可用
        固定测试常量（如 ``Authorization`` header 比较）作为假凭据。

    返回
    ----
    ``Blueprint('free_task_protected_preview', url_prefix='/api/free-tasks')``，
    全部路由都先过 ``bp.before_request`` 授权闸门，再进入视图。

    不变量
    ------
    1. **import 期 / 构造期零副作用**：不读配置、不碰文件、不联网、不
       import 真实 ``app_factory``；
    2. 被拒请求 **绝不** 访问 store（授权闸门在视图与适配器之前）；
    3. 任何错误路径都 **绝不** 返回 HTTP 200；
    4. **没有** 绕过保护的备用路径（不存在 “skip_auth” 参数 / 环境变量 /
       header 白名单）。
    """
    # -- fail closed：先校验授权器，再碰 store ---------------------------
    # 顺序刻意如此：授权器不合格时，**根本不会** 去构造适配器，
    # 因此连 ``store`` 都不会被读取或调用。
    if authorizer is None:
        raise TypeError(
            "create_protected_free_task_blueprint 必须显式注入 authorizer "
            "(authorizer(request) -> bool)；None 一律拒绝，绝不默认放行"
        )
    if not callable(authorizer):
        raise TypeError(
            "authorizer 必须是 callable，签名为 authorizer(request) -> bool；"
            f"收到 {type(authorizer).__name__}"
        )

    return _build_free_task_blueprint(
        store,
        blueprint_name="free_task_protected_preview",
        authorizer=authorizer,
    )


def _build_free_task_blueprint(
    store: Any,
    *,
    blueprint_name: str,
    authorizer: Any = None,
) -> Blueprint:
    """两个工厂共用的蓝图构造器（``authorizer=None`` 表示无授权闸门）。

    只有 :func:`create_protected_free_task_blueprint` 才会传入非 ``None``
    的 ``authorizer``；旧工厂永远保持“无认证”的既有合成语义。
    """
    adapter = FreeTaskAdapter(store)

    bp = _FreeTaskPreviewBlueprint(blueprint_name, __name__, url_prefix="/api/free-tasks")

    # -- 角色标记（互斥检测的 **主依据**，与 Blueprint 名字无关）---------
    role = (
        ROLE_PROTECTED
        if authorizer is not None
        else ROLE_LEGACY_UNPROTECTED
    )
    bp.free_task_role = role

    # -- 第二层闸门：Flask 官方 ``record_once`` 钩子 ----------------------
    # ``record_once`` 的回调在 **Blueprint 注册时**（Flask 执行
    # ``deferred_functions`` 时）被调用，早于任何请求到达；它接收
    # ``BlueprintSetupState``，从 ``state.app`` 拿到目标 app。
    # 这里用它做一次 **独立于 ``register()`` 覆盖** 的复核：即便有人绕过
    # 本类的 ``register``（例如直接调用 ``Blueprint.register``），只要走
    # Flask 的正常注册管线，这道闸门依然会在路由生效 **之前** fail closed。
    @bp.record_once
    def _assert_no_conflicting_free_task_blueprint_hook(state):
        role_now = getattr(bp, "free_task_role", None)
        if role_now is None:
            return
        _assert_no_conflicting_free_task_blueprint(state.app, role_now)

    # -- 授权闸门（仅受保护工厂）---------------------------------------
    # ``before_request`` 覆盖本 Blueprint 的 **全部** 路径：POST append 与
    # GET summary 都在触碰适配器之前被拒绝，因此被拒请求不写库、不改账本。
    if authorizer is not None:

        @bp.before_request
        def _enforce_free_task_authorization():
            return _authorize_or_reject(authorizer)

    # -- POST /events ---------------------------------------------------
    @bp.route("/events", methods=["POST"])
    def append_free_task_event():
        """追加一个自由任务事件（append-only）。

        请求体：``{"action": "append", "session_id": ..., "event_id": ...,
        "event_payload": {...}}``，键集 **恰好** 这四项。
        """
        if not request.is_json:
            return _fail(
                "unsupported_media_type",
                "请求必须是 Content-Type: application/json",
                415,
            )

        raw_body = request.get_data(cache=True)
        if not raw_body.strip():
            return _fail("empty_body", "请求体不能为空", 400)

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return _fail("invalid_json", "请求体不是合法 JSON", 400)
        if not isinstance(body, dict):
            return _fail("body_not_object", "请求体必须是 JSON 对象", 400)

        # action 必须在“多余字段”检查之前被确认是 append：本端点只追加。
        if body.get("action") != REQUIRED_ACTION:
            return _fail(
                "action_not_append",
                f"本端点只接受 action={REQUIRED_ACTION!r}",
                400,
            )

        # 其余形状校验（多余字段、缺失 / 空白 ID、payload 类型）全部交给
        # 稳定公共适配器，并且它在触碰账本 **之前** 完成 → 被拒请求绝不写入。
        try:
            result = adapter.dispatch(body)
        except FreeTaskAdapterError as exc:
            # 适配层的形状问题永远是调用方的错 → 400
            return _fail(exc.code, exc.message, 400)
        except Exception as exc:  # 账本层错误 / sqlite / 路径错误
            return _ledger_failure(exc)

        return jsonify(result)

    # -- GET /sessions/<session_id>/summary ------------------------------
    @bp.route("/sessions/<session_id>/summary", methods=["GET"])
    def free_task_session_summary(session_id: str):
        """只读汇总（**用户自报**，账本无法独立验证）。"""
        try:
            result = adapter.dispatch({"action": "summary", "session_id": session_id})
        except FreeTaskAdapterError as exc:
            return _fail(exc.code, exc.message, 400)
        except Exception as exc:
            return _ledger_failure(exc)
        return jsonify(result)

    # -- 404 / 405 语义（见模块文档） -----------------------------------
    # 视图内部若显式 ``abort``，由下面的 Blueprint 级 handler 保证 JSON 形状；
    # URL **匹配阶段** 产生的 404 / 405 不会被 bp handler 覆盖，且本模块
    # 刻意不安装 app 级 handler（那会改变生产应用既有行为），因此保留标准
    # 状态码（未知路由 404、方法不允许 405）与 werkzeug 默认响应体。
    @bp.errorhandler(404)
    def _view_not_found(_error: Any):
        return _fail("not_found", "未知路由", 404)

    @bp.errorhandler(405)
    def _view_method_not_allowed(_error: Any):
        return _fail("method_not_allowed", "该路由不接受此 HTTP 方法", 405)

    return bp


def _ledger_failure(exc: BaseException) -> Tuple[Any, int]:
    """把账本 / sqlite / 路径错误映射成 JSON 失败，**绝不**伪报成功。

    - ``FreeTaskEventError``（或其子类）→ 用它自己的稳定 code；
    - 其余一切（``sqlite3.Error``、``OSError``、未知异常）→ 500
      ``internal_error``，细节只写日志。
    """
    # 延迟导入，避免在本模块顶层拉起整个事件层（保持 import 图最小）。
    from server.services.free_task_events import FreeTaskEventError

    if isinstance(exc, FreeTaskEventError):
        return _fail(exc.code, exc.message, _ledger_status(exc.code))

    current_app.logger.exception(
        "free-task preview 端点出现未预期异常: %s: %s",
        type(exc).__name__,
        exc,
    )
    code = "internal_sqlite_error" if isinstance(exc, sqlite3.Error) else "internal_error"
    return _fail(code, f"内部错误，事件未写入: {type(exc).__name__}", 500)


# ---------------------------------------------------------------------------
# 显式 opt-in：匹配阶段 404 / 405 → 统一 JSON（**仅限 synthetic app**）
# ---------------------------------------------------------------------------

#: opt-in 处理器只接管的 URL 前缀（含前缀本身或其子路径）。
PREVIEW_URL_PREFIX = "/api/free-tasks"


def _is_preview_request(request) -> bool:
    """该请求是否落在隔离预览前缀下。

    **精确**按路径分隔符判定：``/api/free-tasks`` 及其 ``/api/free-tasks/...``
    子路径为真；**前缀相似但不是同一路径**（如 ``/api/free-tasksXYZ``、
    ``/api/free-tasks-old``）为假 —— 后者必须保持原生 werkzeug 行为。
    """
    path = request.path or ""
    if not path.startswith(PREVIEW_URL_PREFIX):
        return False
    return len(path) == len(PREVIEW_URL_PREFIX) or path[len(PREVIEW_URL_PREFIX)] == "/"


def register_free_task_preview_errors(app: Any) -> Any:
    """**显式 opt-in**：把匹配阶段的 404 / 405 收口为统一 JSON 形状。

    目的
    ----
    Flask 3.1 起 Blueprint 级 errorhandler **不** 捕获 URL 匹配阶段产生的
    404 / 405，因此隔离预览的未知 URL / 错误方法会得到 werkzeug 的默认
    **HTML** 响应体。调用本函数后，**只** 位于 ``/api/free-tasks`` 前缀下的
    匹配阶段 404 / 405 变为::

        {"ok": false, "error": {"code": "not_found" | "method_not_allowed",
                                "message": "..."}}

    状态码 **完全不变**（404 / 405）；``Allow`` 等原生 HTTPException 属性
    也被保留（``HEAD``/``PUT`` 等自动方法语义不受影响）。

    边界（必须保证的负向契约）
    ------------------------
    - **非** preview 路径（其它前缀、普通路由、其它 Blueprint）**原样返回
      传入的 :class:`werkzeug.exceptions.HTTPException`**，状态码与响应体
      与未调用本函数时 **逐字一致**；
    - 仅覆盖 404 / 405 两种状态码，其它 HTTPException 不受影响；
    - 重复调用是幂等的。

    生产禁用（重要）
    ----------------
    本函数会往 **传入的 app** 安装 app 级 errorhandler。凡是注册了真实
    用户的 app、共享 app 或任何非一次性合成 app，都 **禁止** 调用：它会改变
    该 app 的全局错误行为。本接口 **没有认证、没有 CSRF、没有速率限制**，
    **仅供 synthetic 测试 / 隔离预览** 使用。

    纯函数、无 import 期副作用：仅在调用时注册 handler；模块 import 不会
    注册任何东西。默认的 :func:`create_free_task_blueprint` 不调用本函数。

    参数
    ----
    app:
        调用方自己新建的合成 :class:`flask.Flask` app。

    返回
    ----
    同一个 ``app``，便于链式写法。
    """
    from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound

    def _wants_preview_json(exc: HTTPException) -> bool:
        if not isinstance(exc, HTTPException):  # 防御：非 HTTP 异常不接管
            return False
        if isinstance(exc, NotFound) or exc.code == 404:
            return _is_preview_request(request)
        if isinstance(exc, MethodNotAllowed) or exc.code == 405:
            return _is_preview_request(request)
        return False

    def _preview_not_found(exc: HTTPException):
        if not _wants_preview_json(exc):
            return exc            # 原生异常 → 状态码与 body 均不变
        return _fail("not_found", "未知路由", 404)

    def _preview_method_not_allowed(exc: HTTPException):
        if not _wants_preview_json(exc):
            return exc            # 原生异常（含 Allow 头）→ 原样透传
        return _fail("method_not_allowed", "该路由不接受此 HTTP 方法", 405)

    app.register_error_handler(404, _preview_not_found)
    app.register_error_handler(405, _preview_method_not_allowed)
    return app


__all__ = [
    "ALLOWED_POST_KEYS",
    "AUTHORIZATION_UNAVAILABLE_CODE",
    "AUTHORIZATION_UNAVAILABLE_MESSAGE",
    "LEGACY_PREVIEW_BLUEPRINT_NAME",
    "PREVIEW_URL_PREFIX",
    "PROTECTED_PREVIEW_BLUEPRINT_NAME",
    "REGISTRATION_CONFLICT_CODE",
    "REGISTRATION_CONFLICT_CONFIG_KEY",
    "REGISTRATION_CONFLICT_MESSAGE",
    "REQUIRED_ACTION",
    "ROLE_LEGACY_UNPROTECTED",
    "ROLE_PROTECTED",
    "UNAUTHORIZED_CODE",
    "UNAUTHORIZED_MESSAGE",
    "create_free_task_blueprint",
    "create_protected_free_task_blueprint",
    "register_free_task_preview_errors",
]