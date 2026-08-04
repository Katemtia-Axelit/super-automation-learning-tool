# -*- coding: utf-8 -*-
"""Extract all remaining PPT chapters"""
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

    targets = ["第3章", "第4章", "第5章", "第6章", "第7章", "第8章", "第9章", "第10章", "第二章"]

    for ppt in ppt_files:
        if not any(t in ppt.name for t in targets):
            continue

        print(f"{'='*50}")
        print(f"Processing: {ppt.name}")

        prefix = ppt.stem.replace(' ', '_').replace('\u3000', '_')
        out_dir = out_base / prefix
        os.makedirs(out_dir, exist_ok=True)

        tmp_dir = Path(os.environ.get('TEMP', r'C:\Temp')) / "ppt_extract"
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = tmp_dir / "input.ppt"

        try:
            shutil.copy2(ppt, tmp_path)
            export_slides(tmp_path, out_dir, prefix)
        except Exception as e:
            print(f"  Copy failed: {e}")
        finally:
            try:
                if tmp_path.exists():
                    os.remove(tmp_path)
            except: pass

    print(f"\n{'='*50}")
    print("All done!")

if __name__ == "__main__":
    main()
