"""server.services.free_task_session_ownership - 自由任务会话所有权原语。

定位
----
这是一个 **独立、默认未接线、纯合成** 的最小组件：回答一个只有两个
输入的问题——**“这个 ``session_id`` 是不是属于这个 ``owner_id``？”**

它存在的理由
------------
`create_protected_free_task_blueprint(store, authorizer)` 的 preview 目前
只要求 authorizer 返回一个布尔值。一个布尔授权 **不表达归属**：真实接入
时，任何已认证用户都可能用别人的 ``session_id`` 读取或写入别人的自由
任务会话。本模块提供“可被未来显式组合”的归属原语，使 Blueprint 在
POST 前与 GET summary 前都能强制 **“会话属于当前用户”**。

**这不是一个已接线的认证系统**
--------------------------------
    本模块 **不** 提供登录、会话 Cookie、密码、令牌签发、CSRF、CORS、
    浏览器端身份或任何速率限制；它 **不** 从 Flask request / header /
    环境变量 / 配置文件里自行提取 ``owner_id``；它 **不** 内置任何
    “测试密码”式的准入凭据。

    ``owner_id`` **必须** 由未来的真实认证系统（登录态、session cookie、
    OIDC claim 等）解析后 **显式传入**。本模块只是被那个系统 *调用* 的
    策略原语。

    因此：**即使本模块完全正确，也不会自动产生任何保护效果。** 只有当
    未来的真实 API 在 **每个** POST 与 **每个** GET summary 之前调用
    :meth:`SessionOwnershipStore.require_owner`（或
    :meth:`SessionOwnershipStore.first_claim`）时，归属检查才会生效。
    未接线的调用方默认 **不受保护**。

安全与无副作用约束
------------------
- **纯标准库**；不 import Flask，不 import Blueprint，不 import Factory。
- **不读** ``config/config.json``，**不读** 环境变量，**不联网**。
- **不自主选库**：没有默认路径；调用方必须 **显式注入** 一个已经打开的
  ``sqlite3.Connection``。模块 **不会** 定位 ``data/task_publisher.db``。
- **import 不产生任何副作用**：不建表、不建文件、不建连接。
- **不创建真实数据库**：表只会在调用方显式调用
    :meth:`SessionOwnershipStore.ensure_schema` 时，且只在调用方注入的连接
  上创建。
- 所有 SQL 均 **参数化**；除固定表名常量外不做任何字符串拼接。

无身份归属查询（已刻意移除）
--------------------------
    本模块 **不提供** 任何 “仅凭 ``session_id`` 返回 raw ``owner_id``” 的
    入口：既没有 ``get_owner``，也没有等价的 **公共** 查询方法、属性或
    自由函数，:data:`__all__` 里同样不存在这类名字。理由是：那样的入口
    **不含身份约束**，任何拿到 ``session_id`` 的调用方都能直接读出归属
    身份，等于给 “未知 / 他人会话不得泄露归属” 开了后门；而且即使调用方
    “暂时只是拿来做展示或审计”，这种用法也极易被后续接线代码误当成授权
    判定。

    对外唯一正道只有两条，且都 **必须** 显式携带 ``owner_id``：

    1. :meth:`SessionOwnershipStore.require_owner` —— 授权判定（fail closed）；
    2. :meth:`SessionOwnershipStore.first_claim` —— 合法创建 / 首次认领。

    确需在模块 **内部** 诊断归属时，只能使用私有实现（``_conn`` 与
    表名常量），并由测试在 **合成** 临时库上自行做只读 ``SELECT``；公共
    API **不得** 为此重新暴露 raw ``owner_id``。

原子性边界（重要，不要过度宣称）
--------------------------------
    归属的写入使用 ``BEGIN IMMEDIATE`` + ``INSERT ... ON CONFLICT DO
    NOTHING``，**不是** “先 SELECT 再 INSERT”。因此在 **同一个 SQLite
    数据库文件** 上，两个不同的 ``sqlite3.Connection``（含多线程 / 多
    进程）并发争抢同一个 ``session_id`` 时，SQLite 的写锁会把写入串行
    化，最终 **只会有唯一 owner**。

    边界与限制：
    - 该保证来自 **SQLite 自身的文件级写锁**，不是本模块实现的分布式
      锁；不覆盖跨机器、跨文件系统的场景（尤其不可靠的网络文件系统）。
    - 锁竞争可能触发 ``SQLITE_BUSY``；本模块 **不吞掉**
      ``sqlite3.OperationalError``，而是 fail closed 抛出
      ``db_busy``，绝不因此默认放行访问。
    - 多个 *进程* 同时打开同一个库文件时，Windows / POSIX 语义略有
      差异，但 “唯一 owner” 的结论同样成立（写入被串行化）。

错误语义
--------
- 未知会话 与 别人拥有的会话：抛出 **同一个** 错误类型、同一个
  ``code``、同一句外部文案（:data:`NOT_OWNED_CODE` /
  :data:`NOT_OWNED_MESSAGE`），**不泄露** 会话是否存在、属于谁、也不
  回显任何 ``session_id`` / ``owner_id`` / 令牌内容。
- ``first_claim`` 被 **其他 owner** 抢先时，同样使用上述统一错误，避免
  通过“抢占成功/失败”探测会话是否存在。
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict

__all__ = [
    "MAX_ID_LENGTH",
    "NOT_OWNED_CODE",
    "NOT_OWNED_MESSAGE",
    "TABLE_NAME",
    "SessionOwnershipError",
    "SessionOwnershipStore",
]

#: 归属表名（固定常量，非用户输入）。
TABLE_NAME = "free_task_session_ownership"

#: ``session_id`` / ``owner_id`` 长度上限。
MAX_ID_LENGTH = 128

#: 统一 fail-closed 错误码：未知会话与他人会话 **完全一致**。
NOT_OWNED_CODE = "session_not_owned"

#: 统一 fail-closed 外部文案：**不得** 包含任何 id / 令牌 / 存在性信息。
NOT_OWNED_MESSAGE = "会话不存在或不属于当前用户"

#: 合法 ID 字符集：字母、数字、``.`` ``_`` ``-`` ``:``，且必须以字母或
#: 数字开头。大小写 **被保留**（归属比较区分大小写），但 **不** 做任何
#: 归一化（不 strip、不折叠空白、不大小写映射）。
_ID_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:\-]{0,%d}\Z" % (MAX_ID_LENGTH - 1))


class SessionOwnershipError(Exception):
    """会话归属错误（fail closed）。

    ``code`` 是稳定的机器可读原因码；``message`` 是对外文案。
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _require_identifier(value: Any, field: str) -> str:
    """校验标识符：非空、非空白、非控制字符、长度受限、字符合法。

    **不做归一化**：返回值与输入逐字符相同（仅做合法性检查）。因此
    ``"abc"`` 与 ``"ABC"`` 是不同 owner，``" abc"`` / ``"abc "`` 会被
    **拒绝**（而不是悄悄折叠成同一个 owner）。
    """
    if not isinstance(value, str):
        raise SessionOwnershipError(f"{field}_invalid", f"{field} 必须是字符串")
    if not value:
        raise SessionOwnershipError(f"{field}_invalid", f"{field} 不能为空")
    if len(value) > MAX_ID_LENGTH:
        raise SessionOwnershipError(f"{field}_invalid", f"{field} 过长")
    if value != value.strip():
        raise SessionOwnershipError(f"{field}_invalid", f"{field} 不得含首尾空白")
    if not _ID_PATTERN.match(value):
        raise SessionOwnershipError(f"{field}_invalid", f"{field} 含非法字符")
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_rollback(conn: sqlite3.Connection) -> None:
    try:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
    except sqlite3.Error:  # pragma: no cover - 回滚失败不应掩盖原始错误
        pass


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------


class SessionOwnershipStore:
    """会话归属存储（依赖 **注入** 的 ``sqlite3.Connection``）。

    参数
    ----
    connection:
        调用方 **显式** 打开并注入的 SQLite 连接。模块 **不** 提供默认
        路径，**绝不** 自主定位任何数据库文件。
    busy_timeout_ms:
        SQLite 锁等待超时（默认 5000ms）。竞争失败时抛 ``db_busy``，
        绝不静默放行。
    create_schema:
        为 ``True`` 时在构造期建表（只发生在注入的连接上）。默认
        ``False``：默认 **不** 产生任何写入副作用；缺表时所有操作
        fail closed（``schema_missing``）。
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        busy_timeout_ms: int = 5000,
        create_schema: bool = False,
    ) -> None:
        if connection is None:
            raise SessionOwnershipError(
                "connection_required",
                "必须显式注入 sqlite3.Connection；本模块不提供默认连接",
            )
        if not isinstance(connection, sqlite3.Connection):
            raise SessionOwnershipError(
                "connection_invalid", "connection 必须是 sqlite3.Connection"
            )
        self._conn = connection
        # 显式 autocommit：事务边界由本模块用 BEGIN IMMEDIATE / COMMIT
        # 明确管理，避免与调用方的隐式事务互相干扰。
        self._conn.isolation_level = None
        self._conn.execute("PRAGMA busy_timeout = %d" % int(busy_timeout_ms))
        if create_schema:
            self.ensure_schema()

    # -- 连接（只读暴露，方便调用方在同一连接上组合其它操作） ----------
    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    # -- schema ----------------------------------------------------------
    def ensure_schema(self) -> None:
        """在 **注入的连接** 上创建归属表（幂等）。

        只应在合成 / 临时数据库上调用；本方法 **不会** 打开任何文件，
        只会写入调用方已经打开的那个库。
        """
        try:
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    session_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL
                )
                """
            )
        except sqlite3.OperationalError as exc:
            raise SessionOwnershipError(
                "db_unavailable", "无法在注入的连接上创建会话归属表"
            ) from exc

    def _require_table(self) -> None:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (TABLE_NAME,),
        ).fetchone()
        if row is None:
            raise SessionOwnershipError(
                "schema_missing",
                "会话归属表不存在，请先调用 ensure_schema()（fail closed）",
            )

    # -- 写入（原子 first-claim） ----------------------------------------
    def first_claim(self, session_id: Any, owner_id: Any) -> Dict[str, Any]:
        """原子地 **首次** 认领一个会话。

        语义
        ----
        - 会话从未被认领 → 认领成功，返回 ``claimed=True``；
        - 会话已被 **同一** owner 认领 → **幂等**成功，返回
          ``claimed=False``（不产生第二行）；
        - 会话已被 **其他** owner 认领 → 抛 :class:`SessionOwnershipError`
          （``code == NOT_OWNED_CODE``），**不** 改写既有归属。

        原子性：``BEGIN IMMEDIATE`` + ``INSERT ... ON CONFLICT DO NOTHING``，
        **不是** “SELECT 后 INSERT”，因此不存在跨连接 / 跨进程的检查-写入
        竞态窗口。
        """
        sid = _require_identifier(session_id, "session_id")
        oid = _require_identifier(owner_id, "owner_id")
        self._require_table()

        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise SessionOwnershipError(
                "db_busy", "数据库忙，无法认领会话归属（fail closed）"
            ) from exc

        try:
            before = self._conn.total_changes
            self._conn.execute(
                f"INSERT INTO {TABLE_NAME} (session_id, owner_id, claimed_at) "
                f"VALUES (?, ?, ?) ON CONFLICT(session_id) DO NOTHING",
                (sid, oid, _now_iso()),
            )
            # ``total_changes`` 差值 == 1 表示本事务真正插入了一行；
            # 比 ``cursor.rowcount`` 在不同 sqlite3 版本上更稳妥。
            claimed_new = (self._conn.total_changes - before) == 1
            row = self._conn.execute(
                f"SELECT owner_id FROM {TABLE_NAME} WHERE session_id = ?",
                (sid,),
            ).fetchone()
            self._conn.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            _safe_rollback(self._conn)
            raise SessionOwnershipError(
                "db_busy", "数据库忙或不可用，无法认领会话归属（fail closed）"
            ) from exc
        except sqlite3.Error:
            _safe_rollback(self._conn)
            raise

        existing_owner = row[0] if row is not None else None
        if existing_owner != oid:
            # 统一 fail-closed：既不泄露会话是否存在，也不泄露既有 owner。
            raise SessionOwnershipError(NOT_OWNED_CODE, NOT_OWNED_MESSAGE)
        return {
            "session_id": sid,
            "owner_id": oid,
            "claimed": claimed_new,
            "idempotent": not claimed_new,
        }

    # -- 读取（只校验，不认领） -------------------------------------------
    def require_owner(self, session_id: Any, owner_id: Any) -> Dict[str, Any]:
        """要求 ``owner_id`` 拥有 ``session_id``，否则 fail closed。

        - 未知会话 与 他人会话 → **同一** 错误类型 / ``code`` / 文案；
        - **绝不** 隐式认领：调用本方法不会创建任何归属行。因此在
          “首次 GET / summary” 前，未认领的会话永远拿不到数据。
        """
        sid = _require_identifier(session_id, "session_id")
        oid = _require_identifier(owner_id, "owner_id")
        self._require_table()

        try:
            row = self._conn.execute(
                f"SELECT owner_id FROM {TABLE_NAME} WHERE session_id = ?",
                (sid,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            raise SessionOwnershipError(
                "db_unavailable", "无法读取会话归属（fail closed）"
            ) from exc

        if row is None or row[0] != oid:
            raise SessionOwnershipError(NOT_OWNED_CODE, NOT_OWNED_MESSAGE)
        return {"session_id": sid, "owner_id": oid}

    # -- 刻意不提供的东西 ------------------------------------------------
    # 没有 ``get_owner`` / ``owner_of`` 之类的公共只读查询：任何仅凭
    # ``session_id`` 就返回 raw ``owner_id`` 的入口都缺少身份约束，会让
    # “未知 / 他人会话不得泄露归属” 失效。授权判定一律用
    # :meth:`require_owner`，首次认领用 :meth:`first_claim`；诊断只在模块
    # **内部** 通过私有 ``_conn`` + 表名常量完成（见模块文档）。
