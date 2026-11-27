#!/usr/bin/env bash
# Phase 1 DB table count check (红线 2 验证)
cd "/d/Axelit/.工作/trae/超级自动化学习工具"
export PYTHONPATH="$PWD"

.venv/Scripts/python.exe - <<'PY'
import sqlite3
conn = sqlite3.connect('data/task_publisher.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
rows = [r[0] for r in cur.fetchall()]
print(f"table_count: {len(rows)}")
for r in rows:
    print(f"  - {r}")
conn.close()
PY
