# -*- coding: utf-8 -*-
# 验证 2024 高数真题内容
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import docx

p = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\习题和真题\2024年春高等数学AII期末考试试卷(A卷)参考答案与评分标准.doc'
doc = docx.Document(p)
paras = [p.text for p in doc.paragraphs if p.text.strip()]
for i, t in enumerate(paras[:30]):
    print(f'{i}: {t[:200]}')
print('---')
print(f'共 {len(paras)} 段')
# 找 f(lnx) 或 复合函数
for i, t in enumerate(paras):
    if 'f(ln' in t or 'ln x' in t.lower() or '复合' in t:
        print(f'HIT {i}: {t[:150]}')
