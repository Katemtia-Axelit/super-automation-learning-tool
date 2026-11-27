"""server.services.config — 配置域的业务编排。

AR03-P2 / Stage 5
-----------------
Stage 5 之前，配置域（``GET /api/config`` / ``POST /api/config/save``）
完全住在 legacy 单体 ``server/backend_api.py`` 里，由兼容桥转发。

Stage 5 把它变成 **真 Blueprint**，并把业务规则下沉到本模块：

* **读取**：只暴露 **脱敏** 后的配置（API key 只回 ``has_openai_key`` /
  ``has_claude_key`` 布尔值，**绝不**回显 key 本身）；
* **写入**：把扁平的 API 相关字段合并到 ``api`` 子对象、把 ``bed_time``
  合并到 ``obsidian`` 子对象，再做 **深度合并** 落盘。

安全边界
--------
* 本模块只写 ``config/config.json``；**绝不**触碰
  ``data/task_publisher.db*`` 与 ``src/notes/**``；
* 写入采用 **原子替换**（先写临时文件再 ``os.replace``）——
  避免写到一半崩溃留下损坏的配置文件。

配置路径
--------
配置文件路径 **不写死** 在本模块，而是由调用方（Blueprint）从
``app.config`` 解析：``app.config["_config_path"]`` → 合成根内的配置路径；
没有时回落到 :func:`server.app.config.config_path`。
这样合成环境（``%TEMP%`` 根）不会写到真实项目的 ``config/config.json``。
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "API_SCOPED_FIELDS",
    "build_config_view",
    "merge_config_payload",
    "resolve_config_path",
    "save_config",
]


#: 扁平化请求体里 **属于** ``api`` 子对象的字段。
API_SCOPED_FIELDS = ("openai_api_key", "claude_api_key", "api_base", "model")

#: 扁平化请求体里 **属于** ``obsidian`` 子对象的字段。
OBSIDIAN_SCOPED_FIELDS = ("bed_time",)


def resolve_config_path(app_config: Optional[Dict[str, Any]] = None) -> str:
    """解析配置文件绝对路径。

    优先 ``app_config["_config_path"]``（合成环境注入）；
    否则回落到 ``server.app.config.config_path()``。
    """
    if app_config:
        injected = app_config.get("_config_path")
        if injected:
            return str(injected)
    from server.app.config import config_path

    return config_path()


def build_config_view(config: Dict[str, Any]) -> Dict[str, Any]:
    """构造 ``GET /api/config`` 的响应体（**脱敏**）。

    响应字段（与 legacy 逐条一致）：

    * ``port`` / ``notes_directory`` / ``vault_path``
    * ``has_openai_key`` / ``has_claude_key`` —— **只有布尔值**，
      绝不回显 key 本身；
    * ``api_base`` / ``model``（缺省值与 legacy 一致）。

    数据来源
    --------
    ``config`` 是 **应用的完整配置 dict**（含 ``server`` / ``obsidian`` /
    ``api`` 三个子对象 **以及** 派生键 ``_notes_dir`` / ``_db_path`` 等）。

    ``notes_directory`` / ``vault_path`` 取自 ``obsidian`` 子对象 —— 与
    legacy 的 ``CONFIG['obsidian']['notes_directory']`` /
    ``CONFIG['obsidian']['vault_path']`` **逐字一致**。
    """
    api = config.get("api") or {}
    obsidian = config.get("obsidian") or {}
    server = config.get("server") or {}
    return {
        "port": server.get("port"),
        "notes_directory": obsidian.get("notes_directory"),
        "vault_path": obsidian.get("vault_path"),
        "has_openai_key": bool(api.get("openai_api_key")),
        "has_claude_key": bool(api.get("claude_api_key")),
        "api_base": api.get("api_base", "https://api.openai.com/v1"),
        "model": api.get("model", "gpt-4o-mini"),
    }


def merge_config_payload(
    existing: Dict[str, Any], data: Dict[str, Any]
) -> Dict[str, Any]:
    """把请求体 **深度合并** 进既有配置。

    合并规则（与 legacy ``api_save_config`` 逐条一致）：

    1. 扁平化的 API 字段（``openai_api_key`` / ``claude_api_key`` /
       ``api_base`` / ``model``）→ 合并进 ``api`` 子对象；
    2. ``bed_time`` → 合并进 ``obsidian`` 子对象；
    3. 其余键：两侧都是 dict → 逐子键更新；否则整块替换。

    **不修改** 入参（返回新 dict）。
    """
    merged: Dict[str, Any] = {
        key: (dict(value) if isinstance(value, dict) else value)
        for key, value in existing.items()
    }
    payload: Dict[str, Any] = dict(data)

    for key in list(payload.keys()):
        if key in API_SCOPED_FIELDS:
            merged.setdefault("api", {})[key] = payload.pop(key)
        if key in OBSIDIAN_SCOPED_FIELDS:
            merged.setdefault("obsidian", {})[key] = payload.pop(key)

    for key, value in payload.items():
        if (
            key in merged
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def save_config(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """把配置 **原子** 写入 ``path``。

    返回 ``{"success": True, "message": "Config saved successfully"}``。

    失败时抛异常（调用方负责转成 200 + ``success: False`` —— 与 legacy
    的错误语义逐条一致）。
    """
    existing: Dict[str, Any] = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            existing = loaded

    merged = merge_config_payload(existing, data)

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    # 原子替换：先写同目录临时文件，再 os.replace —— 崩溃时不会留下半个文件。
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        prefix=".config-",
        suffix=".tmp",
        delete=False,
    )
    temp_path = handle.name
    try:
        with handle:
            json.dump(merged, handle, ensure_ascii=False, indent=4)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return {"success": True, "message": "Config saved successfully"}
