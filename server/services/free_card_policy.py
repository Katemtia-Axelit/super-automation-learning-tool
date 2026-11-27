"""server.services.free_card_policy - 正式自由卡策略读取器（唯一权威）。

定位
----
自由卡（``tasks.task_type == "free"``）的 **时长** 与 **活动建议** 只能来自
**同一份已批准的个人策略**（``data/agent-policy/latest.json``）。本模块是
这条读取路径的 **唯一权威**：

- 抽卡侧（``server/blueprints/gacha_bp.py``）只通过本模块取得合法时长；
- "帮我选" 只通过本模块从 **已批准候选池** 里取一条具体建议；
- 任何地方都 **不会** 从 ``weights`` 猜时长、也不会回落
  ``tasks.estimated_time``、更不会内置一份"想象的活动"。

只读、fail closed
-----------------
- **只读**：只以 ``"r"`` 打开 ``latest.json``；**绝不** 创建目录、
  **绝不** 写 latest、**绝不** 调用 Publisher、**绝不** 碰真实用户 DB。
- **fail closed**：目录缺失 / 文件缺失 / JSON 损坏 / 未获批准 / 时长非法 /
  候选为空 → 返回 **稳定的、可审计的 reason code**，并且 **没有** 可用的
  自由卡时长或建议。**绝不** 默认 25 / 30 / 55，**绝不** 伪造个人数据。

与既有领域模块的关系（复用清单）
--------------------------------
本模块 **复用** ``server/services/free_task.py`` 的纯函数与常量（该模块没有
数据库、没有文件系统、没有 Flask 副作用）：

- ``FREE_TASK_MINUTES_OPTIONS``（``(25, 55)``）—— 时长合法值的唯一来源；
- ``validate_activity`` —— 活动文本校验（非空 / 无控制字符 / ≤200 字）；
- ``normalize_reason`` —— 缺省理由 ``"没有什么理由，我就是想。"``；
- ``select_free_task_minutes`` —— **实际的时长抽取**（等概率）；
- ``FreeTaskError`` —— 领域错误码。

**为什么"候选规范化"与"抽一条建议"在本地最小实现**：``free_task.suggest_activity``
要求每个候选自带 ``approved is True`` **且** 带合法的 ``study`` /
``entertainment`` 分类；而"已批准策略里的候选活动"并不保证带分类（策略只保证
活动本身获批）。给缺失分类的候选 **硬补** 一个分类等于替用户编造"这是娱乐
还是学习"，与"娱乐不得冒充学习"的产品红线冲突。因此这里只复用 ``free_task``
的纯校验函数，候选规范化与单条抽取按最小纯规则本地实现
（``_normalize_activity_candidate`` / ``suggest_free_card_activity``）。

键名约定（与真实 Publisher 行为一致）
-------------------------------------
``latest.json`` 的真实形状由受控 Publisher 决定：提案里的 ``policy`` 袋会被
**展平** 到 ``latest.json`` 顶层（``scripts/agent_policy_publisher.py`` 的
``document[key] = value``）。因此自由卡键按 **同一优先级** 读取（与
``free_task._extract_time_source`` 完全一致）：

1. ``free_task_time_strategy``（对象，内含 ``options``）；
2. ``free_task_minutes``（整数或整数列表，兼容旧写法）；
3. 嵌套 ``policy`` 袋里的同名键。

活动候选同理：``free_task_activity_candidates``（顶层或嵌套 ``policy`` 袋）。

**``weights`` 绝不被当作时长来源**：它是 ``[0, 1]`` 的相对倾向系数域，
与 25 / 55 分钟毫无关系（把时长塞进 ``weights`` 会被静默忽略，也绝不会被
本模块读成时长）。
"""

from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from server.services import free_task
from server.services.agent_policy import (
    POLICY_FILENAME,
    read_policy_status,
    validate_policy_document,
)

#: 自由卡合法时长（分钟）。唯一权威来自既有领域模块，本模块不另立一套。
FREE_CARD_MINUTES_OPTIONS: Tuple[int, ...] = tuple(free_task.FREE_TASK_MINUTES_OPTIONS)

#: 活动文本长度上限（与领域模块一致）。
MAX_ACTIVITY_LENGTH = free_task.MAX_ACTIVITY_LENGTH

#: 候选活动条数上限（防御性上限；真实个人策略远少于此）。
MAX_ACTIVITY_CANDIDATES = 32

#: 候选活动分类标签的长度上限（分类是可选的纯文本标签，不是受控枚举）。
MAX_CATEGORY_LABEL_LENGTH = 32

#: 自由文本里禁止出现的控制字符（本地定义，避免依赖其它模块的私有名）。
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# --- 稳定 reason code（可审计，不含路径、不含策略正文） ---------------------

#: 策略目录未配置（无应用上下文 / 没有可读目录）。
REASON_POLICY_DIR_MISSING = "policy_dir_not_configured"

#: 策略不存在 / 损坏 / 未获批准（``policy_status`` 给出更细的状态）。
REASON_POLICY_NOT_INITIALIZED = "policy_not_initialized"

#: 二次校验未通过（防御性；正常情况下 ``read_policy_status`` 已先校验过）。
REASON_POLICY_DOCUMENT_INVALID = "policy_document_invalid"

#: 策略已批准但没有自由卡时长信息。
REASON_MINUTES_MISSING = "free_card_time_options_missing"

#: 策略里有时长信息但取值非法（不是 25 / 55 的严格整数等）。
REASON_MINUTES_INVALID = "free_card_time_options_invalid"

#: 策略已批准但没有活动候选。
REASON_CANDIDATES_MISSING = "free_card_activity_candidates_missing"

#: 活动候选存在但全部非法（超长 / 控制字符 / HTML 注入 / 结构错误）。
REASON_CANDIDATES_INVALID = "free_card_activity_candidates_invalid"

#: 一切正常。
REASON_OK = "approved_policy_read"


class FreeCardPolicyError(Exception):
    """自由卡策略读取失败（fail closed）。

    ``code`` 是稳定的机器可读原因码；``message`` 是给用户看的中文说明。
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


# ---------------------------------------------------------------------------
# 内部纯函数
# ---------------------------------------------------------------------------


def _is_strict_int(value: Any) -> bool:
    """是否为 *严格* 整数（拒绝 ``bool`` / ``float`` / 字符串）。"""
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def _lookup(document: Any, key: str) -> Tuple[Any, bool]:
    """在策略文档里取一个键：顶层优先，其次是嵌套的 ``policy`` 袋。

    返回 ``(值, 是否找到)``。找不到时返回 ``(None, False)``——**绝不**返回
    一个猜测出来的兜底值。
    """
    if not isinstance(document, dict):
        return None, False
    if key in document:
        return document[key], True
    nested = document.get("policy")
    if isinstance(nested, dict) and key in nested:
        return nested[key], True
    return None, False


def _extract_minutes_source(document: Any) -> Optional[Dict[str, Any]]:
    """定位时长策略所在的字典；优先级与 ``free_task`` 完全一致。

    1. 顶层 ``free_task_time_strategy``（必须是对象）；
    2. 顶层 ``free_task_minutes``（任何取值都先交给选项解析器判定合法性）；
    3. 嵌套 ``policy.free_task_time_strategy``（必须是对象）；
    4. 嵌套 ``policy.free_task_minutes``。

    找不到 → 返回 ``None``（调用方必须 fail closed，**绝不** 默认时长）。
    """
    if not isinstance(document, dict):
        return None

    strategy = document.get("free_task_time_strategy")
    if isinstance(strategy, dict):
        return strategy
    if "free_task_minutes" in document:
        return {"free_task_minutes": document["free_task_minutes"]}

    nested = document.get("policy")
    if isinstance(nested, dict):
        nested_strategy = nested.get("free_task_time_strategy")
        if isinstance(nested_strategy, dict):
            return nested_strategy
        if "free_task_minutes" in nested:
            return {"free_task_minutes": nested["free_task_minutes"]}
    return None


def _parse_minutes_options(source: Any) -> Tuple[List[int], str]:
    """严格解析时长选项；返回 ``(options, reason_code)``。

    合法值 **严格** 是整数 ``25`` / ``55``：

    - 布尔、字符串、浮点、零、负数、空列表、其它整数 → 全部 **非法**
      （返回空列表 + ``REASON_MINUTES_INVALID``）；**绝不** 部分接受、
      **绝不** 悄悄丢掉非法项后继续（那会让用户拿到"意外"的时长）；
    - 缺字段 → ``REASON_MINUTES_MISSING``。
    """
    if not isinstance(source, dict):
        return [], REASON_MINUTES_INVALID

    raw = source.get("options")
    if raw is None:
        raw = source.get("free_task_minutes")
    if raw is None:
        return [], REASON_MINUTES_MISSING

    if _is_strict_int(raw):
        candidates: List[Any] = [raw]
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        return [], REASON_MINUTES_INVALID

    if not candidates:
        return [], REASON_MINUTES_INVALID

    options: List[int] = []
    for item in candidates:
        if not _is_strict_int(item):
            return [], REASON_MINUTES_INVALID
        if item not in FREE_CARD_MINUTES_OPTIONS:
            return [], REASON_MINUTES_INVALID
        if item not in options:
            options.append(int(item))
    return options, REASON_OK


def _normalize_activity_candidate(raw: Any) -> Optional[Dict[str, Any]]:
    """把一个候选活动规范化为可用视图；不合法返回 ``None``（该候选被丢弃）。

    合法候选：

    - ``activity``：**必填**，非空纯文本、无控制字符、≤
      :data:`MAX_ACTIVITY_LENGTH` 字（复用 ``free_task.validate_activity``）；
    - ``category``：**可选**的纯文本标签（≤32 字，无控制字符）。它只是
      用户可见的说明，**不** 被解释成受控的"学习 / 娱乐"枚举（那等于替用户
      编造分类）；
    - ``minutes``：**可选**，必须是 25 / 55 的严格整数；
    - ``approved``：显式 ``False`` 表示该候选已被撤下 → 丢弃。

    **防 HTML 注入**：活动文本里出现 ``<`` 或 ``>`` 的候选 **一律丢弃**
    （标签 / 脚本注入的最短路径），因此建议接口不可能吐出可执行标记。
    """
    if isinstance(raw, str):
        raw = {"activity": raw}
    if not isinstance(raw, dict):
        return None

    if raw.get("approved") is False:
        return None

    try:
        activity = free_task.validate_activity(raw.get("activity"))
    except free_task.FreeTaskError:
        return None
    if "<" in activity or ">" in activity:
        return None

    candidate: Dict[str, Any] = {"activity": activity}

    category = raw.get("category")
    if category is not None:
        if not isinstance(category, str) or not category.strip():
            return None
        if len(category) > MAX_CATEGORY_LABEL_LENGTH:
            return None
        if _CONTROL_CHARS.search(category):
            return None
        candidate["category"] = category.strip()

    minutes = raw.get("minutes")
    if minutes is not None:
        if not _is_strict_int(minutes) or minutes not in FREE_CARD_MINUTES_OPTIONS:
            return None
        candidate["minutes"] = int(minutes)

    return candidate


def _normalize_activity_candidates(raw: Any) -> Tuple[List[Dict[str, Any]], str]:
    """规范化候选活动列表；返回 ``(candidates, reason_code)``。"""
    if raw is None:
        return [], REASON_CANDIDATES_MISSING
    if not isinstance(raw, (list, tuple)):
        return [], REASON_CANDIDATES_INVALID

    candidates: List[Dict[str, Any]] = []
    for item in list(raw)[:MAX_ACTIVITY_CANDIDATES]:
        normalized = _normalize_activity_candidate(item)
        if normalized is not None:
            candidates.append(normalized)

    if not candidates:
        return [], REASON_CANDIDATES_INVALID
    return candidates, REASON_OK


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def read_free_card_policy(policy_dir: str) -> Dict[str, Any]:
    """读取 **同一份已批准** 策略里的自由卡时长与活动候选。

    返回结构（永远可 JSON 序列化、绝不包含路径或策略正文）::

        {
          "ok": bool,               # 策略文档本身是否已批准且可读
          "status": "ok" | "unavailable",
          "reason": "<稳定 reason code>",
          "policy_status": str | None,   # agent_policy 的细状态
          "policy_reason": str | None,
          "version": str | None,
          "minutes_options": [25, 55],    # 没有可用时长时为 []
          "minutes_reason": "<稳定 reason code>",
          "activity_candidates": [ {...} ],  # 没有可用候选时为 []
          "candidates_reason": "<稳定 reason code>",
        }

    权威校验复用既有只读函数：先 ``read_policy_status``（确认 latest 存在
    且已获明确批准），再把 **同一份** 文件的文档过一遍
    ``validate_policy_document``。草案里自称的 ``approved_by_user`` 因此
    永远无法单独激活自由卡时长。

    **绝不** 创建目录、**绝不** 写 latest、**绝不** 调用 Publisher。
    """
    result: Dict[str, Any] = {
        "ok": False,
        "status": "unavailable",
        "reason": REASON_POLICY_DIR_MISSING,
        "policy_status": None,
        "policy_reason": None,
        "version": None,
        "minutes_options": [],
        "minutes_reason": REASON_MINUTES_MISSING,
        "activity_candidates": [],
        "candidates_reason": REASON_CANDIDATES_MISSING,
    }

    if not policy_dir or not isinstance(policy_dir, (str, bytes, os.PathLike)):
        return result

    try:
        status = read_policy_status(str(policy_dir))
    except Exception:  # pragma: no cover - 任何意外都 fail closed
        return result

    result["policy_status"] = status.get("status")
    result["policy_reason"] = status.get("reason")
    if not status.get("initialized"):
        result["reason"] = REASON_POLICY_NOT_INITIALIZED
        return result

    try:
        with open(
            os.path.join(str(policy_dir), POLICY_FILENAME), "r", encoding="utf-8"
        ) as handle:
            document = json.load(handle)
    except Exception:  # pragma: no cover - 缺文件 / 坏 JSON / I/O 皆 fail closed
        result["reason"] = REASON_POLICY_NOT_INITIALIZED
        return result

    if not validate_policy_document(document).get("initialized"):
        result["reason"] = REASON_POLICY_DOCUMENT_INVALID
        return result

    result["ok"] = True
    result["status"] = "ok"
    result["reason"] = REASON_OK
    result["version"] = document.get("version")

    source = _extract_minutes_source(document)
    if source is None:
        result["minutes_reason"] = REASON_MINUTES_MISSING
    else:
        options, code = _parse_minutes_options(source)
        result["minutes_options"] = options
        result["minutes_reason"] = code

    raw_candidates, found = _lookup(document, "free_task_activity_candidates")
    if not found:
        result["candidates_reason"] = REASON_CANDIDATES_MISSING
    else:
        candidates, code = _normalize_activity_candidates(raw_candidates)
        result["activity_candidates"] = candidates
        result["candidates_reason"] = code

    return result


def select_free_card_minutes(
    policy: Dict[str, Any],
    rng: Optional[Any] = None,
) -> Optional[int]:
    """从已批准策略里抽出本次发行的自由卡时长。

    - ``policy`` 是 :func:`read_free_card_policy` 的返回值；
    - 没有合法时长 → 返回 ``None``（**绝不** 回落 25 / 30 / 55，**绝不**
      回落 ``tasks.estimated_time``）；
    - 只有一个合法值 → 直接返回它（不消耗随机数）；
    - 两个合法值 → 通过领域模块 ``free_task.select_free_task_minutes``
      **等概率** 抽取（随机源可注入，便于确定性测试）。

    ``rng`` 只需提供 ``.random() -> float``；缺省使用全新的
    ``random.Random()`` 实例（不污染全局随机状态）。
    """
    if not isinstance(policy, dict):
        return None
    options = list(policy.get("minutes_options") or [])
    if not options:
        return None

    random_source = rng if rng is not None else random.Random()
    try:
        minutes = free_task.select_free_task_minutes(
            {"free_task_time_strategy": {"options": options}}, random_source
        )
    except free_task.FreeTaskError as exc:
        raise FreeCardPolicyError(exc.code, exc.message) from exc

    if minutes not in FREE_CARD_MINUTES_OPTIONS:
        raise FreeCardPolicyError(
            REASON_MINUTES_INVALID, "自由卡时长只能是 25 或 55 分钟"
        )
    return int(minutes)


def suggest_free_card_activity(
    policy: Dict[str, Any],
    rng: Optional[Any] = None,
) -> Dict[str, Any]:
    """"帮我选"：从 **已批准** 候选池里取出 **一个** 具体建议。

    没有合法候选 → 抛 :class:`FreeCardPolicyError`（``code`` 为
    ``free_card_activity_candidates_missing`` / ``..._invalid``），
    **绝不** 返回内置想象的活动、**绝不** 返回占位建议。
    """
    if not isinstance(policy, dict):
        raise FreeCardPolicyError(
            REASON_CANDIDATES_MISSING, "没有可用的已批准候选活动"
        )
    candidates = list(policy.get("activity_candidates") or [])
    if not candidates:
        raise FreeCardPolicyError(
            REASON_CANDIDATES_MISSING, "没有可用的已批准候选活动"
        )

    random_source = rng if rng is not None else random.Random()
    draw = random_source.random()
    if isinstance(draw, bool) or not isinstance(draw, (int, float)):
        raise FreeCardPolicyError(
            "random_source_invalid", "随机源必须返回 0..1 之间的数值"
        )
    index = int(draw * len(candidates))
    if index < 0:
        index = 0
    elif index >= len(candidates):
        index = len(candidates) - 1

    return {
        "suggestion": dict(candidates[index]),
        "candidate_count": len(candidates),
    }


__all__ = [
    "FREE_CARD_MINUTES_OPTIONS",
    "MAX_ACTIVITY_CANDIDATES",
    "MAX_ACTIVITY_LENGTH",
    "MAX_CATEGORY_LABEL_LENGTH",
    "REASON_CANDIDATES_INVALID",
    "REASON_CANDIDATES_MISSING",
    "REASON_MINUTES_INVALID",
    "REASON_MINUTES_MISSING",
    "REASON_OK",
    "REASON_POLICY_DIR_MISSING",
    "REASON_POLICY_DOCUMENT_INVALID",
    "REASON_POLICY_NOT_INITIALIZED",
    "FreeCardPolicyError",
    "read_free_card_policy",
    "select_free_card_minutes",
    "suggest_free_card_activity",
]
