"""只读输出 SQLite 表结构，供 P0 验收使用。

用法:
  python scripts/inspect_db_schema.py
  .venv\\Scripts\\python.exe scripts/inspect_db_schema.py
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, 'config', 'config.json')

# Web 后端运行时必需（任务核心）
CORE_TABLES = {
    'tasks', 'tags', 'task_tags', 'task_dependencies',
    'gacha_records', 'task_rejection_log', 'task_completion_feedback',
}

# 日程（桌面端 canonical）
SCHEDULE_CANONICAL = {'user_schedule', 'daily_schedules', 'activities'}

# 旧 Web 表（兼容保留，不删除）
SCHEDULE_LEGACY = {'weekly_schedule', 'daily_schedule'}

# 其他 Web 可选表
OPTIONAL_TABLES = {'daily_user_state', 'state_assessments', 'timer_sessions', 'task_feedback_events'}

KEY_TABLES = sorted(CORE_TABLES | SCHEDULE_CANONICAL | SCHEDULE_LEGACY | OPTIONAL_TABLES)


def table_columns(cur, name):
    cur.execute(f'PRAGMA table_info({name})')
    return [row[1] for row in cur.fetchall()]


def main():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        db_path = os.path.join(ROOT, cfg['database']['task_db_path'])
    else:
        db_path = os.path.join(ROOT, 'data', 'task_publisher.db')

    print('=== DATABASE PATH ===')
    print(db_path)
    if not os.path.exists(db_path):
        print('ERROR: database file not found')
        return 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall() if not r[0].startswith('sqlite_')]

    print('\n=== ALL TABLES ===')
    for t in tables:
        print(' ', t)

    print('\n=== CORE TASK TABLES ===')
    for t in sorted(CORE_TABLES):
        status = 'OK' if t in tables else 'MISSING'
        print(f'  {t}: {status}')

    print('\n=== SCHEDULE (canonical: user_schedule / daily_schedules) ===')
    for t in sorted(SCHEDULE_CANONICAL):
        print(f'  {t}: {"OK" if t in tables else "MISSING"}')
    for t in sorted(SCHEDULE_LEGACY):
        present = t in tables
        print(f'  {t} (legacy): {"present" if present else "absent"}')

    if 'user_schedule' in tables and 'daily_schedules' in tables:
        print('  schedule_compat: OK (Web API 应对齐桌面端表)')
    else:
        print('  schedule_compat: NEEDS_MIGRATION (启动 backend 时会 ensure_schedule_schema)')

    print('\n=== OPTIONAL WEB TABLES ===')
    for t in sorted(OPTIONAL_TABLES):
        print(f'  {t}: {"OK" if t in tables else "missing (non-P0)"}')

    for t in ['tasks', 'task_dependencies', 'user_schedule', 'daily_schedules']:
        if t in tables:
            cols = table_columns(cur, t)
            print(f'\n=== COLUMNS: {t} ===')
            print(' ', ', '.join(cols))

    missing_core = sorted(CORE_TABLES - set(tables))
    print('\n=== SUMMARY ===')
    print('missing_core:', missing_core or '(none)')
    print('task_dependency_ready:', not missing_core or missing_core == [])

    conn.close()
    return 0 if not missing_core else 2


if __name__ == '__main__':
    raise SystemExit(main())
