# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
src_dir = os.path.join(base, 'src', 'notes', '未分类')
dst_dir = os.path.join(base, 'src', 'notes', '已分类', '大物')
os.makedirs(dst_dir, exist_ok=True)

docx_files = [
    '静电场与恒定电流基础.docx',
    '通电导线的稳恒磁场_剪辑1.docx',
    '无限长载流圆柱磁场分析.docx',
]

for fname in docx_files:
    src = os.path.join(src_dir, fname)
    dst = os.path.join(dst_dir, fname)
    if not os.path.exists(src):
        print(f'MISSING: {src}')
        continue
    if os.path.exists(dst):
        print(f'ALREADY EXISTS at destination: {dst}')
        continue
    # 验证对应的txt已成功生成
    txt_path = os.path.join(dst_dir, fname.replace('.docx', '.txt'))
    if not os.path.exists(txt_path):
        print(f'SKIP: txt not extracted yet for {fname}')
        continue
    txt_size = os.path.getsize(txt_path)
    if txt_size < 100:
        print(f'SKIP: txt too small ({txt_size}B) for {fname}')
        continue
    # 移动docx
    import shutil
    shutil.move(src, dst)
    print(f'MOVED: {fname} -> {os.path.relpath(dst, base)} ({os.path.getsize(dst)//1024}KB)')

# 检查未分类目录是否为空
remaining = [f for f in os.listdir(src_dir) if not f.startswith('.gitkeep')]
print(f'\n未分类目录剩余文件: {len(remaining)} 个')
for f in remaining:
    print(f'  {f}')
