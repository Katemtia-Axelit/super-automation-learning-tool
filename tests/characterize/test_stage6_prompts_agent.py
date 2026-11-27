"""AR03-P2 / Stage 6 — Prompts 域 + Agent 域的 **分层契约** 与 **安全** 测试。

Stage 6 把 ``/api/agent/*``（9 条）与 ``/api/prompts/*``（5 条）从 legacy
单体迁到 **真 Blueprint**（``agent_bp`` / ``prompts_bp``），并把业务规则
下沉到 :mod:`server.services.agent` / :mod:`server.services.prompts`，
文件 IO 下沉到 :mod:`server.repositories.vault_repo` /
:mod:`server.repositories.prompt_repo`。

本文件锁定：

1. **分层方向** —— repo 不依赖 service / blueprint / Flask；
2. **兼容桥收口** —— ``PREFIX_ROUTES`` 已清空（桥不再挂载任何路由）；
3. **无 stub 残留** —— ``_STUB_BP_MODULES`` 已清空，14 个 BP 全是真 BP；
4. **AI 不得写 Obsidian** —— ``/api/agent/save-note`` 恒返回 **403**
   且 **零文件写入**（用户策略，内建于 BP，不再依赖兼容桥注入）；
5. **路径穿越防护** —— raw / vault / prompts 三条路径解析都拒绝
   ``..``、绝对路径与越界路径；
6. **提示词备份/恢复** —— 保存前自动备份，恢复前再备份一次；
7. **产出导入** —— 手动粘贴 JSON → 解析 → 写库；
8. **合成隔离** —— 全部读写落在合成根，**绝不**触碰生产的
   ``src/notes/**``（红线）。

全程 **不** 触碰生产数据库与生产配置：全部在
``tests/characterize/sandbox_env.py`` 的合成根内。
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tokenize
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BP_DIR = PROJECT_ROOT / "server" / "blueprints"
SERVICE_DIR = PROJECT_ROOT / "server" / "services"
REPO_DIR = PROJECT_ROOT / "server" / "repositories"
AI_DIR = PROJECT_ROOT / "server" / "ai"

#: Stage 6 新建的蓝图 / service / repo。
STAGE6_BLUEPRINTS = ("agent_bp.py", "prompts_bp.py")
STAGE6_SERVICES = ("agent.py", "prompts.py", "ai.py")
STAGE6_REPOSITORIES = ("vault_repo.py", "prompt_repo.py")


def _code_only(path: Path) -> str:
    """返回去掉注释与字符串字面量的代码（避免注释里的关键字误判）。"""
    out = []
    try:
        tokens = tokenize.generate_tokens(
            io.StringIO(path.read_text(encoding="utf-8")).readline
        )
        for token in tokens:
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(token.string)
    except (tokenize.TokenError, IndentationError):
        return path.read_text(encoding="utf-8")
    return " ".join(out)


class Stage6LayeringTests(unittest.TestCase):
    """1./2./3. 分层方向 + 兼容桥收口 + 无 stub 残留。"""

    def test_stage6_repos_have_no_upward_dependency(self):
        for name in STAGE6_REPOSITORIES:
            code = _code_only(REPO_DIR / name)
            for forbidden in (
                "server.services",
                "server.blueprints",
                "from flask",
                "import flask",
                "server.backend_api",
            ):
                self.assertNotIn(forbidden, code, f"{name} 依赖越界: {forbidden}")

    def test_stage6_services_have_no_flask_dependency(self):
        for name in STAGE6_SERVICES:
            code = _code_only(SERVICE_DIR / name)
            self.assertNotIn("from flask", code, f"{name} 依赖 Flask")
            self.assertNotIn("import flask", code, f"{name} 依赖 Flask")

    def test_stage6_blueprints_have_no_raw_sql(self):
        for name in STAGE6_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            for marker in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
                self.assertNotIn(marker, code, f"{name} 仍含裸 SQL: {marker}")
            self.assertNotIn(".execute(", code, f"{name} 直接执行 SQL")

    def test_stage6_blueprints_delegate_to_service(self):
        agent_text = (BP_DIR / "agent_bp.py").read_text(encoding="utf-8")
        prompts_text = (BP_DIR / "prompts_bp.py").read_text(encoding="utf-8")
        self.assertIn(
            "from server.services import agent as agent_service", agent_text
        )
        self.assertIn(
            "from server.services import prompts as prompt_service", prompts_text
        )

    def test_stage6_blueprints_do_not_import_backend_api(self):
        for name in STAGE6_BLUEPRINTS:
            code = _code_only(BP_DIR / name)
            self.assertNotIn(
                "server.backend_api", code, f"{name} 仍依赖 legacy 单体"
            )

    def test_compat_bridge_prefix_routes_is_empty(self):
        """Stage 6 后兼容桥的 ``PREFIX_ROUTES`` 已清空。

        **双形态**（AR03-P5）：兼容桥文件若已被归档，本断言改为校验
        「归档后 **无运行时引用**」—— 断言的是 **不变量**（零路由、
        零引用、零副作用），而 **不是** 「文件必须在原地」。
        """
        compat_path = PROJECT_ROOT / "server" / "app" / "legacy_compat.py"
        if not compat_path.is_file():
            # 归档分支：零运行时引用 + 归档登记
            offenders = []
            for path in (PROJECT_ROOT / "server").rglob("*.py"):
                if path.name == "legacy_compat.py":
                    continue
                code = _code_only(path)
                if "legacy_compat" in code or "register_legacy_compat" in code:
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))
            self.assertFalse(
                offenders,
                "兼容桥归档后仍存在运行时引用: " + ", ".join(offenders),
            )
            archived = list(
                (PROJECT_ROOT / "_archive").rglob("legacy_compat.py")
            )
            self.assertTrue(
                archived, "兼容桥归档后必须在 _archive/ 下可追溯"
            )
            return

        text = compat_path.read_text(encoding="utf-8")
        self.assertIn("PREFIX_ROUTES: tuple[str, ...] = ()", text)

    def test_blueprints_package_has_no_stub_modules(self):
        text = (BP_DIR / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("_STUB_BP_MODULES: set[str] = set()", text)

    def test_blueprints_all_are_real_blueprint_instances(self):
        """``server.blueprints.__all__`` 里的每一项都必须是 **真 Blueprint**。

        Stage 6 之前 ``prompts_bp`` / ``agent_bp`` 是 PEP 562 惰性 stub
        （模块内 **没有** Blueprint 实例），只做 legacy re-export。
        现在全部 14 个都是真 BP。

        **AR03-P2 / Stage 7 的口径**：``__all__`` 里放的是 **子模块名**
        （不是 Blueprint 实例）—— 因为部分模块保留了 **模块级** 的
        PEP 562 legacy 别名钩子（``api_xxx`` 旧名），只有包属性指向
        **模块** 时才可达。

        因此本断言改为：包属性解析为 **模块**，且该模块 **确实** 持有
        一个真 ``Blueprint`` 实例（``<name>.<name>``）。
        """
        import flask

        import server.blueprints as bp_package

        for name in bp_package.__all__:
            module = getattr(bp_package, name)
            self.assertTrue(
                hasattr(module, name),
                f"{name} 模块内没有名为 {name} 的 Blueprint 实例（仍是 stub？）",
            )
            instance = getattr(module, name)
            self.assertIsInstance(
                instance,
                flask.Blueprint,
                f"{name}.{name} 不是 Blueprint 实例（仍是 stub？）",
            )

    def test_blueprint_helper_returns_instances(self):
        """``blueprint(name)`` 助手必须返回该域的 Blueprint 实例。

        Blueprint 实例的 ``name`` 属性（``tasks`` / ``gacha`` / …）**不**
        必等于模块名（``tasks_bp`` / ``gacha_bp`` / …）—— 契约是
        "助手返回的就是该域注册用的那个实例"。
        """
        import flask

        import server.blueprints as bp_package
        from server.app.app_factory import REGISTERED_BLUEPRINTS

        registered = {id(bp) for bp in REGISTERED_BLUEPRINTS}
        for name in bp_package.__all__:
            instance = bp_package.blueprint(name)
            self.assertIsInstance(instance, flask.Blueprint)
            # 该实例必须 **正是** app_factory 注册的那一个。
            self.assertIn(
                id(instance),
                registered,
                f"{name} 的 Blueprint 实例未被 app_factory 注册",
            )

    def test_factory_registers_all_fourteen_blueprints(self):
        from server.app.app_factory import REGISTERED_BLUEPRINTS

        names = {bp.name for bp in REGISTERED_BLUEPRINTS}
        self.assertEqual(len(REGISTERED_BLUEPRINTS), 14, names)
        for expected in ("agent", "prompts"):
            self.assertIn(expected, names)

    def test_blueprints_all_is_aligned_with_factory(self):
        """``__all__`` 必须反映真实注册状态（P1 契约）。"""
        import server.blueprints as bp_package
        from server.app.app_factory import REGISTERED_BLUEPRINTS

        registered = {bp.name for bp in REGISTERED_BLUEPRINTS}
        exported = set(bp_package.__all__)
        self.assertEqual(len(bp_package.__all__), len(exported), "清单有重复项")
        # 每个导出的名字都必须能在包里取到（不再有 stub 惰性解析）
        for name in bp_package.__all__:
            self.assertTrue(hasattr(bp_package, name), f"{name} 未导出")
        self.assertEqual(
            registered,
            {"tasks", "gacha", "tags", "discard", "config", "index", "state",
             "timer", "schedule", "knowledge", "feedback", "agent_policy",
             "prompts", "agent"},
            registered,
        )


class PromptServiceUnitTests(unittest.TestCase):
    """5./6. 路径穿越防护 + 备份 / 恢复。"""

    def test_safe_basename_rejects_traversal(self):
        from server.services import prompts as prompt_service

        for bad in (
            "../secret.md",
            "..\\secret.md",
            "/etc/passwd.md",
            "sub/dir.md",
            "notes.md.txt",
            ".hidden.md",
            "",
            None,
            "C:/x.md",
        ):
            self.assertIsNone(
                prompt_service.safe_basename(bad), f"未拒绝: {bad!r}"
            )

    def test_safe_basename_accepts_plain_md(self):
        from server.services import prompts as prompt_service

        self.assertEqual(
            prompt_service.safe_basename("笔记整理师.md"), "笔记整理师.md"
        )

    def test_save_creates_backup_before_writing(self):
        from server.services import prompts as prompt_service

        with TemporaryDirectory(prefix="lt_prompt_") as temp:
            root = Path(temp)
            (root / "a.md").write_text("original", encoding="utf-8")
            payload, error = prompt_service.save_prompt(
                str(root), "a.md", "updated"
            )
            self.assertIsNone(error, error)
            self.assertTrue(payload["saved"])
            self.assertEqual(
                (root / "a.md").read_text(encoding="utf-8"), "updated"
            )
            backups = list((root / ".backups").glob("a.*.save.bak.md"))
            self.assertEqual(len(backups), 1, backups)
            self.assertEqual(
                backups[0].read_text(encoding="utf-8"), "original"
            )

    def test_save_refuses_to_create_new_file(self):
        from server.services import prompts as prompt_service

        with TemporaryDirectory(prefix="lt_prompt_") as temp:
            payload, error = prompt_service.save_prompt(
                str(temp), "missing.md", "x"
            )
            self.assertIsNone(payload)
            self.assertEqual(error, "文件不存在")

    def test_restore_latest_round_trips(self):
        from server.services import prompts as prompt_service

        with TemporaryDirectory(prefix="lt_prompt_") as temp:
            root = Path(temp)
            (root / "a.md").write_text("v1", encoding="utf-8")
            prompt_service.save_prompt(str(root), "a.md", "v2")
            payload, error = prompt_service.restore_latest(str(root), "a.md")
            self.assertIsNone(error, error)
            self.assertTrue(payload["restored"])
            self.assertEqual(
                (root / "a.md").read_text(encoding="utf-8"), "v1"
            )
            # 恢复前又备份了一次当前内容（可回退）
            restores = list((root / ".backups").glob("a.*.restore.bak.md"))
            self.assertEqual(len(restores), 1, restores)

    def test_restore_without_backup_reports_error(self):
        from server.services import prompts as prompt_service

        with TemporaryDirectory(prefix="lt_prompt_") as temp:
            root = Path(temp)
            (root / "a.md").write_text("v1", encoding="utf-8")
            payload, error = prompt_service.restore_latest(str(root), "a.md")
            self.assertIsNone(payload)
            self.assertEqual(error, "无可用备份")

    def test_write_leaves_no_temp_file(self):
        from server.services import prompts as prompt_service

        with TemporaryDirectory(prefix="lt_prompt_") as temp:
            root = Path(temp)
            (root / "a.md").write_text("v1", encoding="utf-8")
            prompt_service.save_prompt(str(root), "a.md", "v2")
            leftovers = [p.name for p in root.iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [], leftovers)


class VaultRepoPathSafetyTests(unittest.TestCase):
    """5. raw / vault 路径穿越防护。"""

    def test_safe_raw_path_rejects_traversal(self):
        from server.repositories import vault_repo

        with TemporaryDirectory(prefix="lt_vault_") as temp:
            root = Path(temp)
            raw_dir = root / "未分类"
            raw_dir.mkdir()
            (raw_dir / "ok.txt").write_text("x", encoding="utf-8")
            for bad in (
                "../secret.txt",
                "..\\secret.txt",
                "/abs/path.txt",
                "ok.md",
            ):
                self.assertIsNone(
                    vault_repo.safe_raw_path(bad, str(root)),
                    f"未拒绝: {bad!r}",
                )

    def test_safe_raw_path_accepts_txt_under_raw_dir(self):
        from server.repositories import vault_repo

        with TemporaryDirectory(prefix="lt_vault_") as temp:
            root = Path(temp)
            raw_dir = root / "未分类"
            raw_dir.mkdir()
            (raw_dir / "ok.txt").write_text("x", encoding="utf-8")
            resolved = vault_repo.safe_raw_path("ok.txt", str(root))
            self.assertIsNotNone(resolved)
            self.assertTrue(resolved.endswith("ok.txt"))

    def test_safe_vault_path_rejects_traversal(self):
        from server.repositories import vault_repo

        with TemporaryDirectory(prefix="lt_vault_") as temp:
            root = Path(temp)
            (root / "ok.md").write_text("x", encoding="utf-8")
            for bad in (
                "../outside.md",
                "..\\outside.md",
                "/etc/passwd.md",
            ):
                self.assertIsNone(
                    vault_repo.safe_vault_path(bad, str(root)),
                    f"未拒绝: {bad!r}",
                )

    def test_safe_vault_path_adds_md_extension(self):
        from server.repositories import vault_repo

        with TemporaryDirectory(prefix="lt_vault_") as temp:
            root = Path(temp)
            (root / "note.md").write_text("x", encoding="utf-8")
            resolved = vault_repo.safe_vault_path("note", str(root))
            self.assertIsNotNone(resolved)
            self.assertTrue(resolved.endswith("note.md"))


class AgentServiceUnitTests(unittest.TestCase):
    """7. 产出解析 + 导入归一。"""

    def test_parse_json_code_block(self):
        from server.services import agent as agent_service

        raw = '```json\n{"tasks": [{"name": "A"}]}\n```'
        tasks, error = agent_service.parse_import_payload(raw)
        self.assertIsNone(error, error)
        self.assertEqual(tasks, [{"name": "A"}])

    def test_parse_single_task_shape(self):
        from server.services import agent as agent_service

        tasks, error = agent_service.parse_import_payload('{"task": {"name": "B"}}')
        self.assertIsNone(error, error)
        self.assertEqual(tasks, [{"name": "B"}])

    def test_parse_invalid_json_reports_error(self):
        from server.services import agent as agent_service

        tasks, error = agent_service.parse_import_payload("not json at all")
        self.assertIsNone(tasks)
        self.assertEqual(error, "无法解析JSON，请确认输出格式")

    def test_parse_empty_reports_error(self):
        from server.services import agent as agent_service

        tasks, error = agent_service.parse_import_payload('{"tasks": []}')
        self.assertIsNone(tasks)
        self.assertEqual(error, "未找到可导入的任务")

    def test_save_note_blocked_payload(self):
        from server.services import agent as agent_service

        payload = agent_service.save_note_blocked()
        self.assertIn("error", payload)

    def test_agent_config_shape(self):
        from server.services import agent as agent_service

        self.assertIn("note_organizer", agent_service.AGENT_CONFIG)
        self.assertIn("task_publisher", agent_service.AGENT_CONFIG)
        for config in agent_service.AGENT_CONFIG.values():
            for key in ("name", "desc", "icon", "prompt_file", "input_type"):
                self.assertIn(key, config)


class LlmClientUnitTests(unittest.TestCase):
    """LLM 客户端的 **等价性** 契约（不发起真实网络请求）。"""

    def test_payload_matches_legacy_shape(self):
        from server.ai import llm_client

        import json as _json

        body = llm_client.build_chat_payload("sys", "usr", "gpt-4o-mini")
        payload = _json.loads(body.decode("utf-8"))
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "usr"},
            ],
        )

    def test_missing_key_raises_configuration_error(self):
        from server.ai import llm_client

        with self.assertRaises(llm_client.LLMConfigurationError):
            llm_client.resolve_api_credentials({})
        with self.assertRaises(llm_client.LLMConfigurationError):
            llm_client.resolve_api_credentials(None)

    def test_credentials_prefer_openai_key(self):
        from server.ai import llm_client

        creds = llm_client.resolve_api_credentials(
            {"openai_api_key": "sk-1", "claude_api_key": "ck-2"}
        )
        self.assertEqual(creds["api_key"], "sk-1")

    def test_credentials_fall_back_to_claude_key(self):
        from server.ai import llm_client

        creds = llm_client.resolve_api_credentials({"claude_api_key": "ck-2"})
        self.assertEqual(creds["api_key"], "ck-2")

    def test_llm_client_has_no_backend_api_dependency(self):
        code = _code_only(AI_DIR / "llm_client.py")
        self.assertNotIn("server.backend_api", code)


# ---------------------------------------------------------------------------
# 合成环境行为测试
# ---------------------------------------------------------------------------

_RUNNER = r'''
import json, os, sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from server.app import create_app

db = root / "data" / "stage6.sqlite3"
if db.exists():
    db.unlink()

notes_dir = root / "vault"
prompts_dir = root / "prompts"
raw_dir = root / "未分类"
classified_dir = root / "已分类"
for d in (notes_dir, prompts_dir, raw_dir, classified_dir):
    d.mkdir(parents=True, exist_ok=True)

(prompts_dir / "笔记整理师.md").write_text("PROMPT_ORIGINAL", encoding="utf-8")
(notes_dir / "note.md").write_text("VAULT_NOTE_BODY", encoding="utf-8")
(raw_dir / "a.txt").write_text("RAW_TXT_BODY", encoding="utf-8")

config_path = root / "config" / "config.json"

def make_cfg():
    return {
        "server": {"host": "127.0.0.1", "port": 0, "debug": False},
        "obsidian": {"vault_path": "vault", "notes_directory": "vault"},
        "api": {"openai_api_key": "", "claude_api_key": "",
                "api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
        "database": {"task_db_path": str(Path(db).relative_to(root))},
        "_project_root": str(root),
        "_static_dir": str(root / "static"),
        "_db_path": str(db),
        "_notes_dir": str(notes_dir),
        "_config_path": str(config_path),
        "_prompts_dir": str(prompts_dir),
        "_raw_dir": str(raw_dir),
        "_classified_dir": str(classified_dir),
    }

app = create_app(make_cfg())
client = app.test_client()
out = {}

# ---- 1. Agent 清单 --------------------------------------------------------
r = client.get("/api/agent/agents")
out["agents_status"] = r.status_code
out["agents"] = r.get_json(force=True)
out["agent_ids"] = sorted(a["id"] for a in out["agents"])
out["agent_has_actions"] = all("actions" in a for a in out["agents"])

# ---- 2. Agent 提示词读取 --------------------------------------------------
r = client.get("/api/agent/agents/note_organizer/prompt")
out["prompt_status"] = r.status_code
out["prompt_body"] = r.get_json(force=True)

r = client.get("/api/agent/agents/does_not_exist/prompt")
out["prompt_bad_status"] = r.status_code

# ---- 3. raw / vault 文件清单与内容 ----------------------------------------
r = client.get("/api/agent/files/raw")
out["raw_status"] = r.status_code
out["raw_body"] = r.get_json(force=True)

r = client.get("/api/agent/files/raw/content?path=a.txt")
out["raw_content_status"] = r.status_code
out["raw_content"] = r.get_json(force=True)

r = client.get("/api/agent/files/raw/content?path=../escape.txt")
out["raw_escape_status"] = r.status_code

r = client.get("/api/agent/files/vault")
out["vault_status"] = r.status_code
out["vault_body"] = r.get_json(force=True)

r = client.get("/api/agent/files/vault/content?path=note.md")
out["vault_content_status"] = r.status_code
out["vault_content"] = r.get_json(force=True)

r = client.get("/api/agent/files/vault/content?path=../escape.md")
out["vault_escape_status"] = r.status_code

# ---- 4. save-note 恒 403 且零写入 -----------------------------------------
vault_before = sorted(p.name for p in notes_dir.iterdir())
r = client.post("/api/agent/save-note",
                 json={"content": "HACKED", "filename": "hacked.md"})
out["save_note_status"] = r.status_code
out["save_note_body"] = r.get_json(force=True)
vault_after = sorted(p.name for p in notes_dir.iterdir())
out["save_note_no_file_written"] = vault_before == vault_after
out["save_note_content_absent"] = not (notes_dir / "hacked.md").exists()

# ---- 5. import-tasks：粘贴产出 → 写库 --------------------------------------
r = client.post("/api/agent/import-tasks", json={
    "output": '```json\n{"tasks": [{"name": "IMPORTED_ONE", "priority": 7}]}\n```'
})
out["import_status"] = r.status_code
out["import_body"] = r.get_json(force=True)

r = client.post("/api/agent/import-tasks", json={"output": "not json"})
out["import_bad_status"] = r.status_code
out["import_bad_body"] = r.get_json(force=True)

tasks = client.get("/api/tasks").get_json(force=True)
rows = tasks.get("tasks", tasks) if isinstance(tasks, dict) else tasks
out["imported_task_present"] = any(
    (t.get("name") == "IMPORTED_ONE") for t in rows
)

# ---- 6. Prompts 域 ---------------------------------------------------------
r = client.get("/api/prompts")
out["prompts_status"] = r.status_code
out["prompts_body"] = r.get_json(force=True)

r = client.get("/api/prompts/" + "笔记整理师.md")
out["prompt_get_status"] = r.status_code
out["prompt_get_body"] = r.get_json(force=True)

r = client.get("/api/prompts/../escape.md")
out["prompt_escape_status"] = r.status_code

r = client.put("/api/prompts/" + "笔记整理师.md", json={"content": "PROMPT_V2"})
out["prompt_put_status"] = r.status_code
out["prompt_put_body"] = r.get_json(force=True)
out["prompt_file_after_put"] = (
    prompts_dir / "笔记整理师.md"
).read_text(encoding="utf-8")

r = client.get("/api/prompts/" + "笔记整理师.md" + "/backup/latest")
out["backup_status"] = r.status_code
out["backup_body"] = r.get_json(force=True)

r = client.post("/api/prompts/" + "笔记整理师.md" + "/restore-latest")
out["restore_status"] = r.status_code
out["restore_body"] = r.get_json(force=True)
out["prompt_file_after_restore"] = (
    prompts_dir / "笔记整理师.md"
).read_text(encoding="utf-8")

# ---- 7. 兼容桥不再挂载任何路由 ---------------------------------------------
# AR03-P2 / Stage 7：兼容桥已从装配流程整体移除 → ``_compat_route_count``
# 这个配置键 **不再** 被写入（默认 app 上根本不存在）。断言它的缺席，
# 并直接调用墓碑函数证明它 **零路由、零副作用**。
#
# AR03-P5：**双形态** —— 兼容桥文件若已归档，则改为断言
# 「归档后无运行时引用」；若仍在原位，则校验墓碑不变量。
out["compat_route_count"] = app.config.get("_compat_route_count")

_compat_path = Path(root) / "server" / "app" / "legacy_compat.py"
out["compat_module_present"] = _compat_path.is_file()

if out["compat_module_present"]:
    from server.app import legacy_compat as compat_module

    out["compat_exact_routes"] = sorted(compat_module.EXACT_ROUTES)
    out["compat_prefix_routes"] = sorted(compat_module.PREFIX_ROUTES)
    out["compat_retired"] = bool(getattr(compat_module, "RETIRED", False))

    # 墓碑函数：调用它必须返回 0、不注册任何路由、不 import backend_api。
    from flask import Flask

    _probe_app = Flask(__name__)
    _rules_before = {
        (r.rule, m) for r in _probe_app.url_map.iter_rules()
        for m in r.methods - {"HEAD", "OPTIONS"}
    }
    out["compat_register_return"] = compat_module.register_legacy_compat(
        _probe_app,
        {"_project_root": str(root), "_db_path": str(root / "data" / "x.db")},
    )
    _rules_after = {
        (r.rule, m) for r in _probe_app.url_map.iter_rules()
        for m in r.methods - {"HEAD", "OPTIONS"}
    }
    out["compat_rules_added"] = sorted(
        f"{rule} {method}" for rule, method in (_rules_after - _rules_before)
    )
    out["compat_route_count_after_register"] = _probe_app.config.get(
        "_compat_route_count"
    )
else:
    # 归档分支：零路由 / 零副作用 / 零运行时引用。
    out["compat_exact_routes"] = []
    out["compat_prefix_routes"] = []
    out["compat_retired"] = True
    out["compat_register_return"] = 0
    out["compat_rules_added"] = []
    out["compat_route_count_after_register"] = None

    import ast as _ast

    _offenders = []
    for _p in (Path(root) / "server").rglob("*.py"):
        if _p.name == "legacy_compat.py":
            continue
        try:
            _tree = _ast.parse(_p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for _node in _ast.walk(_tree):
            if isinstance(_node, _ast.Import):
                for _alias in _node.names:
                    if _alias.name.endswith("legacy_compat"):
                        _offenders.append(
                            f"{_p.relative_to(root)}:{_node.lineno}"
                        )
            elif isinstance(_node, _ast.ImportFrom):
                _base = _node.module or ""
                if _base.endswith("legacy_compat"):
                    _offenders.append(f"{_p.relative_to(root)}:{_node.lineno}")
                for _alias in _node.names:
                    if _alias.name == "register_legacy_compat":
                        _offenders.append(
                            f"{_p.relative_to(root)}:{_node.lineno}"
                        )
    out["compat_runtime_references"] = sorted(_offenders)

# 写到文件而不是 stdout：Windows 控制台 stdout 的编码不一定是 UTF-8，
# 中文文件名会被解码成乱码（golden_snapshot.py 用的是同一个办法）。
(root / "_stage6_probe.json").write_text(
    json.dumps(out, ensure_ascii=False), encoding="utf-8"
)
print("PROBE_OK")
'''


def _run_probe() -> dict:
    with TemporaryDirectory(prefix="lt_stage6_") as temp:
        root = materialize(Path(temp) / "sandbox", available_port())
        seed(root)
        runner = root / "_stage6_probe.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        env = {
            k: v
            for k, v in os.environ.items()
            if (
                "API_KEY" not in k.upper()
                and "TOKEN" not in k.upper()
                and "SECRET" not in k.upper()
                and k.upper() not in ("PYTHONPATH", "PYTHONHOME")
            )
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-I", str(runner)],
            cwd=root,
            env=env,
            capture_output=True,
            timeout=120,
        )
        stdout = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
        stderr = proc.stderr.decode("utf-8", "replace") if proc.stderr else ""
        if proc.returncode != 0:
            raise AssertionError(f"probe 退出码非0: {stderr[-3000:]}")
        if "PROBE_OK" not in stdout:
            raise AssertionError(f"probe 未完成: {stdout[-3000:]}")
        payload_path = root / "_stage6_probe.json"
        if not payload_path.exists():
            raise AssertionError("probe 未写出结果文件")
        return json.loads(payload_path.read_text(encoding="utf-8"))


class Stage6BehaviorTests(unittest.TestCase):
    PROBE: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.PROBE = _run_probe()

    # -- Agent 只读端点 ----------------------------------------------------
    def test_agent_list_returns_the_five_agents(self):
        p = self.PROBE
        self.assertEqual(p["agents_status"], 200, p)
        self.assertEqual(
            p["agent_ids"],
            [
                "content_reviewer",
                "knowledge_extractor",
                "note_organizer",
                "structure_reviewer",
                "task_publisher",
            ],
            p,
        )
        self.assertTrue(p["agent_has_actions"], p)

    def test_agent_prompt_is_readable(self):
        p = self.PROBE
        self.assertEqual(p["prompt_status"], 200, p)
        self.assertTrue(p["prompt_body"]["exists"], p)
        self.assertEqual(p["prompt_body"]["content"], "PROMPT_ORIGINAL", p)

    def test_invalid_agent_prompt_returns_404(self):
        p = self.PROBE
        self.assertEqual(p["prompt_bad_status"], 404, p)

    def test_raw_files_are_listed_and_readable(self):
        """raw 域清单的形状与 legacy ``api_list_raw_files`` 逐条一致。

        * ``subdirs`` / ``files`` / ``current`` 三个键；
        * ``files[].path`` 是 **相对当前 subdir** 的路径（根级别 → 只有文件名）。
        """
        p = self.PROBE
        self.assertEqual(p["raw_status"], 200, p)
        self.assertIn("subdirs", p["raw_body"], p)
        self.assertIn("current", p["raw_body"], p)
        paths = [f["path"] for f in p["raw_body"]["files"]]
        self.assertIn("a.txt", paths, p)
        self.assertEqual(p["raw_content_status"], 200, p)
        self.assertEqual(p["raw_content"]["content"], "RAW_TXT_BODY", p)

    def test_vault_files_are_listed_and_readable(self):
        p = self.PROBE
        self.assertEqual(p["vault_status"], 200, p)
        names = [f["name"] for f in p["vault_body"]["files"]]
        self.assertIn("note.md", names, p)
        self.assertEqual(p["vault_content_status"], 200, p)
        self.assertEqual(p["vault_content"]["content"], "VAULT_NOTE_BODY", p)

    def test_path_traversal_is_rejected(self):
        p = self.PROBE
        self.assertEqual(p["raw_escape_status"], 400, p)
        self.assertEqual(p["vault_escape_status"], 400, p)

    # -- AI 不得写 Obsidian -------------------------------------------------
    def test_save_note_is_forbidden(self):
        """用户策略：AI 不得写 Obsidian 笔记 → 恒 403。"""
        p = self.PROBE
        self.assertEqual(p["save_note_status"], 403, p)
        self.assertIn("error", p["save_note_body"], p)

    def test_save_note_writes_nothing(self):
        """403 的同时 **零文件写入**。"""
        p = self.PROBE
        self.assertTrue(p["save_note_no_file_written"], p)
        self.assertTrue(p["save_note_content_absent"], p)

    # -- 产出导入 ----------------------------------------------------------
    def test_import_tasks_writes_to_db(self):
        p = self.PROBE
        self.assertEqual(p["import_status"], 200, p)
        self.assertEqual(p["import_body"]["imported"], 1, p)
        self.assertTrue(p["imported_task_present"], p)

    def test_import_tasks_rejects_invalid_json(self):
        p = self.PROBE
        self.assertEqual(p["import_bad_status"], 400, p)
        self.assertIn("error", p["import_bad_body"], p)

    # -- Prompts 域 --------------------------------------------------------
    def test_prompts_are_listed_and_readable(self):
        p = self.PROBE
        self.assertEqual(p["prompts_status"], 200, p)
        names = [f["name"] for f in p["prompts_body"]]
        self.assertIn("笔记整理师.md", names, p)
        self.assertEqual(p["prompt_get_status"], 200, p)
        self.assertEqual(p["prompt_get_body"]["content"], "PROMPT_ORIGINAL", p)

    def test_prompt_save_creates_backup(self):
        p = self.PROBE
        self.assertEqual(p["prompt_put_status"], 200, p)
        self.assertTrue(p["prompt_put_body"].get("saved"), p)
        self.assertIn("backup", p["prompt_put_body"], p)
        self.assertEqual(p["prompt_file_after_put"], "PROMPT_V2", p)
        self.assertEqual(p["backup_status"], 200, p)
        self.assertTrue(p["backup_body"]["exists"], p)

    def test_prompt_restore_latest(self):
        p = self.PROBE
        self.assertEqual(p["restore_status"], 200, p)
        self.assertTrue(p["restore_body"].get("restored"), p)
        self.assertEqual(p["prompt_file_after_restore"], "PROMPT_ORIGINAL", p)

    def test_prompt_traversal_is_rejected(self):
        p = self.PROBE
        self.assertEqual(p["prompt_escape_status"], 400, p)

    # -- 兼容桥 -----------------------------------------------------------
    def test_compat_bridge_mounts_no_routes(self):
        """兼容桥 **零路由、零副作用**，且已标记退役。

        AR03-P2 / Stage 7：兼容桥从装配流程整体移除 → ``_compat_route_count``
        配置键 **不再** 被写入（默认 app 上不存在），且墓碑函数被直接
        调用时也 **不得** 注册任何路由。
        """
        p = self.PROBE
        self.assertIsNone(
            p["compat_route_count"],
            "兼容桥已退出装配流程，不应再写入 _compat_route_count",
        )
        self.assertEqual(p["compat_exact_routes"], [], p)
        self.assertEqual(p["compat_prefix_routes"], [], p)
        self.assertTrue(p["compat_retired"], p)
        self.assertEqual(p["compat_register_return"], 0, p)
        self.assertEqual(p["compat_rules_added"], [], p)
        if p.get("compat_module_present"):
            # 文件保留：墓碑函数被调用后必须把计数写为 0。
            self.assertEqual(p["compat_route_count_after_register"], 0, p)
        else:
            # 文件已归档：无墓碑函数可调用 → 该键不存在，且必须 **零运行时引用**。
            self.assertIsNone(p["compat_route_count_after_register"], p)
            self.assertEqual(p.get("compat_runtime_references", []), [], p)


if __name__ == "__main__":
    unittest.main()
