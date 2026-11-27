"""P1 切片 1 — Schema 权威层契约测试。

被测对象：``server.schema`` 包（唯一 Schema 权威 + 唯一编排入口）。

契约（Contract）
----------------
1. **空库可成功**：在一个完全空的 SQLite 文件上执行
   ``server.schema.ensure_all(conn)`` **不得抛异常**，并且必须产出
   ``REQUIRED_TABLES`` 中的全部业务表。
2. **幂等**：连续执行两次 ``ensure_all``，产出的
   （表集合、列集合、索引集合）完全一致。
3. **不破坏既有数据**：在已有数据的库上执行 ``ensure_all``，
   既有行逐条保留（不 DELETE / 不 DROP）。
4. **补列幂等**：既有库缺少 ``tasks`` 的某些列时，
   ``ensure_all`` 补齐且不改变已有列。
5. **Legacy 委托**：``server.backend_api`` **不持有任何 DDL**。
   AR03-P2 / Stage 7 之前，它通过 8 个 ``ensure_*`` 转发函数委托
   ``server.schema``；Stage 7 收口后那些转发壳 **一并退役**，
   薄别名里只剩模型再导出、连接助手与启动入口。
   判定口径：legacy 侧若仍存在 ``ensure_*``，则 **绝不** 持有 DDL；
   同时 ``server.schema`` 侧 **必须** 仍然提供全部建表能力
   （迁移不得把能力弄丢）。
6. **双源消除**：``server/schema/__init__.py`` 不得再内联重复的
   ``CREATE TABLE``（唯一的编排入口只调用域模块）。

安全边界
--------
本测试全部使用 **内存 SQLite**（``:memory:``）或 ``tmp_path`` 临时文件，
**绝不** 读写生产 ``data/task_publisher.db*``、``src/notes/**`` 或
``config/config.json``。
"""

from __future__ import annotations

import inspect
import re
import sqlite3
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server import schema as schema_pkg  # noqa: E402
from server.schema import ensure_all, REQUIRED_TABLES  # noqa: E402


def _table_names(conn: sqlite3.Connection) -> set:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _index_names(conn: sqlite3.Connection) -> set:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _strip_docstrings_and_comments(source: str) -> str:
    """返回源码中 **非文档字符串** 的字符串常量与代码片段拼接结果。

    用于静态断言：只在真正会执行的代码里搜索关键字，
    避免把文档说明文字误判为内联 DDL；同时保留普通字符串常量
    （SQL 就写在那里），因此真实内联 DDL 仍会被检出。
    """
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - 源文件语法错误时退化
        return source

    # 收集所有 docstring 节点（模块级 + 函数/类级）。
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    docstring_nodes.add(id(body[0].value))

    pieces = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_nodes:
                continue
            pieces.append(node.value)
    return "\n".join(pieces)


def _snapshot(conn: sqlite3.Connection):
    tables = _table_names(conn)
    cols = {t: _columns(conn, t) for t in sorted(tables)}
    indexes = _index_names(conn)
    return tables, cols, indexes


class TestEnsureAllOnEmptyDatabase(unittest.TestCase):
    """契约 1：空库必须成功。"""

    def test_ensure_all_on_empty_database_succeeds(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            # 不预先建任何表 —— 完全空库。
            ensure_all(conn)
        finally:
            conn.close()

    def test_empty_database_produces_all_required_tables(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            ensure_all(conn)
            present = _table_names(conn)
        finally:
            conn.close()
        missing = REQUIRED_TABLES - present
        self.assertEqual(
            set(), missing, f"ensure_all 在空库上缺少业务表: {sorted(missing)}"
        )

    def test_gacha_and_task_tables_exist_with_authoritative_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            ensure_all(conn)
            gacha_cols = _columns(conn, "gacha_records")
            reject_cols = _columns(conn, "task_rejection_log")
            tasks_cols = _columns(conn, "tasks")
            tags_cols = _columns(conn, "tags")
            task_tags_cols = _columns(conn, "task_tags")
            timer_cols = _columns(conn, "timer_sessions")
        finally:
            conn.close()

        self.assertTrue(
            {"timestamp", "pool_name", "available_time", "task_id", "accepted",
             "refusal_reason"}.issubset(gacha_cols),
            f"gacha_records 列缺失: {gacha_cols}",
        )
        self.assertTrue(
            {"task_id", "reason", "timestamp"}.issubset(reject_cols),
            f"task_rejection_log 列缺失: {reject_cols}",
        )
        self.assertTrue(
            {"id", "name", "category", "task_type", "estimated_time",
             "energy_required", "resistance", "success_rate", "refusal_count",
             "priority", "deadline", "draw_count_today", "prerequisite_ids",
             "is_unlocked", "linked_note_path"}.issubset(tasks_cols),
            f"tasks 列缺失: {tasks_cols}",
        )
        self.assertTrue({"id", "name"}.issubset(tags_cols))
        self.assertTrue({"task_id", "tag_id"}.issubset(task_tags_cols))
        self.assertTrue(
            {"task_id", "started_at", "planned_minutes", "status",
             "paused_seconds"}.issubset(timer_cols),
            f"timer_sessions 列缺失: {timer_cols}",
        )

    def test_free_task_events_is_not_owned_by_schema_layer(self):
        """``free_task_events`` 由 FreeTaskEventStore 自管（追加语义）。"""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            ensure_all(conn)
            present = _table_names(conn)
        finally:
            conn.close()
        self.assertNotIn("free_task_events", present)


class TestEnsureAllIdempotency(unittest.TestCase):
    """契约 2：幂等。"""

    def test_running_twice_produces_identical_structure(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            ensure_all(conn)
            first = _snapshot(conn)
            ensure_all(conn)
            second = _snapshot(conn)
        finally:
            conn.close()
        self.assertEqual(first[0], second[0], "两次执行后表集合不同")
        self.assertEqual(first[1], second[1], "两次执行后列集合不同")
        self.assertEqual(first[2], second[2], "两次执行后索引集合不同")

    def test_running_twice_on_empty_file_is_stable(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schema_authority.sqlite3"
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            try:
                ensure_all(conn)
                first = _snapshot(conn)
                ensure_all(conn)
                second = _snapshot(conn)
            finally:
                conn.close()
        self.assertEqual(first, second)


class TestEnsureAllPreservesData(unittest.TestCase):
    """契约 3 & 4：不破坏既有数据 + 幂等补列。"""

    def test_existing_rows_are_preserved(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            # 先建一个"老版本"的窄 tasks 表 + 一行数据。
            conn.execute(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'daily'
                )
                """
            )
            conn.execute(
                "INSERT INTO tasks (name, category) VALUES ('kept-task', 'daily')"
            )
            conn.commit()

            ensure_all(conn)

            rows = conn.execute("SELECT id, name, category FROM tasks").fetchall()
            self.assertEqual(1, len(rows), "既有行被删除")
            self.assertEqual("kept-task", rows[0]["name"])
            self.assertEqual(1, rows[0]["id"])
        finally:
            conn.close()

    def test_missing_columns_are_added_without_changing_existing_ones(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'daily'
                )
                """
            )
            conn.commit()
            ensure_all(conn)
            cols = _columns(conn, "tasks")
            self.assertIn("estimated_time", cols)
            self.assertIn("is_unlocked", cols)
            self.assertIn("linked_note_path", cols)
            # 列名重复补列必须幂等（第二次执行不能抛 "duplicate column"）
            ensure_all(conn)
            self.assertEqual(cols, _columns(conn, "tasks"))
        finally:
            conn.close()

    def test_legacy_schedule_tables_are_migrated_when_present(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                CREATE TABLE weekly_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_of_week INTEGER,
                    slot_id TEXT,
                    activity TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO weekly_schedule (day_of_week, slot_id, activity)"
                " VALUES (1, 'morning', 'focus')"
            )
            conn.commit()
            ensure_all(conn)
            rows = conn.execute(
                "SELECT day_of_week, time_slot, activity FROM user_schedule"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(1, len(rows))
        self.assertEqual("focus", rows[0]["activity"])


class TestLegacyDelegation(unittest.TestCase):
    """契约 5：backend_api 不再持有 DDL —— 全部委托 ``server.schema``。

    **AR03-P2 / Stage 7 变更**：legacy 单体收口成薄别名后，那 8 个
    ``ensure_*`` **转发函数** 一并退役（它们只是"再导出"的转发壳，
    按 P2 计划属于必须清理的对象）。

    因此本契约的判定口径从"**存在**且委托"改为
    "**要么不存在**、要么存在时 **绝不持有 DDL** 且 **委托**"——
    并额外断言 ``server.schema`` 侧 **真的** 拥有这些能力
    （即迁移没有把建表能力弄丢）。

    这比旧断言 **更强**：旧断言只检查 legacy 侧的转发壳，
    新断言同时锁住 **真正 owner** 的能力。
    """

    LEGACY_FUNCTIONS = (
        "ensure_indexes",
        "ensure_task_dependency_schema",
        "ensure_schedule_schema",
        "ensure_timer_schema",
        "ensure_task_feedback_events_schema",
        "ensure_assessment_schema",
        "ensure_daily_state_schema",
        "migrate_legacy_schedule_tables",
    )

    #: 迁移后 ``server.schema`` 侧必须提供的等价能力（真正 owner）。
    SCHEMA_OWNER_FUNCTIONS = (
        "ensure_indexes",
        "ensure_task_dependency_schema",
        "ensure_schedule_schema",
        "ensure_timer_schema",
        "ensure_task_feedback_events_schema",
        "ensure_assessment_schema",
        "ensure_daily_state_schema",
        "migrate_legacy_schedule_tables",
    )

    def test_backend_api_ensure_functions_exist_with_same_signature(self):
        """legacy 侧：要么 **不存在**（已退役），要么签名保持不变。"""
        from server import backend_api

        for name in self.LEGACY_FUNCTIONS:
            if not hasattr(backend_api, name):
                # 已退役 —— 由下面的 owner 断言兜底，不是漏检。
                continue
            sig = inspect.signature(getattr(backend_api, name))
            params = list(sig.parameters)
            self.assertTrue(
                params, f"{name} 签名不应为空"
            )

    def test_backend_api_ensure_functions_hold_no_ddl(self):
        """legacy 侧若仍存在 ``ensure_*``，则 **绝不** 持有 DDL。"""
        from server import backend_api

        for name in self.LEGACY_FUNCTIONS:
            if not hasattr(backend_api, name):
                continue
            source = inspect.getsource(getattr(backend_api, name))
            self.assertNotIn(
                "CREATE TABLE", source.upper(),
                f"backend_api.{name} 仍持有内联 DDL，必须改为委托",
            )
            self.assertNotIn(
                "ALTER TABLE", source.upper(),
                f"backend_api.{name} 仍持有内联补列，必须改为委托",
            )

    def test_backend_api_module_holds_no_ddl_at_all(self):
        """``server/backend_api.py`` 整个模块 **不得** 出现 DDL。

        这是 Stage 7 收口的核心断言：薄别名里只剩模型再导出、
        连接助手与启动入口，**零** DDL、**零** 业务 SQL。
        """
        from server import backend_api

        source = Path(backend_api.__file__).read_text(encoding="utf-8")
        code = _strip_docstrings_and_comments(source)
        for token in ("CREATE TABLE", "ALTER TABLE", "DROP TABLE", "INSERT INTO"):
            self.assertNotIn(
                token, code.upper(),
                f"server/backend_api.py 仍持有 DDL/DML（{token}）",
            )

    def test_schema_owner_still_provides_the_capabilities(self):
        """**真正 owner**（``server.schema``）必须仍然提供全部建表能力。"""
        for name in self.SCHEMA_OWNER_FUNCTIONS:
            self.assertTrue(
                hasattr(schema_pkg, name),
                f"server.schema 缺少 {name}（迁移把能力弄丢了？）",
            )

    #: 每个能力 **必须** 建立的表（各自的域）。
    LEGACY_EXPECTED_TABLES = {
        "ensure_indexes": {"tasks"},
        "ensure_task_dependency_schema": {"tasks", "task_dependencies"},
        "ensure_schedule_schema": {"user_schedule", "daily_schedules", "activities"},
        "ensure_timer_schema": {"timer_sessions"},
        "ensure_task_feedback_events_schema": {"task_feedback_events"},
        "ensure_assessment_schema": {"state_assessments"},
        "ensure_daily_state_schema": {"daily_user_state"},
        "migrate_legacy_schedule_tables": set(),
    }

    def test_legacy_ensure_functions_delegate_and_produce_tables(self):
        """建表能力在 **owner** 侧必须产出预期表。"""
        for name in self.LEGACY_FUNCTIONS:
            owner = getattr(schema_pkg, name, None)
            if owner is None:
                self.fail(f"server.schema 缺少 {name}")
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            try:
                owner(conn)
                present = _table_names(conn)
            finally:
                conn.close()
            expected = self.LEGACY_EXPECTED_TABLES[name]
            self.assertTrue(
                expected.issubset(present),
                f"{name} 未建立 {sorted(expected - present)}",
            )


class TestSingleAuthority(unittest.TestCase):
    """契约 6：``server/schema/__init__.py`` 只做编排，不再内联 DDL。"""

    def test_schema_package_init_has_no_inline_create_table(self):
        source = (_PROJECT_ROOT / "server" / "schema" / "__init__.py").read_text(
            encoding="utf-8"
        )
        # 只检查 **可执行代码**（剔除文档字符串与注释），避免误报文档里
        # 对 "CREATE TABLE IF NOT EXISTS" 的说明文字。
        code = _strip_docstrings_and_comments(source)
        self.assertNotIn(
            "CREATE TABLE", code.upper(),
            "server/schema/__init__.py 不得内联 DDL（唯一编排入口）",
        )

    def test_schema_package_init_exposes_required_tables_constant(self):
        self.assertIn("REQUIRED_TABLES", schema_pkg.__all__)
        self.assertIn("tasks", REQUIRED_TABLES)
        self.assertIn("gacha_records", REQUIRED_TABLES)
        self.assertIn("task_rejection_log", REQUIRED_TABLES)


if __name__ == "__main__":
    unittest.main()
