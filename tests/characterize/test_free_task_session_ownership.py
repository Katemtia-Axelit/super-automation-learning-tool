"""自由任务会话所有权原语的 **合成** 刻画测试。

范围（``LT_RETENTION_FREE_TASK_SESSION_AUTHZ_SYNTH_20261023_O``）：

  A. 首次认领成功；同一 owner 重复认领幂等。
  B. 其他 owner 无法认领 / 无法 require 他人会话（fail closed）。
  C. 未知会话与非归属者 **不可区分** 的错误（类型 / code / 文案一致）。
  D. ``require_owner`` 不隐式认领：GET / summary 前必须先认领。
  E. 不同 owner 的不同会话可并存，互不干扰。
  F. 无 SQL 注入 / 非法 ID（含空白、控制字符、超长、大小写混淆）。
  G. 跨 **不同** ``sqlite3.Connection`` 的竞争抢占：唯一最终 owner。
  H. 关闭并重开同一个临时 SQLite 后归属持续。
  I. 模块 import / 构造 **不** 打开任何数据库（monkeypatch 记录
     ``sqlite3.connect`` + 临时 CWD 产物快照），全文件 **零** 生产库访问。
  J. **不存在** 无身份约束的公共 owner 查询入口（``get_owner`` 已移除）。

约束：本文件 **只** 使用 ``tempfile.TemporaryDirectory`` / ``tmp_path``
内 的合成 sqlite3 连接与内存连接，关闭后自动清理；**绝不** 访问
``data/``、``config/config.json``、``src/notes/**``、真实账号或凭据；
**不** 启动任何端口或应用；**不** 打开任何项目路径下的数据库文件
——即使只读探测也 **不允许**。
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services.free_task_session_ownership import (  # noqa: E402
    NOT_OWNED_CODE,
    NOT_OWNED_MESSAGE,
    TABLE_NAME,
    SessionOwnershipError,
    SessionOwnershipStore,
)

#: 合成 ID（纯测试常量，与任何真实用户 / 账号无关）。
OWNER_A = "user-alpha"
OWNER_B = "user-beta"
SESSION_1 = "session-0001"
SESSION_2 = "session-0002"


# ---------------------------------------------------------------------------
# 合成夹具
# ---------------------------------------------------------------------------


def _connect(db_path: str, *, timeout: float = 5.0) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=timeout, isolation_level=None)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _read_owner_raw(conn: sqlite3.Connection, session_id: str):
    """在 **合成** 库上用只读 ``SELECT`` 直接读取唯一归属行。

    模块刻意 **不** 暴露 ``get_owner``，因此测试内用一条显式
    ``sqlite3.Connection`` 自行断言 “唯一归属”。本函数 **只** 接受测试
    自己打开的临时 / 内存合成连接；调用方必须保证 ``conn`` 不指向任何
    项目真实数据库。
    """
    return conn.execute(
        f"SELECT owner_id FROM {TABLE_NAME} WHERE session_id = ?", (session_id,)
    ).fetchone()


def _owner_rows(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return list(conn.execute(f"SELECT session_id, owner_id FROM {TABLE_NAME}"))


@pytest.fixture()
def synthetic_db():
    """临时合成 SQLite 文件；teardown 自动删除整个目录。"""
    with TemporaryDirectory(prefix="ft-owner-") as tmp:
        db_path = os.path.join(tmp, "synthetic_ownership.db")
        yield db_path
    assert not os.path.exists(db_path), "临时合成库必须被自动清理"


@pytest.fixture()
def store(synthetic_db):
    """默认构造的 store（显式建表）。"""
    conn = _connect(synthetic_db)
    try:
        yield SessionOwnershipStore(conn, create_schema=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# A. 首次认领 + 幂等
# ---------------------------------------------------------------------------


def test_a_first_claim_succeeds_and_is_idempotent_for_same_owner(store):
    first = store.first_claim(SESSION_1, OWNER_A)
    assert first["claimed"] is True
    assert first["idempotent"] is False

    second = store.first_claim(SESSION_1, OWNER_A)
    assert second["claimed"] is False
    assert second["idempotent"] is True
    assert second["owner_id"] == OWNER_A

    rows = store.connection.execute(
        f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE session_id = ?", (SESSION_1,)
    ).fetchone()[0]
    assert rows == 1, "重复认领不得产生第二行"


# ---------------------------------------------------------------------------
# B. 其他 owner 无法认领 / 无法读取
# ---------------------------------------------------------------------------


def test_b_other_owner_cannot_claim_existing_session(store):
    store.first_claim(SESSION_1, OWNER_A)
    with pytest.raises(SessionOwnershipError) as excinfo:
        store.first_claim(SESSION_1, OWNER_B)
    assert excinfo.value.code == NOT_OWNED_CODE
    # 无公共 get_owner：测试用显式合成连接只读断言唯一归属未被改写。
    assert store.require_owner(SESSION_1, OWNER_A)["owner_id"] == OWNER_A
    assert _read_owner_raw(store.connection, SESSION_1)[0] == OWNER_A, (
        "归属不得被跨 owner 改写"
    )
    assert _owner_rows(store.connection) == [(SESSION_1, OWNER_A)]


def test_b_other_owner_cannot_require_owner(store):
    store.first_claim(SESSION_1, OWNER_A)
    with pytest.raises(SessionOwnershipError) as excinfo:
        store.require_owner(SESSION_1, OWNER_B)
    assert excinfo.value.code == NOT_OWNED_CODE
    assert OWNER_B not in excinfo.value.message, "错误不得回显 owner_id"
    assert SESSION_1 not in excinfo.value.message, "错误不得回显 session_id"


# ---------------------------------------------------------------------------
# C. 未知会话与非归属者不可区分
# ---------------------------------------------------------------------------


def test_c_unknown_session_and_foreign_session_are_indistinguishable(store):
    store.first_claim(SESSION_1, OWNER_A)

    with pytest.raises(SessionOwnershipError) as unknown:
        store.require_owner(SESSION_2, OWNER_A)  # 从未认领
    with pytest.raises(SessionOwnershipError) as foreign:
        store.require_owner(SESSION_1, OWNER_B)  # 他人拥有

    assert type(unknown.value) is type(foreign.value)
    assert unknown.value.code == foreign.value.code == NOT_OWNED_CODE
    assert unknown.value.message == foreign.value.message == NOT_OWNED_MESSAGE
    assert "session-0001" not in unknown.value.message
    assert "user-alpha" not in foreign.value.message


def test_c_preemption_probe_leaks_nothing_about_existence(store):
    """抢占失败对 “已被 A 认领的会话” 与 “已被 A2 认领的会话” 一致。"""
    store.first_claim(SESSION_1, OWNER_A)
    store.first_claim(SESSION_2, OWNER_B)
    with pytest.raises(SessionOwnershipError) as probe_a:
        store.first_claim(SESSION_1, OWNER_B)
    with pytest.raises(SessionOwnershipError) as probe_b:
        store.first_claim(SESSION_2, OWNER_A)

    assert type(probe_a.value) is type(probe_b.value)
    assert probe_a.value.code == probe_b.value.code == NOT_OWNED_CODE
    assert probe_a.value.message == probe_b.value.message == NOT_OWNED_MESSAGE


# ---------------------------------------------------------------------------
# D. GET / require 不隐式认领
# ---------------------------------------------------------------------------


def test_d_require_owner_does_not_implicitly_claim(store):
    with pytest.raises(SessionOwnershipError) as excinfo:
        store.require_owner(SESSION_1, OWNER_A)
    assert excinfo.value.code == NOT_OWNED_CODE

    assert _read_owner_raw(store.connection, SESSION_1) is None, (
        "require_owner 绝不能创建归属"
    )
    rows = store.connection.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    assert rows == 0


def test_d_first_claim_required_before_any_read(store):
    """真实 API 的调用顺序契约：先 POST 认领 → 再 GET summary。"""
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_1, OWNER_A)
    store.first_claim(SESSION_1, OWNER_A)
    assert store.require_owner(SESSION_1, OWNER_A)["owner_id"] == OWNER_A


# ---------------------------------------------------------------------------
# E. 不同 owner / 不同会话并存
# ---------------------------------------------------------------------------


def test_e_distinct_sessions_coexist_across_owners(store):
    store.first_claim(SESSION_1, OWNER_A)
    store.first_claim(SESSION_2, OWNER_B)

    assert store.require_owner(SESSION_1, OWNER_A)["owner_id"] == OWNER_A
    assert store.require_owner(SESSION_2, OWNER_B)["owner_id"] == OWNER_B
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_1, OWNER_B)
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_2, OWNER_A)


# ---------------------------------------------------------------------------
# F. 非法 ID / SQL 注入 / 大小写与空白混淆
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_session",
    [
        "",
        " ",
        " session-1",
        "session-1 ",
        "session\n1",
        "sess\x00ion",
        "sess'ion",
        'sess"ion',
        "sess;ion",
        "drop table " + TABLE_NAME,
        "session/1",
        "会话0001",
        "x" * 129,
    ],
)
def test_f_invalid_session_ids_are_rejected(store, bad_session):
    with pytest.raises(SessionOwnershipError):
        store.first_claim(bad_session, OWNER_A)
    with pytest.raises(SessionOwnershipError):
        store.require_owner(bad_session, OWNER_A)
    rows = store.connection.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    assert rows == 0


@pytest.mark.parametrize("bad_owner", [None, 123, True, b"user", "", " owner", "own er"])
def test_f_non_string_or_invalid_owner_ids_are_rejected(store, bad_owner):
    with pytest.raises(SessionOwnershipError):
        store.first_claim(SESSION_1, bad_owner)
    rows = store.connection.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    assert rows == 0


def test_f_sql_injection_attempt_is_inert(store):
    hostile = "sess' OR '1'='1"
    with pytest.raises(SessionOwnershipError):
        store.first_claim(hostile, OWNER_A)
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_1, hostile)
    # 表结构完好，未被注入语句破坏
    assert store.first_claim(SESSION_1, OWNER_A)["claimed"] is True


def test_f_case_and_whitespace_are_not_normalized(store):
    """不得通过 normalize 混淆大小写归属或空白值。"""
    store.first_claim(SESSION_1, OWNER_A)
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_1, OWNER_A.upper())
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_1.upper(), OWNER_A)
    store.first_claim(SESSION_2, "MixedCaseOwner")
    with pytest.raises(SessionOwnershipError):
        store.require_owner(SESSION_2, "mixedcaseowner")
    assert store.require_owner(SESSION_2, "MixedCaseOwner")["owner_id"] == "MixedCaseOwner"


# ---------------------------------------------------------------------------
# G. 跨不同 sqlite3.Connection 的竞争抢占
# ---------------------------------------------------------------------------


def test_g_race_across_connections_yields_single_final_owner(synthetic_db):
    """两个 **独立连接** 抢同一个 session_id → 恰好一个 owner。

    注意边界：这是同一 SQLite 文件上写锁串行化的结果，**不是** 分布式
    锁；跨机器 / 跨文件系统的保证不在本模块范围内。
    """
    setup = _connect(synthetic_db)
    SessionOwnershipStore(setup, create_schema=True)
    setup.close()

    barrier = threading.Barrier(2)
    results: dict[str, str] = {}
    db_errors: list[str] = []
    unexpected: list[BaseException] = []

    def claim(owner: str) -> None:
        conn = _connect(synthetic_db, timeout=10.0)
        try:
            local = SessionOwnershipStore(conn, busy_timeout_ms=10000)
            barrier.wait(timeout=10)
            local.first_claim(SESSION_1, owner)
            results[owner] = "claimed"
        except SessionOwnershipError as exc:
            # ``session_not_owned`` 是 **预期** 的竞争失败（抢输）；
            # 其余（含 SQLite busy → ``db_busy``）都视为可解释故障并显式暴露。
            if exc.code == NOT_OWNED_CODE:
                results[owner] = "lost"
            else:
                db_errors.append(f"{owner}: {exc.code}")
        except BaseException as exc:  # noqa: BLE001 - 记录并交由断言解释
            unexpected.append(exc)
        finally:
            conn.close()

    threads = [
        threading.Thread(target=claim, args=(OWNER_A,)),
        threading.Thread(target=claim, args=(OWNER_B,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not any(t.is_alive() for t in threads), "竞争线程未在超时内结束"
    assert not unexpected, f"竞争中出现未预期异常: {unexpected!r}"
    # SQLite busy/lock 是可解释的失败：显式报出，绝不选择性跳过。
    assert not db_errors, f"竞争中出现数据库忙/锁故障: {db_errors!r}"

    winners = [owner for owner, outcome in results.items() if outcome == "claimed"]
    losers = [owner for owner, outcome in results.items() if outcome == "lost"]
    assert len(winners) == 1, f"必须恰好一个 owner 认领成功，实际: {results}"
    assert len(losers) == 1, f"另一个 owner 必须以 session_not_owned 失败: {results}"

    verify = _connect(synthetic_db)
    try:
        final = SessionOwnershipStore(verify)
        winner = winners[0]
        assert final.require_owner(SESSION_1, winner)["owner_id"] == winner
        # 合成库上只读断言：竞争后确实只有唯一一行、归属即胜者。
        assert _owner_rows(verify) == [(SESSION_1, winner)]
        loser = losers[0]
        with pytest.raises(SessionOwnershipError) as excinfo:
            final.require_owner(SESSION_1, loser)
        assert excinfo.value.code == NOT_OWNED_CODE
    finally:
        verify.close()


def test_g_fail_closed_when_schema_absent(synthetic_db):
    """缺表 → 所有操作 fail closed，绝不默许访问。"""
    conn = _connect(synthetic_db)
    try:
        bare = SessionOwnershipStore(conn)  # create_schema 默认 False
        with pytest.raises(SessionOwnershipError) as excinfo:
            bare.require_owner(SESSION_1, OWNER_A)
        assert excinfo.value.code == "schema_missing"
        with pytest.raises(SessionOwnershipError):
            bare.first_claim(SESSION_1, OWNER_A)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# H. 重开持久性
# ---------------------------------------------------------------------------


def test_h_ownership_persists_after_reopen(synthetic_db):
    conn = _connect(synthetic_db)
    try:
        SessionOwnershipStore(conn, create_schema=True).first_claim(SESSION_1, OWNER_A)
    finally:
        conn.close()

    reopened = _connect(synthetic_db)
    try:
        store = SessionOwnershipStore(reopened)
        assert store.require_owner(SESSION_1, OWNER_A)["owner_id"] == OWNER_A
        with pytest.raises(SessionOwnershipError):
            store.require_owner(SESSION_1, OWNER_B)
        # 幂等认领在重开后依然幂等
        assert store.first_claim(SESSION_1, OWNER_A)["idempotent"] is True
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# I. import / 构造无副作用（零生产库访问）
# ---------------------------------------------------------------------------


def test_i_import_and_construction_touch_no_real_database(monkeypatch):
    """import + 构造 **不** 打开任何数据库（含项目真实库）。

    判定方式（**不** 探测任何真实路径）：

    1. ``sqlite3.connect`` 被替换为记录器 → import / reload / 构造期间
       任何连接尝试都会立即失败并被断言捕获；
    2. ``monkeypatch.chdir(tmp)`` → 若模块按相对路径定位 ``data/`` 之类
       的项目目录，只会落到空的临时目录，不可能碰到真实文件；
    3. 临时 CWD 产物快照 → import / 构造后目录仍为空。

    本测试 **绝不** 读取 / 探测 / 只读打开 ``PROJECT_ROOT/data``、
    ``config/``、``src/notes/`` 或任何项目内数据库。
    """
    import importlib
    import sqlite3 as sqlite3_module

    opened: list[tuple] = []
    real_connect = sqlite3_module.connect

    def _recording_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        opened.append((args, kwargs))
        raise AssertionError(
            f"import/构造阶段禁止打开任何数据库: args={args!r} kwargs={kwargs!r}"
        )

    monkeypatch.setattr(sqlite3_module, "connect", _recording_connect)
    # 即便解析失败也应走真实的 connect 调用路径，保证记录器被触达。
    assert real_connect is not _recording_connect

    with TemporaryDirectory(prefix="ft-import-") as tmp:
        original_cwd = os.getcwd()
        monkeypatch.chdir(tmp)
        before = sorted(os.listdir(tmp))
        assert before == [], "临时 CWD 必须初始为空"

        module = importlib.import_module("server.services.free_task_session_ownership")
        importlib.reload(module)
        assert module.TABLE_NAME == TABLE_NAME
        assert not opened, f"import/reload 期间不得连接任何数据库: {opened!r}"

        # 构造非法连接 → fail closed，且不创建任何文件。
        with pytest.raises(module.SessionOwnershipError):
            module.SessionOwnershipStore(None)
        with pytest.raises(module.SessionOwnershipError):
            module.SessionOwnershipStore("not-a-connection")
        assert not opened, f"构造阶段不得连接任何数据库: {opened!r}"

        # 只在 **临时目录** 内的合成库上完成一次真实端到端冒烟。
        monkeypatch.setattr(sqlite3_module, "connect", real_connect)
        smoke_path = os.path.join(tmp, "synthetic_import_smoke.db")
        conn = real_connect(smoke_path, isolation_level=None)
        try:
            store = module.SessionOwnershipStore(conn, create_schema=True)
            assert store.first_claim(SESSION_1, OWNER_A)["claimed"] is True
            assert store.require_owner(SESSION_1, OWNER_A)["owner_id"] == OWNER_A
        finally:
            conn.close()

        after = sorted(os.listdir(tmp))
        assert after == ["synthetic_import_smoke.db"], (
            f"临时目录中只允许出现我们自己的合成库: {after!r}"
        )

        # Windows: 必须先离开临时目录，否则 TemporaryDirectory 清理失败。
        monkeypatch.chdir(original_cwd)


# ---------------------------------------------------------------------------
# J. 不存在无身份约束的公共 owner 查询入口
# ---------------------------------------------------------------------------


def test_j_no_identity_free_owner_lookup_is_publicly_callable():
    """``get_owner`` 已彻底移除：只有携带 ``owner_id`` 的正道可用。"""
    import inspect

    import server.services.free_task_session_ownership as ownership_module

    store_members = set(dir(SessionOwnershipStore))
    public_callables = {
        name
        for name, value in inspect.getmembers(SessionOwnershipStore, callable)
        if not name.startswith("_")
    }

    # 直接负例：不存在仍可被用户直接调用的无身份读取路径。
    assert "get_owner" not in store_members
    assert not hasattr(SessionOwnershipStore, "get_owner")
    for banned in ("get_owner", "owner_of", "lookup_owner", "find_owner", "read_owner"):
        assert banned not in store_members, f"{banned} 属于无身份归属查询，禁止公开"
        assert banned not in getattr(ownership_module, "__all__", [])

    module_level = [
        name
        for name in dir(ownership_module)
        if not name.startswith("_") and callable(getattr(ownership_module, name, None))
    ]
    for name in module_level:
        assert not name.startswith(("get_owner", "owner_of", "find_owner"))

    # 公共方法签名 **必须** 携带 owner_id 身份约束（property 除外）。
    for name in sorted(public_callables):
        if name == "connection":
            continue
        sig = inspect.signature(getattr(SessionOwnershipStore, name))
        params = [
            p
            for p in sig.parameters
            if p not in ("self",)
            and sig.parameters[p].kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        assert "owner_id" in params or name == "ensure_schema", (
            f"公共方法 {name}{sig} 缺少 owner_id 身份约束"
        )

    # 正例：授权判定只走 require_owner / first_claim。
    assert "require_owner" in public_callables
    assert "first_claim" in public_callables

    source = inspect.getsource(ownership_module)
    assert "def get_owner" not in source, "模块源码中不得残留 get_owner 定义"