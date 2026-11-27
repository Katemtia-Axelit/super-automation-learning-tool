"""tests/e2e/synthetic_audit.py — 合成服务器的 **访问审计**（Stage 0 / AR03-P2）。

为什么存在
----------
项目的最高数据保护要求是：**不读取、不写入、不复制、不哈希、不恢复**真实
生产 SQLite 数据库及其 WAL/SHM、Obsidian 知识库与生产配置。

旧的隔离验证器用「运行前后对生产文件做只读 SHA-256 指纹比对」来证明零
触碰 —— 这本身就是一次读取，违反红线。

本模块把证明方式改成 **server 侧审计**：在合成服务器进程内安装
``sys.addaudithook``，记录进程真实发生的

* ``sqlite3.connect`` 目标路径
* ``open`` / ``os.listdir`` / ``os.scandir`` / ``os.stat`` 触达的路径

并把它们写进合成根内的审计清单文件。runner 读该清单做断言：

1. 没有任何访问落在 **真实项目根** 的 ``data/`` / ``config/`` / ``src/notes/``；
2. 没有任何 SQLite 连接落在合成根之外；
3. 清单文件本身只写在合成根内。

本模块 **只读**被审计进程的行为，不读取生产数据内容。

用法
----
由 ``tests/e2e/factory-sandbox-server.py`` 在启动子进程前安装；子进程通过
环境变量拿到真实项目根与审计输出路径。

环境变量
--------
``SAL_AUDIT_REAL_ROOT``
    真实项目根绝对路径（用于判定"越界访问"）。
``SAL_AUDIT_OUTPUT``
    审计清单输出文件绝对路径（**必须**位于合成根内）。
``SAL_AUDIT_SYNTHETIC_ROOT``
    合成根绝对路径（用于判定"是否越出合成环境"）。
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Set

#: 受保护的真实项目相对路径前缀。
PROTECTED_PREFIXES = (
    ("data",),
    ("config",),
    ("src", "notes"),
)

#: 记录到的访问类型。
_KIND_SQLITE = "sqlite3.connect"
_KIND_OPEN = "open"
_KIND_LISTDIR = "os.listdir"
_KIND_SCANDIR = "os.scandir"
_KIND_STAT = "os.stat"

_AUDITED_KINDS = (
    _KIND_SQLITE,
    _KIND_OPEN,
    _KIND_LISTDIR,
    _KIND_SCANDIR,
    _KIND_STAT,
)

_lock = threading.Lock()
_records: List[Dict[str, Any]] = []
_installed = False


def _norm(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(path))
    except (OSError, ValueError):
        return ""


def _relative_parts(root: str, target: str) -> List[str]:
    try:
        rel = os.path.relpath(target, root)
    except (ValueError, OSError):
        return []
    if rel == "." or rel.startswith(".."):
        return []
    return [p for p in rel.split(os.sep) if p]


def _is_under(root: str, target: str) -> bool:
    """target 是否严格位于 root 之内（root 自身不算）。"""
    if not root or not target:
        return False
    try:
        common = os.path.commonpath([_norm(root), _norm(target)])
    except (ValueError, OSError):
        return False
    return _norm(common) == _norm(root) and _norm(target) != _norm(root)


def _within(root: str, target: str) -> bool:
    """target 是否位于 root 之内或 **就是** root 自身。"""
    if not root or not target:
        return False
    try:
        common = os.path.commonpath([_norm(root), _norm(target)])
    except (ValueError, OSError):
        return False
    return _norm(common) == _norm(root)


def _matches_protected(real_root: str, target: str) -> bool:
    """target 是否落在真实项目根的受保护区域内。"""
    if not real_root or not target:
        return False
    if not _is_under(real_root, target):
        return False
    parts = _relative_parts(real_root, target)
    if not parts:
        return False
    for prefix in PROTECTED_PREFIXES:
        if len(parts) >= len(prefix) and tuple(parts[: len(prefix)]) == prefix:
            return True
    return False


def _audit(event: str, args: tuple) -> None:
    if event not in _AUDITED_KINDS:
        return
    raw: Any = args[0] if args else None
    if isinstance(raw, int):  # file descriptor
        return
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return
    if not isinstance(raw, (str, os.PathLike)):
        return
    try:
        target = _norm(os.fspath(raw))
    except (TypeError, ValueError):
        return
    if not target:
        return
    with _lock:
        _records.append({"kind": event, "path": target})


def install() -> bool:
    """安装审计钩子。幂等。返回是否成功安装。"""
    global _installed
    if _installed:
        return True
    try:
        sys.addaudithook(_audit)
    except Exception:  # noqa: BLE001 — 审计钩子装不上就必须 fail closed
        return False
    _installed = True
    return True


def flush(output_path: str) -> Dict[str, Any]:
    """把审计记录写盘并返回摘要。

    输出文件 **必须** 位于合成根内（调用方保证）；这里再断言一次。
    """
    real_root = os.environ.get("SAL_AUDIT_REAL_ROOT", "")
    synthetic_root = os.environ.get("SAL_AUDIT_SYNTHETIC_ROOT", "")

    with _lock:
        records = list(_records)

    violations: List[Dict[str, str]] = []
    outside_synthetic: List[Dict[str, str]] = []
    for record in records:
        target = record["path"]
        if _matches_protected(real_root, target):
            violations.append(record)
        elif record["kind"] == _KIND_SQLITE and synthetic_root:
            if not _is_under(synthetic_root, target):
                outside_synthetic.append(record)

    summary: Dict[str, Any] = {
        "real_root": real_root,
        "synthetic_root": synthetic_root,
        "record_count": len(records),
        "protected_violations": violations,
        "sqlite_outside_synthetic": outside_synthetic,
        "records": records,
    }

    if output_path:
        out = Path(output_path)
        # 输出文件必须位于合成根之内（**允许** 直接位于合成根本身之下）。
        if synthetic_root and not _within(synthetic_root, str(out)):
            raise RuntimeError(
                "audit output must live inside the synthetic root: " + str(out)
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return summary


def install_from_env() -> bool:
    """按环境变量安装审计钩子并注册退出时落盘。"""
    output = os.environ.get("SAL_AUDIT_OUTPUT", "")
    if not install():
        return False
    if output:
        import atexit

        def _dump() -> None:
            try:
                flush(output)
            except Exception:  # noqa: BLE001
                pass

        atexit.register(_dump)
    return True


__all__ = [
    "PROTECTED_PREFIXES",
    "flush",
    "install",
    "install_from_env",
]
