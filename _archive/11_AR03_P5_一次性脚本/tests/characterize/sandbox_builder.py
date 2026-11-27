# sandbox_builderimport os
import shutil
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具')


def build_sandbox(parent, port=18766):
    sandbox = parent / 'sandbox'
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / 'server').mkdir(exist_ok=True)
    (sandbox / 'server' / 'app').mkdir(exist_ok=True)
    (sandbox / 'server' / 'blueprints').mkdir(exist_ok=True)
    (sandbox / 'server' / 'schema').mkdir(exist_ok=True)
    (sandbox / 'synthetic_vault').mkdir(exist_ok=True)
    (sandbox / 'static').mkdir(exist_ok=True)
    (sandbox / 'config').mkdir(exist_ok=True)
    (sandbox / 'data').mkdir(exist_ok=True)
    (sandbox / 'server' / '__init__.py').touch()
    (sandbox / 'server' / 'app' / '__init__.py').touch()
    (sandbox / 'server' / 'blueprints' / '__init__.py').touch()
    (sandbox / 'server' / 'schema' / '__init__.py').touch()
    server_src = PROJECT_ROOT / 'server'
    server_dst = sandbox / 'server'
    for src_file in server_src.rglob('*.py'):
        rel = src_file.relative_to(server_src)
        dst = server_dst / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)
    cfg = {
        'server': {'port': port, 'host': '127.0.0.1', 'debug': False},
        'obsidian': {'vault_path': 'synthetic_vault', 'notes_directory': 'synthetic_vault'},
        'api': {'openai_api_key': '', 'claude_api_key': ''},
        'database': {'task_db_path': 'data/synthetic.db'},
    }
    with open(sandbox / 'config' / 'config.json', 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    init_synthetic_db(sandbox / 'data' / 'synthetic.db')
    return {
        'root': sandbox,
        'db_path': sandbox / 'data' / 'synthetic.db',
        'config_path': sandbox / 'config' / 'config.json',
        'notes_dir': sandbox / 'synthetic_vault',
        'port': port,
    }




def init_synthetic_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, completed INTEGER DEFAULT 0, is_unlocked INTEGER DEFAULT 1, prerequisite_ids TEXT DEFAULT '[]', success_rate REAL DEFAULT 0.0, refusal_count INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, category TEXT DEFAULT 'daily', priority INTEGER DEFAULT 5)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS task_dependencies (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, depends_on_task_id INTEGER NOT NULL, FOREIGN KEY (task_id) REFERENCES tasks(id), FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id))''')
    conn.commit()
    conn.close()


