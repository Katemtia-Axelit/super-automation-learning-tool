"""数据库迁移脚本 - 修复缺失表和列

修复以下问题:
1. tasks 表缺少 task_profile, parent_task_id, group_id 列 (backend_api.py L422 使用)
2. 缺失表: user_states, time_currency, time_logs, task_milestones, task_completions

使用方法:
    .venv\Scripts\python.exe scripts\migrate_fix_missing_tables.py
"""

import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = 'data/task_publisher.db'
BACKUP_DIR = 'data/backup'


def backup_database():
    """创建数据库备份"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'task_publisher_backup_{timestamp}.db')
    shutil.copy2(DB_PATH, backup_path)
    print(f"[备份] 数据库已备份到: {backup_path}")
    return backup_path


def check_and_add_columns(conn):
    """检查并添加 tasks 表缺失的列"""
    cursor = conn.cursor()
    
    # 获取当前列
    cursor.execute("PRAGMA table_info(tasks)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    columns_to_add = [
        ('task_profile', 'TEXT', "'deadline_flexible'"),
        ('parent_task_id', 'INTEGER', 'NULL'),
        ('group_id', 'TEXT', 'NULL'),
    ]
    
    for col_name, col_type, default in columns_to_add:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"[列] 已添加: tasks.{col_name}")
        else:
            print(f"[列] 已存在: tasks.{col_name}")
    
    conn.commit()


def create_missing_tables(conn):
    """创建缺失的表"""
    cursor = conn.cursor()
    
    # 1. user_states 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            energy_level TEXT,
            mood TEXT,
            physical_condition TEXT,
            notes TEXT,
            source TEXT DEFAULT 'manual'
        )
    ''')
    print("[表] user_states 创建/已存在")
    
    # 确保索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_states_timestamp ON user_states(timestamp)')
    
    # 2. time_currency 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_currency (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_minutes INTEGER DEFAULT 0,
            used_minutes INTEGER DEFAULT 0,
            wasted_minutes INTEGER DEFAULT 0
        )
    ''')
    print("[表] time_currency 创建/已存在")
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_time_currency_date ON time_currency(date)')
    
    # 3. time_logs 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            available_time INTEGER,
            used_for_gacha INTEGER DEFAULT 0,
            wasted_time INTEGER DEFAULT 0,
            notes TEXT
        )
    ''')
    print("[表] time_logs 创建/已存在")
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_time_logs_date ON time_logs(date)')
    
    # 4. task_milestones 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            deadline TEXT,
            estimated_time INTEGER,
            completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    print("[表] task_milestones 创建/已存在")
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_milestones_task ON task_milestones(task_id)')
    
    # 5. task_completions 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            actual_duration INTEGER,
            difficulty_rating INTEGER,
            notes TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    print("[表] task_completions 创建/已存在")
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_completions_task ON task_completions(task_id)')
    
    conn.commit()


def verify_tables(conn):
    """验证所有表和列"""
    cursor = conn.cursor()
    
    print("\n[验证] 当前所有表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    for t in tables:
        print(f"  - {t}")
    
    print("\n[验证] tasks 表关键列:")
    cursor.execute("PRAGMA table_info(tasks)")
    cols = [row[1] for row in cursor.fetchall()]
    key_cols = ['task_profile', 'parent_task_id', 'group_id']
    for col in key_cols:
        status = "[OK]" if col in cols else "[MISSING]"
        print(f"  {status} {col}")
    
    # 检查缺失的表
    required_tables = ['user_states', 'time_currency', 'time_logs', 'task_milestones', 'task_completions']
    print("\n[验证] 必需表:")
    for table in required_tables:
        exists = table in tables
        status = "[OK]" if exists else "[MISSING]"
        print(f"  {status} {table}")
    
    return all(col in cols for col in key_cols) and all(t in tables for t in required_tables)


def main():
    print("=" * 60)
    print("数据库迁移: 修复缺失表和列")
    print("=" * 60)
    
    # 1. 备份
    print("\n[步骤 1] 备份数据库...")
    backup_database()
    
    # 2. 连接数据库
    print("\n[步骤 2] 连接数据库...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 3. 添加缺失列
    print("\n[步骤 3] 添加 tasks 表缺失列...")
    check_and_add_columns(conn)
    
    # 4. 创建缺失表
    print("\n[步骤 4] 创建缺失表...")
    create_missing_tables(conn)
    
    # 5. 验证
    print("\n[步骤 5] 验证修复...")
    success = verify_tables(conn)
    
    conn.close()
    
    print("\n" + "=" * 60)
    if success:
        print("迁移完成! 所有缺失的表和列已修复。")
    else:
        print("迁移完成，但部分验证未通过，请检查输出。")
    print("=" * 60)
    
    return success


if __name__ == '__main__':
    main()
