# -*- coding: utf-8 -*-
# 详细验证：所有 2023-2025 高数真题中是否包含笔记引用的题目
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

# 收集笔记中引用的"高数真题"
# 模式：2022-2023 / 2023-2024 / 2024-2025 学年 + 高等数学AI/AII + 期末考试
exam_keywords = [
    ('2022-2023学年', '高等数学AII'),
    ('2023-2024学年', '高等数学AI'),
    ('2024-2025学年', '高等数学AII'),
]

# 实际真题目录
exam_dir = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\习题和真题'
real_exams = os.listdir(exam_dir)
print('实际存在的真题：')
for e in sorted(real_exams):
    print(f'  - {e}')

# 笔记中引用的"AI"和"AII"
# 2023-2024 AI 实际是 AII（罗马数字 I vs II）
# AI 不在 实际存在列表中

print()
print('=' * 60)
print('匹配检查：')
print('=' * 60)
# 笔记中提到 "2023-2024学年高等数学AI期末考试" — 实际是 2023-2024-2 学期
# 但实际真题是 2023年春季高等数学AII试题 — 这个其实是 2022-2023-2
# 命名规则不一致：笔记用"学年"，目录用"年份"
# 即笔记的"2023-2024学年" = 目录的"2024年春"（2024 年 1 月或 6 月考）

# 高数真题中实际存在的试卷
real_2023_2024 = [e for e in real_exams if '2024' in e and '高数' in e]
real_2022_2023 = [e for e in real_exams if '2023' in e and '高数' in e]
real_2024_2025 = [e for e in real_exams if '2025' in e and '高数' in e]

print(f'对应 2023-2024 学年的真题：{real_2023_2024}')
print(f'对应 2022-2023 学年的真题：{real_2022_2023}')
print(f'对应 2024-2025 学年的真题：{real_2024_2025}')

# 关键问题：AI vs AII
print()
print('⚠️ 重要发现：')
print('  - 笔记中频繁出现"高等数学 AI"（"AI"是罗马数字 1）')
print('  - 实际目录中只有"高等数学 AII"（"AII"是罗马数字 2）')
print('  - 高数 AI（数学分析1）通常是上学期课程，高数 AII（数学分析2）通常是下学期')
print('  - **如果课程是高数 AII，则引用"AI"是错误的**')

# 现在搜索"高数AI"是否真的在某笔记中
note_dir = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\高等数学'
ai_mentions = 0
aii_mentions = 0
for f in os.listdir(note_dir):
    if not f.endswith('.md'):
        continue
    p = os.path.join(note_dir, f)
    with open(p, encoding='utf-8') as fp:
        c = fp.read()
    ai_mentions += c.count('高等数学AI')
    aii_mentions += c.count('高等数学AII')

print(f'\n笔记中"高等数学AI"提及次数: {ai_mentions}')
print(f'笔记中"高等数学AII"提及次数: {aii_mentions}')

# 进一步：扫描每份笔记的"题目来源"格式
print()
print('=== 笔记中"题目来源"格式统计 ===')
source_pattern = re.compile(r'\*\*题目来源\*\*[:：](.{0,100})')
for f in sorted(os.listdir(note_dir)):
    if not f.endswith('.md'):
        continue
    p = os.path.join(note_dir, f)
    with open(p, encoding='utf-8') as fp:
        c = fp.read()
    matches = source_pattern.findall(c)
    if matches:
        for m in matches[:3]:
            print(f'  [{f}] {m.strip()[:80]}')
