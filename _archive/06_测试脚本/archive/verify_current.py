# -*- coding: utf-8 -*-
import os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

for fname in ["09_数据运算与位操作.md", "07_非数值数据与字符编码.md", "05_数据表示与编码概述.md"]:
    fpath = os.path.join(base, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip('\n')
        if stripped.startswith('|'):
            pipes = stripped.count('|')
            print(f"  L{i:3d} pipes={pipes}: '{stripped[:70]}'")
