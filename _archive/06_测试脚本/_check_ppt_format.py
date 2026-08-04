# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
ppt_folder = os.path.join(base, 'data', '讲义')

for f in sorted(os.listdir(ppt_folder)):
    if f.endswith('.ppt') and not f.endswith('.pptx'):
        path = os.path.join(ppt_folder, f)
        header = open(path, 'rb').read(8).hex()
        size = os.path.getsize(path)
        print(f'{f}')
        print(f'  Size: {size}, Header: {header}')
        # OLE2 header is d0cf11e0a1b11ae1, ZIP header is 504b0304
        if header.startswith('d0cf11e0'):
            print('  Format: OLE2 (.ppt - legacy binary)')
        elif header.startswith('504b0304'):
            print('  Format: ZIP/XML (.pptx - Open XML)')
        else:
            print('  Format: UNKNOWN')
