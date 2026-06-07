"""直接导入任务 JSON 文件到数据库"""
import sys
sys.path.insert(0, r"D:\Axelit\工作\trae\超级自动化学习工具")

from src.tasks.models.database import Database
from src.tasks.services.ai_import_processor import AIImportProcessor

db = Database()
processor = AIImportProcessor(db)

results, processed_files = processor.process_all_imports()

if results:
    for r in results:
        print(f"[{r['action']}] {r['explanation']}")
        for change in r.get('changes', []):
            print(f"  - {change}")
    
    processor.delete_processed_files(processed_files)
    print(f"\n导入完成！共处理 {len(results)} 个文件")
else:
    print("没有找到需要导入的文件")

# 验证
cursor = db.conn.cursor()
cursor.execute("SELECT COUNT(*) FROM tasks")
count = cursor.fetchone()[0]
print(f"\n数据库中任务总数: {count}")

# 按标签分组统计
cursor.execute("""
    SELECT DISTINCT t.id, t.name FROM tasks t
    JOIN task_tags tt ON t.id = tt.task_id
    JOIN tags g ON tt.tag_id = g.id
    WHERE g.name = '四级'
""")
cet4 = len(cursor.fetchall())
print(f"  CET-4: {cet4}")

cursor.execute("SELECT DISTINCT t.id FROM tasks t JOIN task_tags tt ON t.id = tt.task_id JOIN tags g ON tt.tag_id = g.id WHERE g.name = '电子技术'")
print(f"  电子技术: {len(cursor.fetchall())}")

cursor.execute("SELECT DISTINCT t.id FROM tasks t JOIN task_tags tt ON t.id = tt.task_id JOIN tags g ON tt.tag_id = g.id WHERE g.name = '计算机'")
print(f"  计算机: {len(cursor.fetchall())}")

cursor.execute("SELECT DISTINCT t.id FROM tasks t JOIN task_tags tt ON t.id = tt.task_id JOIN tags g ON tt.tag_id = g.id WHERE g.name = '线性代数'")
print(f"  线性代数: {len(cursor.fetchall())}")

cursor.execute("SELECT DISTINCT t.id FROM tasks t JOIN task_tags tt ON t.id = tt.task_id JOIN tags g ON tt.tag_id = g.id WHERE g.name = '英语Ⅱ'")
print(f"  英语Ⅱ: {len(cursor.fetchall())}")

cursor.execute("SELECT DISTINCT t.id FROM tasks t JOIN task_tags tt ON t.id = tt.task_id JOIN tags g ON tt.tag_id = g.id WHERE g.name = '高数'")
print(f"  高等数学: {len(cursor.fetchall())}")

cursor.execute("SELECT DISTINCT t.id FROM tasks t JOIN task_tags tt ON t.id = tt.task_id JOIN tags g ON tt.tag_id = g.id WHERE g.name = '大物'")
print(f"  大学物理: {len(cursor.fetchall())}")

# 检查依赖关系
cursor.execute("SELECT COUNT(*) FROM task_dependencies")
dep_count = cursor.fetchone()[0]
print(f"\n依赖关系总数: {dep_count}")

db.close()
