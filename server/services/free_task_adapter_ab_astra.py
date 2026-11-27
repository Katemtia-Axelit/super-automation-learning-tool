"""server.services.free_task_adapter_ab_astra - 自由任务 **synthetic-only** 适配层。

定位
----
:mod:`server.services.free_task_events` 已经是一个自洽的、显式传路径的
追加式事件账本。本模块 **不复制它的任何规则**，只在它外面加一层
**极薄的、fail-closed 的入参闸门**，供后续受控调用方使用：

- :class:`FreeTaskAdapter` —— 把 ``dict`` 请求映射到既有
  ``FreeTaskEventStore`` 的 ``append_event`` / ``get_summary``；
- :func:`validate_synthetic_db_path` —— **只验证、不创建** 一个
  sandbox 内的 synthetic SQLite 路径。

两个交付物都 **不接线到任何生产路径**：

- 不 import Flask、不注册 Blueprint、不接前端；
- 不读 ``config/config.json``；
- 不写 ``data/task_publisher.db``（及其 WAL/SHM）；
- 不写 ``src/notes/**``；
- 构造函数 **只接受注入的 store**，绝不隐式建库、绝不隐式连库。

设计契约（fail closed）
----------------------
1. **严格键集合**：`action='append'` 只接受
   ``action / session_id / event_id / event_payload``；
   ``action='summary'` 只接受 ``action / session_id``。
   多一个键 → 拒绝；少一个键 → 拒绝；未知 ``action`` → 拒绝。
2. **纯字符串 ID**：``session_id`` / ``event_id`` 必须是非空、
   非 ``bool`` 的纯字符串；``event_payload`` 必须是 ``dict``。
3. **先校验后写入**：任何校验失败都在调用 store *之前* 抛错，
   因此 **不可能因为非法请求产生写入**。
4. **不吞并底层 code**：store 抛出的
   :class:`server.services.free_task_events.FreeTaskEventError`
   **原样向上传播**（同一个异常对象、同一个 ``code``），
   适配层既不改写也不合并它。
5. **不伪造事件**：适配层不生成 ``event_id``、不修改
   ``event_payload``、不补默认字段、不重放。幂等完全依赖底层的
   ``event_id`` 唯一约束，适配层不自己实现一套。
6. **只透传 summary**：`dispatch`` 返回的 ``summary`` 就是
   ``store.get_summary()`` 的原样结果。适配层 **不** 重新推导、
   不把娱乐完成或流逝分钟折算成“已学分钟”。

错误模型
--------
本模块自有错误 :class:`FreeTaskAdapterError`，与底层
``FreeTaskEventError`` 保持同样的 ``code`` / ``message`` 形状，
但 **两者绝不合并**：底层错误永远保持底层身份。

尚未集成（见 Handoff）
----------------------
本模块 **没有** 接入生产 Factory / Blueprint / 前端，也没有被任何
生产代码 import。它是一次同条件评测用的候选实现，只有合成测试在用。
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Set

__all__ = [
    "APPEND_ALLOWED_KEYS",
    "SUMMARY_ALLOWED_KEYS",
    "FreeTaskAdapter",
    "FreeTaskAdapterError",
    "validate_synthetic_db_path",
]


# ---------------------------------------------------------------------------
# 契约常量
# ---------------------------------------------------------------------------

#: ``action='append'`` 允许出现的键（且这四个都必须出现）。
APPEND_ALLOWED_KEYS: Set[str] = frozenset(
    {"action", "session_id", "event_id", "event_payload"}
)

#: ``action='summary'`` 允许出现的键（且这两个都必须出现）。
SUMMARY_ALLOWED_KEYS: Set[str] = frozenset({"action", "session_id"})

#: 本适配层支持的全部 action。
SUPPORTED_ACTIONS: Set[str] = frozenset({"append", "summary"})

#: 被明确拒绝的“生产数据库”文件名（不区分大小写）。
_FORBIDDEN_BASENAMES = frozenset(
    {"task_publisher.db", "task_publisher.db-wal", "task_publisher.db-shm"}
)

#: Windows reparse point（含 junction）文件属性位。
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

#: 项目根目录下的生产 ``data/`` 目录：任何 candidate 都不得落在里面。
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

#: 内部哨兵（区分“键不存在”与“键存在但值为 None”）。
_MISSING = object()


# ---------------------------------------------------------------------------
# 错误
# ---------------------------------------------------------------------------

class FreeTaskAdapterError(Exception):
    """适配层自身的错误（fail closed）。

    ``code`` 是稳定的机器可读原因码；``message`` 是中文说明。
    底层 ``FreeTaskEventError`` 不会被转换成本错误（code 不被吞并）。
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


# ---------------------------------------------------------------------------
# 入参校验小工具
# ---------------------------------------------------------------------------

def _is_plain_identifier(value: Any) -> bool:
    """非空、非 ``bool`` 的纯字符串。

    ``bool`` 在 Python 里不是 ``str`` 的子类，这里仍然显式排除，
    目的是让“纯字符串”这一契约在代码里可读、可审计。
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, str):
        return False
    return bool(value.strip())


def _require_identifier(value: Any, field: str) -> str:
    if not _is_plain_identifier(value):
        raise FreeTaskAdapterError(
            f"{field}_required", f"{field} 必须是非空的纯字符串"
        )
    return value


def _require_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, bool) or not isinstance(value, dict):
        raise FreeTaskAdapterError("event_payload_invalid", "event_payload 必须是字典")
    return value


def _require_request_dict(request: Any) -> Dict[str, Any]:
    if isinstance(request, bool) or not isinstance(request, dict):
        raise FreeTaskAdapterError("request_invalid", "请求必须是字典")
    return request


def _require_keys(
    request: Dict[str, Any], allowed: Set[str], required: Set[str]
) -> None:
    """严格键集合：先拒绝多余键，再要求必填键全部出现。"""
    unexpected = sorted(set(request) - set(allowed))
    if unexpected:
        raise FreeTaskAdapterError(
            "unexpected_key", f"请求含有不允许的键: {unexpected}"
        )
    missing = sorted(name for name in required if request.get(name, _MISSING) is _MISSING)
    if missing:
        raise FreeTaskAdapterError("field_required", f"请求缺少必填键: {missing}")


# ---------------------------------------------------------------------------
# 适配器
# ---------------------------------------------------------------------------

class FreeTaskAdapter:
    """自由任务事件的 **synthetic-only** 适配层。

    参数
    ----
    store:
        **必须由调用方显式注入** 的既有
        :class:`~server.services.free_task_events.FreeTaskEventStore`
        （或提供同名方法的双对象 / mock）。本类：

        - 绝不构造 store；
        - 绝不隐式创建或连接任何数据库文件；
        - 不读取 ``config/config.json``，没有默认路径。
    """

    def __init__(self, store: Any) -> None:
        if store is None:
            raise FreeTaskAdapterError(
                "store_required",
                "必须显式注入 FreeTaskEventStore；适配层绝不隐式建库或连库",
            )
        for method in ("append_event", "get_summary"):
            if not callable(getattr(store, method, None)):
                raise FreeTaskAdapterError(
                    "store_invalid",
                    f"注入对象缺少可调用的 {method}()；请显式传入 FreeTaskEventStore",
                )
        self._store = store

    # 只读属性：暴露注入的 store，不替换、不代理写入策略。
    @property
    def store(self) -> Any:
        return self._store

    def dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """分发一次请求，返回 ``{'ok', 'action', 'summary'}``。

        ``action='append'``
            校验 → ``store.append_event`` → ``store.get_summary``；
        ``action='summary'``
            校验 → ``store.get_summary``（不写入）。

        校验失败 → 抛 :class:`FreeTaskAdapterError`，
        且 **在调用 store 之前** 就已终止，因此不会有写入。
        store 抛出的 ``FreeTaskEventError`` **原样传播**
        （code 不被吞并、不被改写）。
        """
        req = _require_request_dict(request)

        action = req.get("action")
        if not _is_plain_identifier(action) or action not in SUPPORTED_ACTIONS:
            raise FreeTaskAdapterError(
                "action_unsupported",
                f"不支持的 action: {action!r}（只接受 {sorted(SUPPORTED_ACTIONS)}）",
            )

        if action == "append":
            _require_keys(req, APPEND_ALLOWED_KEYS, APPEND_ALLOWED_KEYS)
            session_id = _require_identifier(req["session_id"], "session_id")
            event_id = _require_identifier(req["event_id"], "event_id")
            event_payload = _require_payload(req["event_payload"])
            # 全部校验通过后才允许触碰 store。
            self._store.append_event(session_id, event_id, event_payload)
        else:
            _require_keys(req, SUMMARY_ALLOWED_KEYS, SUMMARY_ALLOWED_KEYS)
            session_id = _require_identifier(req["session_id"], "session_id")

        # summary 原样透传：不重新推导、不折算任何分钟数。
        summary = self._store.get_summary(session_id)
        return {"ok": True, "action": action, "summary": summary}


# ---------------------------------------------------------------------------
# sandbox 路径验证（只验证，不创建）
# ---------------------------------------------------------------------------

def _is_reparse_point(st: os.stat_result) -> bool:
    """Windows junction / reparse point 判定（其他平台恒为 False）。"""
    attrs = getattr(st, "st_file_attributes", 0)
    if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    tag = getattr(st, "st_reparse_tag", 0)
    return bool(tag)


def _lstat(path: str) -> Optional[os.stat_result]:
    """``os.lstat``，把“不存在”与“无法验证”区分开。"""
    try:
        return os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        raise FreeTaskAdapterError(
            "path_unverifiable", f"无法验证路径状态（fail closed）: {path} ({exc})"
        ) from exc


def _assert_no_link(st: os.stat_result, path: str) -> None:
    if os.path.islink(path) or _is_reparse_point(st):
        raise FreeTaskAdapterError(
            "path_contains_link",
            f"路径中存在符号链接 / junction / reparse point: {path}",
        )


def _resolve_root(sandbox_root: Any) -> str:
    """sandbox_root 必须是 **已经存在** 的真实目录。"""
    if not _is_plain_identifier(sandbox_root):
        raise FreeTaskAdapterError("root_required", "sandbox_root 必须是非空字符串")
    root = os.path.abspath(os.path.normpath(sandbox_root.strip()))
    if os.path.isfile(root) or not os.path.exists(root):
        raise FreeTaskAdapterError("root_missing", f"sandbox_root 不存在: {root}")
    if not os.path.isdir(root):
        raise FreeTaskAdapterError("root_not_directory", f"sandbox_root 不是目录: {root}")
    return os.path.realpath(root)


def _normalize_candidate(candidate: Any) -> str:
    if not _is_plain_identifier(candidate):
        raise FreeTaskAdapterError(
            "candidate_required", "candidate 必须是非空字符串路径"
        )
    return os.path.normpath(candidate.strip())


def validate_synthetic_db_path(candidate: Any, sandbox_root: Any) -> str:
    """验证 ``candidate`` 可以作为 sandbox 内的 synthetic SQLite 路径。

    本函数 **只验证，绝不创建任何文件 / 目录**。

    通过条件（全部满足才返回绝对规范化路径）：

    - ``sandbox_root`` 已经存在且是真实目录；
    - ``candidate`` 严格位于 root 内部，且 **不等于** root；
    - candidate 路径上 **没有** 已存在的符号链接 /
      Windows junction / reparse point 中转（含 candidate 自身）；
    - candidate 不在项目生产 ``data/`` 目录内；
    - candidate 的 basename 不是 ``task_publisher.db`` 及其
      WAL/SHM（不区分大小写）；
    - 若 candidate 已存在：必须是普通文件且 ``st_nlink == 1``
      （存在硬链接别名 → 拒绝）。

    拒绝而非猜测：任何无法可靠验证的情形（``OSError``、混合盘符、
    ``..`` 逃逸、越界）都直接抛
    :class:`FreeTaskAdapterError`。

    返回
    ----
    ``str``：解析后的绝对路径（可用于 ``FreeTaskEventStore``）。
    """
    root_real = _resolve_root(sandbox_root)
    cand_norm = _normalize_candidate(candidate)

    # --- 1) 盘符 / 绝对相对一致性 --------------------------------------
    root_drive, _ = os.path.splitdrive(root_real)
    cand_drive, _ = os.path.splitdrive(cand_norm)
    if os.path.isabs(cand_norm) and cand_drive != root_drive:
        raise FreeTaskAdapterError(
            "path_escape", "candidate 位于与 sandbox_root 不同的盘符下"
        )

    cand_abs = os.path.abspath(
        cand_norm if os.path.isabs(cand_norm) else os.path.join(root_real, cand_norm)
    )

    # --- 2) `..` 一律拒绝（看 **原始** candidate，不做归一化掩盖） ------
    raw_text = candidate.strip()
    raw_parts = [p for p in re.split(r"[\\/]+", raw_text) if p not in ("", ".")]
    if any(part == ".." for part in raw_parts):
        raise FreeTaskAdapterError(
            "path_escape", "candidate 含有 `..`，拒绝（不做猜测式归一化）"
        )

    # --- 3) 严格包含关系（realpath 之后仍然必须在 root 内） -----------
    cand_real = os.path.realpath(cand_abs)
    root_cmp = os.path.normcase(root_real)
    cand_cmp = os.path.normcase(cand_real)
    if cand_cmp == root_cmp:
        raise FreeTaskAdapterError("candidate_is_root", "candidate 不能等于 sandbox_root")
    try:
        if os.path.commonpath([root_cmp, cand_cmp]) != root_cmp:
            raise FreeTaskAdapterError(
                "path_escape", f"candidate 越出 sandbox_root: {candidate!r}"
            )
    except ValueError as exc:  # 不同盘符等不可比较情形
        raise FreeTaskAdapterError(
            "path_escape", f"candidate 与 sandbox_root 不可比较: {exc}"
        ) from exc

    # --- 4) 不得落在生产 data/ 目录 -----------------------------------
    data_cmp = os.path.normcase(os.path.realpath(_PROJECT_DATA_DIR))
    if cand_cmp == data_cmp or cand_cmp.startswith(data_cmp + os.sep):
        raise FreeTaskAdapterError(
            "production_data_dir", "candidate 不得指向项目生产 data/ 目录"
        )

    # --- 5) basename 黑名单（不区分大小写） ----------------------------
    if os.path.basename(cand_abs).lower() in _FORBIDDEN_BASENAMES:
        raise FreeTaskAdapterError(
            "production_db_name", "candidate 不得是 task_publisher.db 及其 WAL/SHM"
        )

    # --- 6) 逐段检查：符号链接 / junction / reparse point 中转 ----------
    walked_base = root_real
    # 相对部分用 realpath 后的候选路径相对 **realpath 后的 root** 计算
    # （relpath 语义稳健，不受大小写 / 尾部分隔符 / 别名路径影响）。
    # 之前基于字符串切片，切片起点一旦与 root 字面不一致就会错位。
    try:
        walked_parts = os.path.relpath(cand_real, walked_base)
    except ValueError as exc:
        raise FreeTaskAdapterError(
            "path_escape", f"candidate 与 sandbox_root 不可比较: {exc}"
        ) from exc
    walked_parts = [
        p for p in re.split(r"[\\/]+", walked_parts) if p not in ("", os.curdir)
    ]
    if any(part == ".." for part in walked_parts):  # pragma: no cover - 防御性
        raise FreeTaskAdapterError("path_escape", "candidate 越出 sandbox_root")

    walk = walked_base
    for index, part in enumerate(walked_parts):
        walk = os.path.join(walk, part)
        st = _lstat(walk)
        if st is None:
            # 该段尚不存在 → 其后也不会存在，直接通过（全新文件路径）。
            break
        _assert_no_link(st, walk)
        is_last = index == len(walked_parts) - 1
        if not is_last and not os.path.isdir(walk):
            raise FreeTaskAdapterError(
                "path_contains_file", f"candidate 路径中段不是目录: {walk}"
            )
        if is_last:
            if os.path.isdir(walk):
                raise FreeTaskAdapterError(
                    "candidate_is_directory", "candidate 已存在且是目录"
                )
            nlink = getattr(st, "st_nlink", 1)
            if isinstance(nlink, int) and nlink > 1:
                raise FreeTaskAdapterError(
                    "hard_link_alias",
                    f"candidate 已存在且有硬链接别名 (st_nlink={nlink}): {walk}",
                )

    return cand_real