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

    # 修复1: 移除行首连续 pipe 前缀，保留表格结构
    # 表格行的多余 pipe 前缀是 1-4 个 pipe：
    # 原来的 5-pipe: |||||col|col| → 现在变成 |col|col| (正确) 或 ||col|col| (需再修)
    # 原来的 6-pipe: ||||||col|col| → 现在变成 ||col|col| (需再修)
    # 统一策略：行首的连续 1-4 个 pipe 后面跟内容行
    # 替换模式：
    #   |||xxx → |xxx   (3 pipes → 1)
    #   ||xxxx → |xxxx  (2 pipes → 1)
    # 但要确保不是分隔行如 |------|
    
    # 先处理 3-pipe 前缀: ||| 开头 → | 开头
    content = re.sub(r'^(\|\|\|)([^\|])', r'|\2', content, flags=re.MULTILINE)
    # 再处理 2-pipe 前缀: || 开头 → | 开头
    content = re.sub(r'^(\|\|)([^\|])', r'|\2', content, flags=re.MULTILINE)

    if content != original:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Fixed: {os.path.basename(fpath)}")
    else:
        print(f"No change: {os.path.basename(fpath)}")
