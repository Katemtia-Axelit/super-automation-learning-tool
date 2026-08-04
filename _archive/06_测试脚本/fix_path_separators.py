# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

notes_dir = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术')

for f in notes_dir.glob('*.md'):
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # Find image lines with backslash paths
    lines = content.split('\n')
    changed = False
    new_lines = []
    for line in lines:
        if 'extracted_pics' in line or 'diagrams' in line:
            # Check if it has backslash
            if '\\' in line:
                # Replace backslashes with forward slashes in image paths
                line = line.replace('\\extracted_pics', '/extracted_pics')
                line = line.replace('\\diagrams', '/diagrams')
                changed = True
        new_lines.append(line)

    if changed:
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(new_lines))
        print(f'Fixed: {f.name}')

print('Done')
