#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AR03-P5 —— Schema 一致性门禁。

Purpose
-------
数据库结构的 **唯一权威** 是 ``server/schema/``（14 张集中管理的业务表）。
另有两张表由 **专用 Store** 自主管理，**不在** 集中 Schema 内：

============================  ==========================================
表                            owner
============================  ==========================================
``free_task_events``          ``server/services/free_task_events.py``
                              ``::FreeTaskEventStore``
                              （append-only 触发器 + 部分唯一索引）
``free_task_session_ownership``  ``server/services/free_task_session_ownership.py``
                              ``::SessionOwnershipStore``
                              （幂等 ``ensure_schema()``）
============================  ==========================================

因此本门禁的准确口径是 **14 + 2**，**不是** 「15 张表全部属于 ``server/schema/``」。

Checks
------
C1  ``REQUIRED_TABLES`` 完整性：14 张集中表 **全部** 由 ``ensure_all()`` 在空库上产出。
C2  **14+2 归属**：
      * 14 张集中表的 DDL **只**出现在 ``server/schema/*``；
      * ``ensure_all()`` **不得**创建两张专用表（越权断言）；
      * 两张专用表 **确实** 由各自的 Store 创建（Store 自证）。
C3  域覆盖关系：``tasks`` / ``gacha`` / ``timer`` / ``state`` / ``feedback``
      五域模块与 ``REQUIRED_TABLES`` 的映射无遗漏、无重复归属。
C4  未授权重复 DDL：AST 扫描 ``server/**``，``CREATE TABLE`` 出现位置必须
      **恰好**落在白名单内。
C5  幂等：``ensure_all()`` 连跑两次 → 表/列/索引集合完全一致。
C6  空库可初始化：临时 SQLite 上 ``ensure_all()`` 成功且产出全部 14 张表。
C7  实际表集合 == 权威定义：空库执行后的表集合 ⊇ ``REQUIRED_TABLES``，
      且 **不含** 两张专用表。
C8  数据保全：既有行不被删、旧列不被改。

数据安全
--------
**全程只用临时合成 SQLite**（``tempfile`` 目录 / ``:memory:``）。
本脚本内置 **红线 fail-closed**：任何解析出的数据库路径若不在临时目录内，
立即以非 0 退出码失败 —— **绝不**打开、读取、哈希或复制生产数据库
（``data/task_publisher.db{,-wal,-shm}``）及其同族文件。

Usage
-----
    python scripts/check_schema_consistency.py
    python scripts/check_schema_consistency.py --json

Exit codes
----------
    0  全部检查通过
    1  存在违规（逐条打印）
    2  脚本自身失败（红线拦截 / 环境问题）
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 常量 —— 权威口径
# ---------------------------------------------------------------------------

#: 集中 Schema 管理的 **14** 张业务表（与 ``server.schema.REQUIRED_TABLES`` 对齐）。
CENTRAL_TABLES: Tuple[str, ...] = (
    # 任务域
    "tasks",
    "tags",
    "task_tags",
    "task_dependencies",
    # 抽卡域
    "gacha_records",
    "task_rejection_log",
    # 计时器域
    "timer_sessions",
    # 状态域
    "daily_user_state",
    "state_assessments",
    "user_schedule",
    "daily_schedules",
    "activities",
    # 反馈域
    "task_feedback_events",
    "task_completion_feedback",
)

#: 由 **专用 Store** 自主管理的表 —— ``ensure_all()`` **不得**创建它们。
DEDICATED_STORES: Dict[str, Dict[str, str]] = {
    "free_task_events": {
        "module": "server/services/free_task_events.py",
        "owner": "FreeTaskEventStore",
        "reason": (
            "append-only 触发器（禁止 UPDATE / DELETE）+ 同一会话仅允许一个完成事件的"
            "部分唯一索引 —— 语义必须由拥有者自己建表"
        ),
    },
    "free_task_session_ownership": {
        "module": "server/services/free_task_session_ownership.py",
        "owner": "SessionOwnershipStore",
        "reason": (
            "会话归属表由 Store 在 **注入的连接** 上幂等建表（ensure_schema()），"
            "并且刻意 **不** 在 import 期产生任何写入副作用"
        ),
    },
}

#: ``CREATE TABLE`` 的 **唯一授权** 出现位置（相对项目根的路径 → 允许的表名集合）。
DDL_WHITELIST: Dict[str, Set[str]] = {
    "server/schema/tasks.py": {"tasks", "tags", "task_tags", "task_dependencies"},
    "server/schema/gacha.py": {"gacha_records", "task_rejection_log"},
    "server/schema/timer.py": {"timer_sessions"},
    "server/schema/state.py": {
        "daily_user_state",
        "state_assessments",
        "user_schedule",
        "daily_schedules",
        "activities",
    },
    "server/schema/feedback.py": {"task_feedback_events", "task_completion_feedback"},
    "server/schema/notes.py": set(),  # 当前为 no-op 占位
    "server/services/free_task_events.py": {"free_task_events"},
    "server/services/free_task_session_ownership.py": {"free_task_session_ownership"},
}

#: 域模块 → 它拥有的表。用于 C3（域覆盖关系）。
DOMAIN_TABLE_MAP: Dict[str, Set[str]] = {
    "server/schema/tasks.py": {
        "tasks",
        "tags",
        "task_tags",
        "task_dependencies",
    },
    "server/schema/gacha.py": {"gacha_records", "task_rejection_log"},
    "server/schema/timer.py": {"timer_sessions"},
    "server/schema/state.py": {
        "daily_user_state",
        "state_assessments",
        "user_schedule",
        "daily_schedules",
        "activities",
    },
    "server/schema/feedback.py": {
        "task_feedback_events",
        "task_completion_feedback",
    },
}

#: 生产数据库家族 —— 本脚本 **绝不** 触碰。
FORBIDDEN_DB_BASENAMES = {
    "task_publisher.db",
    "task_publisher.db-wal",
    "task_publisher.db-shm",
}


# ---------------------------------------------------------------------------
# 结果容器
# ---------------------------------------------------------------------------

class Violation:
    """一条门禁违规。"""

    def __init__(self, check: str, detail: str) -> None:
        self.check = check
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.check}] {self.detail}"

    def to_dict(self) -> Dict[str, str]:
        return {"check": self.check, "detail": self.detail}


class Report:
    """门禁结果聚合。"""

    def __init__(self) -> None:
        self.violations: List[Violation] = []
        self.passed: List[str] = []

    def fail(self, check: str, detail: str) -> None:
        self.violations.append(Violation(check, detail))

    def ok(self, check: str) -> None:
        self.passed.append(check)

    @property
    def failed(self) -> bool:
        return bool(self.violations)


# ---------------------------------------------------------------------------
# 数据安全 —— 红线 fail-closed
# ---------------------------------------------------------------------------

def _assert_temp_path(path: Path) -> Path:
    """确认 ``path`` 位于 **临时目录** 内；否则 fail closed。

    这是本脚本对生产数据库家族的 **硬防线**：任何解析出的数据库路径
    若不在临时目录内，立即抛错，**绝不**打开生产库。
    """
    resolved = Path(os.path.abspath(str(path)))
    base = resolved.name.lower()
    if base in FORBIDDEN_DB_BASENAMES:
        raise RuntimeError(
            "红线拦截：拒绝访问生产数据库家族 "
            f"{base}（本脚本只允许临时合成 SQLite）"
        )
    temp_root = Path(os.path.abspath(tempfile.gettempdir())).resolve()
    try:
        resolved.resolve().relative_to(temp_root)
    except ValueError:
        # 不在 temp 目录下 —— 只允许 ``:memory:``（由调用方保证）。
        raise RuntimeError(
            f"红线拦截：数据库路径不在临时目录内 -> {resolved}"
        )
    return resolved


def _temp_conn() -> Tuple[sqlite3.Connection, Any]:
    """建立一个 **临时** SQLite 连接（``:memory:``）。

    ``:memory:`` 数据库不落盘，天然满足「只用合成数据」约束。
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn, conn


def _temp_file_conn(directory: str) -> Tuple[sqlite3.Connection, Path]:
    """在 ``directory`` 下建立一个临时文件 SQLite 连接（用于幂等持久性检查）。"""
    root = Path(os.path.abspath(directory))
    _assert_temp_path(root / "probe.sqlite3")
    root.mkdir(parents=True, exist_ok=True)
    path = root / "probe.sqlite3"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn, path


# ---------------------------------------------------------------------------
# SQLite  introspection helpers
# ---------------------------------------------------------------------------

def _table_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _index_names(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _snapshot(conn: sqlite3.Connection):
    tables = _table_names(conn)
    cols = {t: _columns(conn, t) for t in sorted(tables)}
    indexes = _index_names(conn)
    return tables, cols, indexes


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _collect_sql_strings(source: str) -> List[str]:
    """收集源码中 **非文档字符串** 的字符串常量（SQL 就住在这些常量里）。

    关键点：**文档字符串** 里出现的 ``CREATE TABLE`` 只是说明文字，
    不是真实 DDL —— 必须排除，否则门禁会产生误报。

    f-string（``ast.JoinedStr``）会被 **拼接** 成一段文本后再交给调用方 ——
    这样 ``CREATE TABLE IF NOT EXISTS {TABLE_NAME} (...)`` 里的插值占位符
    会被保留为一个整体，表名由调用方另行解析。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_ids.add(id(body[0].value))

    out: List[str] = []
    # 先收集 f-string（JoinedStr）内部的常量 id —— 它们必须 **整体** 处理，
    # 否则 "CREATE TABLE IF NOT EXISTS " 这一段会被当成独立常量单独匹配，
    # 造成 "<动态>" 假阳性。
    joined_value_ids: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant):
                    joined_value_ids.add(id(value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            if id(node) in joined_value_ids:
                # 属于某个 f-string 的一部分 —— 已在下面整体处理。
                continue
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            parts: List[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                elif isinstance(value, ast.FormattedValue):
                    # 保留占位符的 **名字**（若可静态解析），
                    # 让下游能把 {TABLE_NAME} 解析为真实表名。
                    expr = value.value
                    if isinstance(expr, ast.Name):
                        parts.append("{" + expr.id + "}")
                    elif (
                        isinstance(expr, ast.Attribute)
                        and isinstance(expr.value, ast.Name)
                    ):
                        parts.append("{" + expr.value.id + "." + expr.attr + "}")
                    else:
                        parts.append("{__dynamic__}")
            joined = "".join(parts)
            if "CREATE TABLE" in joined.upper():
                out.append(joined)
    return out


_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:[\"'`\[]?(?P<name>[A-Za-z_][A-Za-z0-9_]*)|\{(?P<ph>[A-Za-z_][A-Za-z0-9_]*)\})",
    re.IGNORECASE,
)


def _resolve_table_names(source: str) -> Dict[str, str]:
    """解析源码中 **模块级常量** 的字符串值。

    用途：``free_task_events.py`` 里写的是
    ``CREATE TABLE IF NOT EXISTS {TABLE_NAME} (...)``，表名来自模块级常量
    ``TABLE_NAME = "free_task_events"``。门禁必须能把它解析成 **真实表名**，
    否则无法判断归属。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    out: Dict[str, str] = {}
    for node in tree.body:
        # 普通赋值：``TABLE_NAME = "free_task_events"``
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                isinstance(target, ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                out[target.id] = node.value.value
        # 带注解赋值：``TABLE_NAME: str = "free_task_events"``
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if (
                isinstance(target, ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                out[target.id] = node.value.value
    return out


def _find_created_tables(source: str) -> List[str]:
    """找出源码里 ``CREATE TABLE [IF NOT EXISTS] <name>`` 的表名。

    只扫描 **可执行代码**（剔除文档字符串），因此文档里对
    "CREATE TABLE IF NOT EXISTS" 的说明文字 **不会** 被误判。

    f-string 里的 ``{TABLE_NAME}`` 会被解析为该模块的 **真实** 模块级常量值；
    解析不到时保留为 ``<动态>`` 占位。
    """
    consts = _resolve_table_names(source)
    names: List[str] = []
    for text in _collect_sql_strings(source):
        for match in _CREATE_TABLE_RE.finditer(text):
            placeholder = match.group("ph")
            if placeholder:
                names.append(consts.get(placeholder, "<动态>"))
                continue
            raw = match.group("name") or ""
            if raw.upper() in {"IF", "NOT", "EXISTS"}:
                # 畸形 SQL（如缺表名）—— 记为动态，避免误判为具体表名。
                names.append("<动态>")
                continue
            names.append(raw)
    return names


# ---------------------------------------------------------------------------
# C1 / C6 / C7 —— 集中 Schema 的实际产出
# ---------------------------------------------------------------------------

def check_central_tables_produced(report: Report) -> Set[str]:
    """C1 + C6 + C7：空库上 ``ensure_all()`` 产出全部 14 张集中表。"""
    from server.schema import REQUIRED_TABLES, ensure_all

    declared = set(REQUIRED_TABLES)
    if declared != set(CENTRAL_TABLES):
        report.fail(
            "C1",
            "server.schema.REQUIRED_TABLES 与门禁的 14 张权威表清单不一致："
            f"仅在 REQUIRED_TABLES = {sorted(declared - set(CENTRAL_TABLES))}；"
            f"仅在门禁清单 = {sorted(set(CENTRAL_TABLES) - declared)}",
        )
    else:
        report.ok("C1")

    conn, _ = _temp_conn()
    try:
        ensure_all(conn)
        produced = _table_names(conn)
    except Exception as exc:  # noqa: BLE001
        report.fail("C6", f"空库上 ensure_all() 失败：{exc}")
        return set()
    finally:
        conn.close()

    missing = set(CENTRAL_TABLES) - produced
    if missing:
        report.fail("C6", f"空库上 ensure_all() 未产出集中表：{sorted(missing)}")
    else:
        report.ok("C6")

    # C7：实际表集合 ⊇ 权威定义，且不含两张专用表（越权断言）。
    extra_dedicated = set(DEDICATED_STORES) & produced
    if extra_dedicated:
        report.fail(
            "C7",
            "ensure_all() 越权创建了专用 Store 表："
            f"{sorted(extra_dedicated)} —— 专用表必须由各自的 Store 建表",
        )
    else:
        report.ok("C7")

    return produced


# ---------------------------------------------------------------------------
# C2 —— 14+2 归属：专用表由 Store 创建，ensure_all 不越权
# ---------------------------------------------------------------------------

def check_dedicated_store_ownership(report: Report) -> None:
    """C2：两张专用表 **由各自的 Store 创建**，且 ``ensure_all()`` 不创建它们。"""
    from server.schema import ensure_all

    # (a) ensure_all 不越权
    conn, _ = _temp_conn()
    try:
        ensure_all(conn)
        after_ensure_all = _table_names(conn)
    except Exception as exc:  # noqa: BLE001
        report.fail("C2", f"ensure_all() 失败：{exc}")
        return
    finally:
        conn.close()

    for table in DEDICATED_STORES:
        if table in after_ensure_all:
            report.fail(
                "C2",
                f"ensure_all() 越权创建了专用表 {table}"
                f"（owner = {DEDICATED_STORES[table]['owner']}）",
            )
            return
    report.ok("C2a")

    # (b) FreeTaskEventStore 自证：在合成临时库上构造 → 建表
    with tempfile.TemporaryDirectory(prefix="lt_schema_check_") as tmp:
        _assert_temp_path(Path(tmp) / "events.sqlite3")
        try:
            from server.services.free_task_events import FreeTaskEventStore

            store = FreeTaskEventStore(Path(tmp) / "events.sqlite3")
            del store
        except Exception as exc:  # noqa: BLE001
            report.fail(
                "C2",
                f"FreeTaskEventStore 无法在合成临时库上建表：{exc}",
            )
            return
        conn = sqlite3.connect(Path(tmp) / "events.sqlite3")
        try:
            present = _table_names(conn)
        finally:
            conn.close()
        if "free_task_events" not in present:
            report.fail("C2", "FreeTaskEventStore 未创建 free_task_events 表")
            return
    report.ok("C2b")

    # (c) SessionOwnershipStore 自证：注入连接 → ensure_schema()
    with tempfile.TemporaryDirectory(prefix="lt_schema_check_") as tmp:
        _assert_temp_path(Path(tmp) / "ownership.sqlite3")
        path = Path(tmp) / "ownership.sqlite3"
        conn = sqlite3.connect(path)
        try:
            from server.services.free_task_session_ownership import (
                SessionOwnershipStore,
            )

            SessionOwnershipStore(conn).ensure_schema()
            present = _table_names(conn)
        except Exception as exc:  # noqa: BLE001
            report.fail(
                "C2",
                f"SessionOwnershipStore 无法在合成临时库上建表：{exc}",
            )
            return
        finally:
            conn.close()
        if "free_task_session_ownership" not in present:
            report.fail(
                "C2", "SessionOwnershipStore 未创建 free_task_session_ownership 表"
            )
            return
    report.ok("C2c")


# ---------------------------------------------------------------------------
# C3 —— 域覆盖关系
# ---------------------------------------------------------------------------

def check_domain_coverage(report: Report) -> None:
    """C3：五域模块的表归属无遗漏、无重复。"""
    seen: Dict[str, List[str]] = {}
    for module, tables in DOMAIN_TABLE_MAP.items():
        for table in tables:
            seen.setdefault(table, []).append(module)

    duplicated = {t: mods for t, mods in seen.items() if len(mods) > 1}
    if duplicated:
        report.fail(
            "C3",
            "同一张表被多个域模块声明归属："
            + "; ".join(f"{t} -> {mods}" for t, mods in sorted(duplicated.items())),
        )
        return

    covered = set(seen)
    expected = set(CENTRAL_TABLES)
    if covered != expected:
        report.fail(
            "C3",
            "域模块覆盖与 14 张权威表清单不一致 —— "
            f"未覆盖 = {sorted(expected - covered)}；"
            f"多余 = {sorted(covered - expected)}",
        )
        return
    report.ok("C3")


# ---------------------------------------------------------------------------
# C4 —— 未授权重复 DDL
# ---------------------------------------------------------------------------

def check_no_unauthorized_ddl(report: Report) -> None:
    """C4：``server/**`` 中的 ``CREATE TABLE`` 必须恰好落在白名单内。"""
    server_dir = PROJECT_ROOT / "server"
    if not server_dir.is_dir():
        report.fail("C4", f"找不到 server 目录：{server_dir}")
        return

    whitelist_tables: Set[str] = set()
    for tables in DDL_WHITELIST.values():
        whitelist_tables |= tables

    offenders: List[str] = []
    for path in sorted(server_dir.rglob("*.py")):
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        created = _find_created_tables(source)
        if not created:
            continue
        if rel not in DDL_WHITELIST:
            offenders.append(
                f"{rel} 持有未授权的 CREATE TABLE：{sorted(set(created))}"
            )
            continue
        allowed = DDL_WHITELIST[rel]
        extra = set(created) - allowed
        if extra:
            offenders.append(
                f"{rel} 声明了不属于它的表：{sorted(extra)}（允许 = {sorted(allowed)}）"
            )
    if offenders:
        report.fail("C4", "；".join(offenders))
    else:
        report.ok("C4")


# ---------------------------------------------------------------------------
# C5 —— 幂等
# ---------------------------------------------------------------------------

def check_idempotency(report: Report) -> None:
    """C5：``ensure_all()`` 连跑两次 → 表/列/索引集合完全一致。"""
    from server.schema import ensure_all

    conn, _ = _temp_conn()
    try:
        ensure_all(conn)
        first = _snapshot(conn)
        ensure_all(conn)
        second = _snapshot(conn)
    except Exception as exc:  # noqa: BLE001
        report.fail("C5", f"ensure_all() 幂等性检查失败：{exc}")
        return
    finally:
        conn.close()

    if first[0] != second[0]:
        report.fail("C5", f"两次执行后表集合不同：{sorted(first[0] ^ second[0])}")
    elif first[1] != second[1]:
        report.fail("C5", "两次执行后列集合不同")
    elif first[2] != second[2]:
        report.fail("C5", "两次执行后索引集合不同")
    else:
        report.ok("C5")


# ---------------------------------------------------------------------------
# C8 —— 数据保全
# ---------------------------------------------------------------------------

def check_data_preservation(report: Report) -> None:
    """C8：``ensure_all()`` 不删既有行、不改既有列。"""
    from server.schema import ensure_all

    conn, _ = _temp_conn()
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
        conn.execute(
            "INSERT INTO tasks (name, category) VALUES ('kept-task', 'daily')"
        )
        conn.commit()

        ensure_all(conn)
        rows = conn.execute("SELECT id, name, category FROM tasks").fetchall()
        if len(rows) != 1 or rows[0]["name"] != "kept-task":
            report.fail("C8", "ensure_all() 破坏了既有行")
            return
        cols = _columns(conn, "tasks")
        if "estimated_time" not in cols or "is_unlocked" not in cols:
            report.fail("C8", "ensure_all() 未补齐缺失列（幂等补列失效）")
            return
    except Exception as exc:  # noqa: BLE001
        report.fail("C8", f"数据保全检查失败：{exc}")
        return
    finally:
        conn.close()
    report.ok("C8")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def run_all() -> Report:
    """执行全部检查。"""
    report = Report()
    check_central_tables_produced(report)
    check_dedicated_store_ownership(report)
    check_domain_coverage(report)
    check_no_unauthorized_ddl(report)
    check_idempotency(report)
    check_data_preservation(report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AR03-P5 Schema 一致性门禁（14 张集中表 + 2 张专用 Store 表）"
    )
    parser.add_argument(
        "--json", action="store_true", help="以 JSON 输出结果（供 CI / 其它门禁消费）"
    )
    args = parser.parse_args(argv)

    try:
        report = run_all()
    except RuntimeError as exc:
        # 红线 fail-closed
        print(f"[check_schema_consistency] 红线拦截：{exc}", file=sys.stderr)
        if args.json:
            print(
                json.dumps(
                    {"ok": False, "blocked": str(exc)}, ensure_ascii=False, indent=2
                )
            )
        return 2

    payload = {
        "ok": not report.failed,
        "central_tables": list(CENTRAL_TABLES),
        "dedicated_store_tables": {
            k: {"owner": v["owner"], "module": v["module"]}
            for k, v in DEDICATED_STORES.items()
        },
        "passed": report.passed,
        "violations": [v.to_dict() for v in report.violations],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("=== Schema 一致性门禁 ===")
        print(f"集中 Schema 表（server/schema/）：{len(CENTRAL_TABLES)} 张")
        for table in CENTRAL_TABLES:
            print(f"  - {table}")
        print(f"专用 Store 表（ensure_all 不创建）：{len(DEDICATED_STORES)} 张")
        for table, meta in DEDICATED_STORES.items():
            print(f"  - {table}  ← {meta['owner']}（{meta['module']}）")
        print()
        for check in report.passed:
            print(f"[PASS] {check}")
        if report.violations:
            print()
            for violation in report.violations:
                print(f"[FAIL] {violation}", file=sys.stderr)
            print(
                f"\nFAIL —— 发现 {len(report.violations)} 处违规。",
                file=sys.stderr,
            )
        else:
            print("\nPASS —— Schema 一致性全部通过（14 集中 + 2 专用 Store）。")

    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
