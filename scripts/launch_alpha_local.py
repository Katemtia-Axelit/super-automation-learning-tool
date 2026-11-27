"""Stable local-only Alpha launcher for the existing Learning Tool UI.

Never installs packages, kills processes, changes DB paths, copies user data,
or selects V28/V29 prototype assets. Factory's normal startup may apply its
usual idempotent schema checks; no migration code is added here.

Safety contract (LT_BOOTSTRAP_SAFE_LAUNCH_G1_20261022_C)
-------------------------------------------------------
The server-side bootstrap gate (``SAL_ENFORCE_AGENT_POLICY=1``) is forced on
for this process before the Flask app is created, so the Alpha launcher can
never serve an unprotected backend. Only this process is affected; the system
environment is not modified permanently. ``--check`` stays strictly read-only:
it returns before any app is created and never touches the database.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"

#: Server-side bootstrap gate switch (see server/services/agent_policy.py).
ENFORCE_ENV_VAR = "SAL_ENFORCE_AGENT_POLICY"


def enforce_agent_policy_gate() -> str:
    """Force the server-side bootstrap gate on for *this* process only.

    Returns the effective value. The system environment is not modified
    permanently; only ``os.environ`` of this process is, and the Flask app
    created later in :func:`main` reads it through ``create_app``.
    """
    os.environ[ENFORCE_ENV_VAR] = "1"
    return os.environ[ENFORCE_ENV_VAR]


def check_port_available(port: int) -> tuple[bool, str]:
    """Probe bind availability without killing/restarting existing listeners."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError as exc:
            return False, str(exc)
    return True, ""


def open_browser_when_ready(url: str) -> None:
    """Only open our local UI after the newly-started server responds."""
    health_url = url + "api/health"
    for _ in range(80):
        try:
            with urllib.request.urlopen(health_url, timeout=0.35) as response:
                if response.status == 200:
                    webbrowser.open(url, new=2)
                    print("[Alpha] Browser opened:", url, flush=True)
                    return
        except Exception:
            time.sleep(0.2)
    print("[Alpha] Browser auto-open timed out; visit", url, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe local learning tool launcher")
    parser.add_argument("--check", action="store_true", help="Read-only preflight; do not start Flask or open the database")
    parser.add_argument("--no-browser", action="store_true", help="Start Flask without opening a browser")
    args = parser.parse_args()

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from server.app.config import load_config

    cfg = load_config()
    port = cfg["server"].get("port", 5000)
    if type(port) is not int or not (1024 <= port <= 65535):
        print("[Alpha ERROR] Invalid configured port:", port, file=sys.stderr)
        return 2

    db = Path(cfg["_db_path"]).resolve()
    if not db.is_file():
        print("[Alpha ERROR] Existing task DB missing; refusing to create a new real DB.", file=sys.stderr)
        return 3

    available, error = check_port_available(port)
    print("[Alpha] Backend: Factory (existing production code)")
    print("[Alpha] Bind: http://127.0.0.1:{}/".format(port))
    print("[Alpha] Python:", sys.executable)
    print("[Alpha] Database: existing file present")
    print("[Alpha] Art: current original front-end only; V28/V29 not integrated")
    if not available:
        print("[Alpha ERROR] Port is already occupied; no process was stopped:", error, file=sys.stderr)
        return 4

    if args.check:
        print("[Alpha CHECK PASS] Preflight completed, no application started.")
        return 0

    # Explicitly override host in memory, never save back to config/config.json.
    cfg["server"]["host"] = HOST
    cfg["server"]["debug"] = False

    # Server-side bootstrap gate must be on before the Flask app exists.
    # (--check already returned above and never reached this point.)
    gate = enforce_agent_policy_gate()
    print("[Alpha] " + ENFORCE_ENV_VAR + "=" + gate + " (server-side bootstrap gate forced on)")

    from server.app import create_app
    app = create_app(cfg)
    url = "http://127.0.0.1:{}/".format(port)
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()

    print("[Alpha] Server starting; press Ctrl+C in this console to stop.")
    try:
        app.run(host=HOST, port=port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
