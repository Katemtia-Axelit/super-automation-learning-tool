# -*- coding: utf-8 -*-
import os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

for fname in ["09_数据运算与位操作.md", "07_非数值数据与字符编码.md", "05_数据表示与编码概述.md"]:
    fpath = os.path.join(base, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip('\n')
        if stripped.startswith('|') and '|' in stripped:
            pipes = stripped.count('|')
            # 检查是否有多余前缀（连续2个以上|开头但内容不含有效单元格）
            # 检查列对齐：分隔行的|数量应该和表头/数据行匹配
            if pipes >= 4:
                # 截取前60字符显示
                try:
                    snippet = stripped[:65]
                except:
                    snippet = stripped[:65]
                print(f"  L{i:3d} pipes={pipes}: {snippet}")
