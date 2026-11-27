"""server.services.free_task_adapter_ab_opus - 自由任务的 **synthetic 适配层**。

定位
----
本模块是在既有事件账本 (:mod:`server.services.free_task_events`) 之上的一层
**极薄、无状态、synthetic-only** 的适配层，供 A/B 工程评价使用。它把
“请求字典”翻译成对已注入账本的两次调用，并原样透传账本给出的 summary。

它 **不是** 生产接线层。当前状态：

- **没有** 接入 Flask Factory / Blueprint / 前端；
- **没有** 默认数据库路径，**绝不** 隐式创建或连接任何数据库；
- **没有** import Flask，**不读** ``config/config.json``；
- **不写** ``src/notes/**``，**绝不** 访问生产 ``data/`` 目录。

严格契约（LT_MODEL_AB_B_20261022_B）
------------------------------------
1. :class:`FreeTaskAdapter` 的构造函数 **只接受注入** 的既有
   :class:`~server.services.free_task_events.FreeTaskEventStore`。
   本层 **绝不** 构造 store、绝不创建文件、绝不 ``sqlite3.connect``。
2. :meth:`FreeTaskAdapter.dispatch` 只接受两个动作：

   - ``action='append'``：允许键 **恰好** 为
     ``{action, session_id, event_id, event_payload}``（全部必需）；
   - ``action='summary'``：允许键 **恰好** 为
     ``{action, session_id}``（全部必需）。

   ``session_id`` / ``event_id`` 必须是 **非空、非布尔的纯字符串**；
   ``event_payload`` 必须是 **dict**。
3. 任何其它 action、任何额外键、任何不合法输入 → **明确拒绝**
   （抛 :class:`FreeTaskAdapterError`），并且 **在校验通过之前绝不调用
   store**，因此 **不可能造成写入**。
4. 成功时返回 ``{'ok': True, 'action': <动作>, 'summary': <账本 summary>}``。
   ``summary`` 是 **原样透传**：不复制、不改写、不新增字段、不折算任何数字。
5. 底层 :class:`FreeTaskEventError`（含它的 ``code``）**不被捕获、不被
   包装、不被吞并**：直接向调用方传播。本层只对“本层自己的形状校验”
   抛 :class:`FreeTaskAdapterError`，两套 code 命名空间互不重叠。
6. 同一 ``event_id`` 的幂等 **完全依赖底层账本**，本层不缓存、不伪造
   事件、不重放写入。
7. 本层 **绝不** 把娱乐完成数或流逝分钟 (``actual_minutes`` /
   ``timer_elapsed``) 折算成已学分钟。所有数字语义都在底层账本里，
   本层只负责透传。

沙箱路径校验
------------
:func:`validate_synthetic_db_path` **只验证、不创建**任何文件/目录。
它拒绝一切 “无法可靠验证” 的情形（fail closed，绝不猜测）。

安全与无副作用约束
------------------
- 本模块 **不 import Flask**、**不联网**、**不写日志文件**。
- 本模块 **绝不** 打开、创建、删除任何路径；只用 ``os.lstat`` /
  ``os.path.*`` 读取元数据。
- 生产数据目录 (``<project>/data``) 被显式列入拒绝名单（纯字符串比较，
  不做任何 I/O）。
"""

from __future__ import annotations

import os
import stat as stat_module
from typing import Any, Dict, Tuple

# Windows reparse point 属性位（不可用时按 0 处理，随后由 islink 兜底）。
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

#: 生产数据库文件名家族（大小写不敏感）。
FORBIDDEN_DB_BASENAMES = frozenset(
    {
        "task_publisher.db",
        "task_publisher.db-wal",
        "task_publisher.db-shm",
    }
)

#: ``append`` 动作允许的键（恰好这四个，全部必需）。
APPEND_ALLOWED_KEYS = frozenset(
    {"action", "session_id", "event_id", "event_payload"}
)

#: ``summary`` 动作允许的键（恰好这两个，全部必需）。
SUMMARY_ALLOWED_KEYS = frozenset({"action", "session_id"})

#: 支持的动作。
SUPPORTED_ACTIONS = ("append", "summary")

#: 适配层自身的错误 code 前缀（与底层账本 code 命名空间不重叠）。
_CODE_PREFIX = "adapter_"


class FreeTaskAdapterError(Exception):
    """适配层错误（fail closed）。

    ``code`` 是稳定的机器可读原因码；以 ``adapter_`` 开头，与底层
    :class:`~server.services.free_task_events.FreeTaskEventError` 的
    code 完全区分，便于调用方判断错误来自哪一层。
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message or code


# ---------------------------------------------------------------------------
# 形状校验小工具（全部 fail closed）
# ---------------------------------------------------------------------------

def _is_plain_str(value: Any) -> bool:
    """是否为非空、非布尔的纯字符串。

    ``bool`` 被显式排除（Python 里 ``True`` 不是 ``str``，但这里把意图
    写死，避免将来有人放宽 ``isinstance`` 判断时静默放过布尔值）。
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, str):
        return False
    return bool(value.strip())


def _require_request_dict(request: Any) -> Dict[str, Any]:
    if not isinstance(request, dict):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "request_invalid", "请求必须是字典"
        )
    return request


def _require_action(request: Dict[str, Any]) -> str:
    if "action" not in request:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "action_required", "请求必须显式携带 action"
        )
    action = request["action"]
    if not _is_plain_str(action):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "action_invalid", "action 必须是非空字符串"
        )
    if action not in SUPPORTED_ACTIONS:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "action_invalid",
            f"不支持的 action: {action!r}；只允许 {list(SUPPORTED_ACTIONS)}",
        )
    return action


def _assert_no_extra_keys(request: Dict[str, Any], allowed: frozenset) -> None:
    extra = sorted(set(request) - set(allowed))
    if extra:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "request_unknown_field",
            f"请求含有未声明的键（多余参数一律拒绝）: {extra}",
        )


def _require_id(request: Dict[str, Any], field: str) -> str:
    if field not in request:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + field + "_required", f"请求必须携带 {field}"
        )
    value = request[field]
    if not _is_plain_str(value):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + field + "_invalid",
            f"{field} 必须是非空、非布尔的字符串",
        )
    return value


def _require_payload(request: Dict[str, Any]) -> Dict[str, Any]:
    if "event_payload" not in request:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "event_payload_required",
            "append 请求必须携带 event_payload",
        )
    payload = request["event_payload"]
    if not isinstance(payload, dict) or isinstance(payload, bool):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "event_payload_invalid",
            "event_payload 必须是字典",
        )
    return payload


# ---------------------------------------------------------------------------
# 适配器
# ---------------------------------------------------------------------------

class FreeTaskAdapter:
    """自由任务事件的 **注入式** 适配层（synthetic-only）。

    参数
    ----
    store:
        **必须由调用方显式注入** 的既有
        :class:`~server.services.free_task_events.FreeTaskEventStore`
        实例（或行为等价的对象 / 测试替身）。本类 **绝不** 构造 store、
        **绝不** 提供默认路径、**绝不** 打开数据库。

    本类没有 ``db_path`` 参数，因为本层不负责选路径；路径安全由
    :func:`validate_synthetic_db_path` 在接线前独立校验。
    """

    def __init__(self, store: Any) -> None:
        if store is None:
            raise FreeTaskAdapterError(
                _CODE_PREFIX + "store_required",
                "必须显式注入既有的 FreeTaskEventStore；本层绝不隐式创建或连接数据库",
            )
        for method in ("append_event", "get_summary"):
            if not callable(getattr(store, method, None)):
                raise FreeTaskAdapterError(
                    _CODE_PREFIX + "store_invalid",
                    f"注入的 store 缺少可调用方法 {method}()",
                )
        self._store = store

    # -- 只读属性 --------------------------------------------------------
    @property
    def store(self) -> Any:
        """注入的账本实例（只读引用，本层不替换它）。"""
        return self._store

    # -- 主入口 ----------------------------------------------------------
    def dispatch(self, request: Any) -> Dict[str, Any]:
        """把一个请求字典翻译成对既有账本的调用。

        成功返回::

            {'ok': True, 'action': 'append' | 'summary', 'summary': <账本 summary>}

        ``summary`` 是账本 :meth:`get_summary` 返回值的 **原样透传**：
        本层不复制、不新增、不折算、不把娱乐完成或流逝分钟折算成
        已学分钟。

        拒绝（抛 :class:`FreeTaskAdapterError`）的情形：

        - 请求不是字典；
        - ``action`` 缺失 / 非纯字符串 / 不在支持列表内；
        - 出现任何未声明的键（多余参数）；
        - 必需键缺失，或 ``session_id`` / ``event_id`` 不是非空非布尔字符串，
          或 ``event_payload`` 不是字典。

        底层 :class:`~server.services.free_task_events.FreeTaskEventError`
        （含其 ``code``）**原样传播**，不被捕获、不被包装。

        保证：所有形状校验都在调用 store **之前** 完成，因此被拒绝的
        请求 **绝不会造成任何写入**。
        """
        req = _require_request_dict(request)
        action = _require_action(req)

        if action == "summary":
            _assert_no_extra_keys(req, SUMMARY_ALLOWED_KEYS)
            session_id = _require_id(req, "session_id")
            summary = self._store.get_summary(session_id)
            return {"ok": True, "action": "summary", "summary": summary}

        # action == 'append'
        _assert_no_extra_keys(req, APPEND_ALLOWED_KEYS)
        session_id = _require_id(req, "session_id")
        event_id = _require_id(req, "event_id")
        event_payload = _require_payload(req)

        # 幂等 / 冲突 / 状态机 / 娱乐分账 全部由底层账本裁决；
        # 这里的异常一律向上传播，code 原样保留。
        self._store.append_event(session_id, event_id, event_payload)
        summary = self._store.get_summary(session_id)
        return {"ok": True, "action": "append", "summary": summary}


# ---------------------------------------------------------------------------
# 合成沙箱路径校验（只验证，不创建）
# ---------------------------------------------------------------------------

def _project_root() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir)
    )


def _protected_project_dirs() -> Tuple[str, ...]:
    """生产数据目录（纯字符串比较，绝不对其做任何 I/O）。"""
    root = _project_root()
    return (os.path.join(root, "data"),)


def _is_reparse_or_link(path: str) -> bool:
    """``path`` 是否是符号链接 / Windows junction / reparse point。

    只读取元数据（``os.lstat``），不跟随、不打开目标。
    """
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    except NotADirectoryError:
        return False
    except OSError as exc:  # 权限 / IO 异常 → 无法可靠验证
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_unverifiable",
            f"无法读取路径元数据，拒绝猜测: {path!r} ({exc})",
        ) from exc
    if os.path.islink(path):
        return True
    attributes = getattr(st, "st_file_attributes", 0) or 0
    if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    if getattr(st, "st_reparse_tag", 0):
        return True
    if stat_module.S_ISLNK(st.st_mode):
        return True
    return False


def _lstat_or_none(path: str) -> Any:
    try:
        return os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_unverifiable",
            f"无法读取路径元数据，拒绝猜测: {path!r} ({exc})",
        ) from exc


def _is_strictly_inside(child: str, parent: str) -> bool:
    """``child`` 是否严格位于 ``parent`` 之内（不相等、不越界）。

    比较前先 ``normcase``，因此在 Windows 上大小写与分隔符差异被吸收。
    """
    c = os.path.normcase(child)
    p = os.path.normcase(parent)
    if c == p:
        return False
    prefix = p if p.endswith(os.sep) else p + os.sep
    return c.startswith(prefix)


def _assert_not_protected(path: str) -> None:
    for protected in _protected_project_dirs():
        if _is_strictly_inside(path, os.path.realpath(protected)) or (
            os.path.normcase(path) == os.path.normcase(os.path.realpath(protected))
        ):
            raise FreeTaskAdapterError(
                _CODE_PREFIX + "db_path_forbidden",
                "禁止使用生产数据目录",
            )


def validate_synthetic_db_path(candidate: Any, sandbox_root: Any) -> str:
    """校验 ``candidate`` 是一个位于 ``sandbox_root`` 内的 **合成** 数据库路径。

    本函数 **只验证、绝不创建**：不 ``mkdir``、不 ``open``、不 ``touch``、
    不建符号链接。成功时返回规范化后的绝对路径字符串。

    拒绝清单（fail closed，绝不猜测）：

    - ``sandbox_root`` 不是字符串/PathLike，或不存在，或不是目录，
      或本身是符号链接 / junction / reparse point（必须是“真实目录”）；
    - ``candidate`` 不是字符串/PathLike、含 NUL、或为空白；
    - ``candidate`` 含 ``..`` 段（相对路径越界尝试一律拒绝）；
    - ``candidate`` 解析后 **不在** ``sandbox_root`` 内，或恰好等于
      ``sandbox_root`` 本身（必须严格在内）；
    - 从 root 到目标的 **任一已存在** 路径段是符号链接 / Windows junction /
      reparse point（链接中转一律拒绝）；
    - 目标已存在且是目录；
    - 目标已存在且 ``st_nlink > 1``（存在硬链接别名 → 拒绝）；
    - 目标名（大小写不敏感）为 ``task_publisher.db`` /
      ``task_publisher.db-wal`` / ``task_publisher.db-shm``；
    - 目标落在生产数据目录 ``<project>/data`` 之内；
    - 任何路径元数据无法可靠读取的异常情形。

    合法情形：``sandbox_root`` 内一个 **尚不存在** 的 ``*.db`` 路径
    （父目录可已存在或尚不存在）。

    错误一律抛 :class:`FreeTaskAdapterError`，``code`` 以 ``adapter_`` 开头。
    """
    # --- sandbox_root 必须是已存在的真实目录 ----------------------------
    if isinstance(sandbox_root, bool) or not isinstance(
        sandbox_root, (str, os.PathLike)
    ):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "sandbox_root_invalid", "sandbox_root 必须是字符串或 PathLike"
        )
    root_text = os.fspath(sandbox_root)
    if not isinstance(root_text, str) or not root_text.strip():
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "sandbox_root_invalid", "sandbox_root 必须是非空路径"
        )
    if "\x00" in root_text:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "sandbox_root_invalid", "sandbox_root 含 NUL 字符"
        )
    if not os.path.isdir(root_text):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "sandbox_root_missing",
            f"sandbox_root 必须是已经存在的真实目录: {root_text!r}",
        )
    if _is_reparse_or_link(root_text):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "sandbox_root_not_real",
            f"sandbox_root 本身是链接 / junction / reparse point，拒绝: {root_text!r}",
        )
    root_real = os.path.realpath(root_text)

    # --- candidate 形状 -------------------------------------------------
    if isinstance(candidate, bool) or not isinstance(candidate, (str, os.PathLike)):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_invalid", "candidate 必须是字符串或 PathLike"
        )
    cand_text = os.fspath(candidate)
    if not isinstance(cand_text, str) or not cand_text.strip():
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_invalid", "candidate 必须是非空路径"
        )
    if "\x00" in cand_text:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_invalid", "candidate 含 NUL 字符"
        )

    # --- 生产库文件名家族（大小写不敏感） --------------------------------
    basename = os.path.basename(cand_text.rstrip("\\/")).lower()
    if basename in FORBIDDEN_DB_BASENAMES:
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_forbidden",
            "禁止使用生产数据库文件名（task_publisher.db*）",
        )

    # --- 相对路径不得含 '..' -------------------------------------------
    if not os.path.isabs(cand_text):
        parts = cand_text.replace("\\", "/").split("/")
        if any(part == os.pardir for part in parts):
            raise FreeTaskAdapterError(
                _CODE_PREFIX + "db_path_escape",
                f"candidate 含 '..' 段，拒绝一切越界尝试: {cand_text!r}",
            )
    resolved = os.path.abspath(
        cand_text if os.path.isabs(cand_text) else os.path.join(root_real, cand_text)
    )

    # --- 严格包含关系 ---------------------------------------------------
    if not _is_strictly_inside(resolved, root_real):
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_outside_sandbox",
            f"candidate 必须严格位于 sandbox_root 之内: {cand_text!r}",
        )

    # --- 逐段检查已存在组件上的链接 ------------------------------------
    # 必须先于 realpath 一致性检查：junction / reparse point 会让
    # realpath 解析到别处，而“链路上存在链接”才是更精确的原因码。
    relative = os.path.relpath(resolved, root_real)
    walk = root_real
    for part in relative.split(os.sep):
        if part in ("", os.curdir):
            continue
        walk = os.path.join(walk, part)
        if not os.path.lexists(walk):
            break  # 尚未存在 ⇒ 其下也不可能存在链接
        if _is_reparse_or_link(walk):
            raise FreeTaskAdapterError(
                _CODE_PREFIX + "db_path_link_intermediate",
                f"路径段是符号链接 / junction / reparse point，拒绝: {walk!r}",
            )

    target_real = os.path.realpath(resolved)
    if os.path.normcase(target_real) != os.path.normcase(resolved):
        # realpath 解析后发生变化 ⇒ 链路上存在我们没能静态识别的重解析点
        # （例如映射到别处的挂载点）→ 无法可靠验证，拒绝而不是猜测。
        raise FreeTaskAdapterError(
            _CODE_PREFIX + "db_path_unverifiable",
            f"解析后的路径与声明路径不一致，可能存在未识别的链接，拒绝: {cand_text!r}",
        )
    _assert_not_protected(target_real)

    # --- 目标自身的检查（存在时） ---------------------------------------
    st = _lstat_or_none(resolved)
    if st is not None:
        if stat_module.S_ISDIR(st.st_mode):
            raise FreeTaskAdapterError(
                _CODE_PREFIX + "db_path_is_directory",
                "candidate 已存在且是目录，不是数据库文件路径",
            )
        nlink = getattr(st, "st_nlink", 0)
        if isinstance(nlink, int) and nlink > 1:
            raise FreeTaskAdapterError(
                _CODE_PREFIX + "db_path_hardlinked",
                f"candidate 已存在硬链接别名（st_nlink={nlink}），拒绝: {resolved!r}",
            )

    return resolved


__all__ = [
    "APPEND_ALLOWED_KEYS",
    "FORBIDDEN_DB_BASENAMES",
    "SUMMARY_ALLOWED_KEYS",
    "SUPPORTED_ACTIONS",
    "FreeTaskAdapter",
    "FreeTaskAdapterError",
    "validate_synthetic_db_path",
]