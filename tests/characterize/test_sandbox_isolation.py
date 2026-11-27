import os
import sys
import sqlite3
import tempfile
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具')

PROTECTED_PATHS = [
    PROJECT_ROOT / 'data' / 'task_publisher.db',
    PROJECT_ROOT / 'data' / 'task_publisher.db-wal',
    PROJECT_ROOT / 'data' / 'task_publisher.db-shm',
    PROJECT_ROOT / 'src' / 'notes',
    PROJECT_ROOT / 'config' / 'config.json',
]

PROTECTED_STRINGS = [str(p) for p in PROTECTED_PATHS]


def _build_sandbox(root):
    sandbox = root / 'sandbox'
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / 'server' / 'app').mkdir(parents=True, exist_ok=True)
    (sandbox / 'server' / 'blueprints').mkdir(parents=True, exist_ok=True)
    (sandbox / 'server' / 'schema').mkdir(parents=True, exist_ok=True)
    (sandbox / 'server' / 'extensions.py').touch()
    (sandbox / 'server' / '__init__.py').touch()
    (sandbox / 'server' / 'app' / '__init__.py').touch()
    (sandbox / 'server' / 'blueprints' / '__init__.py').touch()
    (sandbox / 'server' / 'schema' / '__init__.py').touch()
    (sandbox / 'synthetic_vault').mkdir(parents=True, exist_ok=True)
    (sandbox / 'static').mkdir(parents=True, exist_ok=True)
    (sandbox / 'config').mkdir(parents=True, exist_ok=True)
    (sandbox / 'data').mkdir(parents=True, exist_ok=True)
    cfg = {
        'server': {'port': 18765, 'host': '127.0.0.1', 'debug': False},
        'obsidian': {'vault_path': 'synthetic_vault', 'notes_directory': 'synthetic_vault'},
        'api': {'openai_api_key': '', 'claude_api_key': ''},
        'database': {'task_db_path': 'data/synthetic.db'},
    }
    with open(sandbox / 'config' / 'config.json', 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    return {
        'root': sandbox,
        'config_path': sandbox / 'config' / 'config.json',
        'db_path': sandbox / 'data' / 'synthetic.db',
        'notes_dir': sandbox / 'synthetic_vault',
    }



@pytest.fixture
def sandbox_root():
    with tempfile.TemporaryDirectory(prefix='sal_sandbox_') as td:
        yield Path(td)


@pytest.fixture
def sandbox_env(sandbox_root):
    env = _build_sandbox(sandbox_root)
    env['PYTHONPATH'] = str(env['root'])
    return env


@pytest.fixture
def synthetic_db(sandbox_env):
    db_path = sandbox_env['db_path']
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, completed INTEGER DEFAULT 0, is_unlocked INTEGER DEFAULT 1, prerequisite_ids TEXT DEFAULT ''[]'', success_rate REAL DEFAULT 0.0, refusal_count INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, category TEXT DEFAULT ''daily'', priority INTEGER DEFAULT 5)')
    conn.execute('CREATE TABLE IF NOT EXISTS task_dependencies (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, depends_on_task_id INTEGER NOT NULL, FOREIGN KEY (task_id) REFERENCES tasks(id), FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id))')
    conn.commit()
    conn.close()
    return db_path


def test_synthetic_db_empty(sandbox_env, synthetic_db):
    conn = sqlite3.connect(str(synthetic_db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as cnt FROM tasks')
    count = cur.fetchone()['cnt']
    conn.close()
    assert count == 0, 'Synthetic DB should be empty'


def test_synthetic_db_path_isolated(sandbox_env, synthetic_db):
    resolved = Path(synthetic_db).resolve()
    original_db = PROJECT_ROOT / 'data' / 'task_publisher.db'
    assert str(resolved) != str(original_db.resolve()), 'DB path equals original - ISOLATION VIOLATION!'
    assert str(resolved).startswith(str(sandbox_env['root'])), f'DB {resolved} not under sandbox!'


def test_sqlite_wal_shm_in_sandbox(sandbox_env, synthetic_db):
    conn = sqlite3.connect(str(synthetic_db))
    conn.execute('PRAGMA journal_mode=WAL')
    conn.commit()
    conn.close()
    wal_file = Path(str(synthetic_db) + '-wal')
    shm_file = Path(str(synthetic_db) + '-shm')
    for f in [wal_file, shm_file]:
        if f.exists():
            assert str(f.resolve()).startswith(str(sandbox_env['root'])), f'{f.name} created outside sandbox!'


def test_sandbox_config_has_empty_keys(sandbox_env):
    with open(sandbox_env['config_path']) as f:
        cfg = json.load(f)
    assert cfg['api']['openai_api_key'] == '', 'Sandbox config should have empty API keys'
    assert cfg['api']['claude_api_key'] == '', 'Sandbox config should have empty API keys'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])


