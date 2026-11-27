"""server.services.free_task - 自由任务 (free task) 领域逻辑。

定位
----
这是一个 **纯逻辑、无副作用** 的领域模块：它只做判定与结构化返回，
不碰数据库、不碰文件系统、不 import Flask、不读取 ``config/config.json``、
不写任何日志。它的返回值是 *纯数据*（``dict``），因此可以被后续独立的
事件日志接入层直接消费。

已确定的产品规则（LT_RETENTION_FREE_TASK_DOMAIN_20261022_A）：

1. **时长由策略自动选择**：自由任务的时间只能是 ``25`` 或 ``55`` 分钟，
   依据有效的 *个人时间策略* 自动决定，用户不再手动选择时长。
   非法或缺失的时间策略 → **明确报错**（fail closed），绝不用兜底值
   悄悄继续。
2. **接受任务必须有具体活动内容**：活动内容为空白 / 缺失 / 含控制字符
   → 明确报错。可选原因缺省为 ``"没有什么理由，我就是想。"``。
3. **只有用户明确报告完成**才算完成：成功的自由任务可增加完成任务数
   （``completed_count_delta = 1``）。娱乐活动的 **有效学习番茄钟贡献为零**；
   学习贡献必须依据用户 *真实报告* 的学习时间；计时结束 **不得** 自动完成。
4. **“帮我选”**：从 *已批准* 的候选活动中返回一个具体建议；没有合法
   候选时明确拒绝（不返回占位建议）。
5. **暂停 / 中断 / 失败 / 实际活动** 均有结构化返回数据，便于后续独立
   事件日志接入。

随机源注入
----------
时长选择与“帮我选”都接受可注入的随机源（``rng``）。随机源只需提供
``.random() -> float`` 方法，因此测试可以传入确定性假随机源，不需要
mock 全局 ``random``。默认使用 ``random.Random()``（**每次调用新建**，
不共享全局状态）。

安全与无副作用约束
------------------
- 本模块 **绝不** 读写 ``data/task_publisher.db`` / ``config/config.json`` /
  ``src/notes/**`` / ``data/agent-policy/``。
- 本模块 **绝不** 产生时间戳副作用：所有时间字段都由调用方注入
  （``occurred_at``），缺省为 ``None``。
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 常量与数据契约
# ---------------------------------------------------------------------------

#: 自由任务允许的时长（分钟）。用户不再手动选择，只能由策略产出。
FREE_TASK_MINUTES_OPTIONS: Tuple[int, ...] = (25, 55)

#: 可选原因的缺省文本。
DEFAULT_FREE_TASK_REASON = "没有什么理由，我就是想。"

#: 活动分类取值。
CATEGORY_STUDY = "study"
CATEGORY_ENTERTAINMENT = "entertainment"

#: 合法活动分类集合。
VALID_CATEGORIES = (CATEGORY_STUDY, CATEGORY_ENTERTAINMENT)

#: 中文 / 英文别名 → 规范分类。
_CATEGORY_ALIASES = {
    "study": CATEGORY_STUDY,
    "learning": CATEGORY_STUDY,
    "学习": CATEGORY_STUDY,
    "entertainment": CATEGORY_ENTERTAINMENT,
    "fun": CATEGORY_ENTERTAINMENT,
    "leisure": CATEGORY_ENTERTAINMENT,
    "娱乐": CATEGORY_ENTERTAINMENT,
}

#: 活动内容长度上限。
MAX_ACTIVITY_LENGTH = 200

#: 自由文本中禁止出现的控制字符。
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# --- 事件类型（供后续独立事件日志接入） ---------------------------------
EVENT_STARTED = "free_task.started"
EVENT_PAUSED = "free_task.paused"
EVENT_RESUMED = "free_task.resumed"
EVENT_INTERRUPTED = "free_task.interrupted"
EVENT_FAILED = "free_task.failed"
EVENT_COMPLETED = "free_task.completed"
EVENT_TIMER_ELAPSED = "free_task.timer_elapsed"
EVENT_ACTIVITY_SUGGESTED = "free_task.activity_suggested"

# --- 任务状态 -------------------------------------------------------------
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_INTERRUPTED = "interrupted"
STATUS_FAILED = "failed"
STATUS_COMPLETED = "completed"


class FreeTaskError(Exception):
    """自由任务领域错误（fail closed）。

    ``code`` 是稳定的机器可读原因码；``message`` 是给用户看的中文说明。
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


# ---------------------------------------------------------------------------
# 内部小工具
# ---------------------------------------------------------------------------

def _is_int(value: Any) -> bool:
    """是否为 *严格* 整数（拒绝 ``bool`` / ``float``）。"""
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def _is_plain_text(value: Any, *, max_len: int) -> bool:
    """是否为不含控制字符的非空字符串。"""
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    if len(value) > max_len:
        return False
    return not _CONTROL_CHARS.search(value)


def _normalize_category(value: Any) -> str:
    """把活动分类规范化为 ``study`` / ``entertainment``。

    非法分类 → 明确报错。
    """
    if not isinstance(value, str) or not value.strip():
        raise FreeTaskError(
            "category_required", "必须明确活动分类（学习 / 娱乐）"
        )
    key = value.strip().lower()
    if key not in _CATEGORY_ALIASES:
        raise FreeTaskError(
            "category_invalid", f"未知的活动分类: {value!r}"
        )
    return _CATEGORY_ALIASES[key]


def _normalize_elapsed_minutes(value: Any) -> int:
    """校验经过分钟数（严格非负整数）。"""
    if not _is_int(value) or value < 0:
        raise FreeTaskError(
            "elapsed_minutes_invalid", "经过分钟数必须是非负整数"
        )
    return int(value)


def _task_copy(task: Dict[str, Any]) -> Dict[str, Any]:
    """复制任务视图（绝不把调用方的对象直接放进返回结构）。"""
    return {
        "task_id": task.get("task_id"),
        "activity": task.get("activity"),
        "category": task.get("category"),
        "planned_minutes": task.get("planned_minutes"),
        "reason": task.get("reason"),
        "status": task.get("status"),
        "elapsed_minutes": task.get("elapsed_minutes"),
    }


def _event(
    event_type: str,
    task: Optional[Dict[str, Any]],
    *,
    occurred_at: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造统一的结构化事件返回数据。"""
    payload: Dict[str, Any] = {
        "event_type": event_type,
        "occurred_at": occurred_at,
        "task": _task_copy(task) if isinstance(task, dict) else None,
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# 1) 时长策略 → 25 / 55
# ---------------------------------------------------------------------------

def _extract_time_source(policy: Any) -> Dict[str, Any]:
    """从策略文档中定位时间策略所在的字典。

    支持两种形态：
    - ``{"free_task_minutes": 25}`` / ``{"free_task_minutes": [25, 55]}``
    - ``{"free_task_time_strategy": {"options": [25, 55]}}``
    - 完整策略文档：``{"policy": {"free_task_minutes": ...}}``
    """
    if not isinstance(policy, dict):
        raise FreeTaskError(
            "time_policy_invalid", "时间策略必须是对象"
        )

    strategy = policy.get("free_task_time_strategy")
    if isinstance(strategy, dict):
        return strategy

    if "free_task_minutes" in policy:
        return policy

    nested = policy.get("policy")
    if isinstance(nested, dict):
        if "free_task_time_strategy" in nested and isinstance(
            nested["free_task_time_strategy"], dict
        ):
            return nested["free_task_time_strategy"]
        if "free_task_minutes" in nested:
            return nested

    raise FreeTaskError(
        "time_policy_missing", "缺少有效的自由任务时间策略"
    )


def _time_options(source: Dict[str, Any]) -> List[int]:
    """解析时间策略允许的时长集合。"""
    raw = source.get("options")
    if raw is None:
        raw = source.get("free_task_minutes")
    if raw is None:
        raise FreeTaskError(
            "time_policy_missing", "缺少有效的自由任务时间策略"
        )

    if _is_int(raw):
        candidates: Sequence[Any] = [raw]
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        raise FreeTaskError(
            "time_policy_invalid", "时间策略的时长必须是整数或整数列表"
        )

    if not candidates:
        raise FreeTaskError(
            "time_policy_empty_options", "时间策略没有可用时长"
        )

    options: List[int] = []
    for item in candidates:
        if not _is_int(item):
            raise FreeTaskError(
                "time_policy_invalid", "时间策略的时长必须是严格整数"
            )
        if item not in FREE_TASK_MINUTES_OPTIONS:
            raise FreeTaskError(
                "time_policy_unsupported_minutes",
                f"自由任务时长只能是 {FREE_TASK_MINUTES_OPTIONS} 分钟",
            )
        if item not in options:
            options.append(int(item))

    if not options:
        raise FreeTaskError(
            "time_policy_empty_options", "时间策略没有可用时长"
        )
    return options


def select_free_task_minutes(
    policy: Any,
    rng: Optional[Any] = None,
) -> int:
    """依据个人时间策略自动选择自由任务时长（25 或 55 分钟）。

    - ``policy`` 为固定时长（整数）→ 直接返回；
    - ``policy`` 为时长列表 → 按随机源在列表中挑选（等概率）；
    - 缺失 / 非法 → 抛 ``FreeTaskError``（**绝不**使用兜底时长）。

    ``rng`` 只需提供 ``.random() -> float``；缺省使用全新的
    ``random.Random()`` 实例（不污染全局随机状态）。
    """
    source = _extract_time_source(policy)
    options = _time_options(source)

    if len(options) == 1:
        return options[0]

    random_source = rng if rng is not None else random.Random()
    draw = random_source.random()
    if not isinstance(draw, (int, float)) or isinstance(draw, bool):
        raise FreeTaskError(
            "random_source_invalid", "随机源必须返回 0..1 之间的数值"
        )
    index = int(draw * len(options))
    if index < 0:
        index = 0
    elif index >= len(options):
        index = len(options) - 1
    return options[index]


# ---------------------------------------------------------------------------
# 2) 原因与活动内容
# ---------------------------------------------------------------------------

def normalize_reason(reason: Any = None) -> str:
    """规范化可选原因。

    - 缺失 / 空白 → 返回缺省文本 ``"没有什么理由，我就是想。"``
    - 非字符串 → 明确报错
    - 含控制字符 → 明确报错
    """
    if reason is None:
        return DEFAULT_FREE_TASK_REASON
    if not isinstance(reason, str):
        raise FreeTaskError("reason_invalid", "原因必须是字符串")
    if not reason.strip():
        return DEFAULT_FREE_TASK_REASON
    if _CONTROL_CHARS.search(reason):
        raise FreeTaskError("reason_invalid", "原因含控制字符")
    if len(reason) > MAX_ACTIVITY_LENGTH:
        raise FreeTaskError("reason_invalid", "原因过长")
    return reason.strip()


def validate_activity(activity: Any) -> str:
    """校验并规范化活动内容（用户必须给出 *具体* 活动）。"""
    if not isinstance(activity, str):
        raise FreeTaskError("activity_required", "必须填写具体的活动内容")
    if not activity.strip():
        raise FreeTaskError("activity_required", "必须填写具体的活动内容")
    if _CONTROL_CHARS.search(activity):
        raise FreeTaskError("activity_invalid", "活动内容含控制字符")
    if len(activity) > MAX_ACTIVITY_LENGTH:
        raise FreeTaskError("activity_invalid", "活动内容过长")
    return activity.strip()


# ---------------------------------------------------------------------------
# 3) 开始自由任务
# ---------------------------------------------------------------------------

def start_free_task(
    *,
    activity: Any,
    category: Any,
    minutes: Any,
    reason: Any = None,
    task_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """接受一个自由任务，返回结构化的开始事件。

    前置条件（缺一即明确报错）：
    - ``activity``：具体活动内容（必须）；
    - ``category``：``study`` / ``entertainment``（必须）；
    - ``minutes``：``25`` 或 ``55``（必须；正常路径来自
      :func:`select_free_task_minutes`）。
    """
    clean_activity = validate_activity(activity)
    clean_category = _normalize_category(category)
    clean_reason = normalize_reason(reason)

    if not _is_int(minutes) or minutes not in FREE_TASK_MINUTES_OPTIONS:
        raise FreeTaskError(
            "minutes_invalid",
            f"自由任务时长只能是 {FREE_TASK_MINUTES_OPTIONS} 分钟",
        )

    task = {
        "task_id": task_id,
        "activity": clean_activity,
        "category": clean_category,
        "planned_minutes": int(minutes),
        "reason": clean_reason,
        "status": STATUS_RUNNING,
        "elapsed_minutes": 0,
    }
    return _event(EVENT_STARTED, task, occurred_at=occurred_at)


# ---------------------------------------------------------------------------
# 4) 暂停 / 中断 / 失败 / 计时结束
# ---------------------------------------------------------------------------

def pause_free_task(
    task: Dict[str, Any],
    *,
    elapsed_minutes: Any = 0,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """暂停自由任务：返回结构化暂停事件（不自动完成）。"""
    elapsed = _normalize_elapsed_minutes(elapsed_minutes)
    paused = _task_copy(task)
    paused["status"] = STATUS_PAUSED
    paused["elapsed_minutes"] = elapsed
    return _event(
        EVENT_PAUSED,
        paused,
        occurred_at=occurred_at,
        extra={"completed_count_delta": 0},
    )


# ---------------------------------------------------------------------------
# 4b) 暂停 → 继续（恢复）
# ---------------------------------------------------------------------------

def resume_free_task(
    task: Dict[str, Any],
    *,
    elapsed_minutes: Any = None,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """**继续** 一个被暂停的自由任务（唯一合法前态是 ``paused``）。

    规则（``LT_RETENTION_FREE_TASK_RESUME_CONTRACT_20261023_L``）：

    - 只能从 :data:`STATUS_PAUSED` 恢复到 :data:`STATUS_RUNNING`；其它
      任何状态（含 ``running`` / ``interrupted`` / ``failed`` /
      ``completed`` / ``None``）→ 抛 :class:`FreeTaskError`
      （``resume_not_allowed``），**绝不** 静默放行；
    - 恢复 **不** 改变活动、计划时长、分类与已有时长；``elapsed_minutes``
      缺省时沿用任务里已有的值；
    - 恢复 **绝不** 计入完成数、已验证学习分钟或番茄钟：三者恒为 ``0``。
      “有效学习分钟” 仍然只能由用户 *明确报告* 的完成事件产生
      （见 :func:`complete_free_task`）；
    - 纯函数：返回新字典，绝不修改调用方传入的任务视图。
    """
    if not isinstance(task, dict):
        raise FreeTaskError("task_invalid", "自由任务必须是任务视图字典")

    current_status = task.get("status")
    if current_status != STATUS_PAUSED:
        raise FreeTaskError(
            "resume_not_allowed",
            f"只有已暂停的自由任务可以继续（当前状态: {current_status!r}）",
        )

    planned = task.get("planned_minutes")
    if not _is_int(planned) or planned not in FREE_TASK_MINUTES_OPTIONS:
        raise FreeTaskError(
            "minutes_invalid",
            f"自由任务时长只能是 {FREE_TASK_MINUTES_OPTIONS} 分钟",
        )

    elapsed = (
        _normalize_elapsed_minutes(elapsed_minutes)
        if elapsed_minutes is not None
        else _normalize_elapsed_minutes(task.get("elapsed_minutes") or 0)
    )

    running = _task_copy(task)
    running["status"] = STATUS_RUNNING
    running["elapsed_minutes"] = elapsed
    return _event(
        EVENT_RESUMED,
        running,
        occurred_at=occurred_at,
        extra={
            "completed_count_delta": 0,
            "study_minutes": 0,
            "study_pomodoros": 0,
            "auto_completed": False,
            "resumed_from": STATUS_PAUSED,
        },
    )


def interrupt_free_task(
    task: Dict[str, Any],
    *,
    elapsed_minutes: Any = 0,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """中断自由任务：返回结构化中断事件（不计完成）。"""
    elapsed = _normalize_elapsed_minutes(elapsed_minutes)
    stopped = _task_copy(task)
    stopped["status"] = STATUS_INTERRUPTED
    stopped["elapsed_minutes"] = elapsed
    return _event(
        EVENT_INTERRUPTED,
        stopped,
        occurred_at=occurred_at,
        extra={"completed_count_delta": 0},
    )


def fail_free_task(
    task: Dict[str, Any],
    *,
    elapsed_minutes: Any = 0,
    reason: Any = None,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """自由任务失败：返回结构化失败事件（不计完成）。"""
    elapsed = _normalize_elapsed_minutes(elapsed_minutes)
    failed = _task_copy(task)
    failed["status"] = STATUS_FAILED
    failed["elapsed_minutes"] = elapsed
    clean_reason = normalize_reason(reason)
    return _event(
        EVENT_FAILED,
        failed,
        occurred_at=occurred_at,
        extra={"completed_count_delta": 0, "reason": clean_reason},
    )


def on_timer_elapsed(
    task: Dict[str, Any],
    *,
    elapsed_minutes: Any = 0,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """计时结束：**不自动完成**。

    计时结束只产生一条“时间到”的事件：``completed_count_delta = 0``，
    ``study_pomodoros = 0``，状态保持 ``running``。完成必须由用户
    *明确报告*（见 :func:`complete_free_task`）。
    """
    elapsed = _normalize_elapsed_minutes(elapsed_minutes)
    running = _task_copy(task)
    running["status"] = STATUS_RUNNING
    running["elapsed_minutes"] = elapsed
    return _event(
        EVENT_TIMER_ELAPSED,
        running,
        occurred_at=occurred_at,
        extra={
            "completed_count_delta": 0,
            "study_minutes": 0,
            "study_pomodoros": 0,
            "auto_completed": False,
        },
    )


# ---------------------------------------------------------------------------
# 5) 明确报告完成
# ---------------------------------------------------------------------------

def complete_free_task(
    task: Dict[str, Any],
    *,
    reported_study_minutes: Any = None,
    elapsed_minutes: Any = None,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """用户 **明确报告** 完成自由任务。

    规则：

    - 成功的自由任务：``completed_count_delta = 1``；
    - **娱乐活动**：有效学习番茄钟贡献恒为 ``0``
      （``study_minutes = 0`` / ``study_pomodoros = 0``）；
    - **学习活动**：贡献必须依据用户 *真实报告* 的学习时间
      （``reported_study_minutes``）。缺失或非正数 → 明确报错
      （绝不按计时结束自动折算）。
    """
    planned = task.get("planned_minutes")
    if not _is_int(planned) or planned not in FREE_TASK_MINUTES_OPTIONS:
        raise FreeTaskError(
            "minutes_invalid",
            f"自由任务时长只能是 {FREE_TASK_MINUTES_OPTIONS} 分钟",
        )

    elapsed = (
        _normalize_elapsed_minutes(elapsed_minutes)
        if elapsed_minutes is not None
        else _normalize_elapsed_minutes(task.get("elapsed_minutes") or 0)
    )

    category = task.get("category")
    if category not in VALID_CATEGORIES:
        raise FreeTaskError(
            "category_invalid", f"未知的活动分类: {category!r}"
        )

    completed = _task_copy(task)
    completed["status"] = STATUS_COMPLETED
    completed["elapsed_minutes"] = elapsed

    if category == CATEGORY_ENTERTAINMENT:
        # 娱乐活动的有效学习番茄钟贡献为零。
        study_minutes = 0
        pomodoros = 0
    else:
        if reported_study_minutes is None:
            raise FreeTaskError(
                "study_minutes_required",
                "学习活动必须报告真实学习时间，不能按计时结束自动完成",
            )
        if not _is_int(reported_study_minutes) or reported_study_minutes <= 0:
            raise FreeTaskError(
                "study_minutes_invalid", "报告的学习时间必须是正整数分钟"
            )
        study_minutes = int(reported_study_minutes)
        pomodoros = study_minutes // int(planned)

    return _event(
        EVENT_COMPLETED,
        completed,
        occurred_at=occurred_at,
        extra={
            "completed_count_delta": 1,
            "study_minutes": study_minutes,
            "study_pomodoros": pomodoros,
            "auto_completed": False,
            "explicitly_reported": True,
        },
    )


# ---------------------------------------------------------------------------
# 6) “帮我选”
# ---------------------------------------------------------------------------

def _candidate_activity(candidate: Any) -> Optional[Dict[str, Any]]:
    """把一个候选活动规范化为可用视图；不合法返回 ``None``。"""
    if not isinstance(candidate, dict):
        return None
    if candidate.get("approved") is not True:
        # 只有 *已批准* 的候选可以被选中。
        return None
    try:
        activity = validate_activity(candidate.get("activity"))
    except FreeTaskError:
        return None
    try:
        category = _normalize_category(candidate.get("category"))
    except FreeTaskError:
        return None
    minutes = candidate.get("minutes")
    if minutes is not None:
        if not _is_int(minutes) or minutes not in FREE_TASK_MINUTES_OPTIONS:
            return None
        minutes = int(minutes)
    else:
        minutes = None
    reason = candidate.get("reason")
    if reason is None:
        reason = DEFAULT_FREE_TASK_REASON
    elif not isinstance(reason, str) or not reason.strip():
        reason = DEFAULT_FREE_TASK_REASON
    return {
        "activity": activity,
        "category": category,
        "minutes": minutes,
        "reason": reason.strip(),
    }


def suggest_activity(
    candidates: Optional[Iterable[Any]],
    rng: Optional[Any] = None,
    *,
    occurred_at: Optional[str] = None,
) -> Dict[str, Any]:
    """“帮我选”：从 **已批准** 的候选活动中返回一个具体建议。

    没有合法候选 → 抛 ``FreeTaskError('no_candidate_available')``，
    绝不返回占位建议。
    """
    legal: List[Dict[str, Any]] = []
    if isinstance(candidates, (list, tuple)):
        for candidate in candidates:
            normalized = _candidate_activity(candidate)
            if normalized is not None:
                legal.append(normalized)

    if not legal:
        raise FreeTaskError(
            "no_candidate_available", "没有可用的已批准候选活动，无法给出建议"
        )

    random_source = rng if rng is not None else random.Random()
    draw = random_source.random()
    if not isinstance(draw, (int, float)) or isinstance(draw, bool):
        raise FreeTaskError(
            "random_source_invalid", "随机源必须返回 0..1 之间的数值"
        )
    index = int(draw * len(legal))
    if index < 0:
        index = 0
    elif index >= len(legal):
        index = len(legal) - 1

    chosen = legal[index]
    return {
        "event_type": EVENT_ACTIVITY_SUGGESTED,
        "occurred_at": occurred_at,
        "suggestion": dict(chosen),
        "candidate_count": len(legal),
        "task": None,
    }


__all__ = [
    "CATEGORY_ENTERTAINMENT",
    "CATEGORY_STUDY",
    "DEFAULT_FREE_TASK_REASON",
    "EVENT_ACTIVITY_SUGGESTED",
    "EVENT_COMPLETED",
    "EVENT_FAILED",
    "EVENT_INTERRUPTED",
    "EVENT_PAUSED",
    "EVENT_RESUMED",
    "EVENT_STARTED",
    "EVENT_TIMER_ELAPSED",
    "FREE_TASK_MINUTES_OPTIONS",
    "MAX_ACTIVITY_LENGTH",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_INTERRUPTED",
    "STATUS_PAUSED",
    "STATUS_RUNNING",
    "VALID_CATEGORIES",
    "FreeTaskError",
    "complete_free_task",
    "fail_free_task",
    "interrupt_free_task",
    "normalize_reason",
    "on_timer_elapsed",
    "pause_free_task",
    "select_free_task_minutes",
    "resume_free_task",
    "start_free_task",
    "suggest_activity",
    "validate_activity",
]
