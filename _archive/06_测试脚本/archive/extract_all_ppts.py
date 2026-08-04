# -*- coding: utf-8 -*-
"""Extract all remaining PPT chapters using explicit encoding"""
import os
import shutil
from pathlib import Path
import pythoncom
import win32com.client

def export_slides(src_path, output_dir, prefix):
    pythoncom.CoInitialize()
    powerpoint = None
    presentation = None
    try:
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        powerpoint.DisplayAlerts = 0

        presentation = powerpoint.Presentations.Open(str(src_path), ReadOnly=True, WithWindow=False)
        slides = presentation.Slides
        slide_count = slides.Count
        print(f"  Slides: {slide_count}")

        for i in range(1, min(slide_count + 1, 200)):
            img_path = os.path.join(output_dir, f"slide_{i:03d}.png")
            try:
                slides(i).Export(str(img_path), "PNG")
            except:
                pass

        all_text = []
        for slide_idx in range(1, slide_count + 1):
            try:
                slide = slides(slide_idx)
                slide_text = []
                for shape_idx in range(1, slide.Shapes.Count + 1):
                    try:
                        shape = slide.Shapes(shape_idx)
                        if shape.HasTextFrame and shape.TextFrame.HasText:
                            text = shape.TextFrame.TextRange.Text.strip()
                            if text:
                                slide_text.append(text)
                    except:
                        pass
                all_text.append({'slide': slide_idx, 'texts': slide_text})
            except:
                pass

        presentation.Close()
        powerpoint.Quit()

        text_path = os.path.join(output_dir, f"{prefix}_content.md")
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(f"# {prefix}\n\n## Overview\n- Slides: {slide_count}\n\n## Content\n\n")
            for item in all_text:
                f.write(f"### Slide {item['slide']}\n\n")
                for t in item['texts']:
                    f.write(f"- {t}\n")
                f.write("\n")
        print(f"  Text saved")
        print(f"  Done!")

    except Exception as e:
        print(f"  Error: {e}")
        try:
            if presentation: presentation.Close()
            if powerpoint: powerpoint.Quit()
        except: pass
    finally:
        pythoncom.CoUninitialize()

def main():
    src_dir = Path(r"D:\Axelit\工作\trae\超级自动化学习工具\data\讲义")
    out_base = Path(r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\PPT提取")

    ppt_files = list(src_dir.glob("*.ppt*"))
    print(f"Found {len(ppt_files)} files\n")

    # Process all unprocessed chapters
    existing = set()
    for d in out_base.iterdir():
        if d.is_dir():
            existing.add(d.name)

    print("Existing dirs:", sorted(existing))

    for ppt in ppt_files:
        # Create a safe prefix from the filename
        # Remove spaces and special chars
        stem = ppt.stem
        # Try to create a readable prefix
        if '1章' in stem and '半导体' in stem:
            prefix = '第1章__半导体基础知识'
        elif '2章' in stem and '基本放大' in stem:
            prefix = '第2章__基本放大电路'
        elif '3章' in stem and '集成运算' in stem:
            prefix = '第3章__集成运算放大器'
        elif '4章' in stem and '放大电路应用' in stem:
            prefix = '第4章__放大电路应用'
        elif '5章' in stem and '直流' in stem:
            prefix = '第5章__直流电源'
        elif '6章' in stem and '模拟仿真' in stem:
            prefix = '第6章__模拟仿真转换'
        elif '7章' in stem and '门电路' in stem:
            prefix = '第7章__门电路与组合逻辑电路'
        elif '8章' in stem and '触发器' in stem:
            prefix = '第8章__触发器与时序逻辑电路'
        elif '9章' in stem and '半导体存储器' in stem:
            prefix = '第9章__半导体存储器'
        elif '10章' in stem and '模数转换' in stem:
            prefix = '第10章__模数转换'
        elif '第一章' in stem and '电路' in stem:
            prefix = '第一章__电路基本概念'
        elif '第二章' in stem and '正弦交流' in stem:
            prefix = '第二章__正弦交流电路'
        else:
            print(f"  Skipping: {ppt.name} (no mapping)")
            continue

        # Check if already processed
        if prefix in existing:
            print(f"  Already processed: {prefix}")
            continue

        print(f"\n{'='*50}")
        print(f"Processing: {ppt.name} -> {prefix}")

        out_dir = out_base / prefix
        os.makedirs(out_dir, exist_ok=True)

        tmp_dir = Path(os.environ.get('TEMP', r'C:\Temp')) / "ppt_extract"
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = tmp_dir / "input.ppt"

        try:
            shutil.copy2(ppt, tmp_path)
            export_slides(tmp_path, out_dir, prefix)
        except Exception as e:
            print(f"  Copy/open failed: {e}")
        finally:
            try:
                if tmp_path.exists():
                    os.remove(tmp_path)
            except: pass

    print(f"\n{'='*50}")
    print("All done!")

if __name__ == "__main__":
    main()
