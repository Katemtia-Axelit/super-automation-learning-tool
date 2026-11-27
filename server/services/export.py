"""server.services.export — 系统状态导出的业务编排。

AR03-P2 / Stage 5
-----------------
Stage 5 之前，``GET /api/export`` 完全住在 legacy 单体里。

Stage 5 把它变成 **真 Blueprint**，并把"导出哪些表"这个 **业务决定**
下沉到本模块：

* **导出表清单** 是业务决定（用户要看到什么），不是 SQL 细节 →
  清单在本模块，SQL 在 :mod:`server.repositories.export_repo`；
* 导出内容是 **只读快照**（``SELECT *``），**绝不** 写任何表。

导出表清单（与 legacy 逐条一致，顺序也一致）
--------------------------------------------
``tasks`` / ``tags`` / ``task_tags`` / ``task_dependencies`` /
``user_schedule`` / ``daily_schedules`` / ``daily_user_state`` /
``gacha_records`` / ``task_rejection_log`` / ``task_completion_feedback``

响应体额外含 ``exported_at``（ISO 时间戳）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from server.repositories import export_repo
from server.repositories.db import service_transaction

__all__ = ["EXPORT_TABLES", "build_export", "build_export_action"]


#: 导出表清单（顺序即响应体里的键顺序）。
EXPORT_TABLES = (
    "tasks",
    "tags",
    "task_tags",
    "task_dependencies",
    "user_schedule",
    "daily_schedules",
    "daily_user_state",
    "gacha_records",
    "task_rejection_log",
    "task_completion_feedback",
)


def build_export(conn) -> Dict[str, Any]:
    """构建导出响应体。

    结构：``{"exported_at": "<ISO>", "<table>": [行, ...], ...}``。
    """
    payload: Dict[str, Any] = {"exported_at": datetime.now().isoformat()}
    for table in EXPORT_TABLES:
        payload[table] = export_repo.dump_table(conn, table)
    return payload


def build_export_action() -> Dict[str, Any]:
    """构建导出响应体（**自持只读事务**）。

    AR03-P2 / P2 收尾：事务边界下沉到 Service，Blueprint 不再开连接。
    导出是 **纯只读快照**，用 ``commit=False``（正常退出不提交，语义与
    迁移前的 ``read_connection()`` 逐条等价）。
    """
    with service_transaction(commit=False) as conn:
        return build_export(conn)
