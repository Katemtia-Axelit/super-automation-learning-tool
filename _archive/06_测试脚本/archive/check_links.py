import sqlite3
DB = 'data/task_publisher.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute('SELECT COUNT(*) as total FROM tasks')
print(f'总任务: {cur.fetchone()[0]}')

cur.execute('SELECT COUNT(*) as c FROM tasks WHERE linked_note_path IS NOT NULL AND linked_note_path != ?', ('',))
print(f'已关联: {cur.fetchone()[0]}')

cur.execute('SELECT COUNT(*) as c FROM tasks WHERE name LIKE ? AND (linked_note_path IS NULL OR linked_note_path = ?)', ('%-复习', ''))
print(f'复习任务未关联: {cur.fetchone()[0]}')

print('\n样本（前5个已关联）:')
cur.execute('SELECT id, name, linked_note_path FROM tasks WHERE linked_note_path IS NOT NULL LIMIT 5')
for r in cur.fetchall():
    print(f'  [{r[0]}] {r[1][:40]} | {r[2]}')

conn.close()
