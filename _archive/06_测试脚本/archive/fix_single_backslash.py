# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

notes_dir = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术')

for f in notes_dir.glob('*.md'):
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # File contains single backslash in paths: ../extracted_pics\ch01_...
    # Need to replace with forward slash
    new = content.replace(r'..\extracted_pics', '../extracted_pics')
    new = new.replace(r'..\diagrams', '../diagrams')

    if content != new:
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(new)
        count_old = content.count(r'..\extracted_pics') + content.count(r'..\diagrams')
        print(f'Fixed {count_old} paths in: {f.name}')
    else:
        print(f'No change: {f.name}')
print('Done')
