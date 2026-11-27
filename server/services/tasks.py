"""server.services.tasks — 任务域的 **业务编排唯一 owner**。

AR03-P2 / Stage 2
-----------------
迁移前，任务域的业务逻辑（解锁判定、循环依赖检测、完成/跳过的副作用、
依赖图组装）散落在 ``server/blueprints/tasks_bp.py`` 与
``server/backend_api.py`` 两处。Stage 2 把它们收敛到本模块：

* Blueprint 只做 **HTTP 边界**（参数解析、状态码、响应组装）；
* Service 负责 **业务编排**（不写 SQL）；
* Repository 负责 **SQL**。

领域规则
--------
* **卡类型词表**（``task_type``）的唯一权威从 Blueprint **上移** 到本模块
  （``CARD_TYPES`` / ``normalize_card_type`` / ``validate_task_type``）。
  ``server/blueprints/gacha_bp.py`` 改为从这里 import —— 词表只有一份，
  不会出现"一处当成 free、另一处当成 standard"的分裂。
* **依赖图**（``/api/dependencies``）归入任务域。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from server.repositories import task_repo
from server.repositories.db import service_transaction

__all__ = [
    "ACCEPTED_TASK_TYPES",
    "CARD_TYPES",
    "CARD_TYPE_FREE",
    "CARD_TYPE_GOAL",
    "CARD_TYPE_MICRO",
    "CARD_TYPE_STANDARD",
    "LEGACY_TASK_TYPE_ALIASES",
    "build_dependency_graph",
    "blocked_message",
    "complete_task",
    "complete_task_action",
    "create_task",
    "create_task_action",
    "delete_task",
    "delete_task_action",
    "get_dependents",
    "get_dependents_action",
    "get_task",
    "get_task_action",
    "list_tasks",
    "list_tasks_action",
    "migrate_dependency_data",
    "normalize_card_type",
    "refuse_task",
    "refuse_task_action",
    "skip_task",
    "skip_task_action",
    "sync_all_unlock_states",
    "update_task",
    "update_task_action",
    "validate_task_type",
]


# ---------------------------------------------------------------------------
# 卡类型词表（task_type 的唯一权威来源）
# ---------------------------------------------------------------------------

#: 正式的四种卡类型（自由卡 / 微型卡 / 目标卡 / 标准卡）。
CARD_TYPE_FREE = "free"
CARD_TYPE_MICRO = "micro"
CARD_TYPE_GOAL = "goal"
CARD_TYPE_STANDARD = "standard"

#: 正式卡类型词表（有序元组）。
CARD_TYPES = (
    CARD_TYPE_FREE,
    CARD_TYPE_MICRO,
    CARD_TYPE_GOAL,
    CARD_TYPE_STANDARD,
)

#: 已知历史存量 ``task_type`` 值 —— 在旧数据里一律表示"普通任务"，
#: **不是**任何一种新卡类型。写入侧允许写回（往返兼容），读取侧归一为
#: ``standard``。
LEGACY_TASK_TYPE_ALIASES = frozenset({
    "normal",
    "other",
    "daily",
    "weekly",
    "accumulation",
    "deadline",
    "note",
    "exercise",
    "note_review",
    "chapter_review",
    "chapter_exam",
    "exam_question",
    "exam_review",
})

#: 写入侧允许的 ``task_type`` 取值全集（正式卡类型 + 已知历史别名）。
ACCEPTED_TASK_TYPES = frozenset(CARD_TYPES) | LEGACY_TASK_TYPE_ALIASES

#: 写入侧错误消息里使用的合法值清单（只列正式卡类型，别名是兼容入口）。
_TASK_TYPE_ERROR = "task_type must be one of: " + ", ".join(CARD_TYPES)


def normalize_card_type(task_type: Any) -> str:
    """把 ``tasks.task_type`` 的历史/异常值归一为四种正式卡类型之一。

    归一规则：

    - ``None`` / 空串 / 非字符串 → ``standard``；
    - 已是四种正式卡类型之一 → 原样返回（只 ``strip()``，不折叠大小写）；
    - 已知历史存量值（``normal`` / ``other`` / …） → ``standard``；
    - 任何 **未知** 旧值 → ``standard``。

    **只读语义**：本函数 **绝不** 改写数据库里的任何一行。
    """
    if not isinstance(task_type, str):
        return CARD_TYPE_STANDARD
    value = task_type.strip()
    if not value:
        return CARD_TYPE_STANDARD
    if value in CARD_TYPES:
        return value
    return CARD_TYPE_STANDARD


def validate_task_type(value: Any) -> Tuple[bool, str]:
    """校验写入侧的 ``task_type``。

    返回 ``(ok, normalized_or_error)``：

    - ``(True, value)`` —— 合法（四种正式卡类型或已知历史别名）；
    - ``(False, message)`` —— 非法，调用方必须回 400 且 **不得** 写入
      任何部分结果。
    """
    if not isinstance(value, str):
        return False, _TASK_TYPE_ERROR
    candidate = value.strip()
    if not candidate:
        return False, _TASK_TYPE_ERROR
    if candidate not in ACCEPTED_TASK_TYPES:
        return False, _TASK_TYPE_ERROR
    return True, candidate


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------

def list_tasks(
    conn,
    *,
    include_completed: bool = False,
    unlocked_only: bool = False,
) -> List[Dict[str, Any]]:
    """列出任务（HTTP 层已把 query 参数解析成 bool）。"""
    return task_repo.list_tasks(
        conn,
        include_completed=include_completed,
        unlocked_only=unlocked_only,
    )


def get_task(conn, task_id: int) -> Optional[Dict[str, Any]]:
    """按 id 取单个任务；不存在返回 ``None``。"""
    return task_repo.get_task(conn, task_id)


def get_dependents(conn, task_id: int) -> Optional[List[Dict[str, Any]]]:
    """返回直接依赖者列表；任务不存在返回 ``None``（→ 404）。"""
    if task_repo.get_task(conn, task_id) is None:
        return None
    return task_repo.get_task_dependents(conn, task_id)


# ---------------------------------------------------------------------------
# 写入
# ---------------------------------------------------------------------------

def create_task(conn, data: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    """创建任务。

    返回 ``(task_id, error_message)``：

    * 成功 → ``(task_id, None)``；
    * 失败 → ``(None, error_message)``，**零副作用**（调用方回 400）。

    校验顺序（与迁移前逐条一致，任何一步失败都在写库 **之前** 返回）：

    1. ``prerequisite_ids`` 必须是 list；
    2. ``task_type`` 合法（省略时写 ``"normal"``）；
    3. ``prerequisite_ids`` 元素必须是正整数；
    4. 前置任务必须存在；
    5. ``is_unlocked`` = 全部前置是否已完成。
    """
    prereq_ids = data.get("prerequisite_ids") or []
    if not isinstance(prereq_ids, list):
        return None, "prerequisite_ids must be list"

    task_type = "normal"
    if "task_type" in data:
        ok, resolved = validate_task_type(data.get("task_type"))
        if not ok:
            return None, resolved
        task_type = resolved

    if any(type(pid) is not int or pid <= 0 for pid in prereq_ids):
        return None, "invalid prerequisite_ids"
    if prereq_ids:
        existing = task_repo.count_existing_ids(conn, prereq_ids)
        if existing != len(set(prereq_ids)):
            return None, "前置任务不存在"

    is_unlocked = int(task_repo.all_prereqs_completed(conn, prereq_ids))
    now = datetime.now().isoformat()
    task_id = task_repo.insert_task(
        conn,
        name=data.get("name", ""),
        category=data.get("category", "daily"),
        task_type=task_type,
        description=data.get("description"),
        estimated_time=data.get("estimated_time", 30),
        preferred_time=data.get("preferred_time"),
        deadline=data.get("deadline"),
        resistance=data.get("resistance", "medium"),
        energy_required=data.get("energy_required", "medium"),
        rarity=data.get("rarity", "common"),
        priority=data.get("priority", 5),
        is_daily=bool(data.get("is_daily", False)),
        repeat_type=data.get("repeat_type", "none"),
        prerequisite_ids=prereq_ids,
        is_unlocked=bool(is_unlocked),
        linked_note_path=data.get("linked_note_path"),
        now=now,
    )
    return task_id, None


#: ``PUT /api/tasks/<id>`` 允许逐列更新的字段白名单。
UPDATABLE_FIELDS = (
    "name",
    "category",
    "description",
    "estimated_time",
    "preferred_time",
    "deadline",
    "resistance",
    "energy_required",
    "rarity",
    "priority",
    "is_daily",
    "repeat_type",
    "linked_note_path",
)


def update_task(
    conn, task_id: int, data: Dict[str, Any]
) -> Tuple[str, Optional[str]]:
    """更新任务。

    返回 ``(result, error_message)``：

    * ``"updated"`` —— 成功；
    * ``"not_found"`` —— 任务不存在（→ 404）；
    * ``"no_fields"`` —— payload 里没有可更新字段；
    * ``(None, message)`` —— 校验失败（→ 400），**零副作用**。
    """
    new_task_type = None
    if "task_type" in data:
        ok, resolved = validate_task_type(data.get("task_type"))
        if not ok:
            return "", resolved
        new_task_type = resolved

    if task_repo.get_task(conn, task_id) is None:
        return "not_found", None

    new_prereqs: Optional[List[int]] = None
    is_unlocked: Optional[int] = None
    if "prerequisite_ids" in data:
        candidate = data["prerequisite_ids"] or []
        if not isinstance(candidate, list) or any(
            type(pid) is not int or pid <= 0 for pid in candidate
        ):
            return "", "invalid prerequisite_ids"
        if candidate:
            existing = task_repo.count_existing_ids(conn, candidate)
            if existing != len(set(candidate)):
                return "", "前置任务不存在"
        cycle = task_repo.detect_cycle(conn, task_id, candidate)
        if cycle:
            return "", f"检测到循环依赖: {cycle}"
        new_prereqs = list(candidate)
        is_unlocked = int(task_repo.all_prereqs_completed(conn, new_prereqs))

    fields: Dict[str, Any] = {}
    for column in UPDATABLE_FIELDS:
        if column in data:
            fields[column] = data[column]
    if new_task_type is not None:
        fields["task_type"] = new_task_type
    if new_prereqs is not None:
        fields["prerequisite_ids"] = json.dumps(new_prereqs)
        fields["is_unlocked"] = is_unlocked

    if not fields:
        return "no_fields", None

    task_repo.update_task_fields(conn, task_id, fields)
    if new_prereqs is not None:
        task_repo.sync_dependency_edges(conn, task_id, new_prereqs)
    return "updated", None


def delete_task(conn, task_id: int) -> bool:
    """删除任务；不存在返回 ``False``（→ 404）。"""
    if task_repo.get_task(conn, task_id) is None:
        return False
    task_repo.delete_task(conn, task_id)
    return True


def complete_task(
    conn, task_id: int
) -> Tuple[str, Optional[List[str]], Optional[str]]:
    """完成任务（``update_rate=True``）。

    返回 ``(outcome, unlocked_names, error_message)``：

    * ``("completed", names, None)`` —— 成功；
    * ``("not_found", None, None)`` —— → 404；
    * ``("blocked", None, message)`` —— → 400。
    """
    return _finish_task(conn, task_id, update_rate=True)


def skip_task(
    conn, task_id: int
) -> Tuple[str, Optional[List[str]], Optional[str]]:
    """跳过任务（``update_rate=False``，不计成功率）。"""
    return _finish_task(conn, task_id, update_rate=False)


def _finish_task(
    conn, task_id: int, *, update_rate: bool
) -> Tuple[str, Optional[List[str]], Optional[str]]:
    task = task_repo.get_task(conn, task_id)
    if task is None:
        return "not_found", None, None
    blocked = task_repo.blocked_message(conn, task)
    if blocked:
        return "blocked", None, blocked
    task_repo.mark_completed(conn, task_id, update_rate=update_rate)
    unlocked = task_repo.unlock_dependents(conn, task_id)
    return "completed", unlocked, None


def refuse_task(conn, task_id: int) -> None:
    """记录一次拒绝（``refusal_count`` +1）。"""
    task_repo.refuse_task(conn, task_id)


# ---------------------------------------------------------------------------
# 启动时的幂等数据同步（Stage 7：从 legacy 单体收口）
# ---------------------------------------------------------------------------

def sync_all_unlock_states(conn) -> int:
    """启动时 **幂等** 同步所有未完成任务的解锁状态。

    与 legacy ``sync_all_unlock_states`` 逐条等价：对每个 ``completed=0``
    的任务重算 ``is_unlocked``。

    返回被重算的任务数量。
    """
    task_ids = task_repo.list_incomplete_task_ids(conn)
    for task_id in task_ids:
        task_repo.recompute_task_unlock(conn, task_id)
    return len(task_ids)


def migrate_dependency_data(conn) -> int:
    """启动时把 ``prerequisite_ids`` JSON 列迁移到 ``task_dependencies`` 表。

    与 legacy ``migrate_dependency_data`` 逐条等价：

    * ``task_dependencies`` **已有行** → 直接返回（已迁移过，幂等）；
    * 否则遍历有前置的任务，逐条 ``INSERT OR IGNORE``。

    返回被迁移的任务数量。
    """
    if task_repo.count_dependency_rows(conn) > 0:
        return 0
    count = 0
    for task_id, prereqs in task_repo.list_tasks_with_prerequisites(conn):
        for pid in prereqs:
            task_repo.insert_dependency_row(conn, task_id, pid)
        count += 1
    return count


# ---------------------------------------------------------------------------
# 依赖图（/api/dependencies）
# ---------------------------------------------------------------------------

def build_dependency_graph(conn) -> Dict[str, Any]:
    """构建依赖图：``{"nodes": [...], "edges": [...]}``。

    节点来自 ``tasks``（``id`` / ``name`` / ``is_unlocked`` / ``completed``）；
    边来自 ``prerequisite_ids`` JSON 列（``from`` = 前置，``to`` = 依赖者）。

    与 legacy 的 ``api_get_dependencies`` 逐条等价：单行解析失败时 **跳过**
    该行的边（不中断整体）。
    """
    rows = conn.execute(
        "SELECT id, name, prerequisite_ids, is_unlocked, completed FROM tasks"
    ).fetchall()
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    for row in rows:
        task = dict(row)
        nodes.append(
            {
                "id": task["id"],
                "name": task["name"],
                "is_unlocked": task["is_unlocked"],
                "completed": task["completed"],
            }
        )
        try:
            prereqs = json.loads(task["prerequisite_ids"] or "[]")
        except (TypeError, ValueError):
            continue
        for pid in prereqs:
            edges.append({"from": pid, "to": task["id"]})
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# 自持事务的整体动作入口（AR03-P2 / P2 收尾）
# ---------------------------------------------------------------------------
#
# 上面那些 ``(conn, ...)`` 函数是 **连接感知** 的：调用方（过去是 Blueprint，
# 现在仍然是 Service 内部的复合动作）管理连接与事务边界。
#
# 下面的 ``*_action`` 函数是 **自持事务** 的：它们 **自己** 开连接、在
# **同一连接** 上完成全部 repo 调用、并在返回前提交或回滚。
#
# 这让 Blueprint 可以退化为纯 HTTP 层（「解析请求 → 调 Service → 组装响应」），
# 事务边界 **下沉到 Service**（见 :func:`server.repositories.db.service_transaction`）。
#
# **提交时机与迁移前逐条等价**：Blueprint 旧写法是
# ``with write_connection() as conn: service.xxx(conn, ...)``，
# 即「退出 with 时提交」；新写法是「Service 内部退出 with 时提交」。
# 异常路径同样回滚（``test_stage3_gacha_domain.py::事务原子性`` 锁定）。


def list_tasks_action(
    *,
    include_completed: bool = False,
    unlocked_only: bool = False,
) -> List[Dict[str, Any]]:
    """只读：列出任务。"""
    with service_transaction(commit=False) as conn:
        return list_tasks(
            conn,
            include_completed=include_completed,
            unlocked_only=unlocked_only,
        )


def get_task_action(task_id: int) -> Optional[Dict[str, Any]]:
    """只读：按 id 取单个任务。"""
    with service_transaction(commit=False) as conn:
        return get_task(conn, task_id)


def get_dependents_action(task_id: int) -> Optional[List[Dict[str, Any]]]:
    """只读：取直接依赖者列表。"""
    with service_transaction(commit=False) as conn:
        return get_dependents(conn, task_id)


def create_task_action(
    data: Dict[str, Any],
) -> Tuple[Optional[int], Optional[str]]:
    """创建任务（自持事务）。"""
    with service_transaction() as conn:
        return create_task(conn, data)


def update_task_action(
    task_id: int, data: Dict[str, Any]
) -> Tuple[str, Optional[str]]:
    """更新任务（自持事务）。"""
    with service_transaction() as conn:
        return update_task(conn, task_id, data)


def delete_task_action(task_id: int) -> bool:
    """删除任务（自持事务）。"""
    with service_transaction() as conn:
        return delete_task(conn, task_id)


def complete_task_action(
    task_id: int,
) -> Tuple[str, Optional[List[str]], Optional[str]]:
    """完成任务（自持事务）。

    ``mark_completed`` + ``unlock_dependents`` 在 **同一连接、同一事务**
    内完成 —— 原子性与迁移前逐条等价。
    """
    with service_transaction() as conn:
        return complete_task(conn, task_id)


def skip_task_action(
    task_id: int,
) -> Tuple[str, Optional[List[str]], Optional[str]]:
    """跳过任务（自持事务）。"""
    with service_transaction() as conn:
        return skip_task(conn, task_id)


def refuse_task_action(task_id: int) -> None:
    """记录一次拒绝（自持事务）。"""
    with service_transaction() as conn:
        refuse_task(conn, task_id)


def build_dependency_graph_action() -> Dict[str, Any]:
    """只读：构建依赖图。"""
    with service_transaction(commit=False) as conn:
        return build_dependency_graph(conn)
