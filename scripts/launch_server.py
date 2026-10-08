"""Start the selected learning-tool backend and record its PID.

Factory is default. Set LEARNING_TOOL_BACKEND=legacy to revert without
editing code or touching the database.
"""
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.path.join(ROOT, ".run")
PID_FILE = os.path.join(RUN_DIR, "server.pid")
LOG_FILE = os.path.join(RUN_DIR, "server.log")


def select_entrypoint(root=ROOT, backend=None):
    mode = (backend or os.environ.get("LEARNING_TOOL_BACKEND", "factory")).lower().strip()
    if mode == "factory":
        return mode, os.path.join(root, "run_app.py")
    if mode == "legacy":
        return mode, os.path.join(root, "server", "backend_api.py")
    raise ValueError("LEARNING_TOOL_BACKEND must be factory or legacy")


def main():
    mode, entry = select_entrypoint()
    if not os.path.isfile(entry):
        raise FileNotFoundError("Backend entrypoint does not exist: " + entry)
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write("\n--- server start: " + mode + " ---\n")
        log.flush()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            [sys.executable, entry],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    with open(PID_FILE, "w", encoding="utf-8") as file:
        file.write(str(proc.pid))
    print("BACKEND=" + mode)
    print("SERVER_PID=" + str(proc.pid))
    print("LOG=" + LOG_FILE)


if __name__ == "__main__":
    main()
