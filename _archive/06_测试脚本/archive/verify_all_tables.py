# -*- coding: utf-8 -*-
import os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

files = {
    "07_非数值数据与字符编码.md": [
        (74, "blank"),
        (75, "header line 1"),
        (76, "separator"),
        (77, "data row 1"),
    ],
    "09_数据运算与位操作.md": [
        (52, "blank line"),
        (53, "ALU table header"),
        (54, "separator"),
        (55, "data row 1"),
        (65, "AND table header"),
        (66, "separator"),
        (67, "data row 1"),
        (115, "OR table header"),
        (149, "NOT table header"),
        (169, "XOR table header"),
        (237, "shift table header"),
        (256, "shift effect header"),
        (272, "case conv header"),
    ],
    "05_数据表示与编码概述.md": [
        (44, "blank"),
        (45, "header"),
        (46, "separator"),
        (47, "data row 1"),
        (64, "blank"),
        (65, "header"),
        (80, "binary table"),
        (109, "data type"),
        (126, "3 elements"),
        (136, "radix"),
        (148, "fixed/float"),
        (175, "unit"),
        (184, "CPU width"),
        (193, "range"),
        (250, "bin/hex"),
        (298, "special values"),
    ],
}

for fname, checks in files.items():
    fpath = os.path.join(base, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    for line_num, desc in checks:
        idx = line_num - 1
        if idx < len(lines):
            line = lines[idx]
            pipes = line.count('|')
            stripped = line.rstrip('\n')
            # Show first 80 chars with pipe positions
            display = stripped[:80].replace('\n', '↵')
            print(f"  L{line_num:3d} [{desc:25s}] pipes={pipes:2d}: '{display}'")
        else:
            print(f"  L{line_num:3d} [{desc:25s}]: OUT OF RANGE (total {len(lines)} lines)")
