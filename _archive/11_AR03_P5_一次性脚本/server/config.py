"""server.config — 配置加载的 **薄 re-export**。

历史路径兼容层：``server.config`` 曾是本项目自己的配置加载器，
但它与 ``server/app/config.py`` 的语义不一致（前者顶层整块替换、
没有派生键；后者有派生键 + 子键浅合并），造成 **双配置权威**。

P1（切片 2）把 ``server/app/config.py`` 定为 **唯一权威**，
本模块只做 re-export，保持历史 import 路径与函数名不变：

    from server.config import load_config, DEFAULT_CONFIG

行为差异（有意为之，且已在 P1 交付文档中记录）
--------------------------------------------------
* ``load_config()`` 现在返回 **带派生键** 的 dict
  （``_project_root`` / ``_static_dir`` / ``_db_path`` / ``_notes_dir``）。
  旧调用点只读取 ``server`` / ``obsidian`` / ``api`` / ``database``
  四个顶层键，因此不受影响。
* ``load_config(override)`` 的 override 语义保持 **顶层整块替换**，
  与旧实现一致。
* 配置文件读取失败时回落到默认值，与旧实现一致（旧实现会抛异常，
  新实现更稳健，且与 ``server/app/config.py`` 的既有行为一致）。

**唯一权威** 在 ``server/app/config.py``；本文件不含任何配置 DDL/默认值副本。
"""

from __future__ import annotations

from server.app.config import (  # noqa: F401
    DEFAULT_CONFIG,
    PROJECT_ROOT,
    config_path,
    load_config,
)

__all__ = [
    "DEFAULT_CONFIG",
    "PROJECT_ROOT",
    "config_path",
    "load_config",
]
