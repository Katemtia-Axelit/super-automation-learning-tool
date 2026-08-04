# -*- coding: utf-8 -*-
import os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

# ============================================================
# 文件 09: 数据运算与位操作
# ============================================================
f09 = os.path.join(base, "09_数据运算与位操作.md")
with open(f09, "r", encoding="utf-8") as f:
    lines = f.readlines()

changes = []
for i, line in enumerate(lines):
    orig = line
    # 修复1: ALU表 - 去掉首列空|前缀，合并为标准4列
    # 第53行: ||   |  运算类型  |  具体操作  |  数据视角  |
    # 第54行: ||------|------|----------|----------|
    # 第55行: ||   |  **算术运算**  |  ADD, SUB, MUL, DIV  |  把二进制串当作**数值**来算  |
    # 第56行: ||   |  **逻辑运算**  |  AND, OR, NOT, XOR, SHIFT  |  把二进制串当作**位串**来操作  |
    if i in (52, 53, 54, 55) and '运算类型' in lines[i]:
        lines[i] = lines[i].replace('||   | ', '| ').replace('||------|', '|------|')
        lines[i] = lines[i].replace('||   |', '|')  # 行55-56
    # 修复2: AND真值表 - 同上模式
    if i in (65, 66, 67, 68) and ' A  ' in lines[i]:
        lines[i] = lines[i].replace('||   | ', '| ').replace('||---|---|', '|---|')
        lines[i] = lines[i].replace('||   |', '|')
    # 修复3: 大小写转换表 - 去掉第三行中多余的|
    # 第275行: | `ch \ | 0x20` | 大写 → 小写（第 5 位置 1） |
    if 'ch \\' in line and '0x20' in line and '|  大写' in line:
        lines[i] = line.replace('| `ch \\ | 0x20`', '| `ch \\| 0x20`')
    if orig != lines[i]:
        changes.append(f"  L{i+1}: {orig.strip()[:50]} → {lines[i].strip()[:50]}")

with open(f09, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"Fixed: 09_数据运算与位操作.md")
for c in changes:
    print(c)

# ============================================================
# 文件 07: 非数值数据与字符编码
# ============================================================
f07 = os.path.join(base, "07_非数值数据与字符编码.md")
with open(f07, "r", encoding="utf-8") as f:
    lines = f.readlines()

changes07 = []
for i, line in enumerate(lines):
    orig = line
    # 修复: 按位运算表中按位或行的 | 符号转义
    # 第98行: | **按位或** | ` | ` | ... → | **按位或** | ` \| ` | ...
    if '按位或' in line and ' | `' in line:
        lines[i] = line.replace('` | `', '` \\| `')
    if orig != lines[i]:
        changes07.append(f"  L{i+1}: {orig.strip()[:60]} → {lines[i].strip()[:60]}")

with open(f07, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"\nFixed: 07_非数值数据与字符编码.md")
for c in changes07:
    print(c)
