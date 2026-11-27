"""server.services.agent — Agent 域的业务编排。

AR03-P2 / Stage 6
-----------------
Stage 6 之前，Agent 域（9 条路由）完全住在 legacy 单体
``server/backend_api.py`` 里，由兼容桥转发。兼容桥还额外注入了一个
"禁止写 Obsidian"的 403 视图函数 —— 那是一种 **打补丁** 式的护栏，
容易在桥被删除时失效。

Stage 6 把它变成 **真 Blueprint**，并把业务规则下沉到本模块：

* **Agent 词表**（:data:`AGENT_CONFIG`）与标签词表；
* **文件清单**（raw / vault / prompts）→ :mod:`server.repositories.vault_repo`；
* **提示词解析** → :func:`resolve_prompt_path`；
* **产出解析与任务导入** → :func:`parse_import_payload` /
  :func:`import_tasks`；
* **"AI 不得写 Obsidian 笔记"** 的策略 → :func:`save_note_blocked`
  （**内建**，不再依赖兼容桥注入）。

产品边界（重要）
----------------
按 ``NO_API_AGENT_INTERACTION_PRODUCT_DIRECTION_20261023``：
Agent 交互的 **主路径** 是"复制提示词 → 外部聊天 → 手动粘贴产出回来"，
本应用 **不** 内置模型 API 作为默认路径。

因此：

* ``/api/agent/process``（服务端直接调 LLM）保留为 **可选** 能力，
  但它 **不** 是默认路径；
* ``/api/agent/import-tasks``（手动粘贴产出 → 解析 → 导入）是主路径；
* ``/api/agent/save-note`` **必须** 返回 **403** 且 **零文件写入**。

安全边界
--------
* 所有文件路径必须先过 :func:`safe_raw_path` / :func:`safe_vault_path`
  / :func:`safe_prompt_basename`，拒绝 ``..``、绝对路径、越界路径；
* raw 域只读 ``.txt``，vault 域只读 ``.md``；
* 本模块 **绝不** 写 vault。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from server.repositories import vault_repo
from server.repositories.db import service_transaction
from server.services import tasks as task_service

__all__ = [
    "ACTION_LABELS",
    "AGENT_CONFIG",
    "INPUT_TYPE_LABELS",
    "SUBJECT_MAP",
    "build_task_context",
    "build_task_context_action",
    "import_tasks",
    "import_tasks_action",
    "list_agents",
    "list_raw_files",
    "list_vault_files",
    "load_prompt",
    "parse_import_payload",
    "read_agent_prompt",
    "read_raw_file",
    "read_vault_file",
    "resolve_prompt_path",
    "safe_prompt_basename",
    "save_note_blocked",
]


# ---------------------------------------------------------------------------
# 词表
# ---------------------------------------------------------------------------

#: 科目缩写 → vault 目录名。
SUBJECT_MAP = {
    "高数": "高等数学",
    "大物": "大学物理",
    "线代": "线性代数",
    "英语": "英语四级",
    "英语四级": "英语四级",
    "计算机": "计算机",
    "电子技术": "电子技术",
}

#: Agent 清单。
AGENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "note_organizer": {
        "name": "笔记整理师",
        "desc": "读取原始录音转写文件，重构为结构化Markdown笔记",
        "icon": "fa-file-pen",
        "prompt_file": "笔记整理师",
        "input_type": "raw_file",
        "actions": ["save_note"],
    },
    "knowledge_extractor": {
        "name": "知识点整理师",
        "desc": "从已有笔记提取核心知识点，生成标准知识点文件",
        "icon": "fa-lightbulb",
        "prompt_file": "知识点整理师",
        "input_type": "vault_note",
        "actions": ["save_knowledge"],
    },
    "structure_reviewer": {
        "name": "结构审查师",
        "desc": "检查笔记格式、链接、Mermaid/Callout语法",
        "icon": "fa-check-double",
        "prompt_file": "结构审查师",
        "input_type": "vault_note",
        "actions": [],
    },
    "content_reviewer": {
        "name": "内容审查师",
        "desc": "检查事实准确性、逻辑一致性、可读性",
        "icon": "fa-magnifying-glass",
        "prompt_file": "内容审查师",
        "input_type": "vault_note",
        "actions": [],
    },
    "task_publisher": {
        "name": "AI任务发布",
        "desc": "用自然语言批量创建学习任务",
        "icon": "fa-wand-magic-sparkles",
        "prompt_file": "AI_assistant_prompt.md",
        "input_type": "text",
        "actions": ["import_tasks"],
    },
}

#: 输入类型标签。
INPUT_TYPE_LABELS = {
    "raw_file": "从未分类/已分类目录选择 txt 文件",
    "vault_note": "从 Vault 选择 Markdown 笔记",
    "text": "纯文本输入（自然语言）",
}

#: 动作标签。三个写动作 **全部标记为不可用** —— AI 不得写 Obsidian 笔记，
#: 也不得直接改任务库；产出由用户手动导入（``import_tasks``）。
ACTION_LABELS = {
    "save_note": "保存笔记到 Vault（写操作，本模式不可用）",
    "save_knowledge": "保存知识点到 Vault（写操作，本模式不可用）",
    "import_tasks": "导入任务（写操作，本模式不可用）",
}


# ---------------------------------------------------------------------------
# 路径安全（委托给 vault_repo，本模块保留同名薄封装）
# ---------------------------------------------------------------------------

def safe_raw_path(
    rel: Any, notes_dir: str, raw_dir: Optional[str] = None,
    classified_dir: Optional[str] = None,
) -> Optional[str]:
    """把 raw 域相对路径解析为安全绝对路径；非法返回 ``None``。"""
    return vault_repo.safe_raw_path(rel, notes_dir, raw_dir, classified_dir)


def safe_vault_path(rel: Any, notes_dir: str) -> Optional[str]:
    """把 vault 相对路径解析为安全绝对路径；非法返回 ``None``。"""
    return vault_repo.safe_vault_path(rel, notes_dir)


def safe_prompt_basename(name: Any) -> Optional[str]:
    """只允许 prompts 根目录下的 ``.md`` 文件名；非法返回 ``None``。"""
    from server.services import prompts as prompt_service

    return prompt_service.safe_basename(name)


def resolve_prompt_path(prompt_file: Any, prompts_dir: str) -> Optional[str]:
    """把提示词文件名解析为绝对路径；不存在返回 ``None``。

    找不到时尝试补 ``.md`` 扩展名。
    """
    if not prompt_file:
        return None
    base = os.path.join(prompts_dir, prompt_file)
    if os.path.isfile(base):
        return base
    if not str(prompt_file).endswith(".md"):
        alt = base + ".md"
        if os.path.isfile(alt):
            return alt
    return None


# ---------------------------------------------------------------------------
# 只读视图
# ---------------------------------------------------------------------------

def list_agents() -> List[Dict[str, Any]]:
    """列出可用 Agent（前端下拉框）。"""
    return [
        {
            "id": agent_id,
            "name": config.get("name", agent_id),
            "desc": config.get("desc", ""),
            "icon": config.get("icon", ""),
            "input_type": config.get("input_type", "text"),
            "input_type_label": INPUT_TYPE_LABELS.get(
                config.get("input_type", "text"), config.get("input_type", "text")
            ),
            "actions": list(config.get("actions", [])),
            "action_labels": [
                ACTION_LABELS.get(action, action)
                for action in config.get("actions", [])
            ],
            "prompt_file": config.get("prompt_file", ""),
        }
        for agent_id, config in AGENT_CONFIG.items()
    ]


def list_raw_files(
    notes_dir: str, raw_dir: Optional[str] = None,
    classified_dir: Optional[str] = None, subdir: str = "",
) -> Dict[str, Any]:
    """列出 raw 域的 ``.txt`` 文件与子目录。"""
    return vault_repo.list_raw_txt_files(
        notes_dir, raw_dir, classified_dir, subdir
    )


def list_vault_files(notes_dir: str, subject: str = "") -> Dict[str, Any]:
    """列出 vault 中可供审查 / 处理的笔记文件。"""
    return vault_repo.list_vault_markdown_files(notes_dir, subject)


def read_raw_file(
    rel: Any, notes_dir: str, raw_dir: Optional[str] = None,
    classified_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """读取 raw 域 ``.txt`` 内容；非法路径返回 ``None``。"""
    return vault_repo.read_raw_txt_file(rel, notes_dir, raw_dir, classified_dir)


def read_vault_file(rel: Any, notes_dir: str) -> Optional[Dict[str, Any]]:
    """读取 vault ``.md`` 内容；非法路径返回 ``None``。"""
    return vault_repo.read_vault_markdown_file(rel, notes_dir)


def load_prompt(agent_id: str, prompts_dir: str) -> Optional[str]:
    """读取某个 Agent 的 **提示词正文**；不存在返回 ``None``。

    与 :func:`read_agent_prompt` 的区别：后者返回 **结构化元信息**
    （含 ``exists`` 标记，供前端展示），本函数只给 "能不能拿到提示词
    正文" 用（例如 ``/api/agent/process``）。
    """
    config = AGENT_CONFIG.get(agent_id)
    if not config:
        return None
    prompt_path = resolve_prompt_path(config["prompt_file"], prompts_dir)
    if not prompt_path:
        return None
    with open(prompt_path, "r", encoding="utf-8") as handle:
        return handle.read()


def read_agent_prompt(
    agent_id: str, prompts_dir: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """读取某个 Agent 的提示词。

    返回 ``(payload, error)``：

    * 无效 Agent → ``(None, "无效的Agent")``；
    * 提示词文件不存在 → ``({"agent_id", "prompt_file", "exists": False,
      "content": "", "size": 0}, None)``（**不是** 错误）；
    * 成功 → ``({"agent_id", "prompt_file", "exists": True, "size",
      "content"}, None)``。
    """
    config = AGENT_CONFIG.get(agent_id)
    if not config:
        return None, "无效的Agent"
    prompt_path = resolve_prompt_path(config["prompt_file"], prompts_dir)
    if not prompt_path:
        return (
            {
                "agent_id": agent_id,
                "prompt_file": config["prompt_file"],
                "exists": False,
                "content": "",
                "size": 0,
            },
            None,
        )
    stat = os.stat(prompt_path)
    with open(prompt_path, "r", encoding="utf-8") as handle:
        content = handle.read()
    return (
        {
            "agent_id": agent_id,
            "prompt_file": os.path.basename(prompt_path),
            "exists": True,
            "size": stat.st_size,
            "content": content,
        },
        None,
    )


def build_task_context(conn) -> Optional[str]:
    """构建现有任务上下文，供任务发布 Agent 参考（含依赖关系）。

    没有未完成任务时返回 ``None``。
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, prerequisite_ids, is_unlocked, completed, repeat_type "
        "FROM tasks WHERE completed=0 ORDER BY id"
    )
    rows = [dict(row) for row in cursor.fetchall()]
    if not rows:
        return None
    lines = ["=== 现有任务列表（供参考，不要重复创建） ==="]
    for row in rows:
        try:
            prereqs = json.loads(row["prerequisite_ids"] or "[]")
        except (json.JSONDecodeError, TypeError):
            prereqs = []
        dep_str = f", 前置依赖: {prereqs}" if prereqs else ""
        status = "已锁定" if not row.get("is_unlocked") else "可用"
        lines.append(f'ID={row["id"]} [{status}] {row["name"]}{dep_str}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 产出导入（手动粘贴 → 解析 → 导入）
# ---------------------------------------------------------------------------

#: 从 Markdown 代码块里提取 JSON。
_JSON_BLOCK = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)

#: 难度中文 → 英文。
_RESISTANCE_MAP = {"低": "low", "中": "medium", "高": "high"}

#: 精力中文 → 英文。
_ENERGY_MAP = {"低": "low", "中": "medium", "高": "high"}


def parse_import_payload(raw_output: Any) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """解析 Agent 产出里的任务 JSON。

    返回 ``(tasks, error_message)``：

    * JSON 解析失败 → ``(None, "无法解析JSON，请确认输出格式")``；
    * 没有任务 → ``(None, "未找到可导入的任务")``；
    * 成功 → ``(tasks, None)``。

    兼容两种形状：``{"tasks": [...]}`` 与 ``{"task": {...}}``。
    """
    text = raw_output if isinstance(raw_output, str) else ""
    match = _JSON_BLOCK.search(text)
    raw_json = match.group(1) if match else text
    try:
        task_data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None, "无法解析JSON，请确认输出格式"
    if not isinstance(task_data, dict):
        return None, "无法解析JSON，请确认输出格式"
    tasks = task_data.get("tasks") or (
        [task_data.get("task")] if task_data.get("task") else []
    )
    if not tasks:
        return None, "未找到可导入的任务"
    return list(tasks), None


def _normalize_import_task(raw: Dict[str, Any]) -> Dict[str, Any]:
    """把一条 Agent 产出的任务归一为内部字段形状。"""
    difficulty = str(raw.get("difficulty", raw.get("resistance", "中")))
    energy = str(raw.get("energy_required", raw.get("energy", "中")))
    return {
        "name": raw.get("name", "未命名"),
        "category": raw.get("category", "daily"),
        "estimated_time": raw.get("estimated_time", 30),
        "deadline": raw.get("deadline"),
        "resistance": _RESISTANCE_MAP.get(difficulty, "medium"),
        "energy_required": _ENERGY_MAP.get(energy, "medium"),
        "priority": raw.get("priority", 5),
        "repeat_type": raw.get("repeat_type", "none"),
        "tags": raw.get("tags", []),
        "prerequisite_ids": raw.get("prerequisite_ids", []),
    }


def import_tasks(conn, raw_output: Any) -> Dict[str, Any]:
    """把 Agent 产出解析成任务并写入数据库。

    返回 ``{"imported": int, "tasks": [...], "errors": [...]}``。

    * 解析失败 → ``{"error": "..."}``（调用方转 400）；
    * 单条任务失败 **不** 中断整体导入，失败原因进 ``errors``。
    """
    tasks, error = parse_import_payload(raw_output)
    if error is not None:
        return {"error": error}

    imported: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for raw in tasks:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        payload = _normalize_import_task(raw)
        task_id, task_error = task_service.create_task(conn, payload)
        if task_error is not None or task_id is None:
            errors.append({"name": raw.get("name", "?"), "error": task_error or "创建失败"})
            continue
        imported.append({"id": task_id, "name": raw.get("name")})
    return {"imported": len(imported), "tasks": imported, "errors": errors}


# ---------------------------------------------------------------------------
# 自持事务的整体动作入口（AR03-P2 / P2 收尾）
# ---------------------------------------------------------------------------
#
# 事务边界 **下沉到 Service**：Blueprint 只做「解析请求 → 调 Service →
# 组装响应」。提交时机与迁移前逐条等价（退出 with 时提交，异常回滚）。


def build_task_context_action() -> Optional[str]:
    """只读：构建现有任务上下文。"""
    with service_transaction(commit=False) as conn:
        return build_task_context(conn)


def import_tasks_action(raw_output: Any) -> Dict[str, Any]:
    """把 Agent 产出解析成任务并写入（自持事务）。

    批量导入的 **多任务写入** 在 **同一连接、同一事务** 内完成 ——
    原子性与迁移前逐条等价。
    """
    with service_transaction() as conn:
        return import_tasks(conn, raw_output)


# ---------------------------------------------------------------------------
# 策略：AI 不得写 Obsidian 笔记
# ---------------------------------------------------------------------------

def save_note_blocked() -> Dict[str, Any]:
    """返回"AI 写笔记被拒绝"的错误载荷。

    **零副作用** —— 本函数 **不** 写任何文件。

    该策略由用户设定：AI 可以改动普通任务，但 **不得** 写入 Obsidian
    知识库。此前由兼容桥注入视图函数实现；Stage 6 起 **内建** 在
    真 Blueprint 里，不再依赖桥。
    """
    return {"error": "AI knowledge-base writes are disabled"}
