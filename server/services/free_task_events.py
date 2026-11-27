"""server.services.free_task_events - 自由任务的 **追加式事件账本**。

定位
----
这是一个 *独立、可测试* 的事件记录层：把用户在使用自由任务过程中的行为
事件，按 **只追加（append-only）** 语义持久化到一个 SQLite 文件里。

设计要点
--------
1. **调用方必须显式传入 SQLite 路径**。本模块 **没有** 默认路径，
   **绝不** 自动定位 ``data/task_publisher.db``，**绝不** 读
   ``config/config.json``。缺少路径 → 明确报错。
2. **禁止写入生产库**：显式拒绝 ``task_publisher.db`` 及其 WAL/SHM。
3. **追加为唯一语义**：事件行只增不改不删；数据库层用触发器强制
   ``UPDATE`` / ``DELETE`` 失败。
4. **幂等**：同一 ``event_id`` + 完全相同的 payload → 幂等无副作用；
   同一 ``event_id`` + 不同 payload → 明确报错（``event_conflict``）。
5. **同一会话只允许一个完成事件**：由部分唯一索引在数据库层保证，
   因此 “成功任务数” 与 “有效学习分钟” 不会被重复累计。
6. **禁止时间流逝自动完成**：只有显式的 ``free_task.completed``
   才计入 “已完成任务”；``free_task.timer_elapsed`` 永远贡献 0。
7. **娱乐 / 学习分账**：娱乐活动即使完成，也只算 1 个成功任务，
   有效学习分钟恒为 0；学习活动必须使用 **用户报告** 的实际有效
   学习分钟，缺失 / 非正数 → 明确拒绝。
8. **信任边界**：事件类型、分类、状态、分钟数都经由
   :mod:`server.services.free_task_domain` 校验后才落库；调用方无法
   通过伪造 ``event_type`` 把娱乐活动记成学习。
9. **summary 明确是“用户自报”**：任务记录本身 **不能** 证明用户真的
   学习了，``get_summary`` 因此显式标注 ``verification`` 字段。

安全与无副作用约束
------------------
- 本模块 **不 import Flask**，**不读** ``config/config.json``，
  **不碰** ``src/notes/**``。
- 本模块 **只在调用方给定的路径** 上创建 / 写入 SQLite 文件。
- 本模块 **不联网**、**不写日志文件**。

尚未集成（见 Handoff）
----------------------
本模块目前 **没有** 接入生产 Factory Blueprint 或真实前端；
事件写入将由后续受控 Blueprint 负责，调用方必须显式传入路径。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import free_task_domain as domain

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 表名。
TABLE_NAME = "free_task_events"

#: 允许写入账本的会话级事件类型（“帮我选”建议不是会话事件，不入账本）。
ALLOWED_EVENT_TYPES: Tuple[str, ...] = (
    domain.EVENT_STARTED,
    domain.EVENT_PAUSED,
    domain.EVENT_RESUMED,
    domain.EVENT_INTERRUPTED,
    domain.EVENT_FAILED,
    domain.EVENT_TIMER_ELAPSED,
    domain.EVENT_COMPLETED,
)

#: 完成事件类型（唯一计入 “已完成任务” 的事件）。
COMPLETION_EVENT_TYPE = domain.EVENT_COMPLETED

#: payload 允许出现的字段（未知字段一律拒绝 → 防止脏数据进入账本）。
ALLOWED_PAYLOAD_FIELDS = frozenset(
    {
        "event_type",
        "activity",
        "category",
        "reason",
        "planned_minutes",
        "actual_minutes",
        "reported_study_minutes",
        "policy_version",
        "occurred_at",
        "status",
    }
)

#: 被明确拒绝的 “生产数据库” 文件名（禁止误写生产数据）。
_FORBIDDEN_BASENAMES = frozenset(
    {"task_publisher.db", "task_publisher.db-wal", "task_publisher.db-shm"}
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

#: 标识符长度上限（session_id / event_id）。
MAX_ID_LENGTH = 128

#: 文本长度上限（活动 / 理由复用领域层上限）。
MAX_TEXT_LENGTH = domain.MAX_ACTIVITY_LENGTH

#: 状态机：每个事件类型允许的前置状态集合。
_ALLOWED_PREVIOUS_STATES: Dict[str, Tuple[Optional[str], ...]] = {
    domain.EVENT_STARTED: (None,),
    domain.EVENT_PAUSED: (domain.STATUS_RUNNING,),
    domain.EVENT_RESUMED: (domain.STATUS_PAUSED,),
    domain.EVENT_INTERRUPTED: (domain.STATUS_RUNNING, domain.STATUS_PAUSED),
    domain.EVENT_FAILED: (domain.STATUS_RUNNING, domain.STATUS_PAUSED),
    domain.EVENT_TIMER_ELAPSED: (domain.STATUS_RUNNING, domain.STATUS_PAUSED),
    domain.EVENT_COMPLETED: (domain.STATUS_RUNNING, domain.STATUS_PAUSED),
}


class FreeTaskEventError(Exception):
    """自由任务事件账本错误（fail closed）。

    ``code`` 是稳定的机器可读原因码；``message`` 是中文说明。
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreeTaskEventError(f"{field}_required", f"{field} 必须是非空字符串")
    if len(value) > MAX_ID_LENGTH:
        raise FreeTaskEventError(f"{field}_too_long", f"{field} 过长")
    if _CONTROL_CHARS.search(value):
        raise FreeTaskEventError(f"{field}_invalid", f"{field} 含控制字符")
    return value.strip()


def _validate_occurred_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreeTaskEventError(
            "occurred_at_required", "事件必须携带发生时间 (occurred_at)"
        )
    text = value.strip()
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(probe)
    except ValueError:
        raise FreeTaskEventError(
            "occurred_at_invalid", f"发生时间不是 ISO-8601 格式: {value!r}"
        ) from None
    return text


def _normalize_optional_text(value: Any, field: str, max_len: int) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise FreeTaskEventError(f"{field}_invalid", f"{field} 必须是字符串")
    text = value.strip()
    if not text:
        return None
    if _CONTROL_CHARS.search(text):
        raise FreeTaskEventError(f"{field}_invalid", f"{field} 含控制字符")
    if len(text) > max_len:
        raise FreeTaskEventError(f"{field}_too_long", f"{field} 过长")
    return text


def _canonical_json(record: Dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _payload_hash(record: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    activity TEXT NOT NULL,
    category TEXT NOT NULL,
    reason TEXT NOT NULL,
    policy_version TEXT,
    status TEXT NOT NULL,
    actual_minutes INTEGER NOT NULL DEFAULT 0,
    reported_study_minutes INTEGER,
    completed_count_delta INTEGER NOT NULL DEFAULT 0,
    study_minutes INTEGER NOT NULL DEFAULT 0,
    study_pomodoros INTEGER NOT NULL DEFAULT 0,
    occurred_at TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_session
    ON {TABLE_NAME} (session_id, id);

-- 同一会话只允许一个完成事件 → 防止 “重复累计”
CREATE UNIQUE INDEX IF NOT EXISTS idx_{TABLE_NAME}_single_completion
    ON {TABLE_NAME} (session_id) WHERE event_type = '{COMPLETION_EVENT_TYPE}';

-- 追加语义：禁止修改 / 删除既有事件行
CREATE TRIGGER IF NOT EXISTS trg_{TABLE_NAME}_no_update
BEFORE UPDATE ON {TABLE_NAME}
BEGIN
    SELECT RAISE(ABORT, 'free_task_events is append-only: UPDATE denied');
END;

CREATE TRIGGER IF NOT EXISTS trg_{TABLE_NAME}_no_delete
BEFORE DELETE ON {TABLE_NAME}
BEGIN
    SELECT RAISE(ABORT, 'free_task_events is append-only: DELETE denied');
END;
"""


class FreeTaskEventStore:
    """自由任务事件账本（追加式）。

    参数
    ----
    db_path:
        **必须显式传入** 的 SQLite 文件路径。不提供默认路径，
        绝不使用 ``data/task_publisher.db``。
    busy_timeout_ms:
        SQLite 锁等待超时（默认 5000ms）。
    """

    def __init__(self, db_path: Any, *, busy_timeout_ms: int = 5000) -> None:
        if db_path is None:
            raise FreeTaskEventError(
                "db_path_required",
                "必须显式传入 SQLite 路径；本模块不提供默认路径",
            )
        if isinstance(db_path, str):
            path = db_path.strip()
        elif isinstance(db_path, os.PathLike):
            path = os.fspath(db_path)
        else:
            raise FreeTaskEventError(
                "db_path_invalid", "SQLite 路径必须是字符串或 PathLike"
            )
        if not path:
            raise FreeTaskEventError(
                "db_path_required", "必须显式传入 SQLite 路径；本模块不提供默认路径"
            )

        self.db_path = os.path.abspath(path)
        base = os.path.basename(self.db_path).lower()
        if base in _FORBIDDEN_BASENAMES:
            raise FreeTaskEventError(
                "db_path_forbidden", "禁止写入生产数据库（task_publisher.db*）"
            )
        self.busy_timeout_ms = int(busy_timeout_ms)
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    # -- 连接 ------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path, timeout=self.busy_timeout_ms / 1000, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = %d" % self.busy_timeout_ms)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:  # pragma: no cover - 某些文件系统不支持 WAL
            pass
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # -- 读取 ------------------------------------------------------------
    def list_events(self, session_id: Any) -> List[Dict[str, Any]]:
        """按写入顺序返回某会话的全部事件。

        损坏的 payload（JSON 无法解析 / 结构非法）→ 明确报错
        （fail closed），绝不返回半真半假的数据。
        """
        sid = _require_identifier(session_id, "session_id")
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM {TABLE_NAME} WHERE session_id = ? ORDER BY id",
                (sid,),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _decode_payload(payload_json: Any, event_id: str) -> Dict[str, Any]:
        """解析已存 payload（损坏 → 明确报错，绝不返回半真半假数据）。"""
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            raise FreeTaskEventError(
                "payload_corrupt", f"事件 {event_id} 的 payload 已损坏，无法解析"
            ) from None
        if not isinstance(payload, dict):
            raise FreeTaskEventError(
                "payload_corrupt", f"事件 {event_id} 的 payload 已损坏，结构非法"
            )
        return payload

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Dict[str, Any]:
        payload = FreeTaskEventStore._decode_payload(
            row["payload_json"], row["event_id"]
        )
        event = dict(payload)
        event.update(
            {
                "row_id": row["id"],
                "event_id": row["event_id"],
                "session_id": row["session_id"],
                "payload_hash": row["payload_hash"],
            }
        )
        return event

    # -- 写入 ------------------------------------------------------------
    def append_event(
        self,
        session_id: Any,
        event_id: Any,
        event_payload: Any,
    ) -> Dict[str, Any]:
        """追加一个事件。

        - 同一 ``event_id`` + 相同 payload → **幂等**，返回既有结果；
        - 同一 ``event_id`` + 不同 payload → 抛 ``event_conflict``；
        - 其余非法输入 → 抛 ``FreeTaskEventError``（fail closed）。
        """
        sid = _require_identifier(session_id, "session_id")
        eid = _require_identifier(event_id, "event_id")

        if not isinstance(event_payload, dict):
            raise FreeTaskEventError("payload_invalid", "事件 payload 必须是字典")
        try:
            request_hash = _payload_hash(
                {"session_id": sid, "event_id": eid, "payload": event_payload}
            )
        except (TypeError, ValueError):
            raise FreeTaskEventError(
                "payload_invalid", "事件 payload 必须可被 JSON 序列化"
            ) from None

        conn = self._connect()
        try:
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                raise FreeTaskEventError(
                    "db_busy", f"数据库被占用，无法写入事件: {exc}"
                ) from exc
            try:
                existing = conn.execute(
                    f"SELECT payload_hash, id, payload_json FROM {TABLE_NAME} "
                    f"WHERE event_id = ?",
                    (eid,),
                ).fetchone()
                if existing is not None:
                    if existing["payload_hash"] == request_hash:
                        conn.execute("ROLLBACK")
                        stored = self._decode_payload(
                            existing["payload_json"], eid
                        )
                        return {
                            "event_id": eid,
                            "session_id": sid,
                            "row_id": existing["id"],
                            "stored": True,
                            "duplicate": True,
                            "status": stored.get("status"),
                            "completed_count_delta": int(
                                stored.get("completed_count_delta") or 0
                            ),
                            "study_minutes": int(stored.get("study_minutes") or 0),
                        }
                    raise FreeTaskEventError(
                        "event_conflict",
                        f"event_id {eid!r} 已存在但 payload 不同，拒绝覆盖",
                    )

                record = self._build_record(sid, eid, event_payload)

                self._assert_state_transition(conn, sid, record)

                cursor = conn.execute(
                    f"""
                    INSERT INTO {TABLE_NAME} (
                        event_id, session_id, event_type, activity, category,
                        reason, policy_version, status, actual_minutes,
                        reported_study_minutes, completed_count_delta,
                        study_minutes, study_pomodoros, occurred_at,
                        payload_hash, payload_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        eid,
                        sid,
                        record["event_type"],
                        record["activity"],
                        record["category"],
                        record["reason"],
                        record["policy_version"],
                        record["status"],
                        record["actual_minutes"],
                        record["reported_study_minutes"],
                        record["completed_count_delta"],
                        record["study_minutes"],
                        record["study_pomodoros"],
                        record["occurred_at"],
                        request_hash,
                        _canonical_json(record),
                    ),
                )
                row_id = cursor.lastrowid
                conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                raise FreeTaskEventError(
                    "event_conflict",
                    f"事件写入被拒绝（唯一性 / 追加约束）: {exc}",
                ) from exc
            except sqlite3.OperationalError as exc:
                conn.execute("ROLLBACK")
                raise FreeTaskEventError(
                    "db_busy", f"数据库被占用，无法写入事件: {exc}"
                ) from exc
            except Exception:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

        return {
            "event_id": eid,
            "session_id": sid,
            "row_id": row_id,
            "stored": True,
            "duplicate": False,
            "status": record["status"],
            "completed_count_delta": record["completed_count_delta"],
            "study_minutes": record["study_minutes"],
        }

    # -- 校验与记录构造 ---------------------------------------------------
    def _build_record(
        self, session_id: str, event_id: str, event_payload: Any
    ) -> Dict[str, Any]:
        if not isinstance(event_payload, dict):
            raise FreeTaskEventError("payload_invalid", "事件 payload 必须是字典")
        unknown = set(event_payload) - ALLOWED_PAYLOAD_FIELDS
        if unknown:
            raise FreeTaskEventError(
                "payload_unknown_field", f"事件 payload 含有未知字段: {sorted(unknown)}"
            )

        event_type = event_payload.get("event_type")
        if not isinstance(event_type, str) or event_type not in ALLOWED_EVENT_TYPES:
            raise FreeTaskEventError(
                "event_type_invalid", f"不支持的事件类型: {event_type!r}"
            )

        occurred_at = _validate_occurred_at(event_payload.get("occurred_at"))

        actual_minutes = event_payload.get("actual_minutes")
        if actual_minutes is None:
            actual_minutes = 0
        if not _is_int(actual_minutes) or actual_minutes < 0:
            raise FreeTaskEventError(
                "actual_minutes_invalid", "实际经过分钟必须是非负整数"
            )

        reported = event_payload.get("reported_study_minutes")
        if reported is not None and (not _is_int(reported) or reported < 0):
            raise FreeTaskEventError(
                "reported_study_minutes_invalid", "报告学习分钟必须是非负整数"
            )

        policy_version = _normalize_optional_text(
            event_payload.get("policy_version"), "policy_version", MAX_TEXT_LENGTH
        )

        # --- 依据会话历史推导任务视图（继承 started 事件的活动 / 时长） ---
        base = self._session_task_view(session_id)
        if base is None and event_type != domain.EVENT_STARTED:
            raise FreeTaskEventError(
                "session_not_started",
                "会话尚未开始，必须先追加 free_task.started 事件",
            )

        activity = event_payload.get("activity")
        if activity is None:
            if base is None:
                raise FreeTaskEventError("activity_required", "首个事件必须携带活动内容")
            activity = base["activity"]
        else:
            self._assert_same_as_base("activity", activity, base)

        category = event_payload.get("category")
        if category is None:
            if base is None:
                raise FreeTaskEventError("category_required", "首个事件必须携带活动分类")
            category = base["category"]
        else:
            self._assert_same_as_base("category", category, base)

        planned_minutes = event_payload.get("planned_minutes")
        if planned_minutes is None:
            if base is None:
                raise FreeTaskEventError(
                    "minutes_invalid", "首个事件必须携带计划时长（25 或 55 分钟）"
                )
            planned_minutes = base["planned_minutes"]
        else:
            self._assert_same_as_base("planned_minutes", planned_minutes, base)
        if (
            not _is_int(planned_minutes)
            or planned_minutes not in domain.FREE_TASK_MINUTES_OPTIONS
        ):
            raise FreeTaskEventError(
                "minutes_invalid",
                f"自由任务时长只能是 {domain.FREE_TASK_MINUTES_OPTIONS} 分钟",
            )

        reason = event_payload.get("reason")
        if reason is None and base is not None:
            reason = base["reason"]

        # --- 用领域层校验并归一化 -------------------------------------------
        try:
            started = domain.start_free_task(
                activity=activity,
                category=category,
                minutes=planned_minutes,
                reason=reason,
                task_id=session_id,
                occurred_at=occurred_at,
            )
        except domain.FreeTaskError as exc:
            raise FreeTaskEventError(exc.code, exc.message) from exc
        task = started["task"]
        clean_reason = task["reason"]

        event: Dict[str, Any]
        completed_delta = 0
        study_minutes = 0
        pomodoros = 0
        try:
            if event_type == domain.EVENT_STARTED:
                if reported is not None:
                    raise FreeTaskEventError(
                        "reported_study_minutes_invalid", "开始事件不能携带学习分钟"
                    )
                if actual_minutes != 0:
                    raise FreeTaskEventError(
                        "actual_minutes_invalid", "开始事件的经过分钟必须为 0"
                    )
                event = started
            elif event_type == domain.EVENT_PAUSED:
                self._reject_reported(reported)
                event = domain.pause_free_task(
                    task, elapsed_minutes=actual_minutes, occurred_at=occurred_at
                )
            elif event_type == domain.EVENT_RESUMED:
                # 恢复：只允许 paused → running，且绝不贡献任何统计数字。
                # 本层统一从 started 事件重建 *running* 基础视图，因此这里
                # 先用 **领域层公开 API** 合成出“当前处于暂停”的前态视图，
                # 再调用 resume_free_task —— 绝不直接改写 status 字面量。
                self._reject_reported(reported)
                paused_view = domain.pause_free_task(
                    task, elapsed_minutes=actual_minutes
                )["task"]
                event = domain.resume_free_task(
                    paused_view, elapsed_minutes=actual_minutes, occurred_at=occurred_at
                )
                # 恢复事件的 completed_count_delta / study_minutes /
                # study_pomodoros 恒为 0（初值即 0，此处显式复核，
                # 防止未来领域层改动把它们泄漏进账本）。
                if (
                    int(event.get("completed_count_delta") or 0) != 0
                    or int(event.get("study_minutes") or 0) != 0
                    or int(event.get("study_pomodoros") or 0) != 0
                ):  # pragma: no cover - 防御性不变量
                    raise FreeTaskEventError(
                        "resume_must_not_contribute_metrics",
                        "恢复事件不得贡献完成数或已验证学习分钟",
                    )
            elif event_type == domain.EVENT_INTERRUPTED:
                self._reject_reported(reported)
                event = domain.interrupt_free_task(
                    task, elapsed_minutes=actual_minutes, occurred_at=occurred_at
                )
            elif event_type == domain.EVENT_FAILED:
                self._reject_reported(reported)
                event = domain.fail_free_task(
                    task,
                    elapsed_minutes=actual_minutes,
                    reason=reason,
                    occurred_at=occurred_at,
                )
            elif event_type == domain.EVENT_TIMER_ELAPSED:
                self._reject_reported(reported)
                event = domain.on_timer_elapsed(
                    task, elapsed_minutes=actual_minutes, occurred_at=occurred_at
                )
                # 时间流逝绝不计入完成 / 学习分钟
            else:  # domain.EVENT_COMPLETED
                is_entertainment = task["category"] == domain.CATEGORY_ENTERTAINMENT
                if is_entertainment:
                    # 娱乐活动：即便报告了学习分钟也一律记 0（防止误计）
                    reported = 0
                event = domain.complete_free_task(
                    task,
                    reported_study_minutes=None if is_entertainment else reported,
                    elapsed_minutes=actual_minutes,
                    occurred_at=occurred_at,
                )
                completed_delta = int(event["completed_count_delta"])
                study_minutes = int(event["study_minutes"])
                pomodoros = int(event["study_pomodoros"])
        except domain.FreeTaskError as exc:
            raise FreeTaskEventError(exc.code, exc.message) from exc

        status = event["task"]["status"]

        declared_status = event_payload.get("status")
        if declared_status is not None:
            if not isinstance(declared_status, str) or declared_status != status:
                raise FreeTaskEventError(
                    "status_mismatch",
                    f"声明的状态 {declared_status!r} 与事件实际状态 {status!r} 不一致",
                )

        return {
            "event_type": event_type,
            "session_id": session_id,
            "event_id": event_id,
            "activity": task["activity"],
            "category": task["category"],
            "reason": clean_reason,
            "planned_minutes": int(planned_minutes),
            "policy_version": policy_version,
            "status": status,
            "actual_minutes": int(actual_minutes),
            "reported_study_minutes": int(reported) if reported is not None else None,
            "completed_count_delta": completed_delta,
            "study_minutes": study_minutes,
            "study_pomodoros": pomodoros,
            "occurred_at": occurred_at,
        }

    @staticmethod
    def _reject_reported(reported: Optional[int]) -> None:
        if reported is not None:
            raise FreeTaskEventError(
                "reported_study_minutes_invalid",
                "只有完成事件可以携带用户报告的学习分钟",
            )

    @staticmethod
    def _assert_same_as_base(field: str, value: Any, base: Optional[Dict[str, Any]]) -> None:
        """会话中途不得改写已登记的活动 / 分类 / 时长。

        这条约束保证调用方无法把一个 “娱乐” 会话在后续事件里伪造成
        “学习” 会话（信任边界的核心）。
        """
        if base is None:
            return
        expected = base.get(field)
        if expected is None:
            return
        if field == "activity":
            try:
                normalized = domain.validate_activity(value)
            except domain.FreeTaskError:
                raise FreeTaskEventError("activity_invalid", "活动内容非法") from None
        elif field == "category":
            # 只用公共 API 归一化分类（不依赖实现体私有函数）
            try:
                normalized = domain.start_free_task(
                    activity=base.get("activity"),
                    category=value,
                    minutes=base.get("planned_minutes"),
                )["task"]["category"]
            except domain.FreeTaskError as exc:
                raise FreeTaskEventError(exc.code, exc.message) from exc
        else:  # planned_minutes
            normalized = value
        if normalized != expected:
            raise FreeTaskEventError(
                f"{field}_mismatch",
                f"会话中途不得修改 {field}（已登记 {expected!r}，收到 {normalized!r}）",
            )

    # -- 会话状态机 --------------------------------------------------------
    def _session_task_view(self, session_id: str) -> Optional[Dict[str, Any]]:
        """取回会话当前任务视图（来自最近的 ``started`` 事件）。"""
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT payload_json FROM {TABLE_NAME} "
                f"WHERE session_id = ? AND event_type = ? ORDER BY id DESC LIMIT 1",
                (session_id, domain.EVENT_STARTED),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError):
            raise FreeTaskEventError(
                "payload_corrupt", "会话的 started 事件 payload 已损坏"
            ) from None
        if not isinstance(payload, dict):
            raise FreeTaskEventError(
                "payload_corrupt", "会话的 started 事件 payload 结构非法"
            )
        return {
            "activity": payload.get("activity"),
            "category": payload.get("category"),
            "planned_minutes": payload.get("planned_minutes"),
            "reason": payload.get("reason"),
        }

    def _assert_state_transition(
        self, conn: sqlite3.Connection, session_id: str, record: Dict[str, Any]
    ) -> None:
        """校验状态顺序；同一会话的第二个完成事件被拒绝。"""
        event_type = record["event_type"]
        row = conn.execute(
            f"SELECT status FROM {TABLE_NAME} WHERE session_id = ? "
            f"ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        previous = row["status"] if row is not None else None
        allowed = _ALLOWED_PREVIOUS_STATES[event_type]
        if previous not in allowed:
            raise FreeTaskEventError(
                "illegal_state_order",
                f"事件 {event_type!r} 不允许出现在状态 {previous!r} 之后",
            )
        if event_type == COMPLETION_EVENT_TYPE:
            done = conn.execute(
                f"SELECT COUNT(*) AS n FROM {TABLE_NAME} "
                f"WHERE session_id = ? AND event_type = ?",
                (session_id, COMPLETION_EVENT_TYPE),
            ).fetchone()
            if done and int(done["n"]) >= 1:
                raise FreeTaskEventError(
                    "duplicate_completion", "同一会话不允许出现第二个完成事件"
                )

    # -- 汇总 --------------------------------------------------------------
    def get_summary(self, session_id: Any) -> Dict[str, Any]:
        """汇总某会话的完成任务数与有效学习分钟。

        **重要**：这里统计的是 *用户自报* 的完成情况。事件账本 **不能**
        证明用户真的学习了，因此结果里显式带有 ``verification`` 标注。
        """
        sid = _require_identifier(session_id, "session_id")
        events = self.list_events(sid)

        completed = [e for e in events if e.get("event_type") == COMPLETION_EVENT_TYPE]
        successful_tasks = len(completed)
        effective_study_minutes = sum(
            int(e.get("study_minutes") or 0) for e in completed
        )
        study_pomodoros = sum(int(e.get("study_pomodoros") or 0) for e in completed)
        entertainment_completions = sum(
            1
            for e in completed
            if e.get("category") == domain.CATEGORY_ENTERTAINMENT
        )
        study_completions = successful_tasks - entertainment_completions
        timer_events = sum(
            1 for e in events if e.get("event_type") == domain.EVENT_TIMER_ELAPSED
        )

        return {
            "session_id": sid,
            "event_count": len(events),
            "successful_tasks": successful_tasks,
            "study_completions": study_completions,
            "entertainment_completions": entertainment_completions,
            "effective_study_minutes": effective_study_minutes,
            "study_pomodoros": study_pomodoros,
            "timer_elapsed_events": timer_events,
            "auto_completed": False,
            "completion_source": "explicit_user_report",
            "verification": "user_reported_not_independently_verified",
            "note": (
                "以上完成情况与学习分钟均为用户自报；任务记录本身不能证明用户实际学习了。"
            ),
        }


def new_event_id() -> str:
    """生成一个随机 UUID4 事件 ID（可选便利函数）。"""
    return str(uuid.uuid4())


__all__ = [
    "ALLOWED_EVENT_TYPES",
    "ALLOWED_PAYLOAD_FIELDS",
    "COMPLETION_EVENT_TYPE",
    "TABLE_NAME",
    "FreeTaskEventError",
    "FreeTaskEventStore",
    "new_event_id",
]
