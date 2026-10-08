"""server.app.extensions - 单例资源（DB connection）。

设计：
- `get_db_connection(config)` 创建新连接（每次调用独立；避免跨线程共享）
- `configure_sqlite(conn)` 强制 WAL + busy_timeout，与 backend_api.py 一致
- `make_request_conn(db_path)` 统一请求级连接：WAL + foreign_keys=ON
  + busy_timeout + row_factory（修复 bug 1+2）。实际实现位于
  `server.extensions.make_request_conn` 以避免 blueprints ⇄ app_factory
  循环依赖；本模块做 re-export 保持向后兼容。
- `SQLITE_BUSY_TIMEOUT_MS` 暴露常量（30 秒，与原代码一致）
- Phase 1 不引入 ORM / connection pool
"""

import sqlite3

from server.extensions import (
    SQLITE_BUSY_TIMEOUT_MS,
    make_request_conn,
)

__all__ = [
    "SQLITE_BUSY_TIMEOUT_MS",
    "make_request_conn",
]


def get_db_connection(config):
    """Open a new sqlite3 connection with row dict factory + busy timeout.

    `config` is the dict returned by `load_config()`.
    Caller is responsible for closing the connection.

    Note: this is used by `create_app()` for one-shot schema bootstrapping
    (configure_sqlite + ensure_all). For per-request connections inside
    blueprints, use `make_request_conn()` instead — it adds foreign_keys=ON
    and centralizes WAL/busy_timeout settings.
    """
    db_path = config.get("_db_path") or config.get("database", {}).get(
        "task_db_path", "data/task_publisher.db"
    )
    conn = sqlite3.connect(db_path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.row_factory = sqlite3.Row
    return conn


def configure_sqlite(conn):
    """Enable WAL journal mode (idempotent); raise if not enabled.

    Matches original `configure_sqlite` in backend_api.py line 3439-3443.
    """
    journal_mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if str(journal_mode).lower() != "wal":
        raise RuntimeError(f"Failed to enable SQLite WAL mode: {journal_mode}")
    print(
        f"[DB] journal_mode={journal_mode}, "
        f"busy_timeout={SQLITE_BUSY_TIMEOUT_MS}ms"
    )
