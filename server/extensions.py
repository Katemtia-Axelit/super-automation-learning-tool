"""server.extensions — shared singletons (DB connection helper, CORS, logger).

Phase 1 keeps the legacy `get_db_connection()` semantics (per-request
connection with `row_factory = sqlite3.Row`). Phase 2 will move to a
repository pattern that hides sqlite entirely from blueprints.

P0 fix 2026-08-16 (bug 1+2): adds `make_request_conn()` which sets
PRAGMA foreign_keys=ON + WAL + busy_timeout on every per-request
connection. This module is intentionally **outside** `server.app` so
that blueprints can import it without creating a circular dependency
(blueprints → server.app.extensions → server.app.__init__ → app_factory
→ blueprints).
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Optional

from flask import Flask
from flask_cors import CORS

LOG = logging.getLogger("sal")

_DB_PATH: Optional[str] = None

# Match the project-wide constant in `server.app.extensions`.
SQLITE_BUSY_TIMEOUT_MS = 30_000


def init_extensions(app: Flask, db_path: str) -> None:
    """Wire CORS + record DB path on the app object.

    Called once from `create_app()`.
    """
    global _DB_PATH
    _DB_PATH = db_path
    CORS(app)
    app.extensions.setdefault("sal", {})
    app.extensions["sal"]["db_path"] = db_path
    LOG.info("extensions initialised: db_path=%s", db_path)


def get_db_path() -> str:
    if _DB_PATH is None:
        raise RuntimeError("extensions.init_extensions() must be called first")
    return _DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """Return a new sqlite3 connection with Row factory (legacy-compatible).

    The connection is closed by the caller (use as a context manager or in
    a `try/finally`). Phase 2 will swap this for a pooled `Repository`
    pattern but the public signature stays identical.

    Note: legacy semantics (no foreign_keys enforcement). Use
    `make_request_conn()` for new code that needs FK enforcement.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def make_request_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a per-request sqlite3 connection with **all** PRAGMA set.

    Fixes bug 1+2 (Phase 1 P0 cleanup 2026-08-16):
    - `PRAGMA foreign_keys=ON` — was missing in tasks_bp / tags_bp / gacha_bp
      per-request connections → SQLite default ignores FK constraints,
      allowing orphan references in `task_dependencies` / `timer_sessions`.
    - `PRAGMA journal_mode=WAL` — matches `configure_sqlite()` so concurrent
      connections don't trip over each other.
    - `PRAGMA busy_timeout=30000` — matches the project-wide constant.
    - `conn.row_factory = sqlite3.Row` — row-dict access for blueprints.

    `db_path` argument is the resolved absolute DB path; if None, defaults
    to the project-relative `data/task_publisher.db` (fallback for BP code
    paths that don't yet pass an explicit path).

    Caller is responsible for closing the connection.
    """
    if db_path is None:
        db_path = "data/task_publisher.db"
    conn = sqlite3.connect(db_path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    # Order matters: enable foreign_keys BEFORE any DDL/DML on the connection.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    # WAL is a per-database property, not per-connection; setting it on
    # every connection is harmless (idempotent) and keeps this helper
    # safe to call even when the DB hasn't been `configure_sqlite()`d yet.
    conn.execute("PRAGMA journal_mode=WAL")
    return conn