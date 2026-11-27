"""AR03-P2 / Stage 8 — 复现 E2E 里观察到的 ``500 /api/tasks/<id>``。

在 **合成根** 里启动真实 Factory（带可见日志），复现 E2E 的任务序列，
把服务端 traceback 抓出来。

用法::

    python scripts/_probe_task_get_500.py
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "characterize"))

from sandbox_env import available_port, materialize, seed  # noqa: E402


def main() -> int:
    temp = TemporaryDirectory(prefix="lt_probe_500_", delete=False)
    try:
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
        app.config["PROPAGATE_EXCEPTIONS"] = True
        client = app.test_client()

        def show(label, resp):
            print(label, resp.status_code, resp.get_data(as_text=True)[:400])
            return resp

        r = show("CREATE", client.post("/api/tasks", json={
            "name": "E2E测试任务-probe",
            "category": "daily",
            "estimated_time": 30,
        }))
        task_id = (r.get_json() or {}).get("id")

        show("PUT", client.put(f"/api/tasks/{task_id}",
                               json={"name": "E2E已编辑-probe"}))
        show("GET-edit", client.get(f"/api/tasks/{task_id}"))
        show("DELETE", client.delete(f"/api/tasks/{task_id}"))
        show("GET-after-delete", client.get(f"/api/tasks/{task_id}"))

        # 前端 deleteTask 先查 dependents。
        show("DEPENDENTS-after-delete",
             client.get(f"/api/tasks/{task_id}/dependents"))

        # 前端编辑器在编辑时可能带 task_type / prerequisite_ids。
        r2 = client.post("/api/tasks", json={
            "name": "E2E测试任务-probe2",
            "category": "daily",
            "estimated_time": 30,
            "task_type": "micro",
            "prerequisite_ids": [1],
        })
        show("CREATE2", r2)
        tid2 = (r2.get_json() or {}).get("id")
        show("GET2", client.get(f"/api/tasks/{tid2}"))

        # 直接触发服务层，看真实异常。
        from server.repositories import db as db_repo
        from server.services import tasks as tasks_service

        conn = db_repo.connect()
        try:
            for fn_name in ("get_task", "get_dependents"):
                try:
                    result = getattr(tasks_service, fn_name)(conn, tid2)
                    print(f"SERVICE {fn_name} ->", repr(result)[:200])
                except Exception:
                    print(f"SERVICE {fn_name} RAISED:")
                    traceback.print_exc()
        finally:
            conn.close()
    finally:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
