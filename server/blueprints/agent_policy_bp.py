"""server.blueprints.agent_policy_bp - Agent 策略状态（只读）。

范围：
- GET /api/agent-policy/status

契约（LT_BOOTSTRAP_FIRST_CARD_20261021_A）：

- 本端点 **只读**。它从不创建、写入或修复
  ``data/agent-policy/`` 与 ``latest.json``。
- 返回内容是"是否已完成初始化"的安全布尔 + 策略版本 + 安全状态码。
  绝不回传策略正文、绝不回传文件系统路径、绝不回传任何密钥。
- 读取目录可通过 ``app.config['_agent_policy_dir']`` 覆盖（测试用合成
  app config）。缺省时使用 ``<project_root>/data/agent-policy``。
- 任何异常情况一律 fail closed：``initialized=False``。
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from server.services.agent_policy import (
    default_policy_dir,
    read_policy_status,
)


agent_policy_bp = Blueprint("agent_policy", __name__, url_prefix="/api")


def _policy_dir() -> str:
    """解析本次请求使用的策略目录。

    优先使用 app config（测试可注入合成目录）；否则回退到项目根下的
    默认目录。绝不创建目录。
    """
    override = current_app.config.get("_agent_policy_dir")
    if override:
        return str(override)
    project_root = current_app.config.get("_project_root")
    if project_root:
        return default_policy_dir(str(project_root))
    return default_policy_dir(".")


@agent_policy_bp.route("/agent-policy/status", methods=["GET"])
def agent_policy_status():
    """返回策略初始化状态。

    响应体（固定形状）::

        {
          "initialized": false,
          "version": null,
          "status": "missing",
          "reason": "latest_json_absent"
        }
    """
    try:
        status = read_policy_status(_policy_dir())
    except Exception:  # pragma: no cover - fail closed on any surprise
        status = {
            "initialized": False,
            "version": None,
            "status": "unreadable",
            "reason": "unexpected_error",
        }
    return jsonify(status)


__all__ = ["agent_policy_bp"]
