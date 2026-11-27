"""server.services.agent_policy - 只读的 Agent 策略存储 (policy store).

用途
----
正式产品 P0「第一次启动引导卡」需要回答一个问题：**用户是否已经拥有一份
经过本人明确批准的初始策略？** 如果没有，正式界面必须停在引导流程里，
不得解锁普通抽卡。

本模块只做 *读取* 与 *校验*：

- 默认只读 ``<project_root>/data/agent-policy/latest.json``
- 永远不创建、不写入、不修复该目录或文件
- 任何异常（缺失 / JSON 损坏 / schema 不符 / 缺少显式批准字段）都视为
  **尚未完成初始化**（fail closed）

canonical schema (``latest.json``)
---------------------------------
::

    {
      "schema_version": 1,          # 必须存在且严格等于整数 POLICY_SCHEMA_VERSION
      "version": "2026-10-21.1",    # 必须是无空白的纯文本字符串
      "approved_by_user": true,     # 显式批准：布尔 True 或非空字符串（数字不算）
      "approved_at": "2026-10-21T12:00:00Z",   # 必须可解析的 ISO-8601 带时区时间
      ...                           # 其余业务字段（自由任务时长等）由 Publisher 写入
    }

严格性要点（LT_BOOTSTRAP_G1_BROWSER_QA_20261022_B 收紧）：

- ``schema_version`` 必须是 **严格的整数 1**。``true`` / ``false`` 虽是
  ``int`` 的子类但被显式排除，``1.0``（float）与 ``"1"``（str）同样拒绝。
- ``approved_at`` 必须能被 ``datetime.fromisoformat`` 真实解析，且必须
  带时区信息（否则会把本地时间当成 UTC 判定）。纯空白 / 非字符串 /
  含控制字符 / 明显未来时间一律拒绝——"仅凭无效字符串构成批准日期"
  不再可能。
- ``approved_by_user`` 只接受布尔 ``True`` 或非空字符串；数字 ``1`` /
  ``0`` 不构成显式批准。
- ``version`` 必须是无控制字符、长度受限的纯文本。

只有当上述四项全部合法时，``read_policy_status`` 才返回
``initialized=True``。其余情况一律返回 ``initialized=False`` 并附带一个
*安全的* 状态码（不含路径、不含内容），供前端做 fail-closed 决策。

安全约束
--------
- 不返回策略内容本身（可能包含用户隐私）。
- 不返回文件系统绝对路径。
- 不写入 ``data/agent-policy/``、``data/task_publisher.db``、
  ``config/config.json``、``src/notes/**``。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

#: ``latest.json`` 必须声明的 schema 版本。
POLICY_SCHEMA_VERSION = 1

#: 策略文件名的固定约定。
POLICY_FILENAME = "latest.json"

#: 策略目录相对项目根的默认位置。
DEFAULT_POLICY_DIRNAME = os.path.join("data", "agent-policy")

#: 允许的批准时间超前量（时钟漂移容忍上限）。
APPROVED_AT_FUTURE_TOLERANCE = timedelta(days=1)

#: 禁止出现在自由文本字段中的控制字符。
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

#: 自由文本字段的长度上限（防止超长 / 注入式载荷）。
MAX_VERSION_LENGTH = 64
MAX_APPROVAL_LENGTH = 128

# --- 安全状态码（不泄露路径 / 内容） -------------------------------------
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_UNREADABLE = "unreadable"
STATUS_INVALID_JSON = "invalid_json"
STATUS_INVALID_SHAPE = "invalid_shape"
STATUS_SCHEMA_MISMATCH = "schema_mismatch"
STATUS_MISSING_VERSION = "missing_version"
STATUS_INVALID_VERSION = "invalid_version"
STATUS_MISSING_APPROVED_AT = "missing_approved_at"
STATUS_INVALID_APPROVED_AT = "invalid_approved_at"
STATUS_NOT_APPROVED = "not_approved"


def default_policy_dir(project_root: str) -> str:
    """返回项目根下的默认策略目录（绝对路径）。

    ``project_root`` 通常来自 ``app.config['_project_root']``。
    """
    root = os.path.abspath(project_root)
    return os.path.join(root, DEFAULT_POLICY_DIRNAME)


def _is_explicit_approval(value: Any) -> bool:
    """判断 ``approved_by_user`` 是否构成 *显式* 批准。

    接受 ``True``（布尔字面量）或非空字符串（如 ``"user"``）。
    拒绝缺失、``None``、``False``、空字符串，以及任何数字类型
    （含 ``1`` / ``0``）——``True`` 之外的"真值"都不是显式批准。
    注意 ``isinstance(True, int)`` 在 Python 中为真，故必须先判定
    布尔，再显式排除 ``int``。
    """
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str) and value.strip():
        if len(value) > MAX_APPROVAL_LENGTH:
            return False
        # 字符串批准人不得包含控制字符（拒绝伪造 / 注入式载荷）。
        return not _CONTROL_CHARS.search(value)
    # 数字（int / float / Decimal 等）一律不构成显式批准。
    return False


def _non_empty_str(value: Any) -> bool:
    """是否为不含控制字符的非空字符串。"""
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    return not _CONTROL_CHARS.search(value)


def _valid_schema_version(value: Any) -> bool:
    """``schema_version`` 必须是 *严格* 的整数 ``1``。

    严格性要点：
    - ``True`` / ``False`` 是 ``bool``，而 ``bool`` 是 ``int`` 的子类，
      因此必须显式排除，否则 ``schema_version: true`` 会冒充整数 1。
    - ``1.0``（浮点）不是整数类型，同样拒绝。
    - ``"1"``（字符串）拒绝。
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, int):
        return False
    return value == POLICY_SCHEMA_VERSION


def _parse_approved_at(value: Any) -> Optional[datetime]:
    """解析 ``approved_at`` 为带时区的 datetime；不可信则返回 ``None``。

    只接受 ISO-8601 风格字符串，且必须能被真实解析。拒绝：
    - 非字符串（数字 / 布尔 / None）
    - 空字符串 / 纯空白
    - 含控制字符的字符串
    - 无法被 ``datetime.fromisoformat`` 解析的字符串
    - 无时区信息的时间戳（避免把本地时间当成 UTC 判定）
    """
    if not isinstance(value, str):
        return None
    if not value.strip():
        return None
    if _CONTROL_CHARS.search(value):
        return None
    text = value.strip()
    # Python 3.10 的 fromisoformat 不接受末尾 "Z"，这里显式归一化。
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        # 无时区信息 → 不可信，拒绝。
        return None
    return parsed


def _approved_at_is_plausible(parsed: datetime) -> bool:
    """批准时间不得明显晚于当前时间（容忍 1 天时钟漂移）。

    这挡不住"手工伪造一个过去的合法时间戳"，但能挡住明显的
    ``2999-12-31`` 之类的不可信 shape。
    """
    now = datetime.now(timezone.utc)
    return parsed <= now + APPROVED_AT_FUTURE_TOLERANCE


def validate_policy_document(doc: Any) -> Dict[str, Any]:
    """校验已解析的策略文档。

    返回 ``{"initialized": bool, "version": Optional[str], "status": str,
    "reason": str}``。不抛异常，不返回原始内容。
    """
    if not isinstance(doc, dict):
        return _result(False, None, STATUS_INVALID_SHAPE, "policy_root_not_object")

    if "schema_version" not in doc:
        return _result(False, None, STATUS_SCHEMA_MISMATCH, "schema_version_missing")
    if not _valid_schema_version(doc.get("schema_version")):
        # 覆盖 true / false / 1.0 / "1" / 99 等所有非严格情形。
        return _result(False, None, STATUS_SCHEMA_MISMATCH, "schema_version_mismatch")

    version = doc.get("version")
    if version is None:
        return _result(False, None, STATUS_MISSING_VERSION, "version_missing")
    if not _non_empty_str(version):
        return _result(False, None, STATUS_INVALID_VERSION, "version_not_plain_text")
    if len(version.strip()) > MAX_VERSION_LENGTH:
        return _result(False, None, STATUS_INVALID_VERSION, "version_too_long")

    if "approved_at" not in doc:
        return _result(False, None, STATUS_MISSING_APPROVED_AT, "approved_at_missing")
    approved_at = _parse_approved_at(doc.get("approved_at"))
    if approved_at is None:
        # 空字符串 / 纯空白 / 非字符串 / 不可解析 / 无时区 → 不可信。
        return _result(False, None, STATUS_INVALID_APPROVED_AT, "approved_at_not_trustworthy")
    if not _approved_at_is_plausible(approved_at):
        return _result(False, None, STATUS_INVALID_APPROVED_AT, "approved_at_implausible")

    if not _is_explicit_approval(doc.get("approved_by_user")):
        return _result(False, None, STATUS_NOT_APPROVED, "approved_by_user_missing")

    return _result(True, version.strip(), STATUS_OK, "approved")


def read_policy_status(policy_dir: str) -> Dict[str, Any]:
    """读取并校验策略目录中的 ``latest.json``。

    - 目录或文件不存在 → ``initialized=False`` / ``status='missing'``
    - 文件不可读 / JSON 损坏 → ``initialized=False``（fail closed）
    - schema 不符 / 缺少显式批准 → ``initialized=False``

    本函数 **绝不** 创建目录或文件。
    """
    if not policy_dir:
        return _result(False, None, STATUS_MISSING, "policy_dir_not_configured")

    policy_path = os.path.join(policy_dir, POLICY_FILENAME)
    if not os.path.isfile(policy_path):
        return _result(False, None, STATUS_MISSING, "latest_json_absent")

    try:
        with open(policy_path, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError):
        return _result(False, None, STATUS_UNREADABLE, "latest_json_unreadable")

    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return _result(False, None, STATUS_INVALID_JSON, "latest_json_not_valid_json")

    return validate_policy_document(doc)


def _result(
    initialized: bool,
    version: Optional[str],
    status: str,
    reason: str,
) -> Dict[str, Any]:
    """构造统一的、安全的返回结构。"""
    return {
        "initialized": bool(initialized),
        "version": version if initialized else None,
        "status": status,
        "reason": reason,
    }


# --- 服务端权威闸门 (LT_BOOTSTRAP_G1_BROWSER_QA_20261022_B) --------------
#
# 威胁模型（务必与 Handoff 一致）：
# 前端 bootstrap-first-card.js 的 fetch / click 守卫属于 **UI 层**，
# 只在真实浏览器里、且脚本成功加载时生效。任何直接 HTTP 客户端
# （curl / 另一个标签页里的裸 fetch / 被改过的前端）都能绕过它。
# 下面的闸门是**服务端**限制：它在 Flask 的 before_request 上重新判定，
# 不依赖前端是否诚实。
#
# 默认 **关闭**（见 app_factory.py 的说明）：现有业务特征套件在合成根里
# 不带策略地直接 POST /api/gacha/*、/api/timer/*、/api/tasks/*，
# 默认开启会让它们全部失败。设置 SAL_ENFORCE_AGENT_POLICY=1 才启用。

#: 初始化完成前必须拒绝写请求的路径前缀（服务端权威）。
BLOCKED_WRITE_PREFIXES = (
    "/api/gacha",
    "/api/timer",
    "/api/tasks",
)

#: 闸门拒绝写请求时使用的 HTTP 状态码（423 Locked）。
LOCKED_STATUS_CODE = 423

#: 控制闸门开关的 app config 键。
ENFORCE_CONFIG_KEY = "_agent_policy_enforce"

#: 启用闸门的环境变量名。
ENFORCE_ENV_VAR = "SAL_ENFORCE_AGENT_POLICY"


def should_block_write(path: str, method: str) -> bool:
    """纯函数：该 ``(path, method)`` 是否应被初始化闸门拒绝。

    只拦 **写** 方法；GET / HEAD / OPTIONS 永不拦截（引导卡仍需读取
    任务、知识库等只读数据）。路径比较使用段边界，避免
    ``/api/gachaxx`` 之类的前缀误伤。
    """
    if not path or not method:
        return False
    if str(method).upper() in ("GET", "HEAD", "OPTIONS"):
        return False
    route = str(path).split("?", 1)[0]
    for prefix in BLOCKED_WRITE_PREFIXES:
        if route == prefix or route.startswith(prefix + "/"):
            return True
    return False


def install_bootstrap_gate(app, policy_dir: str) -> bool:
    """在 app 上安装 ``before_request`` 闸门；返回是否真的安装。

    仅当 ``app.config[ENFORCE_CONFIG_KEY]`` 为真时安装。安装后：
    - 策略有效（``initialized=True``）→ 放行
    - 策略缺失 / 损坏 / 未批准 / 不可读 → 423，且 fail closed
    - 读取本身抛异常 → 同样 423（绝不因异常而放行）
    """
    if not app.config.get(ENFORCE_CONFIG_KEY):
        return False

    from flask import jsonify, request

    @app.before_request
    def _sal_bootstrap_gate():
        if not should_block_write(request.path, request.method):
            return None
        try:
            status = read_policy_status(policy_dir)
            initialized = bool(status.get("initialized"))
            code = status.get("status", "unknown")
        except Exception:  # pragma: no cover - fail closed on any surprise
            initialized, code = False, "unreadable"
        if initialized:
            return None
        return jsonify({
            "error": "bootstrap-locked",
            "initialized": False,
            "status": code,
        }), LOCKED_STATUS_CODE

    return True


__all__ = [
    "BLOCKED_WRITE_PREFIXES",
    "DEFAULT_POLICY_DIRNAME",
    "ENFORCE_CONFIG_KEY",
    "ENFORCE_ENV_VAR",
    "LOCKED_STATUS_CODE",
    "POLICY_FILENAME",
    "POLICY_SCHEMA_VERSION",
    "STATUS_INVALID_APPROVED_AT",
    "STATUS_INVALID_JSON",
    "STATUS_INVALID_SHAPE",
    "STATUS_INVALID_VERSION",
    "STATUS_MISSING",
    "STATUS_MISSING_APPROVED_AT",
    "STATUS_MISSING_VERSION",
    "STATUS_NOT_APPROVED",
    "STATUS_OK",
    "STATUS_SCHEMA_MISMATCH",
    "STATUS_UNREADABLE",
    "APPROVED_AT_FUTURE_TOLERANCE",
    "MAX_APPROVAL_LENGTH",
    "MAX_VERSION_LENGTH",
    "default_policy_dir",
    "install_bootstrap_gate",
    "read_policy_status",
    "should_block_write",
    "validate_policy_document",
]
