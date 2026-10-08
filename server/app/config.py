"""server.app.config - 配置加载（Phase 1 收紧版）.

设计：
- 返回 dict 而非 module-level CONFIG（避免循环 import + 便于测试 override）
- 路径全部基于 `项目根`（config/config.json 所在目录）
- 保持与原 backend_api.py 行为一致：端口 5000 / 路径 src/notes/...
"""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _default_config():
    return {
        "server": {"port": 5000, "host": "0.0.0.0", "debug": True},
        "obsidian": {
            "vault_path": "src/notes/vault",
            "notes_directory": "src/notes/vault",
        },
        "api": {"openai_api_key": "", "claude_api_key": ""},
        "database": {"task_db_path": "data/task_publisher.db"},
    }


def load_config():
    """Read config/config.json; fall back to defaults on missing/unreadable.

    Returns a dict augmented with derived keys:
    - _project_root: absolute path
    - _static_dir: absolute path of /static
    - _db_path: absolute path of sqlite db
    - _notes_dir: absolute path of obsidian notes dir
    """
    config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
    cfg = _default_config()
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # 浅合并：仅覆盖提供的 key
            for top in loaded:
                if isinstance(loaded[top], dict) and isinstance(cfg.get(top), dict):
                    cfg[top].update(loaded[top])
                else:
                    cfg[top] = loaded[top]
        except (json.JSONDecodeError, OSError):
            pass  # 用默认

    cfg["_project_root"] = PROJECT_ROOT
    cfg["_static_dir"] = os.path.join(PROJECT_ROOT, "static")
    cfg["_db_path"] = os.path.join(
        PROJECT_ROOT, cfg["database"].get("task_db_path", "data/task_publisher.db")
    )
    cfg["_notes_dir"] = cfg["obsidian"].get(
        "notes_directory", "src/notes/vault"
    )
    return cfg


__all__ = ["load_config", "PROJECT_ROOT"]
