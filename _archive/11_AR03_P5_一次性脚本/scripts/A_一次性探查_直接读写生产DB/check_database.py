# -*- coding: utf-8 -*-
"""
数据库完整性检验脚本
"""
import sqlite3
import json
from datetime import datetime

DB_PATH = "data/task_publisher.db"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def check_database():
    print("=" * 60)
    print("数据库完整性检验")
    print("=" * 60)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. 获取所有表（不包括索引）
        cursor.execute("""
            SELECT name 
            FROM sqlite_master 
            WHERE type = 'table'
            ORDER BY name
        """)
        tables = [row['name'] for row in cursor.fetchall()]
        
        log(f"\n发现 {len(tables)} 个表:")
        for tbl_name in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM [{tbl_name}]")
                count = cursor.fetchone()['cnt']
                log(f"  - {tbl_name} ({count} 行)")
            except sqlite3.OperationalError:
                log(f"  - {tbl_name} (无法读取)")
        
        # 2. 检查核心表
        core_tables = [
            'tasks', 'tags', 'task_tags', 'gacha_records',
            'timer_sessions', 'user_states', 'time_currency', 'time_logs',
            'daily_user_state', 'user_schedule', 'daily_schedules',
            'task_dependencies', 'task_milestones', 'task_completions',
            'task_rejection_log', 'task_completion_feedback'
        ]
        
        log("\n\n核心表检查:")
        missing_tables = []
        for tbl in core_tables:
            if tbl in tables:
                cursor.execute(f"PRAGMA table_info([{tbl}])")
                columns = [row['name'] for row in cursor.fetchall()]
                log(f"  [OK] {tbl} - 列: {len(columns)}")
            else:
                log(f"  [MISSING] {tbl} - 表不存在!")
                missing_tables.append(tbl)
        
        # 3. 检查 tasks 表结构和数据
        log("\n\ntasks 表详细检查:")
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = {row['name'] for row in cursor.fetchall()}
        log(f"  列数: {len(task_columns)}")
        
        # 检查关键列
        required_columns = [
            'id', 'name', 'category', 'task_type', 'description',
            'estimated_time', 'priority', 'completed', 'is_daily',
            'repeat_type', 'prerequisite_ids', 'is_unlocked', 'in_discard_pile',
            'created_at', 'updated_at'
        ]
        
        missing_columns = [c for c in required_columns if c not in task_columns]
        if missing_columns:
            log(f"  [WARN] 缺少列: {missing_columns}")
        else:
            log(f"  [OK] 所有必需列存在")
        
        # 4. 数据质量检查
        log("\n\n数据质量检查:")
        
        # 检查空任务名
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE name IS NULL OR name = ''")
        null_names = cursor.fetchone()['cnt']
        if null_names > 0:
            log(f"  [WARN] 有 {null_names} 个任务名称为空或NULL")
        else:
            log(f"  [OK] 所有任务都有名称")
        
        # 检查孤立依赖
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM task_dependencies td
            WHERE NOT EXISTS (SELECT 1 FROM tasks WHERE id = td.task_id)
        """)
        orphaned_deps = cursor.fetchone()['cnt']
        if orphaned_deps > 0:
            log(f"  [WARN] 有 {orphaned_deps} 个孤立的任务依赖记录")
        else:
            log(f"  [OK] 无孤立依赖")
        
        # 检查损坏的 prerequisite_ids JSON
        cursor.execute("SELECT id, prerequisite_ids FROM tasks WHERE prerequisite_ids IS NOT NULL")
        bad_json = 0
        for row in cursor.fetchall():
            try:
                if row['prerequisite_ids'] and row['prerequisite_ids'] != '[]':
                    json.loads(row['prerequisite_ids'])
            except:
                bad_json += 1
        if bad_json > 0:
            log(f"  [WARN] 有 {bad_json} 个任务的 prerequisite_ids JSON格式错误")
        else:
            log(f"  [OK] 所有 prerequisite_ids 格式正确")
        
        # 5. 统计信息
        log("\n\n数据统计:")
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE completed = 0")
        log(f"  活跃任务: {cursor.fetchone()['cnt']}")
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE completed = 1")
        log(f"  已完成任务: {cursor.fetchone()['cnt']}")
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE in_discard_pile = 1")
        log(f"  弃置任务: {cursor.fetchone()['cnt']}")
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE is_unlocked = 0")
        log(f"  锁定任务: {cursor.fetchone()['cnt']}")
        
        cursor.execute("SELECT COUNT(*) as cnt FROM gacha_records")
        log(f"  抽卡记录: {cursor.fetchone()['cnt']}")
        
        # 6. 检查索引
        log("\n\n索引检查:")
        cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' ORDER BY name")
        indexes = cursor.fetchall()
        log(f"  索引数量: {len(indexes)}")
        for idx in indexes:
            if not idx['name'].startswith('sqlite_'):
                log(f"    - {idx['name']} (on {idx['tbl_name']})")
        
        # 7. 检查 _meta 表
        log("\n\n数据库元信息:")
        if '_meta' in tables:
            cursor.execute("SELECT * FROM _meta")
            for row in cursor.fetchall():
                log(f"  {row['key']}: {row['value']}")
        
        conn.close()
        
        # 总结
        print("\n" + "=" * 60)
        print("检验结果汇总")
        print("=" * 60)
        if missing_tables:
            print(f"缺失表: {missing_tables}")
        else:
            print("所有核心表存在")
        
        return len(missing_tables) == 0
        
    except Exception as e:
        log(f"数据库检验失败: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return False

if __name__ == "__main__":
    check_database()
