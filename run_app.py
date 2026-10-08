"""run_app.py — Phase 2 launcher using create_app().

Run:
    .venv\\Scripts\\python.exe run_app.py

Same as `python server/backend_api.py` but uses the application factory
which registers all real BPs (tasks/gacha/tags + state/schedule/feedback/
timer/knowledge). Use this for verification (E2E / curl) since the legacy
`backend_api.py` has migrated routes commented out.
"""
from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.app import create_app
from server.app.config import load_config


app = create_app()


if __name__ == "__main__":
    cfg = load_config()
    port = cfg["server"]["port"]
    host = cfg["server"]["host"]
    print(f"[CONFIG] Using port: {port}")
    print(f"[CONFIG] Notes directory: {cfg['obsidian']['notes_directory']}")
    app.run(host=host, port=port, debug=False)