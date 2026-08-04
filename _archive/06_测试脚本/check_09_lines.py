# -*- coding: utf-8 -*-
import os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

f09 = os.path.join(base, "09_数据运算与位操作.md")
with open(f09, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== 09文件相关行精确内容 ===")
for i in range(52, 72):
    print(f"L{i+1}: {repr(lines[i][:70])}")
print()
for i in range(113, 122):
    print(f"L{i+1}: {repr(lines[i][:70])}")
print()
for i in range(273, 280):
    print(f"L{i+1}: {repr(lines[i][:70])}")
