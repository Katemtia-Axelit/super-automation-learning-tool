# -*- coding: utf-8 -*-
# P5.3 阶段2：抽样溯源
# 从每学科抽 5-10 份，验证例题来源
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault'

# 抽 5 学科各抽若干
samples = {
    '大学物理': ['22_静电场与电场强度.md', '23_静电场的环路定理与电势.md', '24_电通量与高斯定理.md', '01_质点运动描述的物理量.md', '26_毕奥-萨伐尔定律与磁场典型模型.md'],
    '高等数学': ['01-01_函数的概念与基本要素.md', '01-04_极限存在准则与重要极限.md', '06-01_向量的数量积.md', '11-04_全微分方程判定与求解.md', '10-05_泰勒级数与函数展开.md', '09-02_格林公式及其应用.md'],
    '线性代数': ['01_线性相关与无关判定.md', '02_线性空间与基底维数.md', '07_行列式展开与逆矩阵.md', '08_特征值与特征向量基础.md', '12_相似矩阵与对角化.md'],
    '电子技术': ['01_半导体基础与PN结.md', '02_二极管特性与等效模型.md', '13_集成运放与负反馈.md', '14_直流稳压电源.md', '08_布尔代数与逻辑门电路.md'],
    '计算机': ['04_计算机硬件组成与总线.md', '06_数值数据的编码_原码反码补码.md', '08_数据存储与单位.md', '11_程序的编译链接与符号解析.md'],
}

# 1. 检查是否有"题目来源"标注
SOURCE_PATTERN = re.compile(r'(题目来源[:：].{0,80}|来源[:：].{0,60}|出处[:：].{0,60}|题源[:：].{0,60}|\d{4}.*?(期末|试卷|试题|题库).*?第[一二三四五六七八九十\d]+题)')

# 2. 检查是否有"PPT"或"slide"等可溯源到 PPT 的引用
PPT_PATTERN = re.compile(r'(slide[_\d]+|PPT|ch\d+_)')

# 3. 检查是否有"重构说明"提及"语音/课堂/录音"等
CLASS_PATTERN = re.compile(r'(课堂|录音|语音|转写|老师)')

# 4. 检查是否在重构说明中有"老师原话"等引用
TEACHER_PATTERN = re.compile(r'(老师原话|老师.*?说道|老师强调)')

results = []
for sub, files in samples.items():
    for f in files:
        path = os.path.join(base, sub, f)
        if not os.path.exists(path):
            print(f'[WARN] {sub}/{f} 不存在')
            continue
        with open(path, encoding='utf-8') as fp:
            content = fp.read()
        sources = SOURCE_PATTERN.findall(content)
        ppt_refs = PPT_PATTERN.findall(content)
        class_refs = CLASS_PATTERN.findall(content)
        teacher_quotes = TEACHER_PATTERN.findall(content)
        # 提取前 100 字符的来源说明
        first_source = sources[0] if sources else None
        first_ppt = ppt_refs[0] if ppt_refs else None
        has_example = ('[!example]' in content or '例题' in content or '题目来源' in content)
        results.append({
            'subject': sub,
            'file': f,
            'size': len(content),
            'has_example': has_example,
            'source_count': len(sources),
            'first_source': first_source,
            'ppt_count': len(ppt_refs),
            'class_count': len(class_refs),
            'teacher_quote_count': len(teacher_quotes),
        })

print('=== P5.3 阶段 2：抽样溯源报告 ===\n')
for r in results:
    print(f'[{r["subject"]}] {r["file"]}')
    print(f'  大小: {r["size"]//1024}KB  含例题: {r["has_example"]}  来源标注: {r["source_count"]} 处  PPT引用: {r["ppt_count"]} 处  课堂引用: {r["class_count"]} 处  老师原话: {r["teacher_quote_count"]} 处')
    if r['first_source']:
        print(f'  首条来源: {r["first_source"][:80]}')
    print()

# 汇总
print('=== 汇总 ===')
total_ex = sum(1 for r in results if r['has_example'])
total_src = sum(1 for r in results if r['source_count'] > 0)
total_ppt = sum(1 for r in results if r['ppt_count'] > 0)
total_class = sum(1 for r in results if r['class_count'] > 0)
print(f'抽样 {len(results)} 份')
print(f'  含例题: {total_ex}/{len(results)}')
print(f'  有"题目来源"标注: {total_src}/{len(results)}')
print(f'  有 PPT 引用: {total_ppt}/{len(results)}')
print(f'  有课堂/录音引用: {total_class}/{len(results)}')

# 保存详细结果
import json
with open(r'D:\Axelit\工作\trae\超级自动化学习工具\_p5_3_phase2.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('\n[结果已写入 _p5_3_phase2.json]')
