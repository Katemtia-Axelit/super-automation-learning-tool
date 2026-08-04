# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import docx

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
src_dir = os.path.join(base, 'src', 'notes', '未分类')
out_dir = os.path.join(base, 'src', 'notes', '已分类', '大物')
os.makedirs(out_dir, exist_ok=True)

docx_files = [
    '静电场与恒定电流基础.docx',
    '通电导线的稳恒磁场_剪辑1.docx',
    '无限长载流圆柱磁场分析.docx',
]

for fname in docx_files:
    src = os.path.join(src_dir, fname)
    out = os.path.join(out_dir, fname.replace('.docx', '.txt'))
    if not os.path.exists(src):
        print(f'MISSING: {src}')
        continue
    doc = docx.Document(src)
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(paras))
    total_chars = sum(len(p) for p in paras)
    print(f'OK: {fname} -> {len(paras)} paragraphs, {total_chars} chars -> {out}')
