"""Inspect database: categories, CET4 tasks, self-references"""
import sqlite3, os

db = 'data/task_publisher.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. all categories
cur.execute('SELECT DISTINCT category FROM tasks ORDER BY category')
cats = [r[0] for r in cur.fetchall()]
print('=== 所有 category ===')
for c in cats:
    print(f'  {repr(c)}')

# 2. CET4 tasks by name
cur.execute("SELECT id, name, category, is_unlocked, completed FROM tasks WHERE name LIKE '%CET%' OR name LIKE '%cet%' ORDER BY id LIMIT 30")
rows = cur.fetchall()
print(f'\n=== CET相关任务（名称含CET/cet，前30）: {len(rows)} 个 ===')
for r in rows:
    print(f"  id={r['id']} unlocked={r['is_unlocked']} done={r['completed']} cat={repr(r['category'])} | {r['name'][:50]}")

# 3. self-reference
cur.execute('SELECT td.task_id, t.name FROM task_dependencies td JOIN tasks t ON td.task_id = t.id WHERE td.task_id = td.depends_on_task_id')
sr = cur.fetchall()
print(f'\n=== 自引用依赖: {len(sr)} 个 ===')
for r in sr:
    print(f"  id={r['task_id']} name={r['name']}")

# 4. stats
cur.execute('SELECT COUNT(*) FROM tasks WHERE is_unlocked=0 AND completed=0')
locked = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM tasks WHERE is_unlocked=1 AND completed=0')
unlocked = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM tasks WHERE completed=1')
done = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM tasks')
total = cur.fetchone()[0]
print(f'\n统计: 锁定未完成={locked}, 解锁未完成={unlocked}, 已完成={done}, 总计={total}')

conn.close()
