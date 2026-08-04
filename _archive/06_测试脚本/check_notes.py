import os, sys
sys.stdout.reconfigure(encoding='utf-8')

notes_dir = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\vault\大学物理"
files = sorted([f for f in os.listdir(notes_dir) if f.endswith('.md')])

for fname in files:
    fpath = os.path.join(notes_dir, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_real = '题库' in content and '真题' in content
    has_fake = '例题1' in content and 'F = -kx²' in content  # AI-fabricated nonsense
    
    if has_real:
        status = "OK (real exam problems)"
    elif has_fake:
        status = "NEEDS UPDATE (AI fake problems)"
    else:
        status = "UNKNOWN"
    
    print(f"{status}: {fname}")
