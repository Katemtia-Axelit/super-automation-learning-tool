"""server.repositories.db — **统一** 的 repository 连接 / 事务助手。

定位（AR03-P2 / Stage 1）
--------------------------
Stage 1 之前，各 Blueprint / Repository 自己开连接、自己 commit，
路径来源五花八门（``current_app.config["_db_path"]`` /
``server.extensions.get_db_path()`` / 硬编码的 ``data/task_publisher.db``）。
这导致：

* **进程级全局** 风险（``server.extensions._DB_PATH``）；
* **事务边界** 不统一 —— 同一业务动作的多个写操作可能被拆成多次 commit；
* **PRAGMA 设置** 不统一 —— 有的连接忘了 ``foreign_keys=ON``。

本模块提供 **唯一** 的连接/事务入口：

* :func:`connect` —— 打开一条带完整 PRAGMA 的连接（复用
  ``server.extensions.make_request_conn`` 的语义，但路径解析统一走
  app 作用域）；
* :func:`transaction` —— 事务上下文管理器：正常退出 **提交**，
  抛异常 **回滚**（在 **已有连接** 上）；
* :func:`service_transaction` —— **Service 层**的事务边界入口：自行开连接，
  在同一连接上完成全部 repo 调用，由 Service 决定提交 / 回滚
  （``commit=False`` 时为只读语义）；
* :func:`read_connection` / :func:`write_connection` —— 只读 / 读写连接
  上下文管理器。

约定（**全仓 repository 统一遵守**）
--------------------------------
1. **Repository 一律接收显式 ``conn``**（调用方管理生命周期）；
   只有本模块负责 **开** 连接。
2. **Service 不直接写 SQL**。
3. **Repository 不读进程级全局**：所有路径经 :func:`resolve_db_path`
   从 **当前 app** 解析。
4. 事务边界由 **Service** 决定（完成 / 跳过 / 拒绝 / 换牌 / 弃牌 / 恢复
   的原子性与提交时机保持 legacy 语义）。
5. **Blueprint 不开连接**（AR03-P2 / P2 收尾）：事务边界一律下沉到
   Service，Blueprint 只做「解析请求 → 调 Service → 组装响应」。
   Service 用 :func:`service_transaction` 自行开连接；**只读** Service
   传 ``commit=False``。

Thread-safety
-------------
每次调用开一条独立连接（与既有语义一致），连接由上下文管理器负责关闭。
"""

from __future__ import annotations

import contextlib
import sqlite3
from typing import Iterator, Optional

from server.extensions import (
    SQLITE_BUSY_TIMEOUT_MS,
    get_db_path,
    make_request_conn,
)

__all__ = [
    "SQLITE_BUSY_TIMEOUT_MS",
    "connect",
    "read_connection",
    "resolve_db_path",
    "service_transaction",
    "transaction",
    "write_connection",
]


def resolve_db_path(db_path: Optional[str] = None) -> str:
    """解析本次操作应当使用的 DB 绝对路径。

    优先级：

    1. 显式传入的 ``db_path``；
    2. 当前 Flask app 上下文的 ``extensions["sal"]["db_path"]`` /
       ``config["_db_path"]``；
    3. 最近一次初始化的 app（请求期之外的兼容兜底）。

    绝不回落到项目相对路径 —— 那会在 CWD 不正确时静默连到 **别的** 数据库。
    """
    if db_path:
        return str(db_path)
    return get_db_path()


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """打开一条带完整 PRAGMA 的 SQLite 连接。

    PRAGMA 语义与 ``server.extensions.make_request_conn`` 完全一致：
    ``foreign_keys=ON`` / ``journal_mode=WAL`` / ``busy_timeout=30s`` /
    ``row_factory=sqlite3.Row``。

    调用方负责关闭（或用 :func:`read_connection` / :func:`write_connection`）。
    """
    return make_request_conn(resolve_db_path(db_path))


@contextlib.contextmanager
def read_connection(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """只读连接上下文：正常退出时 **不提交**（只读语义），异常时回滚。

    用法::

        with read_connection() as conn:
            rows = repo.list_tasks(conn)
    """
    conn = connect(db_path)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextlib.contextmanager
def write_connection(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """读写连接上下文：正常退出 **提交**，异常 **回滚**。

    这是 Service 层做 **多步原子写** 的标准入口：

    .. code-block:: python

        with write_connection() as conn:
            repo.mark_completed(conn, task_id)
            repo.write_completion_feedback(conn, task_id, payload)
        # 到这里才真正落盘
    """
    conn = connect(db_path)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


@contextlib.contextmanager
def transaction(
    conn: sqlite3.Connection, commit: bool = True
) -> Iterator[sqlite3.Connection]:
    """在 **已有连接** 上开启事务边界。

    - 正常退出 → ``commit()``（当 ``commit=True``）；
    - 抛异常 → ``rollback()`` 并原样抛出。

    用于把若干 Repository 调用包成一个原子单元，同时复用调用方已经打开的
    连接（避免在事务中途换连接而丢掉锁）。
    """
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        if commit:
            conn.commit()


@contextlib.contextmanager
def service_transaction(
    db_path: Optional[str] = None, *, commit: bool = True
) -> Iterator[sqlite3.Connection]:
    """**Service 层**的事务边界入口（AR03-P2 / P2 收尾）。

    语义 = "打开连接 → 在 **同一连接** 上完成全部 repo 调用 → 由 Service
    层决定提交 / 回滚"：

    .. code-block:: python

        with service_transaction() as conn:
            repo.mark_completed(conn, task_id)
            repo.unlock_dependents(conn, task_id)
        # 到这里才真正落盘

    与 :func:`write_connection` 的关系
    ----------------------------------
    两者 **提交时机等价**（都在退出 ``with`` 且无异常时提交；异常时回滚），
    但 **归属** 不同：

    - :func:`write_connection` 是 **Blueprint 层**的旧入口 —— 由 HTTP 层
      持有事务边界（Service 只在给定连接上工作）；
    - :func:`service_transaction` 是 **Service 层**的入口 —— 事务边界
      **下沉到 Service**，Blueprint 只做「解析请求 → 调 Service → 组装响应」。

    ``commit=False`` 用于 **只读** Service：正常退出 **不**提交（纯读语义），
    异常时同样回滚 —— 与 :func:`read_connection` 的提交语义一致。

    事务原子性
    ----------
    Service 内部的所有 repo 调用 **必须** 在这一条连接上完成
    （**绝不**中途换连接），否则会丢掉 SQLite 的写锁、破坏原子性。
    """
    conn = connect(db_path)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        if commit:
            conn.commit()
    finally:
        conn.close()
