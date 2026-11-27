"""server.repositories.vault_repo — Vault / raw 目录的文件系统访问。

AR03-P2 / Stage 6
-----------------
Agent 域需要读取两类用户文件：

* **raw 域**：``未分类/`` 与 ``已分类/`` 下的 ``.txt``（录音转写等原始素材）；
* **vault 域**：笔记库下的 ``.md``（知识点笔记）。

本模块承接这两类目录的 **枚举与读取**。

设计约束
--------
* 所有相对路径 **必须** 先过路径穿越校验（拒绝 ``..``、绝对路径、
  越界路径），本模块做 **二次** 校验（纵深防御）；
* 只读 ``.txt``（raw）与 ``.md``（vault）；
* **只读** —— 本模块 **绝不** 写入 vault。AI 不得写 Obsidian 笔记
  （见 :mod:`server.services.agent` 与 ``/api/agent/save-note`` 的 403）。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

__all__ = [
    "classified_dir_for",
    "list_raw_txt_files",
    "list_vault_markdown_files",
    "read_raw_txt_file",
    "read_vault_markdown_file",
    "safe_raw_path",
    "safe_vault_path",
]


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


def classified_dir_for(notes_dir: str) -> str:
    """返回 ``已分类/`` 目录绝对路径（由 vault 根派生）。"""
    return os.path.join(notes_dir, "已分类")


def raw_dir_for(notes_dir: str) -> str:
    """返回 ``未分类/`` 目录绝对路径（由 vault 根派生）。"""
    return os.path.join(notes_dir, "未分类")


def safe_raw_path(
    rel: Any, notes_dir: str, raw_dir: Optional[str] = None,
    classified_dir: Optional[str] = None,
) -> Optional[str]:
    """把 raw 域相对路径解析为安全绝对路径；非法返回 ``None``。

    * ``已分类/xxx.txt`` → ``classified_dir`` 下；
    * 其它 → ``raw_dir`` 下；
    * 拒绝 ``..`` / 绝对路径 / 越界路径；
    * 只接受已存在的 ``.txt`` 文件。

    ``raw_dir`` / ``classified_dir`` 未显式给出时，由 ``notes_dir`` 派生。
    """
    if not rel or not isinstance(rel, str):
        return None
    raw = rel.strip().replace("\\", "/").lstrip("/")
    if ".." in raw or raw.startswith(".."):
        return None
    raw_base = raw_dir if raw_dir else raw_dir_for(notes_dir)
    classified_base = (
        classified_dir if classified_dir else classified_dir_for(notes_dir)
    )
    if raw.startswith("已分类/"):
        base = classified_base
        inner = raw[len("已分类/"):]
    elif raw.startswith("已分类"):
        base = classified_base
        inner = raw[len("已分类"):].lstrip("/")
    else:
        base = raw_base
        inner = raw
    fpath = _safe_join(base, inner)
    if fpath is None:
        return None
    if not fpath.endswith(".txt") or not os.path.isfile(fpath):
        return None
    return fpath


def safe_vault_path(rel: Any, notes_dir: str) -> Optional[str]:
    """把 vault 相对路径解析为安全绝对路径；非法返回 ``None``。

    * 拒绝 ``..`` / 越界路径；
    * 必须位于 ``notes_dir`` 之内；
    * 只接受 ``.md``；缺扩展名时尝试补 ``.md``。
    """
    if not rel or not isinstance(rel, str):
        return None
    raw = rel.strip().replace("\\", "/").lstrip("/")
    if ".." in raw:
        return None
    fpath = _safe_join(notes_dir, raw)
    if fpath is None:
        return None
    if not fpath.endswith(".md"):
        fpath_md = fpath + ".md"
        if os.path.isfile(fpath_md):
            fpath = fpath_md
        elif not os.path.isfile(fpath):
            return None
    elif not os.path.isfile(fpath):
        return None
    return fpath


def list_raw_txt_files(
    notes_dir: str, raw_dir: Optional[str] = None,
    classified_dir: Optional[str] = None, subdir: str = "",
) -> Dict[str, Any]:
    """列出 raw 域的 ``.txt`` 文件与子目录。

    **与 legacy ``api_list_raw_files`` 的响应形状逐条一致**：

    * ``{"subdirs": [...], "files": [...], "current": subdir}``；
    * ``subdirs`` 里的每一项是 ``{"name", "file_count"}``；
    * ``files`` 里的每一项是 ``{"name", "path", "size", "mtime"}``，
      其中 ``path`` 是 **相对当前 subdir** 的路径；
    * ``subdir`` 以 ``已分类`` 开头 → 落到 ``classified_dir``；
      其它非空 ``subdir`` → 落到 ``raw_dir/subdir``；
      空 → ``raw_dir`` 根；
    * 根级别时额外把 ``已分类`` 目录作为入口放进 ``subdirs``。

    ``raw_dir`` / ``classified_dir`` 未显式给出时，由 ``notes_dir`` 派生。
    """
    raw_base = raw_dir if raw_dir else raw_dir_for(notes_dir)
    classified_base = (
        classified_dir if classified_dir else classified_dir_for(notes_dir)
    )

    if subdir.startswith("已分类"):
        rel = subdir[len("已分类"):].lstrip("/")
        base = os.path.join(classified_base, rel) if rel else classified_base
    elif subdir:
        base = os.path.join(raw_base, subdir)
    else:
        base = raw_base

    if not os.path.exists(base):
        # 与 legacy 一致：目录不存在时 **不** 返回 ``current`` 键。
        return {"subdirs": [], "files": []}

    subdirs: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    for item in sorted(os.listdir(base)):
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path):
            txt_count = len(
                [f for f in os.listdir(item_path) if f.endswith(".txt")]
            )
            if txt_count > 0:
                subdirs.append({"name": item, "file_count": txt_count})
        elif item.endswith(".txt"):
            stat = os.stat(item_path)
            files.append(
                {
                    "name": item,
                    "path": (subdir + "/" + item) if subdir else item,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    # 根级别：额外显示 已分类 目录入口
    if not subdir and os.path.isdir(classified_base):
        classified_count = 0
        for entry in os.listdir(classified_base):
            entry_path = os.path.join(classified_base, entry)
            if os.path.isdir(entry_path):
                classified_count += len(
                    [f for f in os.listdir(entry_path) if f.endswith(".txt")]
                )
        if classified_count > 0:
            subdirs.append({"name": "已分类", "file_count": classified_count})

    return {"subdirs": subdirs, "files": files, "current": subdir}


def list_vault_markdown_files(notes_dir: str, subject: str = "") -> Dict[str, Any]:
    """列出 vault 中可供审查 / 处理的笔记。

    * ``subject`` 为空 → 列 vault 根；
    * 目录只列 **含 .md 的** 子目录；文件只列 ``.md``；
    * 隐藏目录（``.`` 开头）被跳过。
    """
    base = os.path.join(notes_dir, subject) if subject else notes_dir
    if not os.path.exists(base) or not os.path.isdir(base):
        # 与 legacy 一致：目录不存在时 **不** 返回 ``current`` 键。
        return {"dirs": [], "files": []}

    dirs: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    for item in sorted(os.listdir(base)):
        if item.startswith("."):
            continue
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path):
            md_count = len([f for f in os.listdir(item_path) if f.endswith(".md")])
            if md_count > 0:
                dirs.append({"name": item, "file_count": md_count})
        elif item.endswith(".md"):
            files.append(
                {
                    "name": item,
                    "path": (subject + "/" + item) if subject else item,
                    "size": os.path.getsize(item_path),
                }
            )
    return {"dirs": dirs, "files": files, "current": subject or ""}


def read_raw_txt_file(
    rel: Any, notes_dir: str, raw_dir: Optional[str] = None,
    classified_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """读取 raw ``.txt`` 内容；非法路径返回 ``None``。"""
    fpath = safe_raw_path(rel, notes_dir, raw_dir, classified_dir)
    if not fpath:
        return None
    with open(fpath, "r", encoding="utf-8", errors="replace") as handle:
        content = handle.read()
    return {"path": rel, "size": os.path.getsize(fpath), "content": content}


def read_vault_markdown_file(rel: Any, notes_dir: str) -> Optional[Dict[str, Any]]:
    """读取 vault ``.md`` 内容；非法路径返回 ``None``。"""
    fpath = safe_vault_path(rel, notes_dir)
    if not fpath:
        return None
    with open(fpath, "r", encoding="utf-8", errors="replace") as handle:
        content = handle.read()
    rel_out = os.path.relpath(fpath, notes_dir).replace("\\", "/")
    return {"path": rel_out, "size": os.path.getsize(fpath), "content": content}
