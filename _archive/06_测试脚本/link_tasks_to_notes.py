"""
保守更新：只填 linked_note_path，不删除任何数据
遍历 vault 中所有笔记文件，用文件名规则匹配到现有任务
"""

import sqlite3, re, os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "task_publisher.db"
VAULT_DIR = Path(__file__).parent.parent / "src" / "notes" / "vault"

# 学科映射：任务名简称 → vault目录名
SUBJECT_MAP = {
    "高数": "高等数学",
    "线代": "线性代数",
    "大物": "大学物理",
    "计算机": "计算机",
    "电子技术": "电子技术",
    "CET4": "英语四级",
}


def build_note_index():
    """扫描 vault，建立 note_key -> vault_relative_path 的索引"""
    index = {}  # key: note stem (原始) -> "subject/file.md"

    for subj_dir in VAULT_DIR.iterdir():
        if not subj_dir.is_dir() or subj_dir.name.startswith('.'):
            continue
        for f in subj_dir.glob("*.md"):
            stem = f.stem
            if stem == subj_dir.name:
                continue
            rel_path = f"{subj_dir.name}/{f.name}"

            # 直接用原始 stem 作为 key
            index[stem] = rel_path

            # 如果标题含 ·（如 xxx·yyy.md），也存一个截断版 key（去掉 · 及之后的部分）
            # 这样可以匹配任务名中没有 · 后缀的情况
            if '·' in stem:
                base = stem.split('·')[0]
                if base not in index:
                    index[base] = rel_path

    print(f"索引了 {len(index)} 个笔记文件")
    return index


def parse_task_name(name):
    """从末尾 -复习 往前截取 note_key（用精确字符集避免越界）"""
    if not name.endswith("-复习"):
        return None
    prefix = name[:-4]
    # note title: 中文/字母数字下划线，不含连字符（任务中 - 是分隔符）
    # 格式1: 06-01_标题 或 11-02_标题（含章节号）
    m = re.search(r'-(\d{2}[-_]\d{2}_[\w\u4e00-\u9fff·（）]+)$', prefix)
    if m:
        return m.group(1)
    # 格式2: 01_标题（无章节前缀，如大物）
    m2 = re.search(r'-(\d{2}_[\w\u4e00-\u9fff·（）]+)$', prefix)
    if m2:
        return m2.group(1)
    return None


def fuzzy_match(note_key, index):
    """模糊匹配：尝试从 note_key 中提取有效 stem 部分去匹配 index"""
    # 尝试去掉前缀（从末尾往前找到第一个 - 编号模式）
    m = re.search(r'(\d{2}[-_]\d{2}_.+)$', note_key)
    if m:
        stem_part = m.group(1)
        if stem_part in index:
            return index[stem_part]
    # 尝试去掉 CET4 前缀
    m2 = re.match(r'CET4[_-].+?[_-](.+)$', note_key)
    if m2:
        suffix = m2.group(1)
        for k, v in index.items():
            if k.endswith(suffix):
                return v
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 确保列存在
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN linked_note_path TEXT")
    except sqlite3.OperationalError:
        pass

    index = build_note_index()

    # 获取所有任务（按 id 顺序）
    cur.execute("SELECT id, name FROM tasks ORDER BY id")
    tasks = cur.fetchall()

    updated = 0
    not_found = []

    for task in tasks:
        if not task["name"]:
            continue
        # 跳过非复习类任务（只处理笔记复习任务）
        if not task["name"].endswith("-复习"):
            continue

        note_key = parse_task_name(task["name"])
        if not note_key:
            not_found.append((task["id"], task["name"], "no parse"))
            continue

        # 直接精确匹配
        vault_path = index.get(note_key)
        if not vault_path:
            # 模糊匹配
            vault_path = fuzzy_match(note_key, index)

        if vault_path:
            cur.execute(
                "UPDATE tasks SET linked_note_path=? WHERE id=?",
                (vault_path, task["id"])
            )
            updated += 1
        else:
            not_found.append((task["id"], task["name"], f"key='{note_key}'"))

    conn.commit()

    print(f"\n[OK] 更新了 {updated} 个任务的 linked_note_path")
    print(f"[WARN] 未匹配 {len(not_found)} 个：")
    for tid, name, reason in not_found[:20]:
        print(f"  [{tid}] {name}")
        print(f"        reason: {reason}")

    conn.close()


if __name__ == "__main__":
    main()
