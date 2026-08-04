# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

notes_dir = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术')

for f in notes_dir.glob('*.md'):
    with open(f, 'rb') as fh:
        content_bytes = fh.read()

    # Replace literal \\ (double backslash) in image paths with /
    new_bytes = content_bytes.replace(b'\\\\', b'/')

    if content_bytes != new_bytes:
        with open(f, 'wb') as fh:
            fh.write(new_bytes)
        count = content_bytes.count(b'\\\\')
        print(f'Fixed {count} paths in: {f.name}')

print('Done')
