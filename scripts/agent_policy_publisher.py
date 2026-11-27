"""scripts.agent_policy_publisher - 受控的 Agent 策略发布器 (Publisher)。

定位
----
这是 **控制端** 在 *取得用户明确同意之后* 使用的独立受控发布工具。
它 **不是** 普通 Cursor Worker 的写入通道，也不是一个能自我批准的 Agent：
写入授权永远来自 *外部*（Controller 对真实用户对话的核对结果），
本脚本只能验证这份授权材料的 **结构完整性**，无法验证人类身份。

信任边界 (TRUST BOUNDARY) — 必须与 Handoff 一致
------------------------------------------------
- 本脚本 **不** 与 ChatGPT / 用户对话交互，**不** 能判定 "说话的人是不是
  人类用户"。它信任调用方（Controller）已经完成了对真实对话的核对。
- 批准证据 (``approval_evidence``) 由 Controller 核对真实对话后提供：
  批准原文 (``approval_text``)、批准人 (``approved_by``)、会话标识
  (``session_id``)、批准时间 (``approved_at``)。
- 提案草案里自称的 ``approved_by_user`` / ``approved_at`` 一律 **被忽略**，
  绝不可用于取得发布授权（见 ``_IGNORED_DRAFT_APPROVAL_FIELDS``）。
- 缺少任一授权要素 → **fail closed**：不产生 ``latest.json``、不产生
  历史版本、不产生回执。

数据模型
--------
策略根目录（由调用方 **显式** 给出，脚本没有任何缺省值）::

    <policy_dir>/latest.json                # 程序唯一读取的当前策略
    <policy_dir>/history/<seq>-<ver>-<sha12>.json   # 不可变历史
    <policy_dir>/receipts/<seq>-<ver>.json  # 发布回执
    <policy_dir>/rollbacks/<seq>-<ver>.json # 回滚记录
    <policy_dir>/.publish.lock              # 独占锁（短生命周期）

提案 JSON（纯数据，Agent 生成，**无执行语义**）::

    {
      "schema_version": 1,
      "version": "2026-10-22.1",
      "effect_summary": "面向用户的可感知效果说明（必须有，机器不得编造）",
      "weights": {"focus": 0.6, "rest": 0.4},   # 可选，取值区间 [0, 1]
      "policy": {"free_task_minutes": 25}       # 可选，额外业务字段
    }

发布出的 ``latest.json`` 必须能被 ``server.services.agent_policy``
的 ``read_policy_status`` 判为 ``initialized=True``：严格的整数
``schema_version=1``、纯文本 ``version``、显式 ``approved_by_user``、
带时区的 ISO ``approved_at``。

安全约束
--------
- **绝不** 默认指向任何真实数据根；每个 API 都必须显式传入 ``policy_dir``，
  且必须是绝对路径。
- **绝不** 隐式创建策略根：目录不存在时默认拒绝（需显式
  ``create_policy_dir=True``），避免 "生产根不存在却被顺手建出来"。
- 拒绝危险目标（位于 ``src/notes`` 之下、指向 ``config/config.json`` /
  ``task_publisher.db`` 等真实数据文件、指向已存在的文件而非目录）。
- 写入顺序：不可变历史 → 原子替换 ``latest.json``（``os.replace``）→ 回执。
  任何失败都不会让既有 ``latest.json`` 变成半截 JSON。
- 绝不删除历史；同一提案重复发布要么幂等返回、要么明确拒绝。
- 仅使用标准库，无第三方依赖。

命令行接口（最小）
------------------
::

    python scripts/agent_policy_publisher.py prepare \\
        --proposal <proposal.json> --policy-dir <abs dir>
    python scripts/agent_policy_publisher.py publish \\
        --proposal <proposal.json> --policy-dir <abs dir> \\
        --proposal-digest <sha256> \\
        --approval-evidence <approval.json> \\
        --authorize --authorization-note "<操作授权说明>"
    python scripts/agent_policy_publisher.py rollback \\
        --policy-dir <abs dir> --version <version> \\
        --approval-evidence <approval.json> \\
        --authorize --authorization-note "<操作授权说明>"

退出码：0 成功，2 fail-closed（拒绝），其它非零表示意外错误。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import errno
import hashlib
import json
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

# --- 允许以脚本方式直接运行（``python scripts/agent_policy_publisher.py``） ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.services import agent_policy  # noqa: E402


#: 提案 / 已发布策略必须声明的 schema 版本（严格整数）。
POLICY_SCHEMA_VERSION = agent_policy.POLICY_SCHEMA_VERSION

#: 当前策略文件名（唯一被程序读取的文件）。
POLICY_FILENAME = agent_policy.POLICY_FILENAME

#: 不可变历史目录名。
HISTORY_DIRNAME = "history"

#: 发布回执目录名。
RECEIPTS_DIRNAME = "receipts"

#: 回滚记录目录名。
ROLLBACKS_DIRNAME = "rollbacks"

#: 独占锁文件名。
LOCK_FILENAME = ".publish.lock"

#: 提案里自称批准的字段——一律忽略，绝不用于取得发布授权。
_IGNORED_DRAFT_APPROVAL_FIELDS = ("approved_by_user", "approved_at", "approval")

#: 历史文件名形态：``<seq>-<version>-<digest12>.json``。
_HISTORY_NAME_RE = re.compile(r"^(\d{6})-(.+)-([0-9a-f]{12})\.json$")

#: **Publisher 托管字段**（LT_BOOTSTRAP_PUBLISHER_METADATA_QA_20261022_E）。
#:
#: 这些字段由 Publisher 自己从 *外部批准证据* 与发布时刻生成，代表
#: 身份（schema/批准）、版本、审计摘要与运行期元数据。Agent 提案的
#: ``policy`` 扩展字段 **绝不** 允许触碰它们：命中即 fail closed
#: （而不是静默忽略），否则一份"纯数据"提案就能改写已被批准的可信
#: 元数据——这正是 D 轮独立审计复现出的可利用缺陷。
#:
#: 比较方式：``key.strip().lower()``，因此大小写 / 首尾空白的变体同样
#: 被拒绝（避免出现语义重复字段）。
PUBLISHER_RESERVED_FIELDS = (
    # 身份与版本
    "schema_version",
    "version",
    # 批准（只能来自外部批准证据）
    "approved_by_user",
    "approved_at",
    "approval",
    "approval_evidence",
    "authorization_note",
    # 审计摘要与效果说明
    "effect_summary",
    "proposal_sha256",
    "published_policy_sha256",
    "previous_policy_sha256",
    # 业务参数（必须走顶层 ``weights``）
    "weights",
    # 发布运行期元数据与历史/回执结构
    "published_at",
    "trust_boundary",
    "entry_type",
    "sequence",
    "previous_version",
    "new_version",
    "history_file",
    "latest_file",
    "policy_document",
    "entry_file",
)

#: 保留字段的归一化集合（用于 O(1) 判定）。
PUBLISHER_RESERVED_FIELD_SET = frozenset(PUBLISHER_RESERVED_FIELDS)

#: 权重取值区间。
MIN_WEIGHT = 0.0
MAX_WEIGHT = 1.0

#: effect_summary 的最小长度（防止空洞占位）。
MIN_EFFECT_SUMMARY_LENGTH = 8

#: 自由文本长度上限。
MAX_EFFECT_SUMMARY_LENGTH = 4000

#: 授权备注的最小长度。
MIN_AUTHORIZATION_NOTE_LENGTH = 4

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

#: 目标路径中禁止出现的危险片段（相对真实用户数据红线）。
#: 比较基于 realpath 解析后的路径段，因此 symlink / junction 绕过同样被覆盖。
_DANGEROUS_SEGMENTS = (
    ("src", "notes"),
    # ``config`` 目录整体受保护（``config/config.json`` 含密钥与路径）。
    ("config",),
)

#: 禁止直接写入的真实数据文件基名。
_DANGEROUS_BASENAMES = (
    "task_publisher.db",
    "task_publisher.db-wal",
    "task_publisher.db-shm",
    "config.json",
)


class PublisherError(Exception):
    """发布器的 fail-closed 错误。

    ``code`` 是稳定的机器可读原因码；``detail`` 是给人看的说明。
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """当前 UTC 时间（带时区的 ISO-8601，秒精度）。"""
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _canonical_bytes(obj: Any) -> bytes:
    """稳定序列化：排序键、紧凑分隔符、保留非 ASCII 原文。"""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_plain_text(value: Any, *, min_len: int = 1, max_len: int = 4000) -> bool:
    if not isinstance(value, str):
        return False
    if len(value.strip()) < min_len:
        return False
    if len(value) > max_len:
        return False
    return not _CONTROL_CHARS.search(value)


def _version_key(version: str) -> Tuple[Any, ...]:
    """把版本号切成可比较的元组。

    ``"2026-10-22.10"`` 必须大于 ``"2026-10-22.2"``，因此数字段按整数比较。
    """
    parts = re.split(r"(\d+)", version)
    key: List[Any] = []
    for part in parts:
        if part == "":
            continue
        if part.isdigit():
            key.append((0, int(part), ""))
        else:
            key.append((1, 0, part))
    return tuple(key)


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------------------------------------------------------------------
# 目标目录安全检查
# ---------------------------------------------------------------------------

def _segments(path: str) -> List[str]:
    """把路径切成小写段（跨 ``/`` 与 ``\\``）。"""
    return [p.lower() for p in re.split(r"[\\/]+", path) if p]


def _contains_segment_run(parts: List[str], run: Tuple[str, ...]) -> bool:
    """``parts`` 中是否存在连续片段序列 ``run``（段边界严格匹配）。"""
    width = len(run)
    if width == 0 or len(parts) < width:
        return False
    for idx in range(len(parts) - width + 1):
        if tuple(parts[idx:idx + width]) == run:
            return True
    return False


def _is_reparse_point(path: str) -> bool:
    """Windows：判断 ``path`` 本身是否为 reparse point（junction / symlink）。

    非 Windows 或不支持时返回 False（POSIX 用 ``os.path.islink`` 覆盖）。
    """
    is_junction = getattr(os.path, "isjunction", None)
    if is_junction is None:
        return False
    try:
        return bool(is_junction(path))
    except OSError:
        return False


def _resolve_target_candidates(target: str) -> List[str]:
    """列出目标自身与所有现存父路径的 realpath 解析结果。

    只做 *解析*，不创建、不修改、不递归扫描任何目录。父路径解析用于
    抓取 "父目录是 junction、末段看起来无害" 这一类绕过。
    """
    candidates: List[str] = []
    current = target
    while True:
        candidates.append(os.path.realpath(current))
        parent = os.path.dirname(current)
        if not parent or parent == current:
            break
        current = parent
    return candidates


def _assert_safe_target(policy_dir: str) -> str:
    """校验发布目标目录；返回规范化后的绝对路径。

    拒绝：
    - 空值 / 相对路径（避免依赖当前工作目录的隐式解析）
    - 文本形式位于 ``src/notes`` 之下或 ``config`` 之下
    - ``realpath`` **解析后**落在上述受保护目录之下（symlink / junction /
      reparse point 绕过）
    - 路径自身是 symlink / junction（潜在重解析点）
    - 指向真实数据文件（``config/config.json`` / ``task_publisher.db*``）
    - 已存在但不是目录
    """
    if not policy_dir or not str(policy_dir).strip():
        raise PublisherError("target_required", "必须显式提供目标策略目录")
    raw = str(policy_dir)
    if not os.path.isabs(raw):
        raise PublisherError("target_not_absolute", "目标策略目录必须是绝对路径")
    target = os.path.abspath(raw)

    # --- 1) 文本形式检查（保留既有行为） --------------------------------
    _assert_path_not_protected(target)

    if os.path.exists(target) and not os.path.isdir(target):
        raise PublisherError("target_not_a_directory", "目标已存在但不是目录")

    # --- 2) 自身是否为潜在重解析点 --------------------------------------
    # 解析结果与目标不一致同样说明存在链接跳转。
    if os.path.islink(target) or _is_reparse_point(target):
        raise PublisherError(
            "target_is_reparse_point",
            "目标路径本身是 symlink / junction，拒绝潜在重解析点",
        )

    # --- 3) 解析后检查（防 symlink / junction 绕过） --------------------
    # 注意：绝不在此创建、修改或递归遍历任何真实目录。
    for resolved in _resolve_target_candidates(target):
        if os.path.normcase(resolved) != os.path.normcase(target):
            resolved_parts = _segments(resolved)
            for run in _PROTECTED_REALPATH_SEGMENTS:
                if _contains_segment_run(resolved_parts, run):
                    raise PublisherError(
                        "target_resolves_to_protected_path",
                        "目标解析后落入受保护的用户数据目录（symlink / junction）",
                    )
            basename = resolved_parts[-1] if resolved_parts else ""
            if basename in _DANGEROUS_BASENAMES:
                raise PublisherError(
                    "target_resolves_to_protected_path",
                    "目标解析后指向受保护的运行期数据文件（symlink / junction）",
                )
    return target


def _assert_path_not_protected(target: str) -> None:
    """对 *文本形式* 的路径做红线段 / 受保护基名检查。"""
    parts = _segments(target)
    for run in _DANGEROUS_SEGMENTS:
        if _contains_segment_run(parts, run):
            raise PublisherError(
                "target_is_protected_path",
                "目标位于受保护的用户数据目录之下",
            )
    basename = parts[-1] if parts else ""
    if basename in _DANGEROUS_BASENAMES:
        raise PublisherError(
            "target_is_protected_path",
            "目标指向受保护的运行期数据文件",
        )


#: 解析后（realpath）额外禁止的片段序列。
#:
#: 刻意 **不** 包含 ``("data",)``：正式策略根
#: ``<project>/data/agent-policy`` 本身就位于 ``data`` 之下，把它列为禁段
#: 会误杀合法的生产目标。``data`` 下的真实数据文件由
#: ``_DANGEROUS_BASENAMES``（``task_publisher.db*``）单独守护。
_PROTECTED_REALPATH_SEGMENTS: Tuple[Tuple[str, ...], ...] = (
    ("src", "notes"),
    ("config",),
)


# ---------------------------------------------------------------------------
# 提案校验
# ---------------------------------------------------------------------------

def load_proposal(path: str) -> Dict[str, Any]:
    """读取并解析提案 JSON 文件（只读，不写任何东西）。"""
    if not path:
        raise PublisherError("proposal_required", "必须提供提案文件路径")
    if not os.path.isfile(path):
        raise PublisherError("proposal_not_found", "提案文件不存在")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise PublisherError("proposal_unreadable", "提案文件无法以 UTF-8 读取") from exc
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise PublisherError("proposal_invalid_json", "提案文件不是合法 JSON") from exc
    if not isinstance(doc, dict):
        raise PublisherError("proposal_not_object", "提案根必须是 JSON 对象")
    return doc


def proposal_digest(proposal: Dict[str, Any]) -> str:
    """提案指纹（SHA-256，结构化规范化后计算）。

    与文件排版（空白 / 换行）无关，但与任何语义变化有关。
    """
    if not isinstance(proposal, dict):
        raise PublisherError("proposal_not_object", "提案根必须是 JSON 对象")
    return _sha256_bytes(_canonical_bytes(proposal))


def _validate_weights(weights: Any) -> Dict[str, float]:
    """校验可选权重表：键为纯文本，值为 [0, 1] 内的有限数字。"""
    if weights is None:
        return {}
    if not isinstance(weights, dict):
        raise PublisherError("invalid_weights", "weights 必须是对象")
    result: Dict[str, float] = {}
    for key, value in weights.items():
        if not isinstance(key, str) or not _is_plain_text(key, min_len=1, max_len=64):
            raise PublisherError("invalid_weights", "weights 的键必须是纯文本")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PublisherError("invalid_weights", "weights 的值必须是数字")
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise PublisherError("invalid_weights", "weights 的值必须是有限数字")
        if number < MIN_WEIGHT or number > MAX_WEIGHT:
            raise PublisherError(
                "invalid_weights",
                "weights 的值必须落在 [0, 1] 区间",
            )
        result[key] = number
    return result


def _reserved_field_hits(policy: Any) -> set:
    """返回 ``policy`` 中命中 Publisher 托管字段的键集合（归一化后比较）。

    归一化：``strip()`` + ``lower()``，因此 ``"Version"``、``" version "``
    这类变体同样视为冲突。空集合表示干净。
    """
    hits = set()
    if not isinstance(policy, dict):
        return hits
    for key in policy:
        if not isinstance(key, str):
            continue
        if key.strip().lower() in PUBLISHER_RESERVED_FIELD_SET:
            hits.add(key)
    return hits


def _assert_no_reserved_fields(policy: Any) -> None:
    """合并阶段的第二道闸门（与 ``validate_proposal`` 的第一道互不依赖）。

    ``validate_proposal`` 已经在预览期拒绝保留字段；这里是 *写入路径*
    上的独立复查，保证即便校验层将来被改动，写入受保护元数据的路径
    依然 fail closed。
    """
    hits = _reserved_field_hits(policy)
    if hits:
        raise PublisherError(
            "policy_reserved_field_conflict",
            "提案 policy 试图覆盖 Publisher 托管字段: "
            + ", ".join(sorted(hits)),
        )


def validate_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """校验提案的结构 / 版本 / 权重合法性。

    返回规范化后的提案视图；非法即抛 ``PublisherError``（fail closed）。
    """
    if not isinstance(proposal, dict):
        raise PublisherError("proposal_not_object", "提案根必须是 JSON 对象")

    if "schema_version" not in proposal:
        raise PublisherError("invalid_schema_version", "提案缺少 schema_version")
    schema_version = proposal.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise PublisherError("invalid_schema_version", "schema_version 必须是严格整数")
    if schema_version != POLICY_SCHEMA_VERSION:
        raise PublisherError("invalid_schema_version", "schema_version 不受支持")

    version = proposal.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PublisherError("invalid_version", "version 必须是非空字符串")
    if len(version.strip()) > agent_policy.MAX_VERSION_LENGTH:
        raise PublisherError("invalid_version", "version 过长")
    if _CONTROL_CHARS.search(version):
        raise PublisherError("invalid_version", "version 含控制字符")

    effect_summary = proposal.get("effect_summary")
    if not isinstance(effect_summary, str):
        raise PublisherError("missing_effect_summary", "提案缺少 effect_summary")
    if len(effect_summary.strip()) < MIN_EFFECT_SUMMARY_LENGTH:
        raise PublisherError(
            "missing_effect_summary", "effect_summary 太短，无法说明可感知效果"
        )
    if len(effect_summary) > MAX_EFFECT_SUMMARY_LENGTH:
        raise PublisherError("invalid_effect_summary", "effect_summary 过长")
    if _CONTROL_CHARS.sub("", effect_summary) != effect_summary:
        raise PublisherError("invalid_effect_summary", "effect_summary 含控制字符")

    weights = _validate_weights(proposal.get("weights"))

    policy = proposal.get("policy")
    if policy is None:
        policy = {}
    if not isinstance(policy, dict):
        raise PublisherError("invalid_policy_payload", "policy 必须是对象")
    reserved_hits = _reserved_field_hits(policy)
    if reserved_hits:
        # 第一道闸门（预览期就 fail closed，绝不静默忽略）
        raise PublisherError(
            "policy_reserved_field_conflict",
            "提案 policy 试图覆盖 Publisher 托管字段: "
            + ", ".join(sorted(reserved_hits)),
        )
    for key in policy:
        if not isinstance(key, str) or not _is_plain_text(key, min_len=1, max_len=64):
            raise PublisherError("invalid_policy_payload", "policy 的键必须是纯文本")

    ignored = [
        field for field in _IGNORED_DRAFT_APPROVAL_FIELDS if field in proposal
    ]

    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "version": version.strip(),
        "effect_summary": effect_summary,
        "weights": weights,
        "policy": policy,
        "ignored_draft_approval_fields": ignored,
    }


# ---------------------------------------------------------------------------
# 当前已发布策略（只读）
# ---------------------------------------------------------------------------

def _read_latest_raw(policy_dir: str) -> Optional[bytes]:
    path = os.path.join(policy_dir, POLICY_FILENAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _current_latest_info(policy_dir: str) -> Dict[str, Any]:
    """当前已发布策略的安全摘要（不含策略正文）。"""
    status = agent_policy.read_policy_status(policy_dir)
    raw = _read_latest_raw(policy_dir)
    info: Dict[str, Any] = {
        "initialized": bool(status.get("initialized")),
        "version": status.get("version"),
        "status": status.get("status"),
        "reason": status.get("reason"),
        "policy_sha256": _sha256_bytes(raw) if raw is not None else None,
    }
    return info


def _list_history_entries(policy_dir: str) -> List[Dict[str, Any]]:
    """读取全部不可变历史条目（按 sequence 排序）。

    只读；损坏的条目被跳过（不删除、不修复）。
    """
    entries = [item["doc"] for item in _scan_history_files(policy_dir) if item["doc"] is not None]
    entries.sort(key=lambda item: int(item.get("sequence") or 0))
    return entries


def _scan_files(directory: str) -> List[Dict[str, Any]]:
    """严格扫描一个目录下的 ``*.json`` 文件（只读）。

    每个条目形如 ``{"name", "path", "doc", "error"}``：

    - ``doc``：解析成功且为 JSON 对象时的内容；
    - ``error``：解析失败的原因（坏 JSON / 非对象 / 不可读）——**不再静默跳过**，
      恢复判定必须看到它们，否则一份坏文件就足以把同指纹碰撞藏起来。
    """
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(directory):
        return items
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        item: Dict[str, Any] = {"name": name, "path": path, "doc": None, "error": None}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            item["error"] = type(exc).__name__
        else:
            if isinstance(doc, dict):
                doc.setdefault("entry_file", name)
                item["doc"] = doc
            else:
                item["error"] = "not_object"
        items.append(item)
    return items


def _scan_history_files(policy_dir: str) -> List[Dict[str, Any]]:
    """严格扫描不可变历史目录（只读）。"""
    return _scan_files(os.path.join(policy_dir, HISTORY_DIRNAME))


def _scan_receipt_files(policy_dir: str) -> List[Dict[str, Any]]:
    """严格扫描回执目录（只读）。"""
    return _scan_files(os.path.join(policy_dir, RECEIPTS_DIRNAME))


def _scan_rollback_files(policy_dir: str) -> List[Dict[str, Any]]:
    """严格扫描回滚记录目录（只读）。"""
    return _scan_files(os.path.join(policy_dir, ROLLBACKS_DIRNAME))


def _rolled_back_past(
    policy_dir: str,
    entries: List[Dict[str, Any]],
    target_entry: Dict[str, Any],
    current_sha: Optional[str],
) -> bool:
    """判断"当前 latest 是否是 *回滚* 到本 entry 之前某个版本"的结果。

    场景：提案 v2 曾经 **成功发布**，之后被受控回滚到 v1。此时再次
    提交 v2 的提案 —— 它 **确实发布过**，因此必须走受控回滚路径，
    而 **不是** 崩溃恢复路径（否则会把一次回滚悄悄变成一次重新发布）。

    判据：存在一条回滚记录，它恢复的是 *本 entry 之前* 的某个历史条目，
    且它写出的 ``published_policy_sha256`` 正好等于当前 latest 的指纹。
    """
    if current_sha is None:
        return False
    own_sequence = target_entry.get("sequence")
    if not isinstance(own_sequence, int):
        return False
    earlier_files = {
        item.get("entry_file")
        for item in entries
        if isinstance(item.get("sequence"), int) and item["sequence"] < own_sequence
    }
    for item in _scan_rollback_files(policy_dir):
        doc = item["doc"]
        if not isinstance(doc, dict):
            continue
        if doc.get("published_policy_sha256") != current_sha:
            continue
        restored_from = doc.get("restored_from_history")
        if restored_from in earlier_files:
            return True
    return False


def _entry_was_rolled_back(
    policy_dir: str,
    entries: List[Dict[str, Any]],
    target_entry: Dict[str, Any],
) -> bool:
    """判断"本 entry 是否曾经真正生效、之后又被受控回滚"。

    判据：存在一条回滚记录，其 ``previous_version`` 正是本 entry 的
    ``new_version``（即"从这个版本回滚走"），且它恢复到本 entry **之前**
    的某个历史条目。

    这一判定 **必须** 在恢复模式判定之前完成：否则"v2 发布过 → 回滚到
    v1 → 再提交 v2"会被误判为"latest 仍等于 previous 指纹"，从而把一次
    受控回滚悄悄变成一次未经再次批准的重新发布。
    """
    own_sequence = target_entry.get("sequence")
    if not isinstance(own_sequence, int):
        return False
    earlier_files = {
        item.get("entry_file")
        for item in entries
        if isinstance(item.get("sequence"), int) and item["sequence"] < own_sequence
    }
    for item in _scan_rollback_files(policy_dir):
        doc = item["doc"]
        if not isinstance(doc, dict):
            continue
        if doc.get("previous_version") != target_entry.get("new_version"):
            continue
        if doc.get("restored_from_history") in earlier_files:
            return True
    return False


def _history_name_digest(name: str) -> Optional[str]:
    """从历史文件名中取出提案指纹前缀（12 位）。

    文件名形态固定为 ``<seq>-<version>-<digest12>.json``；解析不出来
    返回 ``None``（调用方按"无法核对"处理）。
    """
    match = _HISTORY_NAME_RE.match(name)
    if not match:
        return None
    return match.group(3)


def _next_sequence(policy_dir: str, dirname: str) -> int:
    directory = os.path.join(policy_dir, dirname)
    highest = 0
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            match = re.match(r"^(\d{6})-", name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


# ---------------------------------------------------------------------------
# 预览（prepare）：无任何副作用
# ---------------------------------------------------------------------------

def prepare(proposal: Dict[str, Any], policy_dir: Optional[str] = None) -> Dict[str, Any]:
    """预览一次策略变更。

    **绝不写入任何东西**（不建目录、不写文件、不改已有 latest）。

    返回：
        ``ok``, ``proposal_sha256``, ``proposal``(规范化视图),
        ``current``（当前已发布策略摘要）, ``effect_summary``,
        ``expected_change``（预期调整的机器可读摘要）,
        ``warnings``, ``authorized``（恒为 False）, ``trust_boundary``。
    """
    warnings: List[str] = []
    view = validate_proposal(proposal)
    digest = proposal_digest(proposal)

    current: Dict[str, Any] = {
        "initialized": False,
        "version": None,
        "status": agent_policy.STATUS_MISSING,
        "reason": "policy_dir_not_configured",
        "policy_sha256": None,
    }
    if policy_dir:
        try:
            target = _assert_safe_target(policy_dir)
        except PublisherError:
            target = None
        if target:
            current = _current_latest_info(target)
            if not current.get("initialized"):
                warnings.append("current_policy_missing_or_unreadable")
    else:
        warnings.append("no_policy_dir_given")

    if view["ignored_draft_approval_fields"]:
        warnings.append(
            "draft_approval_fields_ignored:"
            + ",".join(view["ignored_draft_approval_fields"])
        )

    expected_change: Dict[str, Any] = {
        "proposed_version": view["version"],
        "previous_version": current.get("version"),
        "weights": view["weights"],
        "policy_fields": sorted(view["policy"].keys()),
    }

    return {
        "ok": True,
        "operation": "prepare",
        "proposal_sha256": digest,
        "proposal": view,
        "current": current,
        "effect_summary": view["effect_summary"],
        "expected_change": expected_change,
        "warnings": warnings,
        "authorized": False,
        "trust_boundary": TRUST_BOUNDARY_NOTE,
    }


# ---------------------------------------------------------------------------
# 授权材料
# ---------------------------------------------------------------------------

TRUST_BOUNDARY_NOTE = (
    "本工具无法验证 ChatGPT/人类身份；批准证据由 Controller 对真实用户对话核对后提供。"
    "提案草案自称的批准字段一律被忽略。"
)


def _validate_approval_evidence(evidence: Any) -> Dict[str, str]:
    """校验外部批准证据的结构（不验证人类身份）。"""
    if not isinstance(evidence, dict):
        raise PublisherError("approval_evidence_missing", "缺少用户同意证据")
    required = ("approved_by", "approval_text", "session_id", "approved_at")
    for field in required:
        value = evidence.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PublisherError(
                "approval_evidence_incomplete", f"批准证据缺少字段: {field}"
            )
        if _CONTROL_CHARS.search(value):
            raise PublisherError(
                "approval_evidence_invalid", f"批准证据字段含控制字符: {field}"
            )
    approved_at = evidence["approved_at"].strip()
    parsed = _parse_iso_tz(approved_at)
    if parsed is None:
        raise PublisherError(
            "approval_evidence_invalid", "approved_at 必须是带时区的 ISO-8601 时间"
        )
    if parsed > _utc_now() + agent_policy.APPROVED_AT_FUTURE_TOLERANCE:
        raise PublisherError(
            "approval_evidence_invalid", "approved_at 明显晚于当前时间"
        )
    return {
        "approved_by": evidence["approved_by"].strip(),
        "approval_text": evidence["approval_text"].strip(),
        "session_id": evidence["session_id"].strip(),
        "approved_at": approved_at,
    }


def _parse_iso_tz(text: str) -> Optional[_dt.datetime]:
    """解析带时区的 ISO-8601 时间（失败返回 None）。"""
    candidate = text.strip()
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(candidate)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _check_authorization(authorize: bool, authorization_note: str) -> str:
    """校验显式操作授权参数。"""
    if not authorize:
        raise PublisherError("authorization_missing", "缺少显式操作授权")
    if not isinstance(authorization_note, str):
        raise PublisherError("authorization_note_missing", "缺少操作授权说明")
    if len(authorization_note.strip()) < MIN_AUTHORIZATION_NOTE_LENGTH:
        raise PublisherError("authorization_note_missing", "操作授权说明过短")
    if _CONTROL_CHARS.search(authorization_note):
        raise PublisherError("authorization_note_invalid", "操作授权说明含控制字符")
    return authorization_note.strip()


# ---------------------------------------------------------------------------
# 写入原语（原子 + 独占）
# ---------------------------------------------------------------------------

class _PublishLock:
    """基于 ``O_CREAT|O_EXCL`` 的独占锁（短生命周期）。

    **崩溃残留锁的处理方案**（LT_BOOTSTRAP_PUBLISHER_CRASH_RECOVERY_20261022_F）::

        进程在持锁期间崩溃 → ``.publish.lock`` 残留 → 后续所有发布都被
        ``publish_locked`` 挡住。本实现 **刻意不提供任何自动解锁**：
        锁文件的存在本身无法区分"另一个进程正在发布"与"上一次进程崩了"，
        无条件解除锁会引入并发写坏 latest 的风险。

        处置流程（**必须由 Controller 人工核对**）：

        1. ``lock_status(policy_dir)`` 返回锁文件的年龄、大小与 mtime；
        2. Controller 确认没有 Publisher 进程存活（进程列表 / PID 核对）；
        3. Controller 人工删除该锁文件（**out of band**，不经本工具）；
        4. 之后再次调用 ``publish()``：它会走常规的崩溃恢复判定
           （孤儿历史 / 缺失回执），把上次中断的状态安全地收敛。

        因此本模块 **永不** 自动删除或覆盖他人持有的锁。
    """

    def __init__(self, policy_dir: str) -> None:
        self._path = os.path.join(policy_dir, LOCK_FILENAME)
        self._fd: Optional[int] = None

    def __enter__(self) -> "_PublishLock":
        try:
            self._fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise PublisherError(
                    "publish_locked",
                    "另一个发布正在进行；若确认是崩溃残留的锁，"
                    "请由 Controller 人工核对后手动删除该锁文件"
                    "（本工具不会自动解锁）: "
                    + _describe_lock(self._path),
                ) from exc
            raise PublisherError("lock_unavailable", "无法获取发布锁") from exc
        try:
            os.write(self._fd, _now_iso().encode("utf-8"))
        except OSError:
            pass
        return self

    def __exit__(self, *_exc_info) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.unlink(self._path)
        except OSError:
            pass


def _describe_lock(path: str) -> str:
    """描述锁文件的可核对信息（只读，不含任何路径以外的隐私）。"""
    try:
        stat = os.stat(path)
    except OSError:
        return "锁文件不可读"
    age = max(0.0, _dt.datetime.now().timestamp() - stat.st_mtime)
    return f"lock_age_seconds={int(age)} lock_size={stat.st_size}"


def lock_status(policy_dir: str) -> Dict[str, Any]:
    """只读报告发布锁的状态（供 Controller 判断是否需要人工清理）。

    **本函数绝不删除锁文件。** 返回：

    - ``locked``：锁文件是否存在；
    - ``age_seconds``：锁文件年龄（秒）；
    - ``detail``：人类可读说明。
    """
    target = _assert_safe_target(policy_dir)
    path = os.path.join(target, LOCK_FILENAME)
    if not os.path.isfile(path):
        return {
            "locked": False,
            "age_seconds": None,
            "detail": "无发布锁",
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }
    try:
        stat = os.stat(path)
    except OSError:
        return {
            "locked": True,
            "age_seconds": None,
            "detail": "锁文件存在但不可读",
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }
    age = max(0.0, _dt.datetime.now().timestamp() - stat.st_mtime)
    return {
        "locked": True,
        "age_seconds": int(age),
        "detail": (
            "锁文件存在。若确认无 Publisher 进程存活（崩溃残留），"
            "必须由 Controller 人工核对并手动删除；本工具不会自动解锁。"
        ),
        "trust_boundary": TRUST_BOUNDARY_NOTE,
    }


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """同目录临时文件 + ``os.replace`` 原子替换。

    失败时临时文件被清理，既有目标保持原样（绝不半截 JSON）。
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-publish-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        tmp_path = ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _write_json_file(path: str, doc: Dict[str, Any], *, exclusive: bool = False) -> None:
    """写 JSON（UTF-8 / LF，无 BOM）。``exclusive=True`` 表示不得覆盖既有文件。"""
    data = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    payload = data.encode("utf-8")
    if exclusive:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise PublisherError("history_collision", "历史文件已存在，拒绝覆盖") from exc
        return
    _atomic_write_bytes(path, payload)


# ---------------------------------------------------------------------------
# 崩溃恢复（LT_BOOTSTRAP_PUBLISHER_CRASH_RECOVERY_20261022_F）
# ---------------------------------------------------------------------------
#
# 故障模型
# --------
# Publisher 的写入顺序是 **不可变历史 → 原子替换 latest → 回执**。
# 进程在任意两步之间崩溃都会留下"半完成"状态：
#
#   (A) 历史已写、latest 替换失败 → 历史里有一条 **从未生效** 的孤儿
#       entry；既有 latest 依然有效（这是正确的）。但旧实现会把该提案
#       指纹标记为"已发布过"，于是用户 **再次批准同一提案** 会被
#       ``duplicate_proposal`` 永久挡住——即使它从未真正发布。
#   (B) latest 已替换成功、回执写入失败 → 策略已经生效，但没有回执。
#
# 恢复原则（全部 fail closed）
# --------------------------
# - 绝不删除 / 覆盖 / 改写不可变历史，绝不假装事故没有发生；
# - 绝不把一份 **缺失或不一致** 的批准悄悄激活；
# - 只有当 *当前 latest 的字节指纹* 与 entry 记录的
#   ``previous_policy_sha256`` 完全一致（即 latest 未被他人更新）、
#   提案原文与摘要与 entry 完全一致、批准证据与本次 Controller 授权
#   一致、历史链无分叉、策略文档可复算出 entry 记录的
#   ``published_policy_sha256`` 时，才允许原子完成那次未成功的
#   ``latest`` 替换（并补写回执）。
# - 任何无法核对的状态 → 拒绝（fail closed），绝不覆盖当前有效 latest。

#: 恢复时写出的回执类型标记。
RECOVERY_RECEIPT_TYPE = "publish_recovered"


def _canonical_policy_payload(document: Dict[str, Any]) -> bytes:
    """按发布时完全相同的配方序列化策略文档。

    必须与 ``publish()`` 里的 ``payload`` 逐字节一致，否则复算出的
    SHA-256 就无法与历史条目记录的 ``published_policy_sha256`` 对上。
    """
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _strict_history_scan(policy_dir: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """严格扫描不可变历史（只读）。

    返回 ``(entries, broken_names)``：

    - ``entries``：可解析为 JSON 对象的全部历史条目（按 sequence 排序）；
    - ``broken_names``：**无法解析**的文件名列表。恢复判定 *不允许*
      依赖"跳过坏文件"——坏文件足以把同指纹的碰撞藏起来，因此只要
      历史目录里存在坏文件，恢复即 fail closed。
    """
    entries: List[Dict[str, Any]] = []
    broken: List[str] = []
    for item in _scan_history_files(policy_dir):
        if item["doc"] is None:
            broken.append(item["name"])
        else:
            entries.append(item["doc"])
    entries.sort(key=lambda item: int(item.get("sequence") or 0))
    return entries, broken


def _relevant_broken_history(broken_names: List[str], digest: str) -> List[str]:
    """筛出与某个提案指纹 **可能相关** 的坏历史文件名。

    历史文件名形如 ``<seq>-<version>-<digest12>.json``，因此：

    - 文件名里的指纹前缀与本次摘要一致 → 一定相关；
    - 文件名无法解析出指纹前缀（被改名 / 格式异常）→ 无法排除相关性，
      按"相关"处理（fail closed）。

    与本次指纹明确无关的坏文件（例如另一版本号的损坏条目）不阻塞本次
    发布——它不可能隐藏 *本次* 提案的碰撞；那一版的发布/恢复动作会
    自行撞上它并被拒绝。
    """
    relevant: List[str] = []
    for name in broken_names:
        name_digest = _history_name_digest(name)
        if name_digest is None or name_digest == digest[:12]:
            relevant.append(name)
    return relevant


def _find_receipt_for_digest(policy_dir: str, digest: str) -> Optional[Dict[str, Any]]:
    """查找与某提案指纹绑定的既有回执（只读）；没有则返回 ``None``。

    回执目录里存在无法解析的文件时 **fail closed**：坏回执同样可能
    隐藏"其实已经有回执"的事实，从而导致重复补写回执。
    """
    for item in _scan_receipt_files(policy_dir):
        if item["doc"] is None:
            raise PublisherError(
                "recovery_receipt_unreadable",
                f"回执目录存在无法解析的文件，无法核对恢复条件: {item['name']}",
            )
        doc = item["doc"]
        if isinstance(doc, dict) and doc.get("proposal_sha256") == digest:
            return doc
    return None


def _build_receipt(
    entry: Dict[str, Any],
    evidence: Dict[str, str],
    note: str,
    status_after: Dict[str, Any],
    *,
    recovery_action: Optional[str] = None,
) -> Dict[str, Any]:
    """构造回执文档（发布与恢复共用同一套审计字段）。

    恢复时 ``evidence`` 是 **本次** Controller 提供的批准证据；历史
    entry 里的原始证据原样保留在不可变历史中，两份都进回执，便于
    审计"当初批的是什么、这次恢复是谁授权的"。
    """
    receipt: Dict[str, Any] = {
        "receipt_type": "publish",
        "published_at": entry.get("published_at"),
        "previous_version": entry.get("previous_version"),
        "new_version": entry.get("new_version"),
        "proposal_sha256": entry.get("proposal_sha256"),
        "published_policy_sha256": entry.get("published_policy_sha256"),
        "history_file": f"{HISTORY_DIRNAME}/{entry.get('entry_file')}",
        "latest_file": POLICY_FILENAME,
        "approval_evidence": evidence,
        "authorization_note": note,
        "status_after": status_after,
        "trust_boundary": TRUST_BOUNDARY_NOTE,
    }
    if recovery_action:
        receipt["receipt_type"] = RECOVERY_RECEIPT_TYPE
        receipt["recovery_action"] = recovery_action
        receipt["recovered_from_history_entry"] = entry.get("entry_file")
        receipt["recovered_at"] = _now_iso()
        receipt["recovery_authorization_note"] = note
        receipt["recovery_approval_evidence"] = evidence
        receipt["original_approval_evidence"] = entry.get("approval_evidence")
        receipt["original_authorization_note"] = entry.get("authorization_note")
    return receipt


def _write_receipt(target: str, receipt: Dict[str, Any], version: str) -> str:
    """写入回执并返回相对文件名（受目录创建失败保护）。"""
    sequence = _next_sequence(target, RECEIPTS_DIRNAME)
    name = f"{sequence:06d}-{_safe_filename(version)}.json"
    path = os.path.join(target, RECEIPTS_DIRNAME, name)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _write_json_file(path, receipt)
    except (OSError, PublisherError) as exc:
        raise PublisherError(
            "receipt_unwritable", "策略已发布但回执写入失败"
        ) from exc
    return f"{RECEIPTS_DIRNAME}/{name}"


def _verify_recovery_entry(
    entry: Dict[str, Any],
    entries: List[Dict[str, Any]],
    view: Dict[str, Any],
    proposal: Dict[str, Any],
    digest: str,
    evidence: Dict[str, str],
) -> bytes:
    """核对一条历史 entry 是否可用于恢复；返回其策略文档的字节载荷。

    任一不一致 → 抛 ``PublisherError``（fail closed）。
    """
    # 1) entry 自身的结构
    if entry.get("entry_type") != "publish":
        raise PublisherError(
            "recovery_entry_invalid", "历史条目不是发布条目，拒绝恢复"
        )
    if entry.get("new_version") != view["version"]:
        raise PublisherError(
            "recovery_version_mismatch",
            "历史条目的目标版本与本次提案不一致，拒绝恢复",
        )
    stored_proposal = entry.get("proposal")
    if not isinstance(stored_proposal, dict):
        raise PublisherError(
            "recovery_entry_invalid", "历史条目缺少提案原文，无法核对"
        )
    if proposal_digest(stored_proposal) != digest:
        raise PublisherError(
            "recovery_proposal_mismatch",
            "历史条目中的提案原文与本次提案摘要不一致，拒绝恢复",
        )
    if proposal_digest(proposal) != digest:
        raise PublisherError(
            "recovery_proposal_mismatch", "本次提案摘要不一致，拒绝恢复"
        )

    # 2) 批准证据必须与本次 Controller 提供的证据 **逐字一致**：
    #    "谁批的 / 批了什么 / 哪次会话 / 什么时候批的" 全部相同，
    #    才说明恢复的是 *同一份* 已获批准的动作。任何一项不同
    #    → fail closed（绝不把一份"不一样的批准"悄悄激活）。
    stored_evidence = entry.get("approval_evidence")
    if not isinstance(stored_evidence, dict):
        raise PublisherError(
            "recovery_entry_invalid", "历史条目缺少批准证据，无法核对"
        )
    for field in ("approved_by", "approval_text", "session_id", "approved_at"):
        if stored_evidence.get(field) != evidence.get(field):
            raise PublisherError(
                "recovery_approval_mismatch",
                f"历史条目中的批准证据与本次不一致: {field}",
            )

    # 3) 策略文档必须可复算出 entry 记录的 published_policy_sha256
    document = entry.get("policy_document")
    if not isinstance(document, dict):
        raise PublisherError(
            "recovery_entry_invalid", "历史条目缺少策略文档，无法核对"
        )
    validation = agent_policy.validate_policy_document(document)
    if not validation.get("initialized"):
        raise PublisherError(
            "recovery_policy_document_invalid",
            f"历史策略文档未通过校验: {validation.get('status')}",
        )
    if document.get("proposal_sha256") != digest:
        raise PublisherError(
            "recovery_metadata_mismatch",
            "历史策略文档的 proposal_sha256 与历史条目不一致",
        )
    if document.get("version") != entry.get("new_version"):
        raise PublisherError(
            "recovery_metadata_mismatch",
            "历史策略文档的版本与历史条目不一致",
        )
    if document.get("approved_at") != stored_evidence.get("approved_at"):
        raise PublisherError(
            "recovery_metadata_mismatch",
            "历史策略文档的批准时间与历史条目记录的批准证据不一致",
        )
    payload = _canonical_policy_payload(document)
    if _sha256_bytes(payload) != entry.get("published_policy_sha256"):
        raise PublisherError(
            "recovery_history_corrupt",
            "历史条目记录的 published_policy_sha256 与策略文档无法对上",
        )

    # 4) 历史链不得有分叉
    for other in entries:
        if other is entry:
            continue
        if other.get("new_version") == entry.get("new_version"):
            raise PublisherError(
                "recovery_history_forked",
                "不可变历史中存在同版本号的另一条目，链条分叉，拒绝恢复",
            )
        if other.get("published_policy_sha256") == entry.get(
            "published_policy_sha256"
        ):
            raise PublisherError(
                "recovery_history_forked",
                "不可变历史中存在同一 published_policy_sha256 的另一条目，拒绝恢复",
            )
        if other.get("proposal_sha256") == entry.get("proposal_sha256"):
            raise PublisherError(
                "recovery_history_forked",
                "不可变历史中存在同一提案指纹的另一条目，拒绝恢复",
            )
    return payload


def _recover_duplicate_publish(
    target: str,
    view: Dict[str, Any],
    proposal: Dict[str, Any],
    digest: str,
    evidence: Dict[str, str],
    note: str,
) -> Dict[str, Any]:
    """处理"该提案已存在历史 entry"的分支（崩溃恢复入口）。

    三种可能：

    1. latest 已等于 entry 的 ``published_policy_sha256``
       → 崩溃发生在"回执写入"之后/之前：若回执缺失则补齐回执，
         **不重复发布、不覆盖 latest**；
    2. latest 仍等于 entry 的 ``previous_policy_sha256``
       → 崩溃发生在"原子替换 latest"这一步：在核对通过后原子完成
         那次替换并补写回执；
    3. 其它任何状态 → fail closed。
    """
    entries, broken = _strict_history_scan(target)
    relevant_broken = _relevant_broken_history(broken, digest)
    if relevant_broken:
        raise PublisherError(
            "recovery_history_unreadable",
            "不可变历史存在无法解析的文件，无法核对恢复条件: "
            + ", ".join(relevant_broken),
        )

    matches = [
        item
        for item in entries
        if item.get("proposal_sha256") == digest
    ]
    if not matches:
        # 理论上不可达（调用方已确认存在）：保守拒绝。
        raise PublisherError(
            "duplicate_proposal", "该提案已存在于不可变历史中，但无法核对恢复条件"
        )
    if len(matches) > 1:
        raise PublisherError(
            "recovery_history_forked",
            "不可变历史中存在多条同指纹条目，链条分叉，拒绝恢复",
        )

    entry = matches[0]
    payload = _verify_recovery_entry(entry, entries, view, proposal, digest, evidence)

    current = _current_latest_info(target)
    latest_path = os.path.join(target, POLICY_FILENAME)
    latest_exists = os.path.isfile(latest_path)
    current_sha = current.get("policy_sha256")
    published_sha = entry.get("published_policy_sha256")
    previous_sha = entry.get("previous_policy_sha256")

    # --- 前置否决：本 entry 是否曾经真正生效、之后被受控回滚 -----------
    # "v2 发布过 → 回滚到 v1 → 再提交 v2"：此时 latest 恰好等于本
    # entry 记录的 previous 指纹，若不拦截就会把一次 **受控回滚**
    # 悄悄变成一次 **未经再次批准的重新发布**。必须走受控回滚路径。
    if _entry_was_rolled_back(target, entries, entry):
        raise PublisherError(
            "duplicate_proposal",
            "该提案已被发布过并被受控回滚；拒绝跨版本重复发布（请使用受控回滚）",
        )

    # --- 状态判定 ---------------------------------------------------------
    # (1) latest 已经等于该 entry 记录的 published 指纹
    #     → 崩溃发生在 "latest 已替换" 之后（回执可能缺失）。
    if latest_exists and current_sha == published_sha:
        mode = "already_applied"
        if current.get("version") != entry.get("new_version"):
            raise PublisherError(
                "recovery_state_mismatch",
                "latest 的指纹与历史条目一致但版本不一致，状态无法核对",
            )
    # (2) latest 仍然等于该 entry 记录的 previous 指纹（且"有没有 latest"
    #     的事实也一致）→ 崩溃发生在 "原子替换 latest" 这一步。
    elif current_sha == previous_sha and (previous_sha is None) == (not latest_exists):
        mode = "replace_latest"
        if current.get("version") != entry.get("previous_version"):
            raise PublisherError(
                "recovery_state_mismatch",
                "latest 与历史条目记录的上一版本不一致，无法核对恢复条件",
            )
    else:
        # latest 既不等于本 entry 的 published 指纹，也不等于它记录的
        # previous 指纹 → 状态无法核对 → fail closed。
        #
        # 先识别"本 entry 之后又有别的发布落地"（latest 被他人更新），
        # 再识别"本 entry 曾成功发布、之后被受控回滚"（必须走回滚路径，
        # 绝不把一次回滚悄悄变成一次重新发布），最后才是链条断裂。
        own_sequence = entry.get("sequence")
        current_owner = None
        for item in entries:
            if item.get("published_policy_sha256") == current_sha:
                current_owner = item
                break

        if current_owner is not None and isinstance(own_sequence, int) and isinstance(
            current_owner.get("sequence"), int
        ):
            if current_owner["sequence"] > own_sequence:
                raise PublisherError(
                    "recovery_state_mismatch",
                    "该提案之后已有其它发布落地（latest 已被他人更新），拒绝自动恢复",
                )
            # current_owner.sequence < own_sequence：latest 对应的是本
            # entry **之前** 的版本。若链条指纹对不上 → 历史被篡改 /
            # 断链；若这条回滚记录存在 → 说明本 entry 曾经成功发布过，
            # 之后被受控回滚（此时必须走受控回滚，不得"恢复"）。
            if _rolled_back_past(target, entries, entry, current_sha):
                raise PublisherError(
                    "duplicate_proposal",
                    "该提案已被发布过并被受控回滚；拒绝跨版本重复发布（请使用受控回滚）",
                )
            raise PublisherError(
                "recovery_state_mismatch",
                "当前 latest 与历史条目记录的期望状态不一致，无法安全恢复",
            )

        if _rolled_back_past(target, entries, entry, current_sha):
            raise PublisherError(
                "duplicate_proposal",
                "该提案已被发布过并被受控回滚；拒绝跨版本重复发布（请使用受控回滚）",
            )

        published_hashes = {
            item.get("published_policy_sha256") for item in entries
        }
        if current_sha in published_hashes:
            raise PublisherError(
                "duplicate_proposal",
                "该提案已被发布过；拒绝跨版本重复发布（请使用受控回滚）",
            )
        raise PublisherError(
            "recovery_state_mismatch",
            "当前 latest 与历史条目记录的期望状态不一致，无法安全恢复",
        )

    existing_receipt = _find_receipt_for_digest(target, digest)

    if mode == "already_applied":
        if existing_receipt is not None:
            return {
                "ok": True,
                "operation": "publish",
                "outcome": "already_published",
                "proposal_sha256": digest,
                "version": view["version"],
                "history_file": f"{HISTORY_DIRNAME}/{entry.get('entry_file')}",
                "current": current,
                "trust_boundary": TRUST_BOUNDARY_NOTE,
            }
        # latest 已生效但回执缺失 → 补齐回执（绝不重新发布、绝不覆盖 latest）
        status_after = agent_policy.read_policy_status(target)
        receipt = _build_receipt(
            entry,
            evidence,
            note,
            status_after,
            recovery_action="receipt_only",
        )
        receipt_file = _write_receipt(target, receipt, view["version"])
        return {
            "ok": True,
            "operation": "publish",
            "outcome": "already_published",
            "recovery": "receipt_recovered",
            "proposal_sha256": digest,
            "version": view["version"],
            "history_file": f"{HISTORY_DIRNAME}/{entry.get('entry_file')}",
            "receipt_file": receipt_file,
            "current": current,
            "status_after": status_after,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }

    # --- mode == "replace_latest" ----------------------------------------
    if existing_receipt is not None:
        # 有回执却没有生效的 latest → 状态自相矛盾，绝不"修复"。
        raise PublisherError(
            "recovery_state_mismatch",
            "该提案已有回执但 latest 未生效，状态自相矛盾，拒绝自动恢复",
        )

    # 原子完成那次未成功的 latest 替换（写锁保护内）
    _atomic_write_bytes(latest_path, payload)

    status_after = agent_policy.read_policy_status(target)
    if not status_after.get("initialized"):
        raise PublisherError(
            "post_publish_unreadable",
            f"恢复发布后校验失败: {status_after.get('status')}",
        )
    if _sha256_bytes(_read_latest_raw(target) or b"") != published_sha:
        raise PublisherError(
            "post_publish_unreadable", "恢复发布后 latest 指纹与历史条目不一致"
        )

    receipt = _build_receipt(
        entry,
        evidence,
        note,
        status_after,
        recovery_action="replace_latest",
    )
    receipt_file = _write_receipt(target, receipt, view["version"])

    return {
        "ok": True,
        "operation": "publish",
        "outcome": "recovered",
        "recovery": "latest_recovered",
        "proposal_sha256": digest,
        "version": view["version"],
        "previous_version": entry.get("previous_version"),
        "history_file": f"{HISTORY_DIRNAME}/{entry.get('entry_file')}",
        "receipt_file": receipt_file,
        "current": _current_latest_info(target),
        "status_after": status_after,
        "trust_boundary": TRUST_BOUNDARY_NOTE,
    }


# ---------------------------------------------------------------------------
# 发布
# ---------------------------------------------------------------------------

def publish(
    policy_dir: str,
    proposal: Dict[str, Any],
    *,
    proposal_digest_expected: Optional[str] = None,
    approval_evidence: Optional[Dict[str, Any]] = None,
    authorize: bool = False,
    authorization_note: str = "",
    create_policy_dir: bool = False,
) -> Dict[str, Any]:
    """发布一份已获用户批准的策略提案。

    前置条件（缺一即 fail closed，不产生任何文件）：

    1. ``policy_dir`` 显式、绝对、非危险路径；
    2. 提案结构 / 版本 / 权重合法，且含 ``effect_summary``；
    3. ``proposal_digest_expected`` 与提案指纹 **精确匹配**；
    4. ``approval_evidence`` 结构完整（批准人 / 原文 / 会话 / 时间）；
    5. ``authorize=True`` 且 ``authorization_note`` 非空。

    成功后的顺序：不可变历史 → 原子替换 ``latest.json`` → 回执。
    """
    target = _assert_safe_target(policy_dir)
    view = validate_proposal(proposal)
    digest = proposal_digest(proposal)

    if not proposal_digest_expected:
        raise PublisherError("proposal_digest_missing", "必须提供提案摘要以便精确匹配")
    if not isinstance(proposal_digest_expected, str):
        raise PublisherError("proposal_digest_invalid", "提案摘要必须是字符串")
    if proposal_digest_expected.strip().lower() != digest:
        raise PublisherError(
            "proposal_digest_mismatch",
            "提案摘要与当前提案不匹配（提案可能已变更）",
        )

    evidence = _validate_approval_evidence(approval_evidence)
    note = _check_authorization(authorize, authorization_note)

    if not os.path.isdir(target):
        if not create_policy_dir:
            raise PublisherError(
                "policy_dir_absent",
                "目标策略目录不存在；如确需创建请显式允许（禁止隐式创建生产根）",
            )
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as exc:
            raise PublisherError("policy_dir_uncreatable", "无法创建目标策略目录") from exc

    with _PublishLock(target):
        current = _current_latest_info(target)

        # 严格扫描：历史里存在 **无法解析且可能与本提案相关** 的文件时，
        # 绝不静默跳过（坏文件足以把同指纹碰撞藏起来）。
        history, broken_history = _strict_history_scan(target)
        relevant_broken = _relevant_broken_history(broken_history, digest)
        if relevant_broken:
            raise PublisherError(
                "history_unreadable",
                "不可变历史存在无法解析的文件，无法核对发布条件: "
                + ", ".join(relevant_broken),
            )

        # 幂等 / 重复检测 → 崩溃恢复入口
        for entry in history:
            if entry.get("proposal_sha256") == digest:
                # 已有同指纹历史条目：可能是"已成功发布"（幂等返回），
                # 也可能是"历史已写但 latest 替换失败"（孤儿条目），
                # 或是"latest 已生效但回执缺失"。三者必须逐项核对，
                # 无法核对即 fail closed。
                return _recover_duplicate_publish(
                    target,
                    view,
                    proposal,
                    digest,
                    evidence,
                    note,
                )

        previous_version = current.get("version")
        if previous_version:
            for entry in history:
                if entry.get("new_version") == view["version"]:
                    raise PublisherError(
                        "duplicate_version", "该版本号已存在于不可变历史中"
                    )
            if _version_key(view["version"]) <= _version_key(str(previous_version)):
                raise PublisherError(
                    "version_not_newer", "新版本号必须严格大于当前已发布版本"
                )

        document = {
            "schema_version": POLICY_SCHEMA_VERSION,
            "version": view["version"],
            "approved_by_user": True,
            "approved_at": evidence["approved_at"],
            "effect_summary": view["effect_summary"],
            "weights": view["weights"],
            "proposal_sha256": digest,
            "published_at": _now_iso(),
        }
        # 第二道闸门：写入路径上的独立复查（第一道在 validate_proposal）。
        # 命中即 fail closed，绝不覆盖已批准的可信元数据，也绝不静默忽略。
        _assert_no_reserved_fields(view["policy"])
        for key, value in view["policy"].items():
            # 纵深防御：即便上面的复查被绕过，也绝不覆盖已有键。
            if key in document:
                raise PublisherError(
                    "policy_reserved_field_conflict",
                    f"提案 policy 试图覆盖 Publisher 托管字段: {key}",
                )
            document[key] = value

        validation = agent_policy.validate_policy_document(document)
        if not validation.get("initialized"):
            raise PublisherError(
                "policy_document_invalid",
                f"生成的策略文档未通过校验: {validation.get('status')}",
            )

        payload = _canonical_policy_payload(document)
        published_policy_sha = _sha256_bytes(payload)

        sequence = _next_sequence(target, HISTORY_DIRNAME)
        history_name = f"{sequence:06d}-{_safe_filename(view['version'])}-{digest[:12]}.json"
        history_path = os.path.join(target, HISTORY_DIRNAME, history_name)
        try:
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
        except OSError as exc:
            raise PublisherError("history_unwritable", "无法创建历史目录") from exc
        if os.path.exists(history_path):
            raise PublisherError("history_collision", "历史文件已存在，拒绝覆盖")

        entry = {
            "entry_type": "publish",
            "sequence": sequence,
            "published_at": _now_iso(),
            "previous_version": previous_version,
            "new_version": view["version"],
            "proposal_sha256": digest,
            "previous_policy_sha256": current.get("policy_sha256"),
            "published_policy_sha256": published_policy_sha,
            "effect_summary": view["effect_summary"],
            "approval_evidence": evidence,
            "authorization_note": note,
            "proposal": proposal,
            "policy_document": document,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
            "entry_file": history_name,
        }
        _write_json_file(history_path, entry, exclusive=True)

        # 原子替换唯一 latest.json
        _atomic_write_bytes(os.path.join(target, POLICY_FILENAME), payload)

        status_after = agent_policy.read_policy_status(target)
        if not status_after.get("initialized"):
            raise PublisherError(
                "post_publish_unreadable",
                f"发布后校验失败: {status_after.get('status')}",
            )

        receipt = _build_receipt(entry, evidence, note, status_after)
        receipt_file = _write_receipt(target, receipt, view["version"])

        return {
            "ok": True,
            "operation": "publish",
            "outcome": "published",
            "proposal_sha256": digest,
            "version": view["version"],
            "previous_version": previous_version,
            "history_file": f"{HISTORY_DIRNAME}/{history_name}",
            "receipt_file": receipt_file,
            "current": _current_latest_info(target),
            "status_after": status_after,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }


def _safe_filename(text: str) -> str:
    """把版本号变成安全的文件名片段。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    cleaned = cleaned.strip("._-") or "version"
    return cleaned[:80]


# ---------------------------------------------------------------------------
# 回滚（受控）
# ---------------------------------------------------------------------------

def rollback(
    policy_dir: str,
    *,
    version: str,
    approval_evidence: Optional[Dict[str, Any]] = None,
    authorize: bool = False,
    authorization_note: str = "",
) -> Dict[str, Any]:
    """受控回滚到 *不可变历史中已批准* 的某个版本。

    明确安全拒绝：
    - 目标版本不在历史中 → 拒绝（禁止自行跨版本覆盖 / 编造回滚目标）
    - 缺少批准证据 / 操作授权 → 拒绝
    - 历史中的策略文档未通过 ``validate_policy_document`` → 拒绝
    """
    target = _assert_safe_target(policy_dir)
    if not os.path.isdir(target):
        raise PublisherError("policy_dir_absent", "目标策略目录不存在")
    if not isinstance(version, str) or not version.strip():
        raise PublisherError("rollback_target_required", "必须指定回滚目标版本")
    wanted = version.strip()

    evidence = _validate_approval_evidence(approval_evidence)
    note = _check_authorization(authorize, authorization_note)

    with _PublishLock(target):
        current = _current_latest_info(target)
        history = _list_history_entries(target)
        match = None
        for entry in history:
            if entry.get("new_version") == wanted:
                match = entry
                break
        if match is None:
            raise PublisherError(
                "rollback_target_not_in_history",
                "回滚目标必须是不可变历史中已批准的版本",
            )
        document = match.get("policy_document")
        if not isinstance(document, dict):
            raise PublisherError("rollback_target_unusable", "历史条目缺少策略文档")
        validation = agent_policy.validate_policy_document(document)
        if not validation.get("initialized"):
            raise PublisherError(
                "rollback_target_invalid",
                f"历史策略未通过校验: {validation.get('status')}",
            )

        # 元数据一致性（LT_BOOTSTRAP_PUBLISHER_METADATA_QA_20261022_E）：
        # 回滚恢复的是"当初被批准的那份文档"，因此它的批准元数据必须与
        # 同一历史条目里记录的批准证据、以及提案指纹 **逐字绑定**。
        # 任一不一致 → 拒绝（历史被篡改 / 结构不自洽 → fail closed）。
        entry_digest = match.get("proposal_sha256")
        if entry_digest and document.get("proposal_sha256") != entry_digest:
            raise PublisherError(
                "rollback_metadata_mismatch",
                "历史策略文档的 proposal_sha256 与历史条目不一致",
            )
        entry_evidence = match.get("approval_evidence")
        if isinstance(entry_evidence, dict) and entry_evidence.get("approved_at"):
            if document.get("approved_at") != entry_evidence["approved_at"]:
                raise PublisherError(
                    "rollback_metadata_mismatch",
                    "历史策略文档的 approved_at 与批准证据不一致",
                )

        payload = (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        published_policy_sha = _sha256_bytes(payload)

        sequence = _next_sequence(target, ROLLBACKS_DIRNAME)
        name = f"{sequence:06d}-{_safe_filename(wanted)}.json"
        record_path = os.path.join(target, ROLLBACKS_DIRNAME, name)
        try:
            os.makedirs(os.path.dirname(record_path), exist_ok=True)
        except OSError as exc:
            raise PublisherError("rollback_unwritable", "无法创建回滚记录目录") from exc
        record = {
            "entry_type": "rollback",
            "sequence": sequence,
            "rolled_back_at": _now_iso(),
            "previous_version": current.get("version"),
            "restored_version": wanted,
            "restored_from_history": match.get("entry_file"),
            "published_policy_sha256": published_policy_sha,
            "approval_evidence": evidence,
            "authorization_note": note,
            "policy_document": document,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }
        _write_json_file(record_path, record, exclusive=True)

        _atomic_write_bytes(os.path.join(target, POLICY_FILENAME), payload)

        status_after = agent_policy.read_policy_status(target)
        if not status_after.get("initialized"):
            raise PublisherError(
                "post_rollback_unreadable",
                f"回滚后校验失败: {status_after.get('status')}",
            )

        return {
            "ok": True,
            "operation": "rollback",
            "outcome": "rolled_back",
            "previous_version": current.get("version"),
            "restored_version": wanted,
            "rollback_file": f"{ROLLBACKS_DIRNAME}/{name}",
            "status_after": status_after,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }


# ---------------------------------------------------------------------------
# 命令行接口
# ---------------------------------------------------------------------------

def _load_evidence(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    if not os.path.isfile(path):
        raise PublisherError("approval_evidence_not_found", "批准证据文件不存在")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise PublisherError("approval_evidence_unreadable", "批准证据文件无法读取") from exc
    if not isinstance(doc, dict):
        raise PublisherError("approval_evidence_invalid", "批准证据必须是 JSON 对象")
    return doc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent_policy_publisher",
        description="受控的 Agent 策略发布器（控制端在获得用户批准后使用）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="预览一次策略变更（无任何写入）")
    prep.add_argument("--proposal", required=True)
    prep.add_argument("--policy-dir", required=True)

    pub = sub.add_parser("publish", help="发布已获用户批准的策略")
    pub.add_argument("--proposal", required=True)
    pub.add_argument("--policy-dir", required=True)
    pub.add_argument("--proposal-digest", required=True)
    pub.add_argument("--approval-evidence", required=True)
    pub.add_argument("--authorize", action="store_true")
    pub.add_argument("--authorization-note", default="")
    pub.add_argument(
        "--create-policy-dir",
        action="store_true",
        help="显式允许创建不存在的目标目录（默认拒绝隐式创建）",
    )

    rb = sub.add_parser("rollback", help="受控回滚到历史中已批准的版本")
    rb.add_argument("--policy-dir", required=True)
    rb.add_argument("--version", required=True)
    rb.add_argument("--approval-evidence", required=True)
    rb.add_argument("--authorize", action="store_true")
    rb.add_argument("--authorization-note", default="")

    st = sub.add_parser("status", help="只读查看目标目录的策略状态")
    st.add_argument("--policy-dir", required=True)

    lk = sub.add_parser("lock-status", help="只读查看发布锁状态（绝不自动解锁）")
    lk.add_argument("--policy-dir", required=True)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            proposal = load_proposal(args.proposal)
            result = prepare(proposal, args.policy_dir)
        elif args.command == "publish":
            proposal = load_proposal(args.proposal)
            result = publish(
                args.policy_dir,
                proposal,
                proposal_digest_expected=args.proposal_digest,
                approval_evidence=_load_evidence(args.approval_evidence),
                authorize=bool(args.authorize),
                authorization_note=args.authorization_note,
                create_policy_dir=bool(args.create_policy_dir),
            )
        elif args.command == "rollback":
            result = rollback(
                args.policy_dir,
                version=args.version,
                approval_evidence=_load_evidence(args.approval_evidence),
                authorize=bool(args.authorize),
                authorization_note=args.authorization_note,
            )
        elif args.command == "status":
            target = _assert_safe_target(args.policy_dir)
            result = {
                "ok": True,
                "operation": "status",
                "current": _current_latest_info(target),
            }
        elif args.command == "lock-status":
            result = {
                "ok": True,
                "operation": "lock_status",
                "lock": lock_status(args.policy_dir),
            }
        else:  # pragma: no cover - argparse 已保证
            parser.error("未知命令")
            return 2
    except PublisherError as exc:
        payload = {
            "ok": False,
            "error": exc.code,
            "detail": exc.detail,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 2
    except Exception as exc:  # pragma: no cover - 意外错误也要 fail closed
        payload = {
            "ok": False,
            "error": "unexpected_error",
            "detail": type(exc).__name__,
            "trust_boundary": TRUST_BOUNDARY_NOTE,
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 3

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


__all__ = [
    "HISTORY_DIRNAME",
    "LOCK_FILENAME",
    "POLICY_FILENAME",
    "POLICY_SCHEMA_VERSION",
    "PUBLISHER_RESERVED_FIELDS",
    "PUBLISHER_RESERVED_FIELD_SET",
    "RECEIPTS_DIRNAME",
    "RECOVERY_RECEIPT_TYPE",
    "ROLLBACKS_DIRNAME",
    "TRUST_BOUNDARY_NOTE",
    "PublisherError",
    "build_arg_parser",
    "load_proposal",
    "lock_status",
    "main",
    "prepare",
    "proposal_digest",
    "publish",
    "rollback",
    "validate_proposal",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
