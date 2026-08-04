# -*- coding: utf-8 -*-
import re, os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"

def fix_file(fpath):
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    orig = content
    
    # 修复策略：
    # 1. 对所有表格数据行/表头行，在每个单元格前后加空格（改善格式）
    #    模式：|xxx|yyy|zzz| → | xxx | yyy | zzz |
    #    关键：只匹配行首有 | 且第一个单元格非空 的行（这样分隔行|------|不会受影响）
    def add_spaces(line):
        if line.startswith('|') and '|' in line[1:]:
            # 检查是否包含分隔符行特征（全是短横线和冒号）
            stripped = line.strip()
            if all(c in '-: |' for c in stripped) and ('-' in stripped):
                return line  # 分隔行保持原样
            # 逐个 | 分割，添加空格
            parts = line.rstrip('\n').split('|')
            # parts[0]是空字符串，parts[-1]是空字符串
            result = '|' + '|'.join(' ' + p + ' ' for p in parts[1:-1]) + '|'
            return result + '\n'
        return line
    
    new_lines = [add_spaces(line) for line in content.splitlines(keepends=True)]
    content = ''.join(new_lines)
    
    if content != orig:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False

files = [
    os.path.join(base, "07_非数值数据与字符编码.md"),
    os.path.join(base, "09_数据运算与位操作.md"),
    os.path.join(base, "05_数据表示与编码概述.md"),
]
for f in files:
    changed = fix_file(f)
    print(f"{'Fixed' if changed else 'No change'}: {os.path.basename(f)}")
