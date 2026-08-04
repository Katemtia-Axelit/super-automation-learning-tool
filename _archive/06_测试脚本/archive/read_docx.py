import subprocess
import sys

# Install python-docx if needed
try:
    import docx
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-docx', '-q'])
    import docx

import os
import json

def read_docx(path):
    """Read docx file and return text content"""
    doc = docx.Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)

base = r"D:\Axelit\工作\大一下期末"

# Read physics question bank
print("=" * 60)
print("大学物理A期末复习题库")
print("=" * 60)
questions_text = read_docx(os.path.join(base, "大学物理A期末复习题库.docx"))
print(questions_text[:5000])  # First 5000 chars
print(f"\n... (total length: {len(questions_text)})")

print("\n" + "=" * 60)
print("大学物理A期末复习题库答案")
print("=" * 60)
answers_text = read_docx(os.path.join(base, "大学物理A期末复习题库答案.docx"))
print(answers_text[:3000])
print(f"\n... (total length: {len(answers_text)})")
