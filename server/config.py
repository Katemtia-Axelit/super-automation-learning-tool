"""server.config — central configuration loader.

Mirrors the original `load_config()` in `backend_api.py` so existing
behaviour is preserved (config file at `config/config.json`; fall-back
defaults baked in).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {"port": 5000, "host": "0.0.0.0", "debug": True},
    "obsidian": {
        "vault_path": "src/notes/vault",
        "notes_directory": "src/notes/vault",
    },
    "api": {"openai_api_key": "", "claude_api_key": ""},
    "database": {"task_db_path": "data/task_publisher.db"},
}


def _config_path() -> str:
    # server/ is one level under project root
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "config.json",
    )


def load_config(override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load project config from disk; merge any caller-provided overrides.

    Returns a deep-merged dict (top-level keys replaced, not deep-merged, to
    keep behaviour identical to the legacy loader).
    """
    cfg = dict(DEFAULT_CONFIG)
    p = _config_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    if override:
        cfg.update(override)
    return cfg