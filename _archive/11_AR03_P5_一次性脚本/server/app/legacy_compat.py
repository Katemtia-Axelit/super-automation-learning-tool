"""server.app.legacy_compat — **已退役的兼容桥（墓碑模块）**。

AR03-P2 / Stage 7
------------------
本模块曾是 Factory 装配期的 **兼容桥**：把尚未迁移的 legacy 路由
（``/``、``/api/config``、``/api/export``、``/api/dependencies``、
discard ×3、``/api/agent/*`` ×9、``/api/prompts/*`` ×5）直接从
``backend_api`` 转发到 Factory 上 —— **view function 就是 legacy 的原
函数**，属于真实的双实现/转发层，**不算迁移**。

演进轨迹：

============  ==================================================
阶段          兼容桥白名单
============  ==================================================
Stage 2      ``/api/dependencies`` + discard ×3 迁到真 Blueprint
Stage 5      ``/``、``/api/config`` ×2、``/api/export`` 迁到真 Blueprint
             → ``EXACT_ROUTES`` **清空**
Stage 6      ``/api/agent/*`` ×9、``/api/prompts/*`` ×5 迁到真 Blueprint
             → ``PREFIX_ROUTES`` **清空**
Stage 7      **本模块退役**；``backend_api.py`` 收口为薄别名
============  ==================================================

现状
----
Stage 7 起本模块 **不再被任何代码 import**
（``server/app/app_factory.py`` 已移除
:func:`server.app.legacy_compat.register_legacy_compat` 的注册调用），
也 **不再挂载任何路由**。它保留在此仅有两个原因：

1. **物理删除尚未执行** —— Cursor 的破坏性操作守卫（``destructive-guard``）
   拒绝在会话内永久删除工作区文件，因此本文件的物理删除由
   **Controller / 用户在会话外** 执行。本模块以 **墓碑** 形式保留，
   在那之前它的语义与"已删除"完全等价：**零路由、零副作用、零依赖**。
2. **可审计性** —— 文件内容明确记录了兼容桥的完整历史与退役理由。

不变量
------
* ``EXACT_ROUTES`` 与 ``PREFIX_ROUTES`` **恒为空**；
* :func:`register_legacy_compat` **恒返回 0**，**不注册任何路由**，
  **不 import** ``server.backend_api``（避免薄别名被再次拉起）；
* ``app.config["_compat_route_count"]`` 恒为 0。

``tests/characterize/test_static_route_inventory.py`` 机械校验以上不变量，
``tests/characterize/test_stage6_prompts_agent.py`` 断言兼容桥
**不挂载任何路由**。

「AI 不得写 Obsidian 笔记」的 403 护栏
------------------------------------
此前由本桥 **注入** 视图函数实现。Stage 6 起该护栏 **内建** 在
``server/blueprints/agent_bp.py`` 里
（:func:`server.services.agent.save_note_blocked`），
**不再依赖本桥**，也 **不会** 因本文件的物理删除而丢失。
"""

from __future__ import annotations

#: 需要 **精确** 匹配才由本桥转发的 legacy 路由（已清空，恒为空）。
EXACT_ROUTES: set[str] = set()

#: 需要 **前缀** 匹配才由本桥转发的 legacy 路由（已清空，恒为空）。
PREFIX_ROUTES: tuple[str, ...] = ()

#: 兼容桥的退役标记 —— 供调用方与测试识别"本桥已退役"。
RETIRED = True


def register_legacy_compat(app, config) -> int:
    """**已退役**的兼容桥：不再挂载任何路由。

    保留此函数签名是为了让任何 **遗留调用方** 得到一个明确的、
    **零副作用** 的结果，而不是 ``ImportError``（那会让启动链炸掉）。

    与旧实现的关键差异：

    * **不** import ``server.backend_api``（旧实现会 import 它，
      从而把薄别名重新拉起并改写其全局）；
    * **不** 改写 ``legacy.DB_PATH`` / ``legacy.NOTES_DIR``
      （旧实现会写 —— 那正是 P1 "Factory 实例互相污染" 的根因之一）；
    * **不** 调用 ``app.add_url_rule``。

    返回值恒为 ``0``（挂载的路由数）。
    """
    app.config["_compat_route_count"] = 0
    return 0


__all__ = [
    "EXACT_ROUTES",
    "PREFIX_ROUTES",
    "RETIRED",
    "register_legacy_compat",
]
