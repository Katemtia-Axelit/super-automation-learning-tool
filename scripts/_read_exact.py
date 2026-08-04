# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding='utf-8')
files = [
    (r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术\10_组合逻辑电路分析与设计.md', 165, 170),
    (r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\电子技术\11_编码器与集成电路实现.md', 43, 48),
]
for path, start, end in files:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f'=== {path.split(chr(92))[-1]} lines {start}-{end} ===')
    for i, line in enumerate(lines[start-1:end], start=start):
        print(f'{i}: {repr(line)}')
