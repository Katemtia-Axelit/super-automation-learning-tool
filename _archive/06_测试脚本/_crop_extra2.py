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

crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_009.png'),
    os.path.join(diagrams_dir, 'ch6_slide009_buck_waveform.png'), (0, 0.05, 1.0, 0.92), 'ch6_009')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_013.png'),
    os.path.join(diagrams_dir, 'ch6_slide013_inverter_intro.png'), (0, 0.05, 1.0, 0.90), 'ch6_013')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_037.png'),
    os.path.join(diagrams_dir, 'ch6_slide037_three_phase_inverter.png'), (0, 0.05, 1.0, 0.90), 'ch6_037')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_041.png'),
    os.path.join(diagrams_dir, 'ch6_slide041_three_phase_pwm.png'), (0, 0.05, 1.0, 0.90), 'ch6_041')
print('Done.')
