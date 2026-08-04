# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
base = r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault'
files = [
    'diagrams/08_01_analog_vs_digital.svg',
    'diagrams/08_02_basic_gates.svg',
    'diagrams/08_03_composite_gates.svg',
    'diagrams/09_01_kmap_2var.svg',
    'diagrams/09_02_kmap_3var.svg',
    'diagrams/10_01_half_adder.svg',
    'diagrams/10_02_full_adder.svg',
    'diagrams/11_01_encoder.svg',
]
for f in files:
    path = os.path.join(base, f)
    exists = os.path.exists(path)
    status = 'EXISTS' if exists else 'MISSING'
    print(status + ': ' + f)
