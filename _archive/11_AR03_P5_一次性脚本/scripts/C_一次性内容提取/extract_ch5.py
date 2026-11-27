# -*- coding: utf-8 -*-
"""Extract ch5 DC power supply"""
import os
import shutil
from pathlib import Path
import pythoncom
import win32com.client

src_dir = Path(r"D:\Axelit\工作\trae\超级自动化学习工具\data\讲义")
out_base = Path(r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\PPT提取")

ppt_files = list(src_dir.glob("*.ppt*"))
ch5_file = None
for ppt in ppt_files:
    name_bytes = ppt.name.encode('gbk', errors='replace')
    # Check for 第5章
    if b'\xb5\xda\x35' in name_bytes or (b'\xb5\xda' in name_bytes and b'\x35' in name_bytes):
        ch5_file = ppt
        print(f"Found: {ppt.name}")
        print(f"  GBK bytes: {name_bytes[:30].hex()}")
        break

if not ch5_file:
    print("Chapter 5 file not found!")
    for ppt in ppt_files:
        print(f"  File: {ppt.name}")

out_dir = out_base / '第5章__直流电源'
os.makedirs(out_dir, exist_ok=True)

tmp_dir = Path(os.environ.get('TEMP', r'C:\Temp')) / 'ppt_ch5'
os.makedirs(tmp_dir, exist_ok=True)
tmp_path = tmp_dir / 'ch5.ppt'

try:
    shutil.copy2(ch5_file, tmp_path)
    print(f"Copied to: {tmp_path}")

    pythoncom.CoInitialize()
    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    powerpoint.DisplayAlerts = 0
    presentation = powerpoint.Presentations.Open(str(tmp_path), ReadOnly=True, WithWindow=False)
    slides = presentation.Slides
    print(f"Slides: {slides.Count}")

    for i in range(1, min(slides.Count + 1, 200)):
        img_path = out_dir / f"slide_{i:03d}.png"
        try:
            slides(i).Export(str(img_path), "PNG")
        except:
            pass
        if i % 10 == 0:
            print(f"  Exported {i} slides...")

    presentation.Close()
    powerpoint.Quit()
    pythoncom.CoUninitialize()
    print("Done!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        if tmp_path.exists():
            os.remove(tmp_path)
    except:
        pass
