# -*- coding: utf-8 -*-
import os

fpath = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\知识点\高等数学\向量积.md"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 根据调试结果：第17-28行（含）是"八大性质"表
# 第17行(索引16)是"### 八大性质"标题
# 第18行(索引17)是空行
# 第19-28行(索引18-27)是9列表格（5列内容+4列空列）
# 替换为2列的简洁表格

new_lines = [
    "### 八大性质\n",
    "\n",
    "| 性质 | 表达式 |\n",
    "|------|--------|\n",
    "| 反交换律 | $\\vec{a} \\times \\vec{b} = -\\vec{b} \\times \\vec{a}$ |\n",
    "| 与数乘结合 | $(k\\vec{a}) \\times \\vec{b} = k(\\vec{a} \\times \\vec{b}) = \\vec{a} \\times (k\\vec{b})$ |\n",
    "| 分配律 | $\\vec{a} \\times (\\vec{b} + \\vec{c}) = \\vec{a} \\times \\vec{b} + \\vec{a} \\times \\vec{c}$ |\n",
    "| 自身叉积为零 | $\\vec{a} \\times \\vec{a} = \\vec{0}$ |\n",
    "| 与零向量 | $\\vec{a} \\times \\vec{0} = \\vec{0}$ |\n",
    "| 不满足结合律 | $\\vec{a} \\times (\\vec{b} \\times \\vec{c}) \\neq (\\vec{a} \\times \\vec{b}) \\times \\vec{c}$ |\n",
    "| 平行判定 | $\\vec{a} \\parallel \\vec{b} \\iff \\vec{a} \\times \\vec{b} = \\vec{0}$ |\n",
    "| 模的性质 | $|\\vec{a} \\times \\vec{b}| = |\\vec{a}| \\cdot |\\vec{b}| \\cdot \\sin\\theta$ |\n",
    "\n",
]

# 替换索引 16 到 27（inclusive），共 12 行
# 替换后lines[16:28] = new_lines
lines[16:28] = new_lines

with open(fpath, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Fixed: 向量积.md")
# 验证
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()
for i, line in enumerate(content.split('\n')[15:35], start=16):
    print(f"{i}: {line[:80]}")
