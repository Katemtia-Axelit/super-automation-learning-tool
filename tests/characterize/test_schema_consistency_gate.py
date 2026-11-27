"""AR03-P5 —— Schema 一致性门禁的自动化回归测试。

被测对象：``scripts/check_schema_consistency.py``（门禁脚本本身）
          + ``server/schema/`` + 两个专用 Store（**14 + 2** 归属）。

本测试 **不** 重复实现门禁逻辑，而是 **验证门禁真的会失败**：
对每一类违规注入一个反例，断言门禁能捕获 —— 否则「门禁永远绿」就毫无意义。

覆盖的 14+2 归属
----------------
============================  ==========================================
表                            owner
============================  ==========================================
14 张集中表                   ``server/schema/*`` + ``ensure_all()``
``free_task_events``          ``FreeTaskEventStore``
``free_task_session_ownership``  ``SessionOwnershipStore``
============================  ==========================================

安全边界
--------
全部使用 **内存 SQLite** 或 ``tmp_path`` 临时文件；
**绝不** 读写生产 ``data/task_publisher.db*``、``src/notes/**``、
``config/config.json``。
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 载入门禁脚本
# ---------------------------------------------------------------------------

def _load_gate():
    """把 ``scripts/check_schema_consistency.py`` 作为模块载入。"""
    script = _PROJECT_ROOT / "scripts" / "check_schema_consistency.py"
    assert script.is_file(), f"门禁脚本不存在：{script}"
    spec = importlib.util.spec_from_file_location(
        "check_schema_consistency_under_test", script
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


# ---------------------------------------------------------------------------
# C1 / C6 —— 集中表由 ensure_all 产出
# ---------------------------------------------------------------------------

def test_ensure_all_creates_all_14_central_tables():
    """C1/C6：空库上 ``ensure_all()`` 产出全部 14 张集中表。"""
    from server.schema import REQUIRED_TABLES, ensure_all

    conn = sqlite3.connect(":memory:")
    try:
        ensure_all(conn)
        produced = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        conn.close()

    assert set(REQUIRED_TABLES) == set(gate.CENTRAL_TABLES), (
        "server.schema.REQUIRED_TABLES 与门禁的 14 张权威清单必须一致"
    )
    missing = set(gate.CENTRAL_TABLES) - produced
    assert not missing, f"ensure_all() 未产出集中表：{sorted(missing)}"


def test_central_table_count_is_14():
    """口径护栏：集中表恰好 14 张（防止悄悄增减）。"""
    assert len(gate.CENTRAL_TABLES) == 14
    assert len(set(gate.CENTRAL_TABLES)) == 14


# ---------------------------------------------------------------------------
# C2 —— 14+2 归属：专用表由 Store 创建，ensure_all 不越权
# ---------------------------------------------------------------------------

def test_ensure_all_does_not_create_dedicated_store_tables():
    """C2a（越权断言）：``ensure_all()`` **不得**创建两张专用表。

    这是本轮 P5 补齐的关键缺口 —— 此前门禁只验证了
    ``free_task_events`` 一张，**第二张** ``free_task_session_ownership``
    的归属从未被验证。
    """
    from server.schema import ensure_all

    conn = sqlite3.connect(":memory:")
    try:
        ensure_all(conn)
        produced = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        conn.close()

    for table in gate.DEDICATED_STORES:
        assert table not in produced, (
            f"ensure_all() 越权创建了专用 Store 表 {table} —— "
            f"owner 必须是 {gate.DEDICATED_STORES[table]['owner']}"
        )


def test_free_task_events_created_by_free_task_event_store(tmp_path):
    """C2b：``free_task_events`` **由** ``FreeTaskEventStore`` 创建。"""
    from server.services.free_task_events import FreeTaskEventStore

    db = tmp_path / "events.sqlite3"
    FreeTaskEventStore(db)

    conn = sqlite3.connect(db)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        triggers = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
    finally:
        conn.close()

    assert "free_task_events" in tables
    # append-only 语义必须真实生效
    assert any("no_update" in t for t in triggers)
    assert any("no_delete" in t for t in triggers)


def test_session_ownership_created_by_session_ownership_store(tmp_path):
    """C2c：``free_task_session_ownership`` **由** ``SessionOwnershipStore`` 创建。

    这是本轮补齐的 **第二张专用表** 的归属验证。
    """
    from server.services.free_task_session_ownership import SessionOwnershipStore

    db = tmp_path / "ownership.sqlite3"
    conn = sqlite3.connect(db)
    try:
        SessionOwnershipStore(conn).ensure_schema()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()

    assert "free_task_session_ownership" in tables


def test_session_ownership_ensure_schema_is_idempotent(tmp_path):
    """``SessionOwnershipStore.ensure_schema()`` 幂等。"""
    from server.services.free_task_session_ownership import SessionOwnershipStore

    db = tmp_path / "ownership.sqlite3"
    conn = sqlite3.connect(db)
    try:
        store = SessionOwnershipStore(conn)
        store.ensure_schema()
        first = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        store.ensure_schema()
        second = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()

    assert first == second


# ---------------------------------------------------------------------------
# C3 —— 域覆盖关系
# ---------------------------------------------------------------------------

def test_domain_coverage_has_no_gaps_or_duplicates():
    """C3：五域模块覆盖 14 张表，无遗漏、无重复归属。"""
    seen = {}
    for module, tables in gate.DOMAIN_TABLE_MAP.items():
        for table in tables:
            seen.setdefault(table, []).append(module)

    duplicated = {t: m for t, m in seen.items() if len(m) > 1}
    assert not duplicated, f"表被多个域声明：{duplicated}"
    assert set(seen) == set(gate.CENTRAL_TABLES)


# ---------------------------------------------------------------------------
# C4 —— 未授权重复 DDL
# ---------------------------------------------------------------------------

def test_create_table_only_in_whitelisted_modules():
    """C4：``server/**`` 中的 ``CREATE TABLE`` 恰好落在白名单内。"""
    whitelist_tables = set()
    for tables in gate.DDL_WHITELIST.values():
        whitelist_tables |= tables

    offenders = []
    for path in sorted((_PROJECT_ROOT / "server").rglob("*.py")):
        rel = path.relative_to(_PROJECT_ROOT).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        created = gate._find_created_tables(source)
        if not created:
            continue
        if rel not in gate.DDL_WHITELIST:
            offenders.append(f"{rel}: {sorted(set(created))}")
            continue
        extra = set(created) - gate.DDL_WHITELIST[rel]
        if extra:
            offenders.append(f"{rel}: 多余表 {sorted(extra)}")

    assert not offenders, f"未授权的 CREATE TABLE：{offenders}"


def test_ddl_finder_ignores_docstrings():
    """门禁的 DDL 扫描器不得把 **文档字符串** 里的示例 SQL 当成真实 DDL。"""
    source = '''
"""模块文档。

CREATE TABLE IF NOT EXISTS should_not_be_detected (id INTEGER);
"""
x = 1
'''
    assert gate._find_created_tables(source) == []


def test_ddl_finder_detects_real_ddl():
    """真实代码里的 ``CREATE TABLE`` 必须被检出。"""
    source = '''
DDL = """
CREATE TABLE IF NOT EXISTS real_table (id INTEGER PRIMARY KEY);
"""
'''
    assert "real_table" in gate._find_created_tables(source)


# ---------------------------------------------------------------------------
# C5 / C8 —— 幂等与数据保全
# ---------------------------------------------------------------------------

def test_ensure_all_is_idempotent():
    """C5：连跑两次 ``ensure_all()`` → 表/列/索引集合一致。"""
    from server.schema import ensure_all

    conn = sqlite3.connect(":memory:")
    try:
        ensure_all(conn)
        first = gate._snapshot(conn)
        ensure_all(conn)
        second = gate._snapshot(conn)
    finally:
        conn.close()

    assert first[0] == second[0], f"表集合不同：{sorted(first[0] ^ second[0])}"
    assert first[1] == second[1], (
        "列集合不同："
        + "; ".join(
            f"{t}: {sorted(first[1].get(t, set()) ^ second[1].get(t, set()))}"
            for t in sorted(set(first[1]) | set(second[1]))
            if first[1].get(t) != second[1].get(t)
        )
    )
    assert first[2] == second[2], f"索引集合不同：{sorted(first[2] ^ second[2])}"


def test_ensure_all_preserves_existing_rows():
    """C8：既有行不被删、旧列不被改。"""
    from server.schema import ensure_all

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO tasks (name) VALUES ('kept')")
        conn.commit()
        ensure_all(conn)
        rows = conn.execute("SELECT name FROM tasks").fetchall()
        cols = gate._columns(conn, "tasks")
    finally:
        conn.close()

    assert [r[0] for r in rows] == ["kept"]
    assert "estimated_time" in cols


# ---------------------------------------------------------------------------
# 门禁脚本自身
# ---------------------------------------------------------------------------

def test_gate_script_runs_and_passes():
    """门禁脚本在当前代码上必须退出码 0。"""
    report = gate.run_all()
    assert not report.failed, (
        "门禁报告违规：\n"
        + "\n".join(f"  - {v}" for v in report.violations)
    )


def test_gate_catches_unauthorized_ddl(tmp_path, monkeypatch):
    """反例注入：出现白名单外的 ``CREATE TABLE`` 时，门禁 **必须** 失败。

    证明门禁不是「永远绿」。
    """
    fake_server = tmp_path / "server"
    fake_server.mkdir()
    (fake_server / "rogue.py").write_text(
        'DDL = """CREATE TABLE IF NOT EXISTS rogue_table (id INTEGER);"""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)

    report = gate.Report()
    gate.check_no_unauthorized_ddl(report)
    assert report.failed, "门禁未能捕获未授权的 CREATE TABLE"
    assert "rogue" in " ".join(v.detail for v in report.violations)


def test_gate_catches_missing_central_table(monkeypatch):
    """反例注入：集中表清单与 ``REQUIRED_TABLES`` 不一致时，门禁必须失败。"""
    monkeypatch.setattr(gate, "CENTRAL_TABLES", gate.CENTRAL_TABLES + ("ghost",))
    report = gate.Report()
    gate.check_central_tables_produced(report)
    assert report.failed, "门禁未能捕获集中表清单不一致"


def test_redline_guard_rejects_production_db_path(tmp_path):
    """红线 fail-closed：门禁拒绝任何非临时目录的数据库路径。"""
    with pytest.raises(RuntimeError):
        gate._assert_temp_path(_PROJECT_ROOT / "data" / "task_publisher.db")


def test_redline_guard_rejects_outside_temp_path(tmp_path, monkeypatch):
    """红线 fail-closed：临时目录之外的路径一律拒绝。

    用 ``monkeypatch`` 把 "temp 根" 指向一个 **空** 子目录，
    于是 ``tmp_path`` 下的路径就变成 "temp 之外" —— 验证守卫确实在检查。
    """
    fake_temp = tmp_path / "_fake_temp_root"
    fake_temp.mkdir()
    monkeypatch.setattr(gate.tempfile, "gettempdir", lambda: str(fake_temp))

    with pytest.raises(RuntimeError):
        gate._assert_temp_path(tmp_path / "somewhere" / "x.sqlite3")
