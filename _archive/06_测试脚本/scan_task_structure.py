"""扫描现有任务结构，分析章节归属"""
import sqlite3, re
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "task_publisher.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 扫描所有任务
cur.execute("SELECT id, name, category, task_type, prerequisite_ids FROM tasks ORDER BY id")
tasks = cur.fetchall()

# 分析任务名格式
# 格式: 科目-章节-笔记名-类型
# 例如: 高数-第6章-06-01_向量的数量积-复习

chapter_map = {}  # {subject}: {chapter_num}: [task_ids]

for t in tasks:
    name = t["name"] or ""
    parts = name.split("-")
    if len(parts) >= 3:
        subject = parts[0]  # 高数/大物/线代...
        chapter = parts[1]   # 第6章/力学/...
        note_part = "-".join(parts[2:])  # 06-01_xxx-类型
    else:
        subject = name[:4]
        chapter = "未知"
        note_part = name

    chapter_map.setdefault(subject, {}).setdefault(chapter, []).append(t["id"])

print("=" * 60)
print(f"总任务数: {len(tasks)}")
print(f"涉及科目: {len(chapter_map)}")
print()

for subj, chapters in sorted(chapter_map.items()):
    print(f"\n【{subj}】")
    total = 0
    for ch, ids in sorted(chapters.items(), key=lambda x: x[0]):
        # 提取章号
        ch_num = re.search(r'\d+', ch)
        ch_num_str = ch_num.group() if ch_num else ch
        print(f"  {ch}: {len(ids)} 个任务  {ids}")
        total += len(ids)
    print(f"  小计: {total} 个")

# 检查习题类任务
print("\n" + "=" * 60)
print("习题类任务（task_type=exercise）:")
cur.execute("SELECT id, name, prerequisite_ids FROM tasks WHERE task_type='exercise' ORDER BY id LIMIT 10")
for t in cur.fetchall():
    print(f"  [{t['id']}] {t['name']} | prereqs: {t['prerequisite_ids']}")

# 检查复习类任务
print("\n复习类任务（task_type=note_review）:")
cur.execute("SELECT id, name, prerequisite_ids FROM tasks WHERE task_type='note_review' ORDER BY id LIMIT 10")
for t in cur.fetchall():
    print(f"  [{t['id']}] {t['name']} | prereqs: {t['prerequisite_ids']}")

# 检查现有的 prerequisite_ids 使用情况
print("\n" + "=" * 60)
print("现有前置依赖使用情况:")
cur.execute("SELECT COUNT(*) as c FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]' AND prerequisite_ids != ''")
print(f"有前置的任务: {cur.fetchone()[0]} 个")
cur.execute("SELECT id, name, prerequisite_ids FROM tasks WHERE prerequisite_ids IS NOT NULL AND prerequisite_ids != '[]' AND prerequisite_ids != '' ORDER BY id")
for t in cur.fetchall():
    print(f"  [{t['id']}] {t['name'][:40]} | prereqs: {t['prerequisite_ids']}")

conn.close()
