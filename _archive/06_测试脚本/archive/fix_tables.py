# -*- coding: utf-8 -*-
import re, os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"
files = [
    os.path.join(base, "07_非数值数据与字符编码.md"),
    os.path.join(base, "09_数据运算与位操作.md"),
    os.path.join(base, "05_数据表示与编码概述.md"),
]

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    original = content

    # 修复 1: 5个|前缀 → 1个|前缀（移除多余的4个|）
    content = re.sub(r'^\|\|\|\|\|', '|', content, flags=re.MULTILINE)

    # 修复 2: 4个|前缀 → 1个|前缀（移除多余的3个|）
    content = re.sub(r'^\|\|\|\|', '|', content, flags=re.MULTILINE)

    # 修复 3: 移除 "||" 行首双| 前缀（单列表格的误加前缀）
    # 但要保留正常的 "| xxx" 行（正常表格数据行）
    # 策略：行首为 "| |" 后面跟非空内容的，改为 "| "
    # 但第2列本身可能为空，所以我们用上下文
    # 简化：把 "|| " 替换为 "| "（只处理表头和分隔行）
    content = re.sub(r'^\|\| ', '| ', content, flags=re.MULTILINE)

    if content != original:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Fixed: {os.path.basename(fpath)}")
    else:
        print(f"No change: {os.path.basename(fpath)}")
