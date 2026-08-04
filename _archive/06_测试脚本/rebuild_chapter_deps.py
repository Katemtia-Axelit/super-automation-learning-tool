"""
重建任务跨章节依赖（rebuild_chapter_deps.py）

修复内容：
  跨章节大门：章节总习题(第N章) ──→ 第(N+1)章第1节复习

执行前：第(N+1)章第1节复习依赖第N章的章节复习（错误）
执行后：第(N+1)章第1节复习依赖第N章的章节总习题（正确）

这是防止用户跳过习题只刷笔记的关键锁。
"""

import sqlite3, json, re
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "task_publisher.db"
BACKUP_SUFFIX = ".before_chapter_deps_fix"

def parse_task_name(name: str):
    """从任务名提取 学科、章节号、节号、类型"""
    if not name:
        return None
    parts = name.split("-")
    if len(parts) < 2:
        return None

    subject = parts[0]
    chapter_raw = parts[1]

    # 章节号：第6章 → 6
    ch_match = re.search(r'\d+', chapter_raw)
    chapter = int(ch_match.group()) if ch_match else chapter_raw

    # 节号：06-01_向量... → 6, 1   或  力学/01_... → None, 1
    section_num = None
    section_sub = None
    if len(parts) >= 3:
        sec_raw = parts[2]
        m = re.match(r'(\d+)[-_](\d+)', sec_raw)
        if m:
            chapter = int(m.group(1))  # 覆盖为数字
            section_num = int(m.group(2))
        else:
            m2 = re.search(r'(\d+)', sec_raw)
            if m2:
                section_sub = int(m2.group())

    # 类型
    suffix = name.split("-")[-1]
    if suffix == "复习":
        task_type = "note_review"
    elif suffix == "习题":
        task_type = "exercise"
    elif "章节复习" in name:
        task_type = "chapter_review"
    elif "章节总习题" in name or "半章总习题" in name:
        task_type = "chapter_exam"
    elif "选择题" in name:
        task_type = "exam_question"
    elif "填空题" in name:
        task_type = "exam_question"
    elif "计算题" in name:
        task_type = "exam_question"
    elif "判断题" in name:
        task_type = "exam_question"
    elif "批改" in name or "复盘" in name:
        task_type = "exam_review"
    elif "综合" in name:
        task_type = "chapter_review"
    else:
        task_type = "unknown"

    return {
        "subject": subject,
        "chapter": chapter,
        "section_num": section_num,
        "section_sub": section_sub,
        "task_type": task_type,
        "name": name,
    }


def load_tasks(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, name, task_type, prerequisite_ids FROM tasks ORDER BY id")
    rows = cur.fetchall()
    tasks = []
    for r in rows:
        parsed = parse_task_name(r["name"])
        if parsed:
            parsed["id"] = r["id"]
            parsed["old_prereqs"] = r["prerequisite_ids"]
            tasks.append(parsed)
    return tasks


def build_chapter_index(tasks):
    """按学科-章节索引任务"""
    index = {}  # (subject, chapter) -> {"exam": id, "first_review": id, "last_review": id, "reviews": [], "exercises": []}
    for t in tasks:
        key = (t["subject"], t["chapter"])
        if key not in index:
            index[key] = {"exam": None, "first_review": None, "last_review": None,
                          "reviews": [], "exercises": [], "all": []}
        index[key]["all"].append(t)
        if t["task_type"] == "chapter_exam":
            index[key]["exam"] = t["id"]
        elif t["task_type"] == "note_review":
            index[key]["reviews"].append(t)
            # 找第一节
            if t["section_num"] is not None:
                if index[key]["first_review"] is None or t["section_num"] < index[key]["first_review"]["section_num"]:
                    index[key]["first_review"] = t
            elif index[key]["first_review"] is None:
                index[key]["first_review"] = t
        elif t["task_type"] == "exercise":
            index[key]["exercises"].append(t)

    # 找每章最后一节复习（用于章节复习的依赖）
    for key, ch in index.items():
        if ch["reviews"]:
            # 按节号排序
            sorted_reviews = sorted(ch["reviews"], key=lambda x: (x["section_num"] or 0))
            ch["last_review"] = sorted_reviews[-1]
            # 第一节如果没有节号，默认第一个
            if ch["first_review"] is None:
                ch["first_review"] = sorted_reviews[0]

    return index


def get_chapter_order(index):
    """获取每科的章节顺序（数字章节优先，小到大；非数字章节按字典序）"""
    order = {}
    for (subject, chapter), ch in index.items():
        if subject not in order:
            order[subject] = []
        order[subject].append(chapter)
    for subject in order:
        # 数字章节排前面，非数字章节排后面
        order[subject] = sorted(
            order[subject],
            key=lambda x: (0, x) if isinstance(x, int) else (1, str(x))
        )
    return order


def plan_changes(tasks, index, chapter_order):
    """生成所有需要修改的 (task_id, new_prereqs)"""
    changes = []
    changed = set()

    # 1. 修正跨章节大门
    for subject, chapters in chapter_order.items():
        for i, chapter in enumerate(chapters):
            if i == 0:
                continue  # 第一章第一节没有前置，这是对的
            prev_chapter = chapters[i - 1]
            prev_exam_id = index.get((subject, prev_chapter), {}).get("exam")
            curr_first_review = index.get((subject, chapter), {}).get("first_review")

            if prev_exam_id is None:
                print(f"  [!] [{subject} 第{chapter}章] 未找到第{prev_chapter}章的章节总习题，跳过跨章大门")
                continue
            if curr_first_review is None:
                print(f"  [!] [{subject} 第{chapter}章] 未找到第{chapter}章的第一节复习任务，跳过")
                continue

            if curr_first_review["id"] not in changed:
                old = curr_first_review["old_prereqs"]
                # 新前置只应该是章节总习题
                new = json.dumps([prev_exam_id])
                if old != new:
                    changes.append({
                        "id": curr_first_review["id"],
                        "name": curr_first_review["name"],
                        "old_prereqs": old,
                        "new_prereqs": new,
                        "reason": f"跨章大门：章节总习题(第{prev_chapter}章)={prev_exam_id} → 第{chapter}章第1节复习"
                    })
                    changed.add(curr_first_review["id"])
                    print(f"  [*] [{subject} 第{chapter}章] 跨章大门: 第{chapter}章第1节复习 <- 章节总习题(第{prev_chapter}章)")

    # 2. 修正章内第一节复习的前置（应为无，而不是其他章节的东西）
    #    检查是否有第一节复习的前置指向了其他章节的内容
    for (subject, chapter), ch in index.items():
        first = ch.get("first_review")
        if first:
            old_prereqs = first.get("old_prereqs", "[]")
            try:
                old_list = json.loads(old_prereqs) if old_prereqs else []
            except:
                old_list = []
            # 如果第一章第一节有前置（不应该），清掉
            chapters = chapter_order.get(subject, [])
            if chapter == chapters[0] if chapters else None:
                if old_list:
                    changes.append({
                        "id": first["id"],
                        "name": first["name"],
                        "old_prereqs": old_prereqs,
                        "new_prereqs": "[]",
                        "reason": "第1章第1节无前置，解锁"
                    })
                    print(f"  [*] [{subject} 第{chapter}章] 第1节复习清除旧前置（应为无）")

    # 3. 确认章节总习题依赖所有小节习题
    for (subject, chapter), ch in index.items():
        exam_id = ch.get("exam")
        exercises = ch.get("exercises", [])
        if exam_id and exercises:
            exercise_ids = sorted([e["id"] for e in exercises])
            old_prereqs_raw = None
            for t in ch["all"]:
                if t["id"] == exam_id:
                    old_prereqs_raw = t.get("old_prereqs", "[]")
                    break
            if old_prereqs_raw:
                try:
                    old_list = json.loads(old_prereqs_raw) if old_prereqs_raw else []
                except:
                    old_list = []
                if set(old_list) != set(exercise_ids):
                    # 兼容已完成的习题（已完成的习题ID无需在prereq中）
                    changes.append({
                        "id": exam_id,
                        "name": f"{subject}-第{chapter}章-章节总习题",
                        "old_prereqs": old_prereqs_raw,
                        "new_prereqs": json.dumps(exercise_ids),
                        "reason": f"章节总习题应依赖全部 {len(exercise_ids)} 道小节习题"
                    })
                    print(f"  [*] [{subject} 第{chapter}章] 章节总习题更新习题依赖: {exercise_ids}")

    return changes


def apply_changes(conn, changes):
    """写入数据库"""
    cur = conn.cursor()
    count = 0
    for c in changes:
        cur.execute(
            "UPDATE tasks SET prerequisite_ids = ? WHERE id = ?",
            (c["new_prereqs"], c["id"])
        )
        count += 1
    conn.commit()
    return count


def main(dry_run=True):
    print("=" * 60)
    print("rebuild_chapter_deps.py — 跨章节依赖重建")
    print("=" * 60)
    print(f"模式: {'[预览] 不写入' if dry_run else '[写入] 正式修改'}")
    print()

    # 备份数据库
    import shutil
    backup_path = DB.with_name(DB.stem + BACKUP_SUFFIX + DB.suffix)
    shutil.copy2(DB, backup_path)
    print(f"[OK] 数据库已备份至: {backup_path.name}")
    print()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    tasks = load_tasks(conn)
    print(f"加载任务: {len(tasks)} 个")
    print()

    index = build_chapter_index(tasks)
    chapter_order = get_chapter_order(index)
    print("章节顺序:")
    for subj, chapters in sorted(chapter_order.items()):
        print(f"  {subj}: {chapters}")
    print()

    print("分析变更...")
    changes = plan_changes(tasks, index, chapter_order)
    print()

    if not changes:
        print("没有需要变更的跨章依赖。")
        conn.close()
        return

    print(f"将修改 {len(changes)} 处:")
    for c in changes:
        print(f"  [{c['id']}] {c['name']}")
        print(f"    原因: {c['reason']}")
        print(f"    旧: {c['old_prereqs']}")
        print(f"    新: {c['new_prereqs']}")
    print()

    if dry_run:
        print("[PREVIEW] 预览模式：未写入数据库")
        print("   如确认无误，以 --write 参数重新运行以实际写入")
        conn.close()
        return

    confirm = input("确认写入数据库？(y/n): ").strip().lower()
    if confirm != "y":
        print("已取消，未写入。")
        conn.close()
        return

    count = apply_changes(conn, changes)
    print(f"\n[OK] 已写入 {count} 处变更。")

    # 验证
    print("\n验证跨章大门:")
    conn.row_factory = None
    cur = conn.cursor()
    for subj, chapters in sorted(chapter_order.items()):
        for i, chapter in enumerate(chapters):
            if i == 0:
                continue
            prev_ch = chapters[i - 1]
            prev_exam = index.get((subj, prev_ch), {}).get("exam")
            first_rev = index.get((subj, chapter), {}).get("first_review")
            if prev_exam and first_rev:
                cur.execute("SELECT prerequisite_ids FROM tasks WHERE id = ?", (first_rev["id"],))
                prereqs_raw = cur.fetchone()[0]
                try:
                    prereqs = json.loads(prereqs_raw) if prereqs_raw else []
                except:
                    prereqs = []
                status = "[OK]" if prev_exam in prereqs else "[!!]"
                print(f"  {status} {subj} 第{chapter}章第1节复习 -> 依赖章节总习题({prev_ch}章)={prev_exam}")
                print(f"      当前前置: {prereqs}")

    conn.close()
    print()
    print("Done.")


if __name__ == "__main__":
    import sys
    dry = "--write" not in sys.argv
    main(dry_run=dry)
