import subprocess
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# Install needed packages
for pkg in ['python-docx', 'pdfplumber']:
    try:
        __import__(pkg.replace('-', '_'))
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

import docx
import pdfplumber

base = r"D:\Axelit\工作\大一下期末"
out_dir = "data/extracted"
os.makedirs(out_dir, exist_ok=True)

# Extract 高等数学 PDFs (2024, 2025)
math_files = [
    "2024年春高等数学AII期末考试试卷(A卷).pdf",
    "2025年春高等数学AII期末考试试卷（A卷） (1).pdf",
]

for fname in math_files:
    fpath = os.path.join(base, fname)
    if os.path.exists(fpath):
        text_parts = []
        with pdfplumber.open(fpath) as pdf:
            for i, page in enumerate(pdf.pages[:5]):  # first 5 pages
                t = page.extract_text()
                if t:
                    text_parts.append(f"--- Page {i+1} ---\n{t}")
        out_name = fname.replace('.pdf', '.txt').replace(' (1)', '')
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(text_parts))
        print(f"Extracted {fname} -> {out_path} ({len(text_parts)} pages)")

# Extract 线性代数 PDFs
linalg_files = [
    "2023-2024-2《线性代数》试卷A参考答案.pdf",
    "2024-2025-2《线性代数》试卷A参考答案 (1).pdf",
    "2025年春季大学数学AII线性代数参���答案与评分标准（A卷）.doc",
    "2024年春季大学数学AII线性代数（A卷）.pdf",
    "2025年春季大学数学AII线性代数（A卷） (1).pdf",
]

for fname in linalg_files:
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        continue
    if fname.endswith('.pdf'):
        text_parts = []
        with pdfplumber.open(fpath) as pdf:
            for i, page in enumerate(pdf.pages[:5]):
                t = page.extract_text()
                if t:
                    text_parts.append(f"--- Page {i+1} ---\n{t}")
        out_name = fname.replace('.pdf', '.txt').replace(' (1)', '')
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(text_parts))
        print(f"Extracted {fname} -> {out_path}")
    elif fname.endswith('.doc'):
        doc = docx.Document(fpath)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        out_name = fname.replace('.doc', '.txt').replace(' (1)', '')
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(paras))
        print(f"Extracted {fname} -> {out_path} ({len(paras)} paragraphs)")

print("\nDone!")
