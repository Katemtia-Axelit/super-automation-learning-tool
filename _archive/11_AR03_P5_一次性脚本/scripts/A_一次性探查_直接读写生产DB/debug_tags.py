"""调试 POST /api/tags 问题"""
import sqlite3

DB_PATH = 'data/task_publisher.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 测试 lastrowid
cur = conn.cursor()
test_name = '调试标签_test1'

cur.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (test_name,))
conn.commit()

print(f"lastrowid after commit: {cur.lastrowid}")

# 尝试通过 lastrowid 查询
tag_id = cur.lastrowid
if tag_id:
    cur.execute('SELECT * FROM tags WHERE id = ?', (tag_id,))
    row = cur.fetchone()
    print(f"Query by lastrowid: {dict(row) if row else 'None'}")

# 尝试通过名称查询
cur.execute('SELECT * FROM tags WHERE name = ?', (test_name,))
row = cur.fetchone()
print(f"Query by name: {dict(row) if row else 'None'}")

conn.close()
