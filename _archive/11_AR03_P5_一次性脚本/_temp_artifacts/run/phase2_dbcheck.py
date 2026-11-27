import sqlite3, os, sys
db = r'D:\Axelit\.工作\trae\超级自动化学习工具\data\task_publisher.db'
conn = sqlite3.connect(db)
rows = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"table_count: {len(rows)}")
print("tables:", ", ".join(sorted(rows)))
notes_dir = r'D:\Axelit\.工作\trae\超级自动化学习工具\src\notes'
nfiles = sum(1 for _, _, fs in os.walk(notes_dir) for _ in fs)
print(f"notes_files: {nfiles}")
