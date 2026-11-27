"""server.blueprints.index_bp — 索引页 HTTP 边界（AR03-P2 / Stage 5）。

Stage 5 之前，``GET /`` 由 legacy 单体的 ``api_index`` 提供（兼容桥转发）。

Stage 5 把它变成 **真 Blueprint**：直接返回应用首页。

首页位置
--------
真实项目里首页是 ``<project_root>/src/index.html``；而 **合成环境**
（``tests/characterize/sandbox_env.py``）把首页放在合成根的
``index.html``（合成根 **没有** ``src/`` 子目录）。

因此本蓝图按顺序尝试：

1. ``<project_root>/src/index.html``（真实布局）
2. ``<project_root>/index.html``（合成布局）

两个都不存在时回落到一段 **最小 HTML**（而不是 404），让前端在
"首页缺失"时也拿到可解析的页面 —— 与 legacy 的行为一致。

安全边界
--------
只读首页文件。**绝不** 写它、**绝不** 读 ``src/notes/**``
（知识库内容 **不是** 静态资源，暴露目录等于泄露用户数据）。
"""

from __future__ import annotations

import os

from flask import Blueprint, current_app, send_from_directory

index_bp = Blueprint("index", __name__)


#: 首页候选位置（相对项目根）：``(子目录, 文件名)``。
INDEX_CANDIDATES = (("src", "index.html"), ("", "index.html"))

#: 找不到首页时的最小回落页面。
FALLBACK_HTML = (
    "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
    "<title>超级自动化学习工具</title></head>"
    "<body><h1>超级自动化学习工具</h1>"
    "<p>首页文件缺失（index.html）。</p></body></html>"
)


@index_bp.route("/", methods=["GET"])
def index():
    """返回应用首页。"""
    project_root = current_app.config.get("_project_root") or os.getcwd()
    for folder, filename in INDEX_CANDIDATES:
        candidate = os.path.join(project_root, folder, filename)
        if os.path.isfile(candidate):
            return send_from_directory(
                os.path.join(project_root, folder), filename
            )
    return FALLBACK_HTML


__all__ = ["index_bp"]
