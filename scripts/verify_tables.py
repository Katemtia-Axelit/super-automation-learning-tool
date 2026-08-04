# -*- coding: utf-8 -*-
import os

base = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\计算机"
files = [
    ("07_非数值数据与字符编码.md", [
        (74, "表头:子表达式"),
        (95, "按位与表头"),
        (114, "字符类别"),
        (132, "控制字符"),
        (140, "可打印字符"),
        (178, "汉字对比"),
        (199, "编码层"),
        (229, "点阵大小"),
        (244, "区位码"),
        (255, "Unicode"),
        (270, "四种编码汇总"),
        (296, "编码方式乱码"),
        (308, "BOM"),
    ]),
    ("09_数据运算与位操作.md", [
        (52, "ALU表头"),
        (65, "AND真值表"),
        (115, "OR真值表"),
        (149, "NOT真值表"),
        (169, "XOR真值表"),
        (237, "移位类型"),
        (256, "移位效果"),
        (272, "大小写转换"),
    ]),
    ("05_数据表示与编码概述.md", [
        (45, "问题表头"),
        (65, "层次"),
        (80, "物理状态"),
        (109, "数据类型"),
        (126, "三要素"),
        (136, "进制"),
        (148, "定点浮点"),
        (175, "单位"),
        (184, "CPU位宽"),
        (193, "表示范围"),
        (250, "二进制十六进制"),
        (298, "特殊值"),
    ]),
]

for fname, checks in files:
    fpath = os.path.join(base, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"\n=== {fname} ===")
    for line_num, desc in checks:
        if line_num - 1 < len(lines):
            line = lines[line_num - 1]
            pipe_count = line.count('|')
            prefix = line.rstrip('\n')
            print(f"  L{line_num} ({desc}): pipes={pipe_count}, content='{prefix[:70]}'")
