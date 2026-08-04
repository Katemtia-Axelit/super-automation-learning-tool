"""直接 UPDATE 剩余 4 个未关联的笔记复习任务"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "task_publisher.db"

# 直接按 ID 更新（安全、无风险）
UPDATES = [
    (57, "高等数学/11-02_一般微分方程（二）·欧拉方程与常系数非齐次方程.md"),
    (286, "电子技术/06_晶体三极管·共射放大电路稳定性.md"),
    (288, "电子技术/07_晶体三极管·共射放大电路稳定性与多级放大.md"),
    (294, "电子技术/09_逻辑表达式·\"与非\"和\"或非\"门.md"),
]

conn = sqlite3.connect(DB)
cur = conn.cursor()

for task_id, vault_path in UPDATES:
    cur.execute(
        "UPDATE tasks SET linked_note_path=? WHERE id=?",
        (vault_path, task_id)
    )
    if cur.rowcount:
        print(f"[OK] [{task_id}] -> {vault_path}")
    else:
        print(f"[--] [{task_id}] not found or no change")

conn.commit()

# 验证
cur.execute("SELECT COUNT(*) as c FROM tasks WHERE linked_note_path IS NOT NULL AND linked_note_path != ?", ('',))
print(f"\nTotal linked: {cur.fetchone()[0]}")
conn.close()
print("Done.")
