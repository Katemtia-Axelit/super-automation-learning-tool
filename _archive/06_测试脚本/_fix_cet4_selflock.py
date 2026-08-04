"""
P5.2 一次性脚本：修复 CET4 任务自锁 + 同步所有任务解锁状态
使用方法：.venv\Scripts\python.exe scripts\_fix_cet4_selflock.py
"""
import sys
sys.path.insert(0, '.')

from server.backend_api import get_db_connection as get_db, sync_all_unlock_states

conn = get_db()

print("=== 第一步：查找自锁任务 ===")
cursor = conn.cursor()

# 查找 self-reference: 任务依赖表中有任务的 depends_on 指向自身
cursor.execute('''
    SELECT td.task_id, t.name, td.depends_on_task_id
    FROM task_dependencies td
    JOIN tasks t ON td.task_id = t.id
    WHERE td.task_id = td.depends_on_task_id
''')
self_refs = cursor.fetchall()
print(f"自引用依赖数量: {len(self_refs)}")
for row in self_refs:
    print(f"  任务ID={row['task_id']}, 名称={row['name']}")

if self_refs:
    print("\n=== 第二步：移除自引用 ===")
    for row in self_refs:
        cursor.execute('''
            DELETE FROM task_dependencies
            WHERE task_id = ? AND depends_on_task_id = ?
        ''', (row['task_id'], row['depends_on_task_id']))
        print(f"  已删除: 任务{row['task_id']}({row['name']}) 的自引用")
    conn.commit()

print("\n=== 第三步：同步所有解锁状态 ===")
sync_all_unlock_states(conn)

print("\n=== 第四步：验证结果 ===")
# 检查 CET4 相关任务状态
cursor.execute('''
    SELECT id, name, category, is_unlocked, completed
    FROM tasks
    WHERE category LIKE '%CET%' OR category LIKE '%cet%' OR category LIKE '%四级%' OR category LIKE '%英语%'
    ORDER BY id
''')
cet4_tasks = cursor.fetchall()
print(f"CET4 相关任务数量: {len(cet4_tasks)}")
print(f"{'ID':<6} {'名称':<40} {'解锁':<6} {'完成':<6}")
print("-" * 62)
for row in cet4_tasks:
    print(f"{row['id']:<6} {row['name'][:38]:<40} {row['is_unlocked']:<6} {row['completed']:<6}")

# 检查还有多少任务处于锁定状态
cursor.execute('SELECT COUNT(*) FROM tasks WHERE is_unlocked = 0 AND completed = 0')
locked = cursor.fetchone()[0]
print(f"\n仍有未完成任务处于锁定状态: {locked} 个")

conn.close()
print("\n完成。")
