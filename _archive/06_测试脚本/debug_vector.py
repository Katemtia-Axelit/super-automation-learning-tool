# -*- coding: utf-8 -*-
import os

fpath = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\知识点\高等数学\向量积.md"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 打印第17-30行的内容（含行号）以便调试
for i, line in enumerate(lines[16:31], start=17):
    print(f"{i}: {repr(line[:80])}")
