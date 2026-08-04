# -*- coding: utf-8 -*-
import re, os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"
fpath = os.path.join(base, "07_非数值数据与字符编码.md")

with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 找第75行前后的内容
for i in range(73, 80):
    print(f"Line {i+1}: {repr(lines[i][:60])}")

# 测试替换
test_lines = []
for i, line in enumerate(lines):
    new_line = re.sub(r'^(\|\|)([^\|])', lambda m: '|' + m.group(2), line)
    test_lines.append(new_line)

changed = any(new != old for new, old in zip(test_lines, lines))
print(f"\nWould change: {changed}")
if changed:
    for i, (old, new) in enumerate(zip(lines, test_lines)):
        if old != new:
            print(f"Line {i+1}: {repr(old[:60])} → {repr(new[:60])}")
