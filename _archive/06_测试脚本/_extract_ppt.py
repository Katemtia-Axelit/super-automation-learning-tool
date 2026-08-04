# -*- coding: utf-8 -*-
import sys, os, shutil, tempfile
sys.stdout.reconfigure(encoding='utf-8')

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
ppt_folder = os.path.join(base, 'data', '讲义')
out_root = os.path.join(base, 'extracted_pics')

import pythoncom
import win32com.client

def ppt_to_pptx(src_ppt, dst_pptx):
    """Convert old .ppt to .pptx using PowerPoint COM automation."""
    pythoncom.CoInitialize()
    try:
        p = win32com.client.Dispatch('PowerPoint.Application')
        p.DisplayAlerts = 2  # ppAlertsNone
        try:
            presentation = p.Presentations.Open(src_ppt, ReadOnly=True, WithWindow=False)
            presentation.SaveAs(dst_pptx, 24)  # ppFormatPPTX = 24
            presentation.Close()
            return True
        finally:
            p.Quit()
    finally:
        pythoncom.CoUninitialize()

def extract_images_from_pptx(pptx_path, out_dir):
    """Extract images from a .pptx file using python-pptx."""
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    import hashlib

    prs = Presentation(pptx_path)
    cnt = 0
    for slide_idx, slide in enumerate(prs.slides):
        stitle = ''
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        stitle = t[:60]
                        break
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                img = shape.image
                img_bytes = img.blob
                img_ext = img.ext
                img_hash = hashlib.md5(img_bytes).hexdigest()[:8]
                out_path = os.path.join(out_dir, f'slide{slide_idx+1:03d}_{img_hash}.{img_ext}')
                with open(out_path, 'wb') as f:
                    f.write(img_bytes)
                print(f'  Slide {slide_idx+1}: [{stitle}] -> {os.path.basename(out_path)}')
                cnt += 1
    return cnt

# Chapters for P2.1
chapters = [
    ('ch01_半导体', '第1章'),
    ('ch02_基本放大', '第2章'),
]

tmp_dir = tempfile.mkdtemp(prefix='ppt_conv_')
print(f'Using temp dir: {tmp_dir}')

for key, prefix in chapters:
    # Find file
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
    out_dir = os.path.join(out_root, key)
    os.makedirs(out_dir, exist_ok=True)

    print(f'\n=== [{key}] Converting: {fname} ===')

    # Copy to temp
    shutil.copy2(src_path, tmp_ppt)
    print(f'Copied to temp: {tmp_ppt}')

    # Convert to pptx
    print(f'Converting to .pptx...')
    success = ppt_to_pptx(tmp_ppt, tmp_pptx)
    if not success or not os.path.exists(tmp_pptx):
        print(f'CONVERSION FAILED for {fname}')
        continue
    print(f'Conversion done: {os.path.getsize(tmp_pptx)} bytes')

    # Extract images
    print(f'Extracting images...')
    cnt = extract_images_from_pptx(tmp_pptx, out_dir)
    print(f'Extracted {cnt} images')

print(f'\nAll done. Temp dir: {tmp_dir}')
