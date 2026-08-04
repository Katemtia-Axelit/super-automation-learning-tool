# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

notes_dir = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术')

for f in notes_dir.glob('*.md'):
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # Find all image lines
    lines = content.split('\n')
    new_lines = []
    changed = False
    for line in lines:
        if 'extracted_pics' in line or 'diagrams' in line:
            # Replace ALL backslash-char sequences with forward-slash-char
            # In Python text: single backslash char is chr(92)
            new_line = line.replace(chr(92), '/')
            if new_line != line:
                new_lines.append(new_line)
                changed = True
                print(f'{f.name}: {repr(line[25:55])} -> {repr(new_line[25:55])}')
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if changed:
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(new_lines))

print('Done')
