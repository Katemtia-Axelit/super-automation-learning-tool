# -*- coding: utf-8 -*-
# P5.3 阶段1：摸底统计
# 只读不改：扫描所有目标笔记，统计例题存在性、出处标注、电路图等
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault'
targets = ['大学物理', '高等数学', '线性代数', '电子技术', '计算机']

# 例题标记模式
EXAMPLE_PATTERNS = [
    r'>\s*\[!example\]',  # Obsidian Callout
    r'>\s*\[!note\]\s*例题',  # note 类型的例题
    r'##\s*例题',  # 二级标题
    r'##\s*真题例题',  # 真题例题
    r'##\s*.*例题',  # 含例字的标题
    r'典型例题',
    r'题目来源',
    r'解答[:：]',
    r'已知条件[:：]',
]

# 出处标记模式
SOURCE_PATTERNS = [
    r'出处[:：]',
    r'来源[:：]',
    r'题目来源[:：]',
    r'题源[:：]',
    r'（.{0,40}期末.{0,40}）',
    r'\d{4}\s*年.{0,5}学期',  # 年份学期
    r'试卷',
    r'题库',
    r'PPT',
    r'来源[：:].*?\.doc',
]

# 电路图标记
CIRCUIT_PATTERNS = [
    r'!\[',
    r'diagrams/',
    r'\.png',
    r'\.jpg',
    r'\.svg',
    r'电路图',
    r'电路',
    r'slide_\d+',
    r'slide\d+',
    r'ch\d+_',
]

def matches_any(text, patterns):
    return sum(1 for p in patterns if re.search(p, text))

results = {}

for sub in targets:
    d = os.path.join(base, sub)
    files = sorted([f for f in os.listdir(d) if f.endswith('.md')])
    sub_results = []
    for fname in files:
        path = os.path.join(d, fname)
        with open(path, encoding='utf-8') as f:
            content = f.read()
        sz = len(content)
        has_example = matches_any(content, EXAMPLE_PATTERNS) > 0
        has_source = matches_any(content, SOURCE_PATTERNS) > 0
        has_circuit = matches_any(content, CIRCUIT_PATTERNS) > 0
        # 特殊：完全没例题但提到"待补充"/"资料不足"也记录
        has_placeholder = '待补充' in content or '资料不足' in content or 'TBD' in content
        sub_results.append({
            'file': fname,
            'size': sz,
            'has_example': has_example,
            'has_source': has_source,
            'has_circuit': has_circuit,
            'has_placeholder': has_placeholder,
        })
    results[sub] = sub_results

# 打印汇总
print('=' * 70)
print('P5.3 阶段 1：摸底统计报告')
print('=' * 70)
print()
total_notes = 0
total_with_example = 0
total_with_source = 0
total_with_circuit = 0
total_with_placeholder = 0
total_size = 0

for sub, items in results.items():
    print(f'### {sub} ({len(items)} 份)')
    n_example = sum(1 for x in items if x['has_example'])
    n_source = sum(1 for x in items if x['has_source'])
    n_circuit = sum(1 for x in items if x['has_circuit'])
    n_placeholder = sum(1 for x in items if x['has_placeholder'])
    total_sub = sum(x['size'] for x in items)
    print(f'  含例题: {n_example}/{len(items)}  含出处: {n_source}/{len(items)}  含图: {n_circuit}/{len(items)}  占位符: {n_placeholder}/{len(items)}  字节: {total_sub//1024}KB')
    total_notes += len(items)
    total_with_example += n_example
    total_with_source += n_source
    total_with_circuit += n_circuit
    total_with_placeholder += n_placeholder
    total_size += total_sub

print()
print(f'### 总计: {total_notes} 份')
print(f'  含例题: {total_with_example}/{total_notes} ({total_with_example*100//total_notes}%)')
print(f'  含出处: {total_with_source}/{total_notes} ({total_with_source*100//total_notes}%)')
print(f'  含图片/电路图: {total_with_circuit}/{total_notes} ({total_with_circuit*100//total_notes}%)')
print(f'  含占位符: {total_with_placeholder}/{total_notes} ({total_with_placeholder*100//total_notes}%)')
print(f'  总字节: {total_size//1024}KB')

# 输出每学科详细（无例题的文件清单）
print()
print('=' * 70)
print('详细：无例题文件清单')
print('=' * 70)
for sub, items in results.items():
    no_ex = [x['file'] for x in items if not x['has_example']]
    if no_ex:
        print(f'\n[{sub}] {len(no_ex)} 份无例题:')
        for f in no_ex:
            print(f'  - {f}')

# 输出每学科详细（无出处标注的文件清单）
print()
print('=' * 70)
print('详细：有例题但无出处文件清单')
print('=' * 70)
for sub, items in results.items():
    no_src = [x['file'] for x in items if x['has_example'] and not x['has_source']]
    if no_src:
        print(f'\n[{sub}] {len(no_src)} 份有例题无出处:')
        for f in no_src:
            print(f'  - {f}')

# 写入临时结果文件供后续使用
import json
with open(r'D:\Axelit\工作\trae\超级自动化学习工具\_p5_3_phase1.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('\n[结果已写入 _p5_3_phase1.json]')
