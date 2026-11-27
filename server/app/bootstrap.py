"""server.app.bootstrap — 服务启动时的 **幂等** 数据同步编排。

AR03-P2 / Stage 7
-----------------
Stage 7 之前，启动期的三段数据同步住在 legacy 单体
``server/backend_api.py`` 里：

* ``migrate_dependency_data()`` —— 把 ``tasks.prerequisite_ids`` JSON 列
  迁移到 ``task_dependencies`` 表；
* ``sync_all_unlock_states(conn)`` —— 按前置完成状态重算
  ``is_unlocked``；
* ``recover_discard_cycle()`` —— 幂等的弃牌周期恢复。

Stage 7 把它们收口到本模块（**唯一** 启动期编排入口），legacy 单体
随即退化成委托 ``create_app()`` 的薄别名。

顺序与语义保持不变
------------------
1. **依赖数据迁移**（先于解锁同步 —— 解锁判定依赖依赖边）；
2. **解锁状态同步**；
3. **弃牌周期恢复**。

三段都是 **幂等** 的：同一天重复启动不会重复推进周期，也不会重复改写
解锁状态。

失败策略
--------
任何一段失败都 **不阻断** 服务启动（只记录）—— 与 legacy 的
``except Exception: print(...)`` 语义一致。数据同步失败不应让用户
完全打不开应用。
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

__all__ = [
    "run_startup_migrations",
]


def run_startup_migrations(
    conn: sqlite3.Connection,
    *,
    verbose: bool = True,
) -> Dict[str, Any]:
    """执行启动期的幂等数据同步。

    返回 ``{"dependencies_migrated": n, "unlocks_synced": n,
    "discard_recovery": {...} | None}``。

    每一段独立 try —— 某段失败不影响其余两段，也不阻断服务启动。
    """
    from server.services import discard as discard_service
    from server.services import tasks as task_service

    result: Dict[str, Any] = {
        "dependencies_migrated": 0,
        "unlocks_synced": 0,
        "discard_recovery": None,
    }

    # -- 1. 依赖数据迁移 ---------------------------------------------------
    try:
        count = task_service.migrate_dependency_data(conn)
        result["dependencies_migrated"] = count
        if verbose and count:
            print(
                f"[MIGRATE] {count} tasks with dependencies synced "
                "to task_dependencies table"
            )
    except Exception as exc:  # noqa: BLE001 - 迁移失败不阻断启动
        if verbose:
            print(f"[MIGRATE] skipped: {exc}")

    # -- 2. 解锁状态同步 ---------------------------------------------------
    try:
        count = task_service.sync_all_unlock_states(conn)
        result["unlocks_synced"] = count
    except Exception as exc:  # noqa: BLE001 - 同步失败不阻断启动
        if verbose:
            print(f"[UNLOCK] sync skipped: {exc}")

    # -- 3. 弃牌周期恢复 ---------------------------------------------------
    try:
        stats = discard_service.recover_discard_cycle(conn)
        result["discard_recovery"] = stats
        if verbose:
            print(f"[DISCARD] cycle recovery: {stats}")
    except Exception as exc:  # noqa: BLE001 - 恢复失败不阻断启动
        if verbose:
            print(f"[DISCARD] cycle recovery skipped: {exc}")

    return result
