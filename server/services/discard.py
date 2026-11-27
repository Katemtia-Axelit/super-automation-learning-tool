"""server.services.discard — 弃牌 / 恢复 / 回收 的业务编排。

AR03-P2 / Stage 2
-----------------
弃牌域有自己的一套业务规则：自然周期边界（daily / weekly）、临时屏蔽到期、
幂等的完成计数、以及 **服务启动时的周期回收**。Stage 2 把这些规则从
``server/backend_api.py`` 迁到这里：

* Blueprint 只做 HTTP 边界；
* Service 负责业务编排（周期计算、恢复决策），**不写 SQL**；
* Repository（:mod:`server.repositories.discard_repo`）负责 SQL。

周期语义（逐条继承 legacy）
----------------------------
1. ``daily``：完成日期的下一天本地 00:00。
2. ``weekly``：完成日期之后的下一个周一本地 00:00（周一完成 → 下一周一）。
3. 其他 ``repeat_type``：不是周期任务 → 无到期时间（fail-closed）。
4. 有效到期时间 = ``max(自然周期边界, 既有 next_available_at)``。
5. 完成操作绝不能提前缩短既有临时屏蔽。

恢复语义
--------
* 未来 ``next_available_at`` → 409，零副作用；
* 已完成的非周期任务 → 409（不能绕过完成状态）；
* 已完成的周期任务：仅在有效到期时间 ``<= now`` 时可恢复，且 **绝不**
  改写 ``completed_count`` / ``last_completed_at``；
* 未完成的手动弃牌：到期或没有未来屏蔽即可恢复；过期值被清除。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from server.repositories import discard_repo
from server.repositories.db import service_transaction

__all__ = [
    "RECURRING_REPEAT_TYPES",
    "effective_due_at",
    "list_discard_pile",
    "list_discard_pile_action",
    "move_to_discard",
    "move_to_discard_action",
    "natural_period_end_iso",
    "parse_local_ts",
    "recover_discard_cycle",
    "restore_from_discard",
    "restore_from_discard_action",
]

#: 周期性 repeat_type（可自动恢复的类型）。
RECURRING_REPEAT_TYPES = ("daily", "weekly")


# ---------------------------------------------------------------------------
# 时间解析与周期计算
# ---------------------------------------------------------------------------

def parse_local_ts(value: Any) -> Optional[datetime]:
    """把 ISO 时间字符串解析成 **本地 naive** datetime；不可解析返回 ``None``。

    带时区的输入先转换到主机本地时间再剥离 tzinfo，保证与
    ``datetime.now()``（本地 naive）可直接比较。绝不猜测非法值。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def natural_period_end_iso(
    repeat_type: Any, completed_at: Any
) -> Optional[str]:
    """任务完成后的 **自然周期边界**（本地日历时间）。

    - ``daily``：完成日期的下一天本地 00:00；
    - ``weekly``：完成日期之后的下一个周一本地 00:00；
    - 其他：``None``（fail-closed，无到期时间）。
    """
    repeat = (repeat_type or "").strip().lower() if isinstance(repeat_type, str) else ""
    if repeat not in RECURRING_REPEAT_TYPES:
        return None
    completed_dt = parse_local_ts(completed_at)
    if completed_dt is None:
        return None
    completed_date = completed_dt.date()
    if repeat == "daily":
        boundary = completed_date + timedelta(days=1)
    else:  # weekly
        days_ahead = 7 - completed_date.weekday()
        boundary = completed_date + timedelta(days=days_ahead)
    return datetime(boundary.year, boundary.month, boundary.day).isoformat()


def effective_due_at(
    repeat_type: Any, last_completed_at: Any, next_available_at: Any
) -> Optional[datetime]:
    """合并自然周期与既有临时屏蔽，返回有效到期时间或 ``None``。

    有效到期时间取「自然周期边界」与「已有 next_available_at」中 **较晚者**；
    两者都拿不到时返回 ``None``（fail-closed：绝不猜一个到期日）。
    """
    natural_iso = natural_period_end_iso(repeat_type, last_completed_at)
    natural_dt = parse_local_ts(natural_iso) if natural_iso else None
    next_dt = parse_local_ts(next_available_at)
    if natural_dt is None and next_dt is None:
        return None
    if natural_dt is None:
        return next_dt
    if next_dt is None:
        return natural_dt
    return next_dt if next_dt > natural_dt else natural_dt


# ---------------------------------------------------------------------------
# 弃牌 / 恢复
# ---------------------------------------------------------------------------

def list_discard_pile(conn) -> List[Dict[str, Any]]:
    """列出弃牌堆中的任务。"""
    return discard_repo.list_discard_pile(conn)


def move_to_discard(conn, task_id: int, now: Optional[datetime] = None) -> None:
    """把任务移入弃牌堆，**区分手动弃牌与完成弃牌**。

    - ``completed=0`` 的手动弃牌：只设置 ``in_discard_pile`` / ``updated_at``，
      **保留** ``last_completed_at``、``completed_count`` 与既有
      ``next_available_at``；
    - ``completed=1`` 且首次移入弃牌堆：记录 ``last_completed_at``、
      ``completed_count + 1``，并为 daily/weekly 设置
      ``next_available_at = max(自然周期边界, 已有的有效 next_available_at)``；
      非周期任务保持不可自动恢复；
    - 已在弃牌堆的已完成任务重复调用 **幂等**，不重复计数。
    """
    now = now or datetime.now()
    now_iso = now.isoformat()
    record = discard_repo.get_task_row(conn, task_id)
    if record is None:
        return

    completed = bool(record.get("completed"))
    already_in_discard = bool(record.get("in_discard_pile"))

    if not completed:
        discard_repo.mark_discard(conn, task_id, now_iso)
        return

    if already_in_discard:
        # 幂等：只刷新 updated_at，不重复计数/推周期。
        conn.execute(
            "UPDATE tasks SET updated_at=? WHERE id=?", (now_iso, task_id)
        )
        return

    repeat_type = (record.get("repeat_type") or "").strip().lower()
    natural_iso = natural_period_end_iso(repeat_type, now_iso)
    next_iso = natural_iso
    if natural_iso is not None:
        existing_next = record.get("next_available_at")
        existing_dt = parse_local_ts(existing_next)
        natural_dt = parse_local_ts(natural_iso)
        if existing_dt is not None and existing_dt > natural_dt:
            next_iso = existing_next
    completed_count = int(record.get("completed_count") or 0) + 1
    discard_repo.mark_discarded_completed(
        conn,
        task_id,
        last_completed_at=now_iso,
        completed_count=completed_count,
        next_available_at=next_iso,
        updated_at=now_iso,
    )


def restore_from_discard(
    conn, task_id: int, now: Optional[datetime] = None
) -> Tuple[str, Dict[str, Any]]:
    """把任务从弃牌堆恢复到卡池。

    返回 ``(outcome, payload)``：

    * ``("restored", {...})`` —— 成功；
    * ``("not_found", {...})`` —— → 404；
    * ``("not_in_pile", {...})`` —— → 400；
    * ``("not_due", {...})`` —— → 409（未到期 / 一次性任务 / 无法判定）。
    """
    now = now or datetime.now()
    record = discard_repo.get_task_row(conn, task_id)
    if record is None:
        return "not_found", {"error": "Task not found"}
    if not record.get("in_discard_pile"):
        return "not_in_pile", {"error": "Task is not in discard pile"}

    next_dt = parse_local_ts(record.get("next_available_at"))

    # 1) 未来 next_available_at → 409，零副作用。
    if next_dt is not None and next_dt > now:
        return "not_due", {
            "error": "任务尚未到期，暂时不能恢复到卡池",
            "next_available_at": record.get("next_available_at"),
        }

    if record.get("completed"):
        repeat_type = (record.get("repeat_type") or "").strip().lower()
        # 2) 已完成的非周期任务不得通过手动恢复绕过完成状态。
        if repeat_type not in RECURRING_REPEAT_TYPES:
            return "not_due", {
                "error": "该任务为一次性/非周期任务，无法手动恢复到卡池",
            }
        # 3) 已完成的周期任务：仅在有效自然到期时间 <= now 时可恢复。
        due_dt = effective_due_at(
            repeat_type,
            record.get("last_completed_at"),
            record.get("next_available_at"),
        )
        if due_dt is None:
            return "not_due", {
                "error": "无法确定该周期任务的到期时间，暂不能恢复；"
                "请稍后重试或检查完成记录",
            }
        if due_dt > now:
            return "not_due", {
                "error": "周期尚未到期，暂时不能恢复到卡池",
                "next_available_at": due_dt.isoformat(),
            }
        # 到期：恢复并清空完成状态（绝不改 completed_count / last_completed_at）。
        discard_repo.restore_to_gacha_pile(
            conn,
            task_id,
            updated_at=now.isoformat(),
            reset_completed=True,
            clear_next_available=True,
        )
        return "restored", {
            "restored": True,
            "task_id": task_id,
            "message": "Task restored from discard pile",
        }

    # 4) 未完成的手动弃牌：到期或没有未来屏蔽即可恢复；
    #    若 next_available_at 已过期则清除该过期值。
    clear_next = next_dt is not None
    discard_repo.restore_to_gacha_pile(
        conn,
        task_id,
        updated_at=now.isoformat(),
        clear_next_available=clear_next,
    )
    return "restored", {
        "restored": True,
        "task_id": task_id,
        "message": "Task restored from discard pile",
    }


# ---------------------------------------------------------------------------
# 服务启动时的周期回收
# ---------------------------------------------------------------------------

def recover_discard_cycle(
    conn, now: Optional[datetime] = None
) -> Dict[str, int]:
    """服务启动时 **幂等** 的弃牌周期恢复。

    语义（继承 legacy ``recover_discard_cycle``）：

    1. 临时屏蔽任务（``in_discard_pile=1`` 且 ``completed=0``）：仅当
       ``next_available_at`` 存在且 ``<= now`` 时清除 ``in_discard_pile``
       并清空过期 ``next_available_at``；没有到期时间的普通手动弃牌继续
       留在弃牌堆。
    2. 已完成的 daily/weekly 任务：取自然周期边界与现有
       ``next_available_at`` 中较晚者为有效到期时间；只有 ``<= now`` 时才
       同时置 ``completed=0`` / ``in_discard_pile=0`` /
       ``next_available_at=NULL``。**不改写** ``completed_count`` 或
       ``last_completed_at``。
    3. 已完成的单次/其他非周期任务不自动恢复；无法确定到期时间的已完成
       周期任务 fail-closed（保持完成状态）。

    返回本次恢复的计数：``{"unblocked": n, "completed_restored": n}``。
    """
    now = now or datetime.now()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE in_discard_pile = 1"
    ).fetchall()
    unblocked = 0
    completed_restored = 0
    now_iso = now.isoformat()

    for row in rows:
        record = dict(row)
        task_id = record["id"]
        if not record.get("completed"):
            next_dt = parse_local_ts(record.get("next_available_at"))
            if next_dt is not None and next_dt <= now:
                discard_repo.restore_to_gacha_pile(
                    conn,
                    task_id,
                    updated_at=now_iso,
                    clear_next_available=True,
                )
                unblocked += 1
            continue

        repeat_type = (record.get("repeat_type") or "").strip().lower()
        if repeat_type not in RECURRING_REPEAT_TYPES:
            continue
        due_dt = effective_due_at(
            repeat_type,
            record.get("last_completed_at"),
            record.get("next_available_at"),
        )
        if due_dt is None or due_dt > now:
            continue
        discard_repo.restore_to_gacha_pile(
            conn,
            task_id,
            updated_at=now_iso,
            reset_completed=True,
            clear_next_available=True,
        )
        completed_restored += 1

    return {
        "unblocked": unblocked,
        "completed_restored": completed_restored,
    }


# ---------------------------------------------------------------------------
# 自持事务的整体动作入口（AR03-P2 / P2 收尾）
# ---------------------------------------------------------------------------
#
# 事务边界 **下沉到 Service**：Blueprint 只做「解析请求 → 调 Service →
# 组装响应」。提交时机与迁移前逐条等价（退出 with 时提交，异常回滚）。


def list_discard_pile_action() -> List[Dict[str, Any]]:
    """只读：列出弃牌堆中的任务。"""
    with service_transaction(commit=False) as conn:
        return list_discard_pile(conn)


def move_to_discard_action(task_id: int, now: Optional[datetime] = None) -> None:
    """把任务移入弃牌堆（自持事务）。

    幂等计数与周期推算在 **同一事务** 内完成 —— 与迁移前逐条等价。
    """
    with service_transaction() as conn:
        move_to_discard(conn, task_id, now)


def restore_from_discard_action(
    task_id: int, now: Optional[datetime] = None
) -> Tuple[str, Dict[str, Any]]:
    """把任务从弃牌堆恢复（自持事务）。"""
    with service_transaction() as conn:
        return restore_from_discard(conn, task_id, now)
