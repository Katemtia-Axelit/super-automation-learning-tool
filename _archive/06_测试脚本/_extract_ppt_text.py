# -*- coding: utf-8 -*-
import sys, os, shutil, tempfile
sys.stdout.reconfigure(encoding='utf-8')
import json

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
ppt_folder = os.path.join(base, 'data', '讲义')
tmp_dir = tempfile.mkdtemp(prefix='ppt_conv_')

import pythoncom, win32com.client

def ppt_to_pptx(src_ppt, dst_pptx):
    pythoncom.CoInitialize()
    try:
        p = win32com.client.Dispatch('PowerPoint.Application')
        p.DisplayAlerts = 2
        try:
            presentation = p.Presentations.Open(src_ppt, ReadOnly=True, WithWindow=False)
            presentation.SaveAs(dst_pptx, 24)
            presentation.Close()
            return True
        finally:
            p.Quit()
    finally:
        pythoncom.CoUninitialize()

def extract_slide_text_and_shapes(pptx_path):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.enum.text import PP_ALIGN
    import hashlib

    prs = Presentation(pptx_path)
    slides_data = []
    for slide_idx, slide in enumerate(prs.slides):
        slide_info = {
            'slide_num': slide_idx + 1,
            'title': '',
            'texts': [],
            'images': [],
            'tables': [],
        }
        for shape in slide.shapes:
            # Title
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    # Get first substantial text as title
                    if not slide_info['title'] or len(text) > len(slide_info['title']):
                        for para in shape.text_frame.paragraphs:
                            t = para.text.strip()
                            if t and len(t) > len(slide_info['title']):
                                slide_info['title'] = t
                                break
                    slide_info['texts'].append(text[:200])

            # Image
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                img = shape.image
                img_bytes = img.blob
                img_ext = img.ext
                img_hash = hashlib.md5(img_bytes).hexdigest()[:8]
                img_size = len(img_bytes)
                slide_info['images'].append({
                    'hash': img_hash,
                    'ext': img_ext,
                    'size': img_size,
                })

            # Table
            try:
                tbl = shape.table
                rows_data = []
                for row in tbl.rows:
                    row_cells = []
                    for cell in row.cells:
                        row_cells.append(cell.text.strip())
                    rows_data.append(row_cells)
                slide_info['tables'].append(rows_data)
            except (AttributeError, ValueError):
                pass

        slides_data.append(slide_info)
    return slides_data

# Process Ch1 and Ch2
chapters = [
    ('ch01', '第1章'),
    ('ch02', '第2章'),
]

for key, prefix in chapters:
    fname = None
    for f in sorted(os.listdir(ppt_folder)):
        if f.startswith(prefix) and f.endswith('.ppt') and not f.endswith('.pptx'):
            fname = f; break
    if not fname:
        print(f'NOT FOUND: {prefix}')
        continue

    src_path = os.path.join(ppt_folder, fname)
    tmp_ppt = os.path.join(tmp_dir, f'{key}.ppt')
    tmp_pptx = os.path.join(tmp_dir, f'{key}.pptx')

    shutil.copy2(src_path, tmp_ppt)
    print(f'Converting {fname}...')
    ppt_to_pptx(tmp_ppt, tmp_pptx)

    slides_data = extract_slide_text_and_shapes(tmp_pptx)

    # Save to JSON
    out_json = os.path.join(base, f'_slides_{key}.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(slides_data, f, ensure_ascii=False, indent=2)
    print(f'Saved {len(slides_data)} slides to {out_json}')

print(f'\nDone. Temp dir: {tmp_dir}')
