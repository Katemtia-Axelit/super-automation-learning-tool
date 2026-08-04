"""
Step 4: 根据知识库笔记直接生成复习任务
- 每个笔记文件 → 一个复习任务
- 任务的 linked_note_path 指向对应的 Obsidian 笔记
- 全部自动解锁，无前置依赖
"""

import sqlite3, json, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "task_publisher.db"
VAULT_DIR = Path(__file__).parent.parent / "src" / "notes" / "vault"

# 有效学科目录（不含知识点的顶层分类）
SUBJECTS = ["大学物理", "高等数学", "线性代数", "计算机", "电子技术", "英语四级"]
SUBJECT_DISPLAY = {
    "大学物理": "大物",
    "高等数学": "高数",
    "线性代数": "线代",
    "计算机": "计算机",
    "电子技术": "电子技术",
    "英语四级": "CET4",
}

# 优先级：按学科顺序分配，越早学科优先级越高
SUBJECT_PRIORITY_OFFSET = {s: (len(SUBJECTS) - i) * 100 for i, s in enumerate(SUBJECTS)}


def scan_vault_notes():
    """返回 [(subject, relative_path, filename_stem), ...]"""
    notes = []
    for subject in SUBJECTS:
        subject_dir = VAULT_DIR / subject
        if not subject_dir.is_dir():
            continue
        for f in sorted(subject_dir.glob("*.md")):
            # 跳过目录级索引（如 大学物理.md）
            if f.stem == subject:
                continue
            notes.append({
                "subject": subject,
                "subject_display": SUBJECT_DISPLAY[subject],
                "relative_path": f"{subject}/{f.name}",  # e.g. "大学物理/01_质点运动.md"
                "filename_stem": f.stem,                  # e.g. "01_质点运动"
                "full_path": f,
            })
    return notes


def rebuild_note_review_tasks(conn, notes):
    """
    清空旧任务，只创建笔记复习任务。
    """
    cur = conn.cursor()

    # 1. 保留 tags 表（手动标签保留）
    # 2. 清空 task_tags
    cur.execute("DELETE FROM task_tags")
    # 3. 清空 task_dependencies
    cur.execute("DELETE FROM task_dependencies")
    # 4. 清空所有旧任务
    cur.execute("DELETE FROM tasks")

    now = datetime.datetime.now().isoformat()
    created = 0

    # 按学科优先级排序（学科内按文件名字典序）
    sorted_notes = sorted(notes, key=lambda n: (
        SUBJECT_PRIORITY_OFFSET.get(n["subject"], 0),
        n["subject"],
        n["filename_stem"]
    ))

    for task_order, note in enumerate(sorted_notes):
        cur.execute('''
            INSERT INTO tasks (
                name, category, task_type, description,
                estimated_time, preferred_time, deadline,
                resistance, energy_required, rarity, priority,
                is_daily, repeat_type, created_at, updated_at,
                prerequisite_ids, is_unlocked, linked_note_path,
                draw_count_today, min_push_time, in_discard_pile, completed_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            note["filename_stem"],   # name
            "study",                 # category
            "note_review",           # task_type
            f"复习笔记：{note['subject_display']} - {note['filename_stem']}",  # description
            30,                      # estimated_time
            None,                    # preferred_time
            None,                    # deadline
            "medium",                # resistance
            "medium",                # energy_required
            "common",                # rarity
            100 - task_order,        # priority（越早越前，优先级越高）
            0,                       # is_daily
            "none",                  # repeat_type
            now,                     # created_at
            now,                     # updated_at
            "[]",                    # prerequisite_ids（无前置）
            1,                       # is_unlocked（解锁）
            note["relative_path"],    # linked_note_path
            0,                       # draw_count_today
            "20:00",                 # min_push_time
            0,                       # in_discard_pile
            0,                       # completed_count
        ))
        created += 1

    conn.commit()
    return created


def main():
    print("=" * 50)
    print("Step 4: 笔记 → 复习任务绑定")
    print("=" * 50)

    notes = scan_vault_notes()
    print(f"\n扫描到 {len(notes)} 篇笔记：")
    by_subject = {}
    for n in notes:
        by_subject.setdefault(n["subject"], []).append(n["filename_stem"])
    for subj, names in by_subject.items():
        print(f"  {subj}: {len(names)} 篇")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 确保 linked_note_path 列存在
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tasks ADD COLUMN linked_note_path TEXT")
        print("\n[OK] added linked_note_path column")
    except sqlite3.OperationalError:
        pass

    created = rebuild_note_review_tasks(conn, notes)
    print(f"\n[OK] 已创建 {created} 个笔记复习任务")

    # 验证
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM tasks")
    total = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE linked_note_path IS NOT NULL AND linked_note_path != ''")
    with_link = cur.fetchone()["cnt"]
    print(f"[OK] 数据库共 {total} 个任务，其中 {with_link} 个关联笔记")

    # 显示前10个
    print("\n前10个任务预览：")
    cur.execute("SELECT id, name, linked_note_path, priority FROM tasks ORDER BY priority DESC LIMIT 10")
    for r in cur.fetchall():
        print(f"  [{r['id']}] P{r['priority']} | {r['name']} | → {r['linked_note_path']}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
