"""Deep analysis: why are 317 tasks locked?"""
import sqlite3

db = 'data/task_publisher.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. 查找所有锁定任务的依赖，看看它们依赖什么
cur.execute('''
    SELECT td.task_id, t.name as task_name, td.depends_on_task_id, p.name as prereq_name
    FROM task_dependencies td
    JOIN tasks t ON td.task_id = t.id
    LEFT JOIN tasks p ON td.depends_on_task_id = p.id
    WHERE t.is_unlocked = 0 AND t.completed = 0
    ORDER BY td.task_id
''')
rows = cur.fetchall()
print(f'锁定任务的依赖关系总数: {len(rows)}')

# 统计：有多少依赖指向了不存在的任务
missing = [r for r in rows if r['depends_on_task_id'] is None]
circular = [r for r in rows if r['task_id'] == r['depends_on_task_id']]
print(f'  依赖不存在的任务: {len(missing)}')
print(f'  自引用: {len(circular)}')

if missing:
    print('\n=== 依赖不存在的任务（前20）===')
    for r in missing[:20]:
        print(f"  任务id={r['task_id']} 名称={r['task_name']} 依赖的id={r['depends_on_task_id']}")

# 2. 找出"第一层"可以解锁但没被解锁的任务（所有依赖都完成了但自身还是锁的）
cur.execute('''
    SELECT t.id, t.name, t.is_unlocked
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
    LIMIT 20
''')
stuck = cur.fetchall()
print(f'\n=== 所有前置任务已完成但自身仍锁定的任务: {len(stuck)} 个 ===')
for r in stuck:
    print(f"  id={r['id']} unlocked={r['is_unlocked']} name={r['name'][:60]}")

# 3. 被 orphaned dependencies 影响的锁定任务数
cur.execute('''
    SELECT COUNT(DISTINCT t.id) as cnt
    FROM tasks t
    JOIN task_dependencies td ON td.task_id = t.id
    WHERE t.is_unlocked = 0 AND t.completed = 0
    AND td.depends_on_task_id NOT IN (SELECT id FROM tasks)
''')
orphaned_count = cur.fetchone()['cnt']
print(f'\n被 orphaned 依赖（指向不存在任务）影响的锁定任务: {orphaned_count} 个')

# 4. 看CET4任务(id 308-337)的具体依赖
cur.execute('''
    SELECT td.task_id, t.name as task_name, td.depends_on_task_id, p.name as prereq_name, p.completed, p.is_unlocked
    FROM task_dependencies td
    JOIN tasks t ON td.task_id = t.id
    LEFT JOIN tasks p ON td.depends_on_task_id = p.id
    WHERE td.task_id BETWEEN 308 AND 337
    ORDER BY td.task_id, td.depends_on_task_id
''')
cet_rows = cur.fetchall()
print(f'\n=== CET4任务(308-337)的依赖详情: {len(cet_rows)} 条 ===')
for r in cet_rows:
    p_status = '不存在' if r['depends_on_task_id'] is None else ('完成' if r['completed'] else f"未完成(解锁={r['is_unlocked']})")
    print(f"  任务id={r['task_id']} 名称={r['task_name'][:40]} 依赖id={r['depends_on_task_id']} [{p_status}]")

conn.close()
