"""server.app.app_factory - Phase 1 收紧版 Flask Application Factory.

设计原则（来自 docs/ARCHITECTURE_REDESIGN_2026-08-16.md §3 选定方案 C）：
- 后端 = Blueprint + Application Factory + Service/Repository 分层
- Phase 1 范围：注册 3 个 BP（tasks_bp / gacha_bp / tags_bp）+ 7 个 ensure_* schema
- 其余 9 个 BP（state/schedule/feedback/timer/knowledge/config/prompts/agent/discard）保留在 backend_api.py
- 入口仍可用 `python server/backend_api.py`（legacy 兼容，36/36 E2E 不受影响）
- 本工厂是**可选**入口；测试/Phase 2 可用 `create_app()` 装配新实例
"""

from flask import Flask
from flask_cors import CORS

from server.app.config import load_config
from server.app.extensions import get_db_connection, configure_sqlite
from server.schema import ensure_all as ensure_all_schema
from server.blueprints.tasks_bp import tasks_bp
from server.blueprints.gacha_bp import gacha_bp
from server.blueprints.tags_bp import tags_bp
from server.blueprints.state_bp import state_bp  # Phase 2 / Todo 1
from server.blueprints.timer_bp import timer_bp  # Phase 2 / Todo 4
from server.blueprints.schedule_bp import schedule_bp  # Phase 2 / Todo 2
from server.blueprints.knowledge_bp import knowledge_bp  # Phase 2 / Todo 5
from server.blueprints.feedback_bp import feedback_bp  # Phase 2 / Todo 3


def create_app(config=None):
    """Build and configure the Flask app instance.

    Returns a fully-wired Flask app with:
    - CORS enabled
    - 3 Blueprints registered (tasks / gacha / tags)
    - All 7 ensure_* schema applied (idempotent)

    Note: 9 other Blueprints remain in backend_api.py for Phase 1.
    Use `python server/backend_api.py` to run the legacy full app (36/36 E2E).
    """
    cfg = config or load_config()
    app = Flask(
        __name__,
        static_folder=cfg["_static_dir"],
        static_url_path="/static",
    )
    CORS(app)
    # Inject derived paths into app.config for blueprints to read.
    app.config["_db_path"] = cfg["_db_path"]
    app.config["_notes_dir"] = cfg["_notes_dir"]
    app.config["_project_root"] = cfg["_project_root"]

    conn = get_db_connection(cfg)
    try:
        # P0 fix 2026-08-16 (bug 1): enable foreign_keys BEFORE running
        # ensure_all so that schema with FOREIGN KEY clauses is created
        # with FK enforcement active. Without this, SQLite defaults to
        # foreign_keys=OFF and would silently allow orphan references.
        conn.execute("PRAGMA foreign_keys=ON")
        configure_sqlite(conn)
        ensure_all_schema(conn)
    finally:
        conn.close()

    app.register_blueprint(tasks_bp)
    app.register_blueprint(gacha_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(state_bp)  # Phase 2 / Todo 1 (11 endpoints)
    app.register_blueprint(timer_bp)  # Phase 2 / Todo 4 (5 endpoints)
    app.register_blueprint(schedule_bp)  # Phase 2 / Todo 2 (8 endpoints)
    app.register_blueprint(knowledge_bp)  # Phase 2 / Todo 5 (9 endpoints)
    app.register_blueprint(feedback_bp)  # Phase 2 / Todo 3 (3 endpoints)

    # M4: preserve remaining legacy-only HTTP routes during Factory cutover.
    # These adapters can be removed one module at a time after independent migration.
    from server.app.legacy_compat import register_legacy_compat
    register_legacy_compat(app, cfg)

    @app.route("/api/health")
    def _health():
        return {"status": "ok", "phase": 1}

    return app


__all__ = ["create_app"]
