# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

notes_dir = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术')

for f in notes_dir.glob('*.md'):
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # The file contains double backslashes in paths (\\). Replace with /
    # Pattern: ..\extracted_pics\ or ..\diagrams\
    # In the file, these appear as double backslashes
    new = content.replace(r'..\extracted_pics', '../extracted_pics')
    new = new.replace(r'..\diagrams', '../diagrams')

    if content != new:
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(new)
        # Count replacements
        count = new.count('../extracted_pics') + new.count('../diagrams')
        print(f'Fixed {count} paths in: {f.name}')
    else:
        print(f'No change: {f.name}')

print('Done')
