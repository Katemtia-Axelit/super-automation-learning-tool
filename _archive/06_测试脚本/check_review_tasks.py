import sqlite3
DB = 'data/task_publisher.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('所有复习任务的关联状态:')
cur.execute('SELECT id, name, linked_note_path FROM tasks WHERE name LIKE ? ORDER BY id', ('%-复习',))
for r in cur.fetchall():
    status = '[OK]' if r['linked_note_path'] else '[--]'
    print(f'  [{r["id"]}] {status}: {r["name"]}')

conn.close()
