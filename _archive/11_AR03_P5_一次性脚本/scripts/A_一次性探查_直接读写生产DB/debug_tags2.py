"""调试标签创建问题 - 检查 lastrowid 行为"""
import sqlite3

DB_PATH = 'data/task_publisher.db'

# 测试场景1: 创建新标签
print("=== 测试1: 创建新标签 ===")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

test_name = '新标签_测试A'
cur.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (test_name,))
conn.commit()
print(f"lastrowid after INSERT OR IGNORE + commit: {cur.lastrowid}")
tag_id = cur.lastrowid

# 用 lastrowid 查询
if tag_id:
    cur.execute('SELECT * FROM tags WHERE id = ?', (tag_id,))
    row = cur.fetchone()
    print(f"通过 lastrowid={tag_id} 查询: {dict(row) if row else 'None'}")

conn.close()

# 测试场景2: 创建已存在的标签
print("\n=== 测试2: 创建已存在的标签 ===")
conn2 = sqlite3.connect(DB_PATH)
conn2.row_factory = sqlite3.Row
cur2 = conn2.cursor()

# 尝试插入已存在的名称
test_name2 = '新标签_测试A'  # 刚创建的
cur2.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (test_name2,))
conn2.commit()
print(f"lastrowid for existing tag: {cur2.lastrowid}")  # 应该是 0 或上一个ID

conn2.close()

# 测试场景3: 检查原始 tags 表的列
print("\n=== 测试3: 检查 tags 表结构 ===")
conn3 = sqlite3.connect(DB_PATH)
conn3.row_factory = sqlite3.Row
cur3 = conn3.cursor()
cur3.execute("PRAGMA table_info(tags)")
print("tags 表结构:")
for col in cur3.fetchall():
    print(f"  {col}")

# 查询所有标签看有多少
cur3.execute("SELECT * FROM tags ORDER BY id DESC LIMIT 5")
print("\n最近5个标签:")
for row in cur3.fetchall():
    print(f"  {dict(row)}")

conn3.close()
