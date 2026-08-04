# -*- coding: utf-8 -*-
import os, re

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

for fname in ["09_数据运算与位操作.md", "07_非数值数据与字符编码.md", "05_数据表示与编码概述.md"]:
    fpath = os.path.join(base, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"\n{'='*60}")
    print(f"FILE: {fname} (total {len(content.splitlines())} lines)")
    
    # 找所有含 pipe 的行
    for i, line in enumerate(content.splitlines(), 1):
        if '|' in line:
            # 标记行首的 pipe 序列
            prefix = ""
            rest = line
            while rest.startswith('|'):
                prefix += "|"
                rest = rest[1:]
            if len(prefix) > 1:
                print(f"  L{i:3d}: prefix={repr(prefix):12s} rest='{rest[:60]}'")
            elif prefix:
                print(f"  L{i:3d}: prefix={repr(prefix):12s} rest='{rest[:60]}'")
