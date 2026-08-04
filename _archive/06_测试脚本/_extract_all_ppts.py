# -*- coding: utf-8 -*-
"""
通用批量 PPT 提取脚本
支持：电子技术、高等数学、计算机的所有 PPT
输出：每章一个目录，含 slide_001.png + _content.md
依赖：win32com（Windows PowerPoint）、python-pptx（备用）
"""
import sys, os, shutil, tempfile
sys.stdout.reconfigure(encoding='utf-8')

import pythoncom
import win32com.client

BASE = r'D:\Axelit\工作\trae\超级自动化学习工具'
PPT_DIRS = {
    '电子技术': os.path.join(BASE, 'src', 'notes', 'PPT', '电子技术'),
    '线性代数': os.path.join(BASE, 'src', 'notes', 'PPT', '线代'),
    '计算机':   os.path.join(BASE, 'src', 'notes', 'PPT', '计算机'),
}
OUT_BASE = os.path.join(BASE, 'src', 'notes', 'ppt_extracted')

def make_safe_name(ppt_file):
    """第X章 -> 第X章__章节名，清理空格和特殊字符"""
    name = os.path.splitext(ppt_file)[0]
    name = name.replace('\u3000', '_').replace(' ', '_').replace('(', '_').replace(')', '_')
    name = name.replace('__', '_')
    return name

def copy_to_temp(src_path, tmp_dir):
    """复制到临时目录，用短 ASCII 名，避免 PowerPoint 中文路径问题"""
    safe_name = 'input_' + str(abs(hash(src_path)) % 100000) + os.path.splitext(src_path)[1]
    tmp_path = os.path.join(tmp_dir, safe_name)
    shutil.copy2(src_path, tmp_path)
    return tmp_path

def export_slides(tmp_path, out_dir, prefix):
    """用 PowerPoint COM 导出 PNG + 提取文本"""
    pythoncom.CoInitialize()
    powerpoint = None
    presentation = None
    try:
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        powerpoint.DisplayAlerts = 0

        try:
            presentation = powerpoint.Presentations.Open(tmp_path, ReadOnly=True, WithWindow=False)
        except:
            try:
                presentation = powerpoint.Presentations.Open(tmp_path, ReadOnly=True, WithWindow=True)
            except Exception as e:
                print(f"    [WARN] 打开失败: {e}")
                return 0, 0

        slides = presentation.Slides
        slide_count = slides.Count
        print(f"    幻灯片总数: {slide_count}")

        # 1. 导出 PNG
        png_count = 0
        for i in range(1, min(slide_count + 1, 500)):
            img_path = os.path.join(out_dir, f"slide_{i:03d}.png")
            if os.path.exists(img_path):
                print(f"    slide_{i:03d}.png 已存在，跳过")
                png_count += 1
                continue
            try:
                slides(i).Export(str(img_path), "PNG")
                png_count += 1
            except Exception as e:
                print(f"    [WARN] slide {i} 导出失败: {e}")

        # 2. 提取文本
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
                            if text and len(text) > 1:
                                slide_text.append(text)
                    except:
                        pass
                all_text.append({'slide': slide_idx, 'texts': slide_text})
            except:
                pass

        presentation.Close()
        powerpoint.Quit()

        # 3. 保存文本
        text_path = os.path.join(out_dir, f"{prefix}_content.md")
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(f"# {prefix}\n\n")
            f.write(f"- 幻灯片总数: {slide_count}\n")
            f.write(f"- 提取时间: 2026-06-15\n\n")
            f.write("---\n\n")
            for item in all_text:
                f.write(f"## 第 {item['slide']} 页\n\n")
                for t in item['texts']:
                    f.write(f"{t}\n\n")
        print(f"    文本已保存: {len(all_text)} 页")

        return png_count, len(all_text)

    except Exception as e:
        print(f"    [ERROR] {e}")
        import traceback; traceback.print_exc()
        try:
            if presentation: presentation.Close()
            if powerpoint: powerpoint.Quit()
        except: pass
        return 0, 0
    finally:
        pythoncom.CoUninitialize()

def process_subject(subject, src_dir, out_base):
    """处理一个学科的所有 PPT"""
    if not os.path.isdir(src_dir):
        print(f"[SKIP] 目录不存在: {src_dir}")
        return

    ppt_files = sorted([f for f in os.listdir(src_dir)
                        if f.endswith(('.ppt', '.pptx')) and not f.startswith('~')])
    if not ppt_files:
        print(f"[SKIP] 目录为空: {src_dir}")
        return

    print(f"\n{'='*60}")
    print(f"【{subject}】共 {len(ppt_files)} 个 PPT")
    print(f"源目录: {src_dir}")
    print(f"输出目录: {out_base}")
    print(f"{'='*60}")

    tmp_dir = tempfile.mkdtemp(prefix='ppt_extract_')
    print(f"临时目录: {tmp_dir}")

    total_png = 0
    total_text = 0
    done = 0
    skipped = 0

    for ppt_file in ppt_files:
        src_path = os.path.join(src_dir, ppt_file)
        safe_name = make_safe_name(ppt_file)
        out_dir = os.path.join(out_base, safe_name)
        os.makedirs(out_dir, exist_ok=True)

        # 检查是否已完全处理（有所有 PNG + content.md）
        slide_count = len([f for f in os.listdir(out_dir) if f.startswith('slide_') and f.endswith('.png')])
        has_text = os.path.exists(os.path.join(out_dir, safe_name + '_content.md'))

        print(f"\n[{done+skipped+1}/{len(ppt_files)}] {ppt_file}")
        print(f"  安全名: {safe_name}")
        print(f"  输出目录: {out_dir}")

        if slide_count > 10 and has_text:
            print(f"  [SKIP] 已处理（{slide_count} slides + content.md）")
            skipped += 1
            continue

        # 复制到临时
        tmp_path = copy_to_temp(src_path, tmp_dir)
        print(f"  临时文件: {tmp_path}")

        png_cnt, txt_cnt = export_slides(tmp_path, out_dir, safe_name)
        total_png += png_cnt
        total_text += txt_cnt
        done += 1

        # 清理临时文件
        try:
            os.remove(tmp_path)
        except:
            pass

    # 清理临时目录
    try:
        shutil.rmtree(tmp_dir)
    except:
        pass

    print(f"\n【{subject}】完成: {done} 个已处理, {skipped} 个跳过, 共导出 {total_png} 张 PNG, {total_text} 页文本")

def main():
    print("="*60)
    print("通用批量 PPT 提取脚本")
    print("="*60)

    for subject, src_dir in PPT_DIRS.items():
        process_subject(subject, src_dir, OUT_BASE)

    print("\n" + "="*60)
    print("全部完成!")
    print("="*60)

if __name__ == "__main__":
    main()
