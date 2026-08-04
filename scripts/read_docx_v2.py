import subprocess
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')

try:
    import docx
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-docx', '-q'])
    import docx

def read_docx(path):
    doc = docx.Document(path)
    return [p.text for p in doc.paragraphs if p.text.strip()]

base = r"D:\Axelit\工作\大一下期末"

# Read physics question bank
paras = read_docx(os.path.join(base, "大学物理A期末复习题库.docx"))
output = os.path.join("data", "physics_questions.txt")
with open(output, 'w', encoding='utf-8') as f:
    f.write('\n'.join(paras))
print(f"Saved {len(paras)} paragraphs to {output}")
print(f"Total chars: {sum(len(p) for p in paras)}")

# Read answers
paras2 = read_docx(os.path.join(base, "大学物理A期末复习题库答案.docx"))
output2 = os.path.join("data", "physics_answers.txt")
with open(output2, 'w', encoding='utf-8') as f:
    f.write('\n'.join(paras2))
print(f"Saved {len(paras2)} paragraphs to {output2}")
print(f"Total chars: {sum(len(p) for p in paras2)}")
