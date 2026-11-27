import sqlite3
conn = sqlite3.connect(r'data/task_publisher.db')
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(len(tables), "tables")
for t in tables:
    print(" ", t)
conn.close()