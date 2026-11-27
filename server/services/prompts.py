"""server.services.prompts — Prompts 域的业务编排。

AR03-P2 / Stage 6
-----------------
Stage 6 之前，Prompts 域（5 条路由）完全住在 legacy 单体
``server/backend_api.py`` 里，由兼容桥转发。

Stage 6 把它变成 **真 Blueprint**，并把业务规则下沉到本模块：

* **合法文件名判定**（防路径穿越）→ :func:`safe_basename`；
* **"要不要备份 / 备份成什么名字"** 的决策 → :func:`save_prompt` /
  :func:`restore_latest`；
* 文件 IO → :mod:`server.repositories.prompt_repo`。

安全边界
--------
* 文件名 **必须** 是 prompts 根目录下的纯 ``.md`` 文件名；
* 拒绝 ``..``、绝对路径、含 ``:`` 的路径、隐藏文件（``.`` 开头）；
* 备份目录固定 ``<prompts>/.backups``，**不** 允许直接编辑备份；
* 写入采用 **原子替换**。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from server.repositories import prompt_repo

__all__ = [
    "list_prompts",
    "read_prompt",
    "restore_latest",
    "safe_basename",
    "save_prompt",
]


def safe_basename(name: Any) -> Optional[str]:
    """只允许 prompts 根目录下的 ``.md`` 文件名；非法返回 ``None``。

    规则（与 legacy ``_safe_prompt_basename`` 逐条一致）：

    * 拒绝空值 / 非字符串；
    * 拒绝 ``..``、绝对路径、含 ``:`` 的路径；
    * 必须是 **纯文件名**（``basename(raw) == raw``）；
    * 必须以 ``.md`` 结尾；
    * 拒绝以 ``.`` 开头（含 ``.backups``）。
    """
    if not name or not isinstance(name, str):
        return None
    raw = name.strip().replace("\\", "/")
    if ".." in raw or raw.startswith("/") or ":" in raw:
        return None
    base = os.path.basename(raw)
    if base != raw or base.startswith("."):
        return None
    if not base.endswith(".md"):
        return None
    if ".backups" in base:
        return None
    return base


def list_prompts(prompts_dir: str) -> List[Dict[str, Any]]:
    """列出可编辑的提示词文件。"""
    return prompt_repo.list_prompt_files(prompts_dir)


def read_prompt(prompts_dir: str, name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """读取提示词。

    返回 ``(payload, error)``：

    * 非法文件名 → ``(None, "非法文件名")``；
    * 文件不存在 → ``(None, "文件不存在")``；
    * 成功 → ``({"name": safe, "content": ...}, None)``。
    """
    safe = safe_basename(name)
    if not safe:
        return None, "非法文件名"
    content = prompt_repo.read_prompt_file(prompts_dir, safe)
    if content is None:
        return None, "文件不存在"
    return {"name": safe, "content": content}, None


def save_prompt(
    prompts_dir: str, name: str, content: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """保存提示词（先备份，再原子写）。

    返回 ``(payload, error)``：

    * 非法文件名 → ``(None, "非法文件名")``；
    * 文件不存在 → ``(None, "文件不存在")``（**只允许编辑已存在的**）；
    * 成功 → ``({"saved": True, "name": safe, "backup": bak_name}, None)``。
    """
    safe = safe_basename(name)
    if not safe:
        return None, "非法文件名"
    fpath = prompt_repo.prompt_file_path(prompts_dir, safe)
    if not fpath or not os.path.isfile(fpath):
        return None, "文件不存在"
    backup_name = prompt_repo.create_backup(prompts_dir, safe, kind="save")
    prompt_repo.write_prompt_file(prompts_dir, safe, content)
    return {"saved": True, "name": safe, "backup": backup_name}, None


def latest_backup(prompts_dir: str, name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """查询最新备份信息。

    返回 ``(payload, error)``：

    * 非法文件名 → ``(None, "非法文件名")``；
    * 文件不存在 → ``(None, "文件不存在")``；
    * 没有备份 → ``({"exists": False, "name": safe}, None)``；
    * 有备份 → ``({"exists": True, "name", "backup_name", "size", "mtime"}, None)``。
    """
    safe = safe_basename(name)
    if not safe:
        return None, "非法文件名"
    fpath = prompt_repo.prompt_file_path(prompts_dir, safe)
    if not fpath or not os.path.isfile(fpath):
        return None, "文件不存在"
    backup_name = prompt_repo.latest_backup_name(prompts_dir, safe, kind="save")
    if not backup_name:
        return {"exists": False, "name": safe}, None
    bak_path = os.path.join(prompt_repo.backup_dir(prompts_dir), backup_name)
    meta = prompt_repo.file_metadata(bak_path)
    return {
        "exists": True,
        "name": safe,
        "backup_name": backup_name,
        "size": meta["size"],
        "mtime": meta["mtime"],
    }, None


def restore_latest(
    prompts_dir: str, name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """用最新备份恢复提示词。

    恢复前会 **再备份一次** 当前内容（``kind="restore"``），保证可回退。

    返回 ``(payload, error)``：

    * 非法文件名 → ``(None, "非法文件名")``；
    * 文件不存在 → ``(None, "文件不存在")``；
    * 没有备份 → ``(None, "无可用备份")``；
    * 成功 → ``({"restored": True, "name": safe, "backup_used": bak}, None)``。
    """
    safe = safe_basename(name)
    if not safe:
        return None, "非法文件名"
    fpath = prompt_repo.prompt_file_path(prompts_dir, safe)
    if not fpath or not os.path.isfile(fpath):
        return None, "文件不存在"
    backup_name = prompt_repo.latest_backup_name(prompts_dir, safe, kind="save")
    if not backup_name:
        return None, "无可用备份"
    content = prompt_repo.read_backup(prompts_dir, backup_name)
    if content is None:
        return None, "无可用备份"
    prompt_repo.create_backup(prompts_dir, safe, kind="restore")
    prompt_repo.write_prompt_file(prompts_dir, safe, content)
    return {"restored": True, "name": safe, "backup_used": backup_name}, None
