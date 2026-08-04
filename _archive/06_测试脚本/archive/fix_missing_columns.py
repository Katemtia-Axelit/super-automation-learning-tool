import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "task_publisher.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 补全 tasks 表缺失列
missing_cols = [
    ("draw_count_today", "INTEGER DEFAULT 0"),
    ("last_drawn_at", "TEXT"),
    ("min_push_time", "TEXT DEFAULT '20:00'"),
    ("in_discard_pile", "BOOLEAN DEFAULT 0"),
    ("completed_count", "INTEGER DEFAULT 0"),
    ("repeat_type", "TEXT DEFAULT 'none'"),
    ("last_completed_at", "TEXT"),
    ("next_available_at", "TEXT"),
    ("difficulty", "TEXT"),
]

for col, col_type in missing_cols:
    try:
        cur.execute(f"ALTER TABLE tasks ADD COLUMN {col} {col_type}")
        print(f"[OK] added column: tasks.{col}")
    except sqlite3.OperationalError as e:
        print(f"[skip] tasks.{col}: {e}")

conn.commit()
conn.close()
print("Done")
