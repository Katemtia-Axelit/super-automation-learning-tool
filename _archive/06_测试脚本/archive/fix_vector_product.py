# -*- coding: utf-8 -*-
import re, os

fpath = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\知识点\高等数学\向量积.md"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()
original = content

# 修复1: 把 9 列的"八大性质"表改为单列格式（移除所有空列）
# 匹配从表头行到模的性质行的完整表格块
old_table = """| 性质     | 表达式                                                                                    |                        |     |         |     |         |               |
| ------ | -------------------------------------------------------------------------------------- | ---------------------- | --- | ------- | --- | ------- | ------------- |
| 反交换律   | $\vec{a} \times \vec{b} = -\vec{b} \times \vec{a}$                                     |                        |     |         |     |         |               |
| 与数乘结合  | $(k\vec{a}) \times \vec{b} = k(\vec{a} \times \vec{b}) = \vec{a} \times (k\vec{b})$    |                        |     |         |     |         |               |
| 分配律    | $\vec{a} \times (\vec{b} + \vec{c}) = \vec{a} \times \vec{b} + \vec{a} \times \vec{c}$ |                        |     |         |     |         |               |
| 自身叉积为零 | $\vec{a} \times \vec{a} = \vec{0}$                                                     |                        |     |         |     |         |               |
| 与零向量   | $\vec{a} \times \vec{0} = \vec{0}$                                                     |                        |     |         |     |         |               |
| 不满足结合律 | $\vec{a} \times (\vec{b} \times \vec{c}) \neq (\vec{a} \times \vec{b}) \times \vec{c}$ |                        |     |         |     |         |               |
| 平行判定   | $\vec{a} \parallel \vec{b} \iff \vec{a} \times \vec{b} = \vec{0}$                      |                        |     |         |     |         |               |
| 模的性质   | $|                                                                                      | \vec{a} \times \vec{b} | =   | \vec{a} | \,  | \vec{b} | \,\sin\theta$ |"""

new_table = """| 性质 | 表达式 |
|------|--------|
| 反交换律 | $\\vec{a} \\times \\vec{b} = -\\vec{b} \\times \\vec{a}$ |
| 与数乘结合 | $(k\\vec{a}) \\times \\vec{b} = k(\\vec{a} \\times \\vec{b}) = \\vec{a} \\times (k\\vec{b})$ |
| 分配律 | $\\vec{a} \\times (\\vec{b} + \\vec{c}) = \\vec{a} \\times \\vec{b} + \\vec{a} \\times \\vec{c}$ |
| 自身叉积为零 | $\\vec{a} \\times \\vec{a} = \\vec{0}$ |
| 与零向量 | $\\vec{a} \\times \\vec{0} = \\vec{0}$ |
| 不满足结合律 | $\\vec{a} \\times (\\vec{b} \\times \\vec{c}) \\neq (\\vec{a} \\times \\vec{b}) \\times \\vec{c}$ |
| 平行判定 | $\\vec{a} \\parallel \\vec{b} \\iff \\vec{a} \\times \\vec{b} = \\vec{0}$ |
| 模的性质 | $|\\vec{a} \\times \\vec{b}| = |\\vec{a}| \\cdot |\\vec{b}| \\cdot \\sin\\theta$ |"""

content = content.replace(old_table, new_table)

if content != original:
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed: 向量积.md")
else:
    print("No change: 向量积.md")
