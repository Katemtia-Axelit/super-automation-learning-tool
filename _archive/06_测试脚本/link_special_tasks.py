"""
补录剩余 18 个特殊格式任务的 linked_note_path
（基于 vault 实际文件名直接映射，不改其他数据）
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "task_publisher.db"

# 手动映射：任务名片段 → vault 相对路径
MANUAL_MAP = [
    # 高数 11-02（标题含 · 和 （））
    ("一般微分方程（二）", "高等数学/11-02_一般微分方程（二）·欧拉方程与常系数非齐次方程.md"),
    # 大物 20（单章节编号 20_）
    ("20_傅科摆", "大学物理/20_傅科摆-科里奥利力与科氏加速度.md"),
    # 电子技术（含 ·）
    ("06_晶体三极管·共射放大电路稳定性", "电子技术/06_晶体三极管·共射放大电路稳定性.md"),
    ("07_晶体三极管·共射放大电路稳定性与多级放大", "电子技术/07_晶体三极管·共射放大电路稳定性与多级放大.md"),
    ("09_逻辑表达式·\"与非\"和\"或非\"门", '电子技术/09_逻辑表达式·"与非"和"或非"门.md'),
    # CET4-写作（格式：模块名-具体标题）
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-写作保底原则与核心策略.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-句型升级与词汇替换.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-段间逻辑与文章结构.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-长句扩写与句型改写.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-现象分析类模板.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-原因建议类模板.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-议论文模板.md"),
    ("CET4-写作-英语四级-写作-...", "英语四级/CET4-写作-图表描述与数据报道.md"),
    # CET4-听力
    ("CET4-听力-英语四级-听力-...", "英语四级/CET4-听力-新闻听力结构与答题技巧.md"),
    ("CET4-听力-英语四级-听力-...", "英语四级/CET4-听力-长对话理解技巧与关键词定位.md"),
    # CET4-阅读
    ("CET4-阅读-英语四级-阅读-...", "英语四级/01CET4-阅读-仔细阅读题型与答题策略.md"),
    ("CET4-阅读-英语四级-阅读-...", "英语四级/02CET4-阅读-词汇理解与快速阅读技巧.md"),
    ("CET4-阅读-英语四级-阅读-...", "英语四级/03CET4-阅读-选词填空与段落匹配技巧.md"),
    # CET4-语法
    ("CET4-语法-英语四级-语法-...", "英语四级/英语四级-语法-谓语动词与非谓语动词.md"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    updated = 0
    skipped = []

    for keyword, vault_path in MANUAL_MAP:
        cur.execute(
            "SELECT id, name FROM tasks WHERE name LIKE ? AND linked_note_path IS NULL",
            (f"%{keyword}%",)
        )
        rows = cur.fetchall()
        if rows:
            for row in rows:
                cur.execute(
                    "UPDATE tasks SET linked_note_path=? WHERE id=?",
                    (vault_path, row["id"])
                )
                updated += 1
                print(f"  [OK] [{row['id']}] {row['name'][:40]} → {vault_path}")
        else:
            skipped.append(keyword)

    conn.commit()

    print(f"\n补充更新: {updated} 个")
    if skipped:
        print(f"未匹配: {skipped}")

    # 验证总数
    cur.execute("SELECT COUNT(*) as c FROM tasks WHERE linked_note_path IS NOT NULL AND linked_note_path != ''")
    total_linked = cur.fetchone()["c"]
    print(f"总计关联: {total_linked} 个任务")

    conn.close()


if __name__ == "__main__":
    main()
