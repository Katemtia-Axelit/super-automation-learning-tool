# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
ppt_dir = os.path.join(base, 'src', 'notes', 'PPT提取')
diagrams_dir = os.path.join(base, 'src', 'notes', 'vault', 'diagrams', '电子技术')

def crop_and_save(src_img, dst_path, crop_box, desc=""):
    img = Image.open(src_img)
    w, h = img.size
    left = int(crop_box[0] * w)
    top = int(crop_box[1] * h)
    right = int(crop_box[2] * w)
    bottom = int(crop_box[3] * h)
    cropped = img.crop((left, top, right, bottom))
    cropped.save(dst_path)
    print(f'  [{desc}] -> {os.path.basename(dst_path)} ({os.path.getsize(dst_path)//1024}KB)')

# Ch4 more pages for Note 13
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_013.png'),
    os.path.join(diagrams_dir, 'ch4_slide013_opamp_apps.png'), (0, 0.05, 1.0, 0.90), 'ch4_013')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_014.png'),
    os.path.join(diagrams_dir, 'ch4_slide014_comparator.png'), (0, 0.05, 1.0, 0.90), 'ch4_014')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_015.png'),
    os.path.join(diagrams_dir, 'ch4_slide015_schmitt.png'), (0, 0.05, 1.0, 0.90), 'ch4_015')

# Ch8 more pages for Notes 08-11
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_083.png'),
    os.path.join(diagrams_dir, 'ch8_slide083_sequential_summary.png'), (0, 0.05, 1.0, 0.90), 'ch8_083')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_084.png'),
    os.path.join(diagrams_dir, 'ch8_slide084_sequential_summary2.png'), (0, 0.05, 1.0, 0.90), 'ch8_084')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_003.png'),
    os.path.join(diagrams_dir, 'ch8_slide003_sequential_intro.png'), (0, 0.05, 1.0, 0.90), 'ch8_003')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_030.png'),
    os.path.join(diagrams_dir, 'ch8_slide030_sequential_analysis.png'), (0, 0.05, 1.0, 0.90), 'ch8_030')

# Ch9 more pages
crop_and_save(os.path.join(ppt_dir, '第9章__半导体存储器件与可编程逻辑器件', 'slide_010.png'),
    os.path.join(diagrams_dir, 'ch9_slide010_pld.png'), (0, 0.05, 1.0, 0.90), 'ch9_010')

print('Done.')
