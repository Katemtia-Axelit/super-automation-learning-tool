# -*- coding: utf-8 -*-
# 读取 .doc（二进制）文件并提取文本
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

p = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\习题和真题\2024年春高等数学AII期末考试试卷(A卷)参考答案与评分标准.doc'
with open(p, 'rb') as f:
    raw = f.read()
# .doc 内部文本用 UTF-16LE 或 GBK 编码。试一下
text = None
for enc in ['utf-16-le', 'gbk', 'utf-8', 'gb18030']:
    try:
        # 提取 >= 2 字节的中文段
        text = raw.decode(enc, errors='ignore')
        if '复合' in text or 'ln' in text.lower() or '填空' in text:
            print(f'  ✓ 用 {enc} 编码解析')
            break
    except:
        pass

# 用正则提取可读中文段
segments = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9，。：；、（）()\s\.\,\/\-\=]+', text)
content = ' '.join(segments)
# 找关键词
keywords = ['复合函数', 'ln x', 'lnx', 'tanh', '反函数', '填空', '填空题', '2024']
for kw in keywords:
    if kw in content:
        # 找上下文
        idx = content.find(kw)
        start = max(0, idx-30)
        end = min(len(content), idx+80)
        print(f'[{kw}]: ...{content[start:end]}...')

print('\n--- 找复合函数定义域例题 ---')
# 高数笔记中的例题：f 定义域 [0,1] 求 f(ln x) 定义域
target = 'f(ln'
if target in content:
    print(f'命中: {target}')
    idx = content.find(target)
    print(f'上下文: {content[max(0,idx-50):idx+150]}')
else:
    print('未找到 f(ln')

# 找"tanh"
if 'tanh' in content:
    idx = content.find('tanh')
    print(f'命中 tanh: {content[max(0,idx-50):idx+150]}')
else:
    print('未找到 tanh')
