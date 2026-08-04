import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\Axelit\工作\大一下期末"

for root, dirs, files in os.walk(base):
    for f in sorted(files):
        full = os.path.join(root, f)
        print(full)
