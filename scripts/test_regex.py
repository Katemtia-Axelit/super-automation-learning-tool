# -*- coding: utf-8 -*-
import re

# 模拟文件内容
test_content = """|子表达式|命题|结果类型|
|----------|------|----------|
|`x > 0`|x 是否大于 0|逻辑值（真/假）|
|`y <= 0`|y 是否小于等于 0|逻辑值（真/假）|
|`(x>0) && (y<=0)`|两个逻辑值的与运算|逻辑值（真/假）|

"""

print("原始内容:")
for i, line in enumerate(test_content.split('\n')):
    print(f"  {i}: pipes={line.count('|')} '{line[:50]}'")

# 测试不同的正则替换
result1 = re.sub(r'^\|([^|]+)\|([^|]+)\|([^|]+)\|$',
                  lambda m: f'| {m.group(1)} | {m.group(2)} | {m.group(3)} |',
                  test_content, flags=re.MULTILINE)

print("\n替换后 (捕获组法):")
for i, line in enumerate(result1.split('\n')):
    print(f"  {i}: pipes={line.count('|')} '{line[:50]}'")

# 更简单的办法：把单行首部的 |col|col|col| 替换为 | col|col|col|
result2 = re.sub(r'^(\|)([^\|]+)(\|)', r'\1 \2\3', test_content, flags=re.MULTILINE)

print("\n替换后 (简单法: 修复首格空格):")
for i, line in enumerate(result2.split('\n')):
    print(f"  {i}: pipes={line.count('|')} '{line[:50]}'")
