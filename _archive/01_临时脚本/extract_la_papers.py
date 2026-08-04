import os, zipfile, xml.etree.ElementTree as ET, re

base = r'd:\Axelit\工作\trae\超级自动化学习工具\src\notes\习题和真题'

def extract_docx_text(path):
    """Extract text from .docx file"""
    try:
        with zipfile.ZipFile(path) as z:
            doc = z.read('word/document.xml')
            root = ET.fromstring(doc)
            ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            text = ''.join(node.text or '' for node in root.iter(f'{{{ns}}}t'))
        return text
    except:
        return None

# Extract all linear algebra exam papers
la_papers = [
    '2020-2021-2线性代数试卷A.docx',
    '2021-2022-2线性代数试卷Ａ.docx',
    '2022-2023-2线性代数试卷A（试题页）.docx',
    '2024-2025-2《线性代数》试卷A.docx'
]

for p in la_papers:
    fp = os.path.join(base, p)
    if os.path.isfile(fp):
        text = extract_docx_text(fp)
        if text:
            # Save extracted text for reading
            outpath = os.path.join(base, p.replace('.docx', '_extracted.txt'))
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(text)
            lines = text.strip().split('\n')
            print(f'{p}: {len(lines)} lines, saved to _extracted.txt')
            # Show first 500 chars
            print(f'  Preview: {text[:300]}...')
        else:
            print(f'{p}: Failed to extract')
    else:
        print(f'{p}: NOT FOUND')

# Also check the .doc files
doc_files = [f for f in os.listdir(base) if f.endswith('.doc') and '线性代数' in f]
for d in doc_files:
    print(f'{d}: .doc format (binary, cannot extract directly)')

print('\nDone.')