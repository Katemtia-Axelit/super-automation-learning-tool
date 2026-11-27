"""server.repositories.export_repo — 导出域的数据访问层。

AR03-P2 / Stage 5
-----------------
导出是 **纯只读** 快照：把若干张表整表读出来。

* 所有函数 **接收显式 ``conn``**；
* **不** import Flask、**不** import legacy 单体、**不** 开连接；
* **绝不** 写任何表。

表清单不在本模块（那是业务决定，见
:data:`server.services.export.EXPORT_TABLES`）；本模块只提供"把某张表
整表读出来"的 SQL。
"""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["dump_table", "table_exists"]


def table_exists(conn, table: str) -> bool:
    """表是否存在（``sqlite_master`` 查询）。"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def dump_table(conn, table: str) -> List[Dict[str, Any]]:
    """整表读出为 dict 列表。

    表不存在时返回 **空列表**（而不是抛错）—— 导出是"尽力而为"的快照，
    一张表缺失不应让整个导出 500。

    ⚠️ 表名来自 :data:`server.services.export.EXPORT_TABLES` 白名单，
    不是用户输入。
    """
    if not table_exists(conn, table):
        return []
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]
