# -*- coding: utf-8 -*-
"""
从旧版PPT中提取干净的图表和图片。
- 图片形状(type=13)直接导出
- 组合形状(type=6)中不含文本的视为纯净图表，直接导出
- 混合页面导出完整幻灯片供后续裁剪
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import win32com.client
import os
import time
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# ========== 配置 ==========
PPT_DIR = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\data\讲义')
OUT_DIR = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\extracted_pics')
OUT_DIR.mkdir(exist_ok=True)

# 要处理的PPT（对应vault中已有的笔记章节）
TARGET_PPT_FILES = [
    ('第1章  半导体基础知识.ppt',      'ch01_半导体'),
    ('第2章  基本放大电路.ppt',        'ch02_放大电路'),
    ('第3章  集成运算放大器.ppt',      'ch03_运放'),
    ('第5讲  直流稳压电源.ppt',        'ch05_直流电源'),
    ('第7章  门电路与组合逻辑电路.ppt', 'ch07_数字电路'),
]

# Shape type constants (PowerPoint)
SHAPE_TYPE_PICTURE = 13
SHAPE_TYPE_GROUP = 6
SHAPE_TYPE_TABLE = 19
SHAPE_TYPE_TEXTBOX = 17
SHAPE_TYPE_AUTOSHAPE = 1

def get_pure_groups(slide):
    """返回不含文本的组合形状（纯净图表）"""
    pure = []
    for j in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(j)
        if shape.Type != SHAPE_TYPE_GROUP:
            continue
        try:
            has_text = False
            for k in range(1, shape.GroupItems.Count + 1):
                item = shape.GroupItems(k)
                if item.Type == SHAPE_TYPE_TEXTBOX:
                    has_text = True
                    break
                try:
                    if item.HasTextFrame and item.TextFrame.HasText:
                        has_text = True
                        break
                except:
                    pass
            if not has_text:
                pure.append((j, shape.Name))
        except:
            pass
    return pure


def get_pictures(slide):
    """返回所有图片形状"""
    pics = []
    for j in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(j)
        if shape.Type == SHAPE_TYPE_PICTURE:
            pics.append((j, shape.Name))
    return pics


def has_significant_text(slide):
    """判断幻灯片是否有大量文字（3个以上文本框）"""
    count = 0
    for j in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(j)
        if shape.Type in [SHAPE_TYPE_TEXTBOX, SHAPE_TYPE_AUTOSHAPE]:
            try:
                if shape.HasTextFrame and shape.TextFrame.HasText:
                    count += 1
            except:
                pass
    return count >= 3


def extract_ppt(ppt_file, chapter_key):
    """提取单个PPT中的图表"""
    chapter_dir = OUT_DIR / chapter_key
    chapter_dir.mkdir(exist_ok=True)

    print(f'\n{"="*60}')
    print(f'Processing: {ppt_file}')
    print(f'{"="*60}')

    # 创建临时目录用于导出幻灯片（避免中文路径问题）
    tmp_dir = Path(tempfile.mkdtemp(prefix='ppt_extract_'))

    ppt_app = None
    prs = None
    try:
        ppt_app = win32com.client.Dispatch('PowerPoint.Application')
        ppt_app.Visible = 1

        prs = ppt_app.Presentations.Open(str(ppt_file), ReadOnly=True, WithWindow=False)
        slide_count = prs.Slides.Count
        print(f'Total slides: {slide_count}')

        extracted = 0
        skipped = 0

        for i in range(1, slide_count + 1):
            slide = prs.Slides(i)

            pics = get_pictures(slide)
            pure_groups = get_pure_groups(slide)
            text_heavy = has_significant_text(slide)

            # 直接导出：纯净图片
            for shape_idx, shape_name in pics:
                shape = slide.Shapes(shape_idx)
                safe_name = shape_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                img_path = chapter_dir / f'slide{i:03d}_pic_{safe_name}.png'
                try:
                    shape.Export(str(img_path), 2)
                    extracted += 1
                    print(f'  [OK] Slide {i}: picture -> {img_path.name}')
                except Exception as e:
                    print(f'  [FAIL] Slide {i}: picture export error: {e}')

            # 直接导出：无文本的组合图表
            for shape_idx, shape_name in pure_groups:
                shape = slide.Shapes(shape_idx)
                safe_name = shape_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                img_path = chapter_dir / f'slide{i:03d}_group_{safe_name}.png'
                try:
                    shape.Export(str(img_path), 2)
                    extracted += 1
                    print(f'  [OK] Slide {i}: group -> {img_path.name}')
                except Exception as e:
                    print(f'  [FAIL] Slide {i}: group export error: {e}')

            # 需要裁剪的：既有图表又有大量文字 → 导出整页再做裁剪
            if pics and text_heavy:
                # 先把形状位置信息收集起来
                shape_positions = []
                for j in range(1, slide.Shapes.Count + 1):
                    shape = slide.Shapes(j)
                    shape_positions.append({
                        'type': shape.Type,
                        'name': shape.Name,
                        'left': shape.Left,
                        'top': shape.Top,
                        'width': shape.Width,
                        'height': shape.Height,
                    })

                # 导出整页到临时文件（无中文路径）
                tmp_slide_path = tmp_dir / f'slide{i:03d}.png'
                try:
                    slide.Export(str(tmp_slide_path), 2)
                    print(f'  [CROP] Slide {i}: full slide exported for cropping ({len(pics)} pics + text)')

                    # 记录裁剪信息供后续脚本使用
                    crop_info_path = chapter_dir / f'slide{i:03d}_crop_info.txt'
                    with open(str(crop_info_path), 'w', encoding='utf-8') as f:
                        f.write(f'# Slide {i} - Mixed content, needs cropping\n')
                        f.write(f'# Source: {tmp_slide_path.name}\n')
                        f.write(f'# Shapes:\n')
                        for sp in shape_positions:
                            f.write(f'  TYPE={sp["type"]} NAME={sp["name"]} '
                                    f'L={sp["left"]} T={sp["top"]} W={sp["width"]} H={sp["height"]}\n')
                except Exception as e:
                    print(f'  [CROP FAIL] Slide {i}: export error: {e}')

            if not pics and not pure_groups:
                skipped += 1

        print(f'\nExtracted {extracted} images, skipped {skipped} slides (no images)')
        prs.Close()

    except Exception as e:
        print(f'Fatal error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if prs:
            try:
                prs.Close()
            except:
                pass
        if ppt_app:
            try:
                ppt_app.Quit()
            except:
                pass
        # 清理临时目录
        try:
            shutil.rmtree(str(tmp_dir))
        except:
            pass

    return extracted


def main():
    total = 0
    for ppt_name, chapter_key in TARGET_PPT_FILES:
        ppt_path = PPT_DIR / ppt_name
        if not ppt_path.exists():
            print(f'NOT FOUND: {ppt_path}')
            continue
        n = extract_ppt(ppt_path, chapter_key)
        total += n

    print(f'\n{"="*60}')
    print(f'Grand total: {total} images extracted')


if __name__ == '__main__':
    main()
