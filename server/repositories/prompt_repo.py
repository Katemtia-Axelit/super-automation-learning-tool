"""server.repositories.prompt_repo — Prompts 域的文件系统访问。

AR03-P2 / Stage 6
-----------------
Stage 6 之前，Prompts 域（5 条路由）完全住在 legacy 单体
``server/backend_api.py`` 里，由兼容桥转发。

本模块承接 **所有** 与 prompts 目录相关的文件 IO：

* 列出 ``.md`` 提示词文件；
* 读取单个提示词；
* **原子写**（先写 ``.tmp`` 再 ``os.replace``）；
* **时间戳备份**（``<name>.<ts>.<kind>.bak.md``）；
* 找出 **最新** 备份（兼容旧的 ``*.bak.md`` 格式）。

设计约束
--------
* 本模块 **只** 操作调用方传入的 ``prompts_dir`` 之下；
* 文件名 **必须** 先过 :func:`server.services.prompts.safe_basename`
  之类的白名单校验（路径穿越防护）—— 本模块对路径做 **二次** 校验，
  纵深防御；
* 备份目录固定为 ``<prompts_dir>/.backups``。

本模块 **不** 决定"什么算合法文件名"（那是 service 层的职责），
也 **不** 决定"什么时候该备份"（同样是 service 层）。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

__all__ = [
    "BACKUP_SUBDIR",
    "create_backup",
    "file_metadata",
    "latest_backup_name",
    "list_prompt_files",
    "prompt_file_path",
    "read_prompt_file",
    "write_prompt_file",
]

#: 备份子目录名（相对 prompts 根）。
BACKUP_SUBDIR = ".backups"


def _safe_join(base: str, relative: str) -> Optional[str]:
    """把 ``relative`` 安全拼到 ``base`` 下；越界返回 ``None``。"""
    if not relative or not isinstance(relative, str):
        return None
    raw = relative.strip().replace("\\", "/").lstrip("/")
    if ".." in raw or raw.startswith(".."):
        return None
    candidate = os.path.abspath(os.path.join(base, raw))
    base_abs = os.path.abspath(base)
    if not candidate.startswith(base_abs + os.sep) and candidate != base_abs:
        return None
    return candidate


def prompt_file_path(prompts_dir: str, name: str) -> Optional[str]:
    """解析提示词文件绝对路径；非法名返回 ``None``。"""
    return _safe_join(prompts_dir, name)


def file_metadata(path: str) -> Dict[str, Any]:
    """返回 ``{"size": int, "mtime": iso}``。"""
    stat = os.stat(path)
    return {
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def list_prompt_files(prompts_dir: str) -> List[Dict[str, Any]]:
    """列出 prompts 目录下的 ``.md`` 文件（不含隐藏文件 / 备份目录）。

    返回 ``[{"name", "size", "mtime"}]``，按文件名排序。
    """
    files: List[Dict[str, Any]] = []
    if not os.path.isdir(prompts_dir):
        return files
    for fname in sorted(os.listdir(prompts_dir)):
        if fname.startswith(".") or not fname.endswith(".md"):
            continue
        fpath = os.path.join(prompts_dir, fname)
        if not os.path.isfile(fpath):
            continue
        meta = file_metadata(fpath)
        files.append({"name": fname, "size": meta["size"], "mtime": meta["mtime"]})
    return files


def read_prompt_file(prompts_dir: str, name: str) -> Optional[str]:
    """读取提示词内容；文件不存在返回 ``None``。"""
    fpath = prompt_file_path(prompts_dir, name)
    if not fpath or not os.path.isfile(fpath):
        return None
    with open(fpath, "r", encoding="utf-8") as handle:
        return handle.read()


def write_prompt_file(prompts_dir: str, name: str, content: str) -> None:
    """**原子** 写入提示词内容。

    先写同目录 ``<name>.tmp``，再 ``os.replace`` —— 崩溃时不会留下半个文件。
    失败时清理临时文件并向上抛 ``OSError``。
    """
    fpath = prompt_file_path(prompts_dir, name)
    if not fpath:
        raise OSError("非法文件名")
    directory = os.path.dirname(os.path.abspath(fpath))
    os.makedirs(directory, exist_ok=True)
    temp_path = fpath + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_path, fpath)
    except OSError:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def backup_dir(prompts_dir: str) -> str:
    """返回备份目录绝对路径（可能尚不存在）。"""
    return os.path.join(prompts_dir, BACKUP_SUBDIR)


def create_backup(prompts_dir: str, name: str, kind: str = "save") -> str:
    """把当前提示词内容复制成一份时间戳备份，返回备份文件名。

    备份名规则：``<name>.<YYYYmmdd-HHMMSS>.<kind>.bak.md``。
    """
    target_dir = backup_dir(prompts_dir)
    os.makedirs(target_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak_name = f"{name}.{stamp}.{kind}.bak.md"
    bak_path = os.path.join(target_dir, bak_name)
    fpath = prompt_file_path(prompts_dir, name)
    with open(fpath, "r", encoding="utf-8") as src:
        content = src.read()
    with open(bak_path, "w", encoding="utf-8") as dst:
        dst.write(content)
    return bak_name


def latest_backup_name(prompts_dir: str, name: str, kind: str = "save") -> Optional[str]:
    """找出最新的备份文件名；没有返回 ``None``。

    优先匹配 ``<name>.*.<kind>.bak.md``；没有时 **兼容** 旧格式
    ``<name>.*.bak.md``（不含 ``.save.`` / ``.restore.`` 标记）。
    """
    target_dir = backup_dir(prompts_dir)
    if not os.path.isdir(target_dir):
        return None
    prefix = f"{name}."
    suffix = f".{kind}.bak.md"
    candidates = [
        entry
        for entry in os.listdir(target_dir)
        if entry.startswith(prefix)
        and entry.endswith(suffix)
        and os.path.isfile(os.path.join(target_dir, entry))
    ]
    if not candidates:
        legacy = [
            entry
            for entry in os.listdir(target_dir)
            if entry.startswith(prefix)
            and entry.endswith(".bak.md")
            and ".save.bak.md" not in entry
            and ".restore.bak.md" not in entry
            and os.path.isfile(os.path.join(target_dir, entry))
        ]
        if not legacy:
            return None
        return max(legacy, key=lambda f: os.path.getmtime(os.path.join(target_dir, f)))
    return max(candidates, key=lambda f: os.path.getmtime(os.path.join(target_dir, f)))


def read_backup(prompts_dir: str, backup_name: str) -> Optional[str]:
    """读取指定备份文件的内容；不存在返回 ``None``。"""
    target_dir = backup_dir(prompts_dir)
    fpath = _safe_join(target_dir, backup_name)
    if not fpath or not os.path.isfile(fpath):
        return None
    with open(fpath, "r", encoding="utf-8") as handle:
        return handle.read()
