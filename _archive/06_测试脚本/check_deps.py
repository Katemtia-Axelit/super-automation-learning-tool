import sqlite3, json, os

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'task_publisher.db')
conn = sqlite3.connect(db)
c = conn.cursor()

print("=" * 60)
print("=== TABLE SCHEMAS ===")
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('tasks', 'task_dependencies')")
for row in c.fetchall():
    print(row[0])
    print()

print("=" * 60)
print("=== TABLE INFO (pragma) ===")
c.execute("PRAGMA table_info(tasks)")
cols = {row[1]: row for row in c.fetchall()}
print("tasks columns:", list(cols.keys()))

c.execute("PRAGMA table_info(task_dependencies)")
cols_dep = {row[1]: row for row in c.fetchall()}
print("task_dependencies columns:", list(cols_dep.keys()))

print()
print("=" * 60)
print("=== TOTAL TASKS ===")
c.execute("SELECT COUNT(*) FROM tasks")
print("total_tasks:", c.fetchone()[0])

print()
print("=" * 60)
print("=== Tasks with prerequisite_ids NOT null/NOT empty ===")
c.execute("SELECT COUNT(*) FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]'")
count_prereq = c.fetchone()[0]
print("tasks_with_prereqs:", count_prereq)

c.execute("SELECT id, name, prerequisite_ids, is_unlocked, completed FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]' LIMIT 20")
for row in c.fetchall():
    print(f"  id={row[0]}, name={row[1][:40] if row[1] else 'None'}, prereq={row[2]}, unlocked={row[3]}, completed={row[4]}")

print()
print("=" * 60)
print("=== task_dependencies TABLE ===")
c.execute("SELECT COUNT(*) FROM task_dependencies")
count_dep = c.fetchone()[0]
print("dep_records:", count_dep)

c.execute("SELECT * FROM task_dependencies LIMIT 20")
cols_names = [d[0] for d in c.description]
for row in c.fetchall():
    print(f"  {dict(zip(cols_names, row))}")

print()
print("=" * 60)
print("=== ORPHANED DEPENDENCIES (depends_on_task_id not in tasks) ===")
c.execute("SELECT td.* FROM task_dependencies td LEFT JOIN tasks t ON td.depends_on_task_id = t.id WHERE t.id IS NULL")
rows = c.fetchall()
print("orphaned depends_on:", len(rows))
for row in rows:
    print(f"  {dict(zip(cols_names, row))}")

print()
print("=== ORPHANED DEPENDENCIES (task_id not in tasks) ===")
c.execute("SELECT td.* FROM task_dependencies td LEFT JOIN tasks t ON td.task_id = t.id WHERE t.id IS NULL")
rows = c.fetchall()
print("orphaned task_id refs:", len(rows))
for row in rows:
    print(f"  {dict(zip(cols_names, row))}")

print()
print("=" * 60)
print("=== CONSISTENCY: tasks with prereq_ids but NO task_dependencies row ===")
c.execute("""SELECT t.id, t.name, t.prerequisite_ids FROM tasks t
  WHERE t.prerequisite_ids IS NOT NULL AND t.prerequisite_ids != '[]'
  AND t.id NOT IN (SELECT task_id FROM task_dependencies)
  LIMIT 10""")
rows = c.fetchall()
print("Count:", len(rows))
for row in rows:
    print(f"  id={row[0]}, name={row[1][:40] if row[1] else 'None'}, prereq={row[2]}")

print()
print("=== CONSISTENCY: task_dependencies exists but tasks.prerequisite_ids empty/null ===")
c.execute("""SELECT t.id, t.name, t.prerequisite_ids, td.depends_on_task_id FROM task_dependencies td
  JOIN tasks t ON td.task_id = t.id
  WHERE t.prerequisite_ids IS NULL OR t.prerequisite_ids = '[]'
  LIMIT 10""")
rows = c.fetchall()
print("Count:", len(rows))
for row in rows:
    print(f"  id={row[0]}, name={row[1][:40] if row[1] else 'None'}, prereq={row[2]}, depends_on={row[3]}")

print()
print("=" * 60)
print("=== DUPLICATE DEPENDENCIES ===")
c.execute("SELECT task_id, depends_on_task_id, COUNT(*) as cnt FROM task_dependencies GROUP BY task_id, depends_on_task_id HAVING cnt > 1")
rows = c.fetchall()
print("duplicate deps:", len(rows))
for row in rows:
    print(f"  {dict(row)}")

print()
print("=" * 60)
print("=== SELF-REFERENCING DEPS ===")
c.execute("SELECT * FROM task_dependencies WHERE task_id = depends_on_task_id")
rows = c.fetchall()
print("self-refs:", len(rows))

print()
print("=" * 60)
print(f"SUMMARY: {count_prereq} tasks have prerequisite_ids, {count_dep} task_dependencies records")

conn.close()
