"""Application Factory **显式 opt-in** 装配自由任务受保护预览的合成刻画测试。

范围（``LT_RETENTION_FACTORY_OPTIN_SYNTH_20261023_I``）：

  A. 默认关闭（最重要的回归门）
     - ``create_app(synthetic_cfg)`` 的 url_map 中 **不存在**
       ``/api/free-tasks`` 及其任何子路由；
     - 默认路径 **不构造** 自由任务 store（不新建任何事件库文件）；
     - ``free_task_preview=None`` / ``{"enabled": False}`` /
       完全不传参 三种“关”的形态产出 **完全相同** 的 route inventory；
     - ``app_factory`` 对 ``server.blueprints.free_task_bp`` 的 import 必须是
       **函数体内的延迟 import**（AST 断言）—— 默认路径根本不会加载它。

  B. 错误 opt-in 在 **任何数据库初始化之前** fail closed
     - 非 dict / 缺 enabled / enabled 非 bool / 缺 store / store=None /
       缺 authorizer / authorizer=None / 非 callable / 未知字段；
     - 每一种都抛 ``TypeError`` 或 ``ValueError``，并且
       ``get_db_connection`` 的调用次数 **为 0**（``mock.patch`` 探针），
       即坏 opt-in **绝不** 触碰普通数据库。

  C. 显式 opt-in 才出现受保护 POST / GET
     - 未授权 POST / GET / OPTIONS → 401，且事件 0；
     - authorizer 抛异常 → 503，且事件 0、响应不回显异常内容；
     - 正确授权 → started → completed → GET summary 全链路 200。

  D. 安全不回退
     - 同一 app 上再注册 **无认证** 旧工厂 → G 阶段注册期守卫抛
       ``RuntimeError``（不得误添加无认证 BP）；
     - Factory **不自动** 安装 E 组 ``register_free_task_preview_errors``：
       opt-in 之后匹配阶段 404 / 405 仍是原生 werkzeug 行为（非 JSON）；
     - 默认 app 的 ``/api/free-tasks`` 仍是原生 404。

  E. 红线未触碰
     - 真实 ``data/task_publisher.db``、``config/config.json``、
       ``src/notes/**`` 的目录快照在测试前后 **完全一致**；
     - 合成 store 的库文件落在 ``TemporaryDirectory`` 内。

**纯合成**：全部 ``_db_path`` / ``_static_dir`` / ``_notes_dir`` /
``_project_root`` 都指向 tempfile 根；**不** 调用 ``load_config()`` 读真实
``config/config.json``；**不** 启动真实服务、**不** 监听端口、**不** 连 socket；
假凭据是固定测试常量，与任何真实机密无关。

已知的合成接缝（刻意、并且被断言覆盖）
--------------------------------------
**AR03-P2 / Stage 7 起该接缝已消失。** 此前 ``create_app`` 内部会调用
``server.app.legacy_compat.register_legacy_compat``，它要求
``server.backend_api`` 的源码根 **严格等于** ``cfg["_project_root"]``。
本文件在 **进程内** 运行，``server`` 包来自真实项目根，因此合成根必然不相等；
过去把该函数替换成 **只记录调用** 的替身（``legacy_compat_recorder``）并
断言它 **恰好被调用一次**。

Stage 7 把兼容桥从装配流程中 **整体移除**（挂载路由数恒为 0），
因此：

* ``create_app`` **不再** 调用兼容桥 —— 断言改为 **零次调用**；
* 该替身保留下来，用来 **证明** 它确实没有被调用（而不是因为
  monkeypatch 失效导致误判）。

自由任务 opt-in 的路由增量正是本条测试要刻画的差异，与 legacy 兼容路由无关。
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

flask = pytest.importorskip("flask")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask  # noqa: E402

from server.app import app_factory  # noqa: E402
from server.app.app_factory import (  # noqa: E402
    FREE_TASK_PREVIEW_CONFIG_KEY,
    FREE_TASK_PREVIEW_OPT_IN_KEYS,
    create_app,
)
from server.blueprints import free_task_bp  # noqa: E402
from server.blueprints.free_task_bp import (  # noqa: E402
    AUTHORIZATION_UNAVAILABLE_CODE,
    LEGACY_PREVIEW_BLUEPRINT_NAME,
    PROTECTED_PREVIEW_BLUEPRINT_NAME,
    REGISTRATION_CONFLICT_CODE,
    REGISTRATION_CONFLICT_CONFIG_KEY,
    UNAUTHORIZED_CODE,
    create_free_task_blueprint,
)
from server.services import free_task_domain as domain  # noqa: E402
from server.services.free_task_events import FreeTaskEventStore  # noqa: E402

URL_PREFIX = "/api/free-tasks"
EVENTS_URL = f"{URL_PREFIX}/events"

TS0 = "2026-10-23T03:00:00Z"
TS1 = "2026-10-23T03:10:00Z"
TS2 = "2026-10-23T03:25:00Z"

#: **固定测试常量**，仅用于合成沙箱；与任何真实机密无关。
FAKE_AUTHORIZATION_HEADER = "Bearer SYNTHETIC-NOT-A-REAL-SECRET"
FAKE_BAD_AUTHORIZATION_HEADER = "Bearer SYNTHETIC-WRONG-VALUE"

#: 合成根里必须预先存在的表（``ensure_indexes`` 会对它们建索引）。
_SEED_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'daily',
    completed INTEGER DEFAULT 0,
    is_unlocked INTEGER DEFAULT 1,
    in_discard_pile INTEGER DEFAULT 0,
    deadline TEXT
);
CREATE TABLE IF NOT EXISTS task_tags (task_id INTEGER, tag_id INTEGER);
CREATE TABLE IF NOT EXISTS task_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    depends_on_task_id INTEGER
);
"""


# ---------------------------------------------------------------------------
# 合成 cfg（所有派生路径都指向 tempfile 根，绝不回落真实项目路径）
# ---------------------------------------------------------------------------

def build_synthetic_config(root: Path) -> dict:
    """构造全合成 cfg：**不** 调用 ``load_config()``，**不** 读真实配置。"""
    root = Path(root)
    data_dir = root / "data"
    static_dir = root / "static"
    notes_dir = root / "notes"
    for directory in (data_dir, static_dir, notes_dir, root / "config"):
        directory.mkdir(parents=True, exist_ok=True)

    (static_dir / "index.html").write_text("SYNTHETIC_ONLY", encoding="utf-8")

    db_path = data_dir / "synthetic_factory.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    # 合成 config.json 只是为了让“没有读到真实 config”这一点可被检验；
    # 它 **不** 是 cfg 的来源（cfg 全部由本函数显式给出）。
    (root / "config" / "config.json").write_text(
        json.dumps({"database": {"task_db_path": "data/synthetic_factory.sqlite3"}}),
        encoding="utf-8",
    )

    return {
        "server": {"host": "127.0.0.1", "port": 0, "debug": False},
        "obsidian": {"vault_path": "notes", "notes_directory": "notes"},
        "api": {"openai_api_key": "", "claude_api_key": ""},
        "database": {"task_db_path": "data/synthetic_factory.sqlite3"},
        "_project_root": str(root),
        "_static_dir": str(static_dir),
        "_db_path": str(db_path),
        "_notes_dir": str(notes_dir),
        # AR03-P2 / Stage 5：配置文件路径也必须在合成根内 ——
        # ``POST /api/config/save`` 绝不能写到生产的 config/config.json。
        "_config_path": str(root / "config" / "config.json"),
    }


@pytest.fixture()
def sandbox():
    with TemporaryDirectory(prefix="lt_ft_factory_optin_") as temp:
        yield Path(temp)


@pytest.fixture()
def synthetic_cfg(sandbox):
    return build_synthetic_config(sandbox / "synthetic_root")


@pytest.fixture()
def legacy_compat_recorder(monkeypatch):
    """替换 legacy 兼容装配为只记录调用的替身（合成接缝，见模块文档）。

    **AR03-P2 / Stage 7**：兼容桥已从装配流程中整体移除，因此断言的是
    **零次调用**。替身本身仍保留，用来证明"没被调用"是真事实，
    而不是 monkeypatch 失效造成的假绿。

    **AR03-P5**：兼容桥文件已归档到 ``_archive/``（零路由 / 零副作用 /
    零运行时引用）。此时 **没有可替换的模块** —— 但断言的 **不变量**
    （零次调用）依然成立，且更强：模块 **根本不存在**，不可能被调用。
    因此本 fixture 在归档后返回 **空列表**，并额外断言
    ``server/**`` 无任何对它的引用。
    """
    calls: list = []

    def _record(app, config):
        calls.append(("legacy_compat", config.get("_db_path")))
        app.config["_compat_route_count"] = 0
        return 0

    try:
        monkeypatch.setattr(
            "server.app.legacy_compat.register_legacy_compat", _record
        )
    except (ImportError, AttributeError):
        # 已归档：模块不存在 → 不可能有调用。
        # 额外校验「server/** 无运行时引用」，确保归档是安全的。
        import ast
        from pathlib import Path

        server_dir = Path(__file__).resolve().parents[2] / "server"
        offenders = []
        for path in server_dir.rglob("*.py"):
            if path.name == "legacy_compat.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.endswith("legacy_compat"):
                            offenders.append(path.name)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    if base.endswith("legacy_compat"):
                        offenders.append(path.name)
                    for alias in node.names:
                        if alias.name == "register_legacy_compat":
                            offenders.append(path.name)
        assert not offenders, (
            "兼容桥归档后仍存在运行时引用: " + ", ".join(sorted(set(offenders)))
        )
    return calls


@pytest.fixture()
def store(sandbox):
    """合成事件账本（唯一按测试用例路径落盘，绝不碰 data/）。"""
    return FreeTaskEventStore(str(sandbox / "synthetic_events.sqlite3"))


@pytest.fixture()
def authorizer():
    return make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)


# ---------------------------------------------------------------------------
# 辅助：假 authorizer（显式注入的合成凭据校验，非生产授权模型）
# ---------------------------------------------------------------------------

def make_constant_header_authorizer(expected_header: str):
    def _authorizer(request) -> bool:
        return request.headers.get("Authorization") == expected_header

    return _authorizer


def make_raising_authorizer(exc: Exception):
    def _authorizer(request) -> bool:
        raise exc

    return _authorizer


def auth_headers(value: str = FAKE_AUTHORIZATION_HEADER) -> dict:
    return {"Authorization": value}


def start_payload():
    return {
        "event_type": domain.EVENT_STARTED,
        "activity": "复习线性代数",
        "category": "学习",
        "planned_minutes": 25,
        "occurred_at": TS0,
        "reason": domain.DEFAULT_FREE_TASK_REASON,
    }


def completion_payload(actual_minutes=25, reported=25):
    return {
        "event_type": domain.EVENT_COMPLETED,
        "actual_minutes": actual_minutes,
        "occurred_at": TS2,
        "reported_study_minutes": reported,
    }


def post_body(session_id, event_id, payload):
    return {
        "action": "append",
        "session_id": session_id,
        "event_id": event_id,
        "event_payload": payload,
    }


def post(client, body, headers=None):
    return client.post(
        EVENTS_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        headers=headers or {},
    )


def authed_post(client, body):
    return post(client, body, headers=auth_headers())


def get_summary(client, session_id, headers=None):
    return client.get(
        f"{URL_PREFIX}/sessions/{session_id}/summary", headers=headers or {}
    )


def error_of(response):
    body = response.get_json()
    assert body is not None and isinstance(body, dict), response.get_data(as_text=True)
    assert body["ok"] is False
    error = body["error"]
    assert set(error) == {"code", "message"}
    return error["code"]


def route_inventory(app) -> set:
    """``{(rule, method)}``，与 test_route_inventory 的统计口径一致。"""
    return {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    }


def free_task_rules(app) -> set:
    return {item for item in route_inventory(app) if item[0].startswith(URL_PREFIX)}


def opt_in(store, authorizer):
    return {"enabled": True, "store": store, "authorizer": authorizer}


# ---------------------------------------------------------------------------
# A. 默认关闭（最重要的回归门）
# ---------------------------------------------------------------------------

def test_default_factory_has_no_free_task_routes(
    synthetic_cfg, legacy_compat_recorder
):
    """默认 ``create_app(cfg)`` 的 url_map 里 **没有** ``/api/free-tasks``。"""
    app = create_app(synthetic_cfg)

    assert free_task_rules(app) == set()
    assert not any(URL_PREFIX in rule for rule, _ in route_inventory(app))
    # 显式标记键在默认 app 中不存在（不是 False，而是根本没有这个 opt-in）。
    assert FREE_TASK_PREVIEW_CONFIG_KEY not in app.config
    # AR03-P2 / Stage 7：兼容桥已从装配流程移除 —— 断言 **零次调用**。
    assert len(legacy_compat_recorder) == 0


def test_default_factory_registers_no_free_task_blueprint(
    synthetic_cfg, legacy_compat_recorder
):
    """默认 app 的 ``app.blueprints`` 不含任何自由任务预览蓝图。"""
    app = create_app(synthetic_cfg)

    assert LEGACY_PREVIEW_BLUEPRINT_NAME not in app.blueprints
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME not in app.blueprints
    assert app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is None


def test_default_factory_constructs_no_store_and_creates_no_event_db(
    synthetic_cfg, legacy_compat_recorder, sandbox
):
    """默认路径 **不构造** 自由任务 store：临时根里不出现任何事件库文件。"""
    before = sorted(p.name for p in Path(synthetic_cfg["_project_root"]).rglob("*"))

    create_app(synthetic_cfg)

    after = sorted(p.name for p in Path(synthetic_cfg["_project_root"]).rglob("*"))
    # 唯一允许新增的是 sqlite 索引 / WAL 之类由 ensure_all 产生的文件。
    new_names = set(after) - set(before)
    assert not any("event" in name.lower() for name in new_names), new_names
    # 新建的 .sqlite3 只能是我们自己 seed 的那一个（WAL/SHM 允许）。
    new_sqlite = {n for n in new_names if n.endswith(".sqlite3")}
    assert new_sqlite <= {"synthetic_factory.sqlite3"}, new_sqlite
    # sandbox 里没有额外的自由任务账本。
    assert not any("synthetic_events" in p.name for p in sandbox.iterdir())


def test_default_route_inventory_identical_for_all_off_forms(
    synthetic_cfg, legacy_compat_recorder
):
    """不传参 / ``None`` / ``{"enabled": False}`` 三种“关”的 inventory 完全一致。"""
    implicit = route_inventory(create_app(synthetic_cfg))
    explicit_none = route_inventory(create_app(synthetic_cfg, free_task_preview=None))
    explicit_off = route_inventory(
        create_app(synthetic_cfg, free_task_preview={"enabled": False})
    )

    # 非空自检：防止“三个空集合相等”的假绿。
    assert len(implicit) > 10, sorted(implicit)[:10]
    assert implicit == explicit_none == explicit_off
    assert not any(URL_PREFIX in rule for rule, _ in implicit)


def test_opt_in_is_keyword_only_in_signature():
    """``free_task_preview`` 必须是 keyword-only，且默认 None（关）。"""
    sig = inspect.signature(create_app)
    param = sig.parameters["free_task_preview"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is None
    # 既有旧调用 ``create_app(cfg)`` 仍只有一个位置参数。
    positional = [
        p.name
        for p in sig.parameters.values()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    assert positional == ["config"]


def test_app_factory_imports_free_task_bp_lazily():
    """默认路径不加载自由任务模块：import 必须在函数体 **内部**。"""
    tree = ast.parse(Path(app_factory.__file__).read_text(encoding="utf-8"))

    module_level_imports = set()
    for node in tree.body:  # 只看模块顶层
        if isinstance(node, ast.Import):
            module_level_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_level_imports.add(node.module)
    assert not any("free_task" in name for name in module_level_imports), (
        module_level_imports
    )

    deferred = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and "free_task" in node.module
    ]
    # 只允许延迟 import **受保护** 工厂模块。
    assert {node.module for node in deferred} == {"server.blueprints.free_task_bp"}
    # 导入的 **符号名** 必须恰好是受保护工厂 —— 无认证工厂绝不得被导入。
    imported_names = {alias.name for node in deferred for alias in node.names}
    assert imported_names == {"create_protected_free_task_blueprint"}, imported_names


def test_factory_reads_no_environment_or_config_for_enable(
    synthetic_cfg, legacy_compat_recorder, monkeypatch
):
    """enable 绝不来自环境变量：把可疑变量设为真值也不得启用。"""
    for name in (
        "FREE_TASK_PREVIEW",
        "LT_FREE_TASK_PREVIEW_OPT_IN",
        "SAL_FREE_TASK_PREVIEW",
        "FLASK_DEBUG",
        "FLASK_ENV",
    ):
        monkeypatch.setenv(name, "1")

    app = create_app(synthetic_cfg)
    assert free_task_rules(app) == set()
    assert FREE_TASK_PREVIEW_CONFIG_KEY not in app.config


# ---------------------------------------------------------------------------
# B. 错误 opt-in 在 **任何数据库初始化之前** fail closed
# ---------------------------------------------------------------------------

BAD_OPT_INS = [
    pytest.param(True, TypeError, id="bool-true"),
    pytest.param(False, TypeError, id="bool-false"),
    pytest.param(1, TypeError, id="int-1"),
    pytest.param("enabled", TypeError, id="str"),
    pytest.param([{"enabled": True}], TypeError, id="list"),
    pytest.param({"store": "x"}, ValueError, id="missing-enabled"),
    pytest.param({}, ValueError, id="empty-dict"),
    pytest.param({"enabled": 1}, TypeError, id="enabled-int"),
    pytest.param({"enabled": "true"}, TypeError, id="enabled-str"),
    pytest.param({"enabled": None}, TypeError, id="enabled-none"),
    pytest.param({"enabled": True}, ValueError, id="missing-store"),
    pytest.param({"enabled": True, "store": None}, ValueError, id="store-none"),
    pytest.param(
        {"enabled": True, "store": "not-a-store"},
        TypeError,
        id="missing-authorizer",
    ),
    pytest.param(
        {"enabled": True, "store": "not-a-store", "authorizer": None},
        TypeError,
        id="authorizer-none",
    ),
    pytest.param(
        {"enabled": True, "store": "not-a-store", "authorizer": "Bearer x"},
        TypeError,
        id="authorizer-str",
    ),
    pytest.param(
        {"enabled": True, "store": "not-a-store", "authorizer": 42},
        TypeError,
        id="authorizer-int",
    ),
    pytest.param(
        {"enabled": True, "store": "not-a-store", "authorizer": lambda r: True,
         "db_path": "data/task_publisher.db"},
        ValueError,
        id="unknown-field",
    ),
    pytest.param(
        {"enabled": True, "store": "not-a-store",
         "authorizer": lambda r: True, "enabled_dbg": True},
        ValueError,
        id="unknown-field-typo",
    ),
]


@pytest.mark.parametrize("bad,expected", BAD_OPT_INS)
def test_bad_opt_in_fails_closed_before_touching_any_database(
    synthetic_cfg, bad, expected, monkeypatch
):
    """坏 opt-in → 抛错，且 ``get_db_connection`` **零调用**（不碰普通 DB）。"""
    calls: list = []

    def _probe(config):  # 任何调用都会被记录（必须保持为空）
        calls.append(config)
        raise AssertionError("坏 opt-in 不得打开普通数据库")

    monkeypatch.setattr(app_factory, "get_db_connection", _probe)

    with pytest.raises(expected):
        create_app(synthetic_cfg, free_task_preview=bad)

    assert calls == [], (
        "坏 opt-in 在 DB 初始化之前就必须被拒绝，实际打开了连接："
        f"{calls!r}"
    )


def test_bad_opt_in_does_not_create_a_flask_app(
    synthetic_cfg, legacy_compat_recorder
):
    """坏 opt-in 在第 1 道关口就崩：legacy 装配与 schema 都不会执行。"""
    with pytest.raises(TypeError):
        create_app(synthetic_cfg, free_task_preview={"enabled": "yes"})

    assert legacy_compat_recorder == []
    # 合成根里的库文件仍是 seed 时的状态（没有被 ensure_all 动过）。
    db = Path(synthetic_cfg["_db_path"])
    conn = sqlite3.connect(db)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert "tasks" in tables
    # ensure_all 会创建这些表；它们缺席证明 schema 从未运行。
    assert "user_schedule" not in tables, tables
    assert "daily_state" not in tables, tables


def test_opt_in_keys_are_exactly_three():
    """opt-in 合同键集固定为三个，不接受任何“附加开关”。"""
    assert FREE_TASK_PREVIEW_OPT_IN_KEYS == {"enabled", "store", "authorizer"}
    assert isinstance(FREE_TASK_PREVIEW_OPT_IN_KEYS, frozenset)


def test_opt_in_contract_rejects_unknown_fields_even_when_enabled_false(
    synthetic_cfg, legacy_compat_recorder
):
    """``enabled=False`` 也不能夹带未知字段（不得静默忽略拼写错误）。"""
    with pytest.raises(ValueError):
        create_app(
            synthetic_cfg,
            free_task_preview={"enabled": False, "store": None, "extra": 1},
        )


# ---------------------------------------------------------------------------
# C. 显式 opt-in 才出现受保护 POST / GET
# ---------------------------------------------------------------------------

@pytest.fixture()
def opted_in_app(synthetic_cfg, legacy_compat_recorder, store, authorizer):
    app = create_app(synthetic_cfg, free_task_preview=opt_in(store, authorizer))
    app.config["TESTING"] = True
    return app


def test_opt_in_registers_protected_post_and_get(opted_in_app):
    """显式 opt-in 后：受保护蓝图的 POST / GET 路由出现。"""
    rules = free_task_rules(opted_in_app)
    assert (EVENTS_URL, "POST") in rules
    assert (f"{URL_PREFIX}/sessions/<session_id>/summary", "GET") in rules
    assert opted_in_app.config[FREE_TASK_PREVIEW_CONFIG_KEY] is True
    # 注册的是 **受保护** 蓝图，不是无认证旧蓝图。
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME in opted_in_app.blueprints
    assert LEGACY_PREVIEW_BLUEPRINT_NAME not in opted_in_app.blueprints


def test_opt_in_delta_is_only_the_free_task_routes(
    synthetic_cfg, legacy_compat_recorder, store, authorizer
):
    """opt-in 相对默认 app 的 **唯一** 增量就是自由任务路由。"""
    default_rules = route_inventory(create_app(synthetic_cfg))
    opted_in_rules = route_inventory(
        create_app(synthetic_cfg, free_task_preview=opt_in(store, authorizer))
    )

    added = opted_in_rules - default_rules
    removed = default_rules - opted_in_rules
    assert removed == set(), f"opt-in 不得删除任何既有路由: {sorted(removed)}"
    assert all(rule.startswith(URL_PREFIX) for rule, _ in added), sorted(added)
    assert (EVENTS_URL, "POST") in added


def test_unauthorized_post_get_options_are_401_and_write_no_event(
    opted_in_app, store
):
    """未授权 POST / GET / OPTIONS → 401，且账本事件数保持 0。"""
    client = opted_in_app.test_client()

    for response in (
        post(client, post_body("sess-u", "u-1", start_payload())),
        post(
            client,
            post_body("sess-u", "u-2", start_payload()),
            headers=auth_headers(FAKE_BAD_AUTHORIZATION_HEADER),
        ),
        get_summary(client, "sess-u"),
        client.options(EVENTS_URL),
    ):
        assert response.status_code == 401
        assert error_of(response) == UNAUTHORIZED_CODE
        raw = response.get_data(as_text=True)
        for forbidden in ("SYNTHETIC", "Bearer", "Authorization"):
            assert forbidden not in raw

    assert store.list_events("sess-u") == []
    assert store.get_summary("sess-u")["event_count"] == 0


def test_authorizer_exception_is_503_and_writes_no_event(
    synthetic_cfg, legacy_compat_recorder, store
):
    """authorizer 抛异常 → 503 ``free_task_authorization_unavailable``，零事件。"""
    app = create_app(
        synthetic_cfg,
        free_task_preview=opt_in(
            store,
            make_raising_authorizer(RuntimeError("secret-token-abc123")),
        ),
    )
    app.config["TESTING"] = True
    client = app.test_client()

    response = post(client, post_body("sess-503", "s-1", start_payload()))
    assert response.status_code == 503
    assert error_of(response) == AUTHORIZATION_UNAVAILABLE_CODE
    raw = response.get_data(as_text=True)
    for forbidden in ("secret-token", "abc123", "RuntimeError"):
        assert forbidden not in raw

    assert get_summary(client, "sess-503").status_code == 503
    assert store.list_events("sess-503") == []
    assert store.get_summary("sess-503")["event_count"] == 0


def test_authorized_full_session_flow(opted_in_app, store):
    """正确授权：started → completed → GET summary 全链路 200。"""
    client = opted_in_app.test_client()

    r1 = authed_post(client, post_body("sess-1", "evt-1", start_payload()))
    assert r1.status_code == 200, r1.get_data(as_text=True)
    b1 = r1.get_json()
    assert b1["ok"] is True and b1["action"] == "append"
    assert b1["summary"]["event_count"] == 1

    r2 = authed_post(client, post_body("sess-1", "evt-2", completion_payload()))
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()["summary"]["successful_tasks"] == 1

    r3 = client.get(
        f"{URL_PREFIX}/sessions/sess-1/summary", headers=auth_headers()
    )
    assert r3.status_code == 200
    b3 = r3.get_json()
    assert b3["action"] == "summary"
    assert b3["summary"]["event_count"] == 2
    assert b3["summary"]["effective_study_minutes"] == 25
    assert (
        b3["summary"]["verification"]
        == "user_reported_not_independently_verified"
    )
    assert len(store.list_events("sess-1")) == 2


def test_opt_in_does_not_change_health_or_other_routes(opted_in_app):
    """opt-in 不改变既有端点的行为（``/api/health`` 仍 200）。"""
    client = opted_in_app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# D. 安全不回退
# ---------------------------------------------------------------------------

def test_legacy_unprotected_blueprint_cannot_be_added_to_opted_in_app(
    opted_in_app, store
):
    """G 守卫不变：同一 app 不得再添加 **无认证** 旧工厂（注册期 fail closed）。"""
    with pytest.raises(RuntimeError) as excinfo:
        opted_in_app.register_blueprint(create_free_task_blueprint(store))

    message = str(excinfo.value)
    assert LEGACY_PREVIEW_BLUEPRINT_NAME in message
    assert PROTECTED_PREVIEW_BLUEPRINT_NAME in message
    assert FAKE_AUTHORIZATION_HEADER not in message
    assert "Bearer" not in message

    # 被拒之后：无认证写入依然不可能（冲突态下前缀返回 503）。
    assert opted_in_app.config.get(REGISTRATION_CONFLICT_CONFIG_KEY) is True
    client = opted_in_app.test_client()
    response = post(client, post_body("sess-guard", "g-1", start_payload()))
    assert response.status_code != 200
    assert error_of(response) == REGISTRATION_CONFLICT_CODE
    assert store.list_events("sess-guard") == []


def test_factory_does_not_auto_install_e_group_json_404_405(opted_in_app):
    """Factory **不** 自动安装 E 组 handler：匹配阶段 404/405 仍是原生行为。"""
    client = opted_in_app.test_client()

    r404 = client.get(f"{URL_PREFIX}/nope")
    assert r404.status_code == 404
    # 原生 werkzeug → HTML，``get_json()`` 为 None（证明不是 E 组的 JSON 形状）。
    assert r404.get_json() is None
    assert r404.is_json is False

    r405 = client.get(EVENTS_URL)
    assert r405.status_code == 405
    assert r405.get_json() is None
    assert r405.is_json is False


def test_default_factory_free_task_path_is_plain_404(
    synthetic_cfg, legacy_compat_recorder
):
    """默认 app 上 ``/api/free-tasks`` 是原生 404（路由根本不存在）。"""
    app = create_app(synthetic_cfg)
    app.config["TESTING"] = True
    client = app.test_client()

    assert client.get(URL_PREFIX).status_code == 404
    assert client.get(EVENTS_URL).status_code == 404
    assert post(client, post_body("sess-d", "d-1", start_payload())).status_code == 404


def test_opted_in_factory_uses_protected_factory_only(
    opted_in_app, authorizer, store
):
    """装配来源只能是受保护工厂：蓝图角色标记必须是 protected。"""
    registry = list(opted_in_app.blueprints.values())
    roles = [
        getattr(bp, "free_task_role", None)
        for bp in registry
        if getattr(bp, "free_task_role", None) is not None
    ]
    assert roles == [free_task_bp.ROLE_PROTECTED], roles
    # 仍有授权闸门（未授权 GET 401）。
    assert get_summary(opted_in_app.test_client(), "sess-r").status_code == 401


def test_opted_in_app_does_not_expose_real_user_credentials(opted_in_app):
    """合成凭据只存在于测试；响应里绝不回显任何 Authorization 值。"""
    client = opted_in_app.test_client()
    raw = client.get(f"{URL_PREFIX}/sessions/none/summary").get_data(as_text=True)
    assert FAKE_AUTHORIZATION_HEADER not in raw
    assert "SYNTHETIC" not in raw


# ---------------------------------------------------------------------------
# E. 红线未触碰
# ---------------------------------------------------------------------------

#: 项目红线路径（**只读快照**，测试前后必须完全一致）。
_REDLINE_PATHS = (
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "config" / "config.json",
    PROJECT_ROOT / "src" / "notes",
)


def _snapshot(paths) -> dict:
    """红线快照。

    ``data/`` 与 ``config/config.json`` 记录 ``(size, mtime_ns)`` —— 本轮测试
    从不打开它们，任何写入都会体现到 mtime。

    ``src/notes/**`` 是 **用户正在使用的 Obsidian 库**（本轮只读，绝不被本
    测试写入），但其 mtime 可能被外部编辑器 / 同步进程独立改动，因此这里
    记录 ``(相对路径, size, 是否目录)``：任何 **新增 / 删除 / 改大小** 都会
    被抓到，而外部元数据抖动不会造成假失败。这条捕获比 mtime 更能证明
    “测试没有动过知识库”。
    """
    snap = {}
    for path in paths:
        path = Path(path)
        if not path.exists():
            snap[str(path)] = None
            continue
        if path.is_dir():
            if path.name == "notes" and path.parent.name == "src":
                # 用户知识库：内容形态快照（不含 mtime）。
                snap[str(path)] = sorted(
                    (str(p.relative_to(path)), p.stat().st_size, p.is_dir())
                    for p in path.rglob("*")
                )
            else:
                snap[str(path)] = sorted(
                    (str(p.relative_to(path)), p.stat().st_size, p.stat().st_mtime_ns)
                    for p in path.rglob("*")
                )
        else:
            stat = path.stat()
            snap[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return snap


@pytest.fixture()
def redline_snapshot():
    return _snapshot(_REDLINE_PATHS)


def test_redline_paths_untouched_by_synthetic_opt_in(
    synthetic_cfg, legacy_compat_recorder, store, authorizer, redline_snapshot
):
    """整轮合成 opt-in 流程 **不接触** data/ 、config.json、src/notes/**。"""
    assert redline_snapshot, "红线快照为空 → 断言本身失效，测试不可信"

    app = create_app(synthetic_cfg, free_task_preview=opt_in(store, authorizer))
    app.config["TESTING"] = True
    client = app.test_client()

    assert authed_post(client, post_body("sess-red", "r-1", start_payload())).status_code == 200
    assert authed_post(client, post_body("sess-red", "r-2", completion_payload())).status_code == 200
    assert get_summary(client, "sess-red", headers=auth_headers()).status_code == 200

    assert _snapshot(_REDLINE_PATHS) == redline_snapshot


def test_synthetic_store_lives_inside_tempdir(store, sandbox):
    """合成事件库落在 ``TemporaryDirectory`` 内，绝不指向项目 data/。"""
    db = Path(store.db_path).resolve()
    assert str(db).startswith(str(sandbox.resolve()))
    assert db.name != "task_publisher.db"
    assert "data" + os.sep + "task_publisher" not in str(db)


def test_cfg_paths_all_point_into_synthetic_root(synthetic_cfg):
    """cfg 的五个派生路径全部在合成根内（不存在真实项目路径回落）。"""
    root = Path(synthetic_cfg["_project_root"]).resolve()
    for key in (
        "_db_path",
        "_static_dir",
        "_notes_dir",
        "_project_root",
        "_config_path",
    ):
        value = Path(synthetic_cfg[key]).resolve()
        assert str(value).startswith(str(root)) or value == root, (key, str(value))
    assert "task_publisher.db" not in synthetic_cfg["_db_path"]


def test_test_module_never_calls_load_config():
    """本测试文件 **不** 调用 ``load_config()``（不读真实 config）。"""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "load_config"
    ]
    assert calls == [], "本测试文件不得调用 load_config()"


def test_helpers_are_self_consistent():
    """小自检：辅助函数可用，避免“断言本身空转”的假绿。"""
    # 合成 authorizer 在拿到带 header 的假 request 时返回 True，否则 False。
    class _FakeRequest:
        def __init__(self, headers):
            self.headers = headers

    authorizer = make_constant_header_authorizer(FAKE_AUTHORIZATION_HEADER)
    assert authorizer(_FakeRequest({"Authorization": FAKE_AUTHORIZATION_HEADER})) is True
    assert authorizer(_FakeRequest({})) is False
    assert set(post_body("s", "e", start_payload())) == {
        "action",
        "session_id",
        "event_id",
        "event_payload",
    }
    # Flask 依赖在位（否则上面的 importorskip 已经 skip）。
    assert Flask is not None
    assert opt_in("store", authorizer) == {
        "enabled": True,
        "store": "store",
        "authorizer": authorizer,
    }
