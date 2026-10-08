"""Synthetic-only runtime harness. Never copies project data, config or notes."""
from __future__ import annotations
import contextlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from urllib.request import urlopen

SOURCE_ROOT = Path(__file__).resolve().parents[2]
SERVER_SOURCE = SOURCE_ROOT / "server"


def _is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    return path.is_symlink() or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def materialize(root: Path, port: int) -> Path:
    """Create independent source-only sandbox; fail closed on path tricks."""
    root = root.resolve(strict=False)
    source = SOURCE_ROOT.resolve(strict=True)
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Sandbox must be independent of actual project")
    if root.exists():
        raise FileExistsError("Sandbox destination must not exist")
    if _is_reparse(SERVER_SOURCE):
        raise ValueError("Source tree is a link/reparse point")
    # Scan first, then copy only .py to avoid copying secrets or private files.
    selected = []
    for dirpath, dirs, files in os.walk(SERVER_SOURCE, followlinks=False):
        directory = Path(dirpath)
        if _is_reparse(directory):
            raise ValueError("Linked source directory")
        checked = []
        for name in dirs:
            candidate = directory / name
            if _is_reparse(candidate):
                raise ValueError("Linked source directory")
            if name != "__pycache__":
                checked.append(name)
        dirs[:] = checked
        for filename in files:
            candidate = directory / filename
            if _is_reparse(candidate):
                raise ValueError("Linked source file")
            if candidate.suffix == ".py":
                selected.append((candidate, candidate.relative_to(SERVER_SOURCE)))
    root.mkdir(parents=True)
    (root / "server").mkdir()
    for original, rel in selected:
        output = root / "server" / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, output, follow_symlinks=False)
    (root / "static").mkdir()
    (root / "vault").mkdir()
    (root / "data").mkdir()
    (root / "config").mkdir()
    config = {
        "server": {"host": "127.0.0.1", "port": port, "debug": False},
        "database": {"task_db_path": "data/synthetic.sqlite3"},
        "obsidian": {"vault_path": "vault", "notes_directory": "vault"},
        "api": {"openai_api_key": "", "claude_api_key": ""},
    }
    (root / "config" / "config.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    return root


def seed(root: Path) -> None:
    """Synthetic SQLite schema. No DB file from the project is used."""
    db = root / "data" / "synthetic.sqlite3"
    if db.resolve().parent != (root / "data").resolve():
        raise ValueError("Unexpected DB path")
    conn = sqlite3.connect(db)
    try:
        conn.executescript("""
        CREATE TABLE tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL, category TEXT DEFAULT 'daily',
          task_type TEXT DEFAULT 'normal', description TEXT,
          estimated_time INTEGER DEFAULT 25, preferred_time TEXT, deadline TEXT,
          resistance TEXT DEFAULT 'medium', energy_required TEXT DEFAULT 'medium',
          rarity TEXT DEFAULT 'common', priority INTEGER DEFAULT 5,
          success_rate REAL DEFAULT 0.0, refusal_count INTEGER DEFAULT 0,
          is_daily INTEGER DEFAULT 0, completed INTEGER DEFAULT 0,
          repeat_type TEXT DEFAULT 'none', task_profile TEXT DEFAULT 'deadline_flexible',
          parent_task_id INTEGER, group_id INTEGER, last_completed_at TEXT,
          next_available_at TEXT, last_drawn_at TEXT, draw_count_today INTEGER DEFAULT 0,
          min_push_time TEXT DEFAULT '20:00', in_discard_pile INTEGER DEFAULT 0,
          completed_count INTEGER DEFAULT 0, tags TEXT,
          difficulty TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          prerequisite_ids TEXT DEFAULT '[]', is_unlocked INTEGER DEFAULT 1,
          linked_note_path TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);
        CREATE TABLE task_tags (task_id INTEGER, tag_id INTEGER);
        CREATE TABLE gacha_records (
          id INTEGER PRIMARY KEY, task_id INTEGER, pool TEXT,
          accepted INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO tasks (id,name,priority,completed,prerequisite_ids,is_unlocked)
        VALUES (1,'synthetic-parent',8,0,'[]',1);
        INSERT INTO tasks (id,name,priority,completed,prerequisite_ids,is_unlocked)
        VALUES (2,'synthetic-child',4,0,'[1]',0);
        INSERT INTO tasks (id,name,priority,completed,prerequisite_ids,is_unlocked)
        VALUES (3,'synthetic-standalone',3,0,'[]',1);
        INSERT INTO tasks (id,name,priority,completed,prerequisite_ids,is_unlocked)
        VALUES (4,'synthetic-locked',5,0,'[3]',0);
        INSERT INTO task_dependencies(task_id,depends_on_task_id) VALUES (2,1),(4,3);
        """.replace(
            "INSERT INTO task_dependencies(task_id,depends_on_task_id) VALUES (2,1),(4,3);",
            "CREATE TABLE task_dependencies (id INTEGER PRIMARY KEY, task_id INTEGER, depends_on_task_id INTEGER);"
            "INSERT INTO task_dependencies(task_id,depends_on_task_id) VALUES (2,1),(4,3);"
        ))
        conn.commit()
    finally:
        conn.close()


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def server(root: Path, mode: str, port: int):
    assert mode in {"legacy", "factory"}
    if mode == "legacy":
        runner = root / "server" / "backend_api.py"
        args = [sys.executable, "-I", str(runner)]
    else:
        runner = root / "_factory_runner.py"
        runner.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0,str(Path(__file__).resolve().parent))\n"
            "from server.app.app_factory import create_app\n"
            "from server.app.config import load_config\n"
            "cfg=load_config()\n"
            "app=create_app(cfg)\n"
            "app.run(host='127.0.0.1',port=int(sys.argv[1]),debug=False,use_reloader=False)\n",
            encoding="utf-8",
        )
        args = [sys.executable, "-I", str(runner), str(port)]
    env = {k:v for k,v in os.environ.items() if not (
        k.upper() in {"PYTHONPATH","PYTHONHOME"} or
        any(secret in k.upper() for secret in ("API_KEY","TOKEN","SECRET"))
    )}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        args, cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        deadline = time.monotonic() + 14
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"{mode} exited early: {proc.returncode}")
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except (OSError, TimeoutError):
                time.sleep(0.15)
        else:
            raise TimeoutError(f"{mode} synthetic server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
