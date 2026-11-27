"""AR03-P2 / Stage 8 —— 生成 P2 迁移映射（Blueprint → Service → Repository）。

读取 **实时 Factory** 的 url_map，按蓝图分组，并把每个蓝图引用的
Service / Repository 模块一并列出。输出 JSON 到 stdout。

用法::

    python scripts/_build_p2_migration_map.py > tests/fixtures/p2_migration_map.json
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "characterize"))

from sandbox_env import available_port, materialize, seed  # noqa: E402


def _imports_of(path: Path) -> list[str]:
    """列出该文件从 ``server.services`` / ``server.repositories`` 导入的
    **具体模块名**（``from server.services.tasks import x`` → ``services.tasks``；
    ``from server.services import tasks`` → ``services.tasks``）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod.startswith("server.services") or mod.startswith("server.repositories"):
                if mod.endswith(("services", "repositories")):
                    for alias in node.names:
                        out.add(f"{mod.split('.')[-1]}.{alias.name}")
                else:
                    out.add(mod.split("server.", 1)[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("server.services") or name.startswith(
                    "server.repositories"
                ):
                    out.add(name.split("server.", 1)[-1])
    return sorted(out)


def main() -> int:
    from tempfile import TemporaryDirectory

    temp = TemporaryDirectory(prefix="lt_p2map_", delete=False)
    root = materialize(Path(temp.name) / "sandbox", available_port())
    seed(root)
    os.chdir(root)
    sys.path.insert(0, str(root))

    from server.app import create_app

    cfg = {
        "server": {"host": "127.0.0.1", "port": 0, "debug": False},
        "obsidian": {"vault_path": "vault", "notes_directory": "vault"},
        "api": {"openai_api_key": "", "claude_api_key": ""},
        "database": {"task_db_path": "data/synthetic.sqlite3"},
        "_project_root": str(root),
        "_static_dir": str(root / "static"),
        "_db_path": str(root / "data" / "synthetic.sqlite3"),
        "_notes_dir": str(root / "vault"),
        "_config_path": str(root / "config" / "config.json"),
    }
    app = create_app(cfg)

    grouped: dict[str, list[dict]] = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        bp = rule.endpoint.split(".")[0]
        if "." not in rule.endpoint:
            bp = "(app-level)"
        methods = sorted(
            m for m in (rule.methods or set()) if m not in {"HEAD", "OPTIONS"}
        )
        grouped.setdefault(bp, []).append(
            {
                "rule": rule.rule,
                "methods": methods,
                "endpoint": rule.endpoint,
            }
        )

    layers = {}
    for bp_file in sorted((PROJECT_ROOT / "server" / "blueprints").glob("*_bp.py")):
        mod = bp_file.stem
        layers[mod] = {
            "blueprint": mod,
            "file": f"server/blueprints/{bp_file.name}",
            "imports": _imports_of(bp_file),
            "routes": sorted(
                grouped.get(bp_file.stem.replace("_bp", ""), []),
                key=lambda r: (r["rule"], r["methods"]),
            ),
        }

    app_level = grouped.get("(app-level)", [])

    # -- Service 层 → Repository 层 ---------------------------------------
    service_layers: dict[str, dict] = {}
    for svc_file in sorted((PROJECT_ROOT / "server" / "services").glob("*.py")):
        service_layers[svc_file.stem] = {
            "file": f"server/services/{svc_file.name}",
            "imports": _imports_of(svc_file),
        }
    repo_layers: dict[str, dict] = {}
    for repo_file in sorted((PROJECT_ROOT / "server" / "repositories").glob("*.py")):
        repo_layers[repo_file.stem] = {
            "file": f"server/repositories/{repo_file.name}",
            "imports": _imports_of(repo_file),
        }

    result = {
        "generated_by": "scripts/_build_p2_migration_map.py",
        "project_root": str(PROJECT_ROOT),
        "blueprint_count": len(layers),
        "app_level_routes": app_level,
        "blueprints": layers,
        "services": service_layers,
        "repositories": repo_layers,
        "service_modules": sorted(
            p.name for p in (PROJECT_ROOT / "server" / "services").glob("*.py")
        ),
        "repository_modules": sorted(
            p.name for p in (PROJECT_ROOT / "server" / "repositories").glob("*.py")
        ),
    }
    out_path = Path(
        os.environ.get(
            "P2_MAP_OUT",
            str(PROJECT_ROOT / "tests" / "fixtures" / "p2_migration_map.json"),
        )
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[P2MAP] written -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
