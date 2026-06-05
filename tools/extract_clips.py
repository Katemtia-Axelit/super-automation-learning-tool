import docx
import os
from pathlib import Path

BASE = Path(__file__).parent.parent / "src" / "notes" / "已分类"

files = [
    BASE / '高数' / '微分法求偏导数讲解.docx',
    BASE / '高数' / '解析空间曲线与曲面问题.docx',
    BASE / '计算机' / '计算机数据表示与编码.docx',
    BASE / '计算机' / '计算机数据表示与编码(1).docx',
    BASE / '大物' / '钢体定轴转动模型.docx',
]

for path in files:
    out_path = path.replace('.docx', '_raw.txt')
    try:
        doc = docx.Document(path)
        text = '\n'.join([p.text for p in doc.paragraphs])
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
        fname = os.path.basename(path)
        ofname = os.path.basename(out_path)
        print(f'OK: {fname} -> {ofname} ({len(text)} chars)')
    except Exception as e:
        print(f'ERR: {path}: {e}')