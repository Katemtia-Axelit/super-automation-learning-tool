"""Fix orphaned locked tasks: tasks with no dependencies that are still locked (legacy data)"""
import sqlite3

db = 'data/task_publisher.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== 第一步：给所有孤立锁定任务强制解锁 ===")
# 孤立任务：有前置任务已完成（或无前置任务）但自身 is_unlocked=0
# 这些任务本身没有依赖（或所有依赖都完成了），但被错误锁定
cur.execute('''
    SELECT t.id, t.name, t.category, t.is_unlocked, t.completed
    FROM tasks t
    WHERE t.completed = 0
    AND t.is_unlocked = 0
    AND NOT EXISTS (
        SELECT 1 FROM task_dependencies td
        WHERE td.task_id = t.id
        AND td.depends_on_task_id NOT IN (
            SELECT id FROM tasks WHERE completed = 1
        )
    )
    ORDER BY t.id
''')
orphaned = cur.fetchall()
print(f'孤立锁定任务总数: {len(orphaned)}')
for r in orphaned:
    print(f"  id={r['id']} cat={r['category']} name={r['name'][:60]}")

if orphaned:
    ids = [r['id'] for r in orphaned]
    placeholders = ','.join('?' * len(ids))
    cur.execute(f'UPDATE tasks SET is_unlocked = 1 WHERE id IN ({placeholders})', ids)
    conn.commit()
    print(f'\n已强制解锁 {cur.rowcount} 个任务')

print("\n=== 第二步：重新运行 sync_all_unlock_states ===")
# 直接调用同步逻辑
cur.execute('SELECT id FROM tasks WHERE completed = 0')
all_incomplete = [r['id'] for r in cur.fetchall()]

def recompute_unlock(conn, task_id):
    cur2 = conn.cursor()
    cur2.execute('SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?', (task_id,))
    prereqs = [r['depends_on_task_id'] for r in cur2.fetchall()]
    if not prereqs:
        unlocked = 1
    else:
        placeholders = ','.join('?' * len(prereqs))
        cur2.execute(f'SELECT id, completed FROM tasks WHERE id IN ({placeholders})', prereqs)
        unlocked = 1 if all(r['completed'] for r in cur2.fetchall()) else 0
    cur2.execute('UPDATE tasks SET is_unlocked = ? WHERE id = ?', (unlocked, task_id))
    return unlocked

for tid in all_incomplete:
    recompute_unlock(conn, tid)
conn.commit()
print(f'已对 {len(all_incomplete)} 个未完成任务重新计算解锁状态')

print("\n=== 第三步：验证结果 ===")
# 统计
cur.execute('SELECT COUNT(*) FROM tasks WHERE is_unlocked=0 AND completed=0')
locked = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM tasks WHERE is_unlocked=1 AND completed=0')
unlocked = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM tasks WHERE completed=1')
done = cur.fetchone()[0]
print(f'锁定未完成: {locked}, 解锁未完成: {unlocked}, 已完成: {done}')

# CET4
cur.execute("SELECT id, name, is_unlocked, completed FROM tasks WHERE id BETWEEN 308 AND 337 ORDER BY id")
cet4 = cur.fetchall()
print(f'\nCET4任务(308-337)状态:')
print(f"{'ID':<6} {'解锁':<6} {'完成':<6} {'名称':<50}")
print("-" * 72)
for r in cet4:
    print(f"{r['id']:<6} {r['is_unlocked']:<6} {r['completed']:<6} {r['name'][:50]}")

conn.close()
print('\n完成。')
