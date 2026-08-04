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

crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_017.png'),
    os.path.join(diagrams_dir, 'ch6_slide017_vsi_pwm.png'), (0, 0.05, 1.0, 0.92), 'ch6_017')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_020.png'),
    os.path.join(diagrams_dir, 'ch6_slide020_inverter_waveform.png'), (0, 0.05, 1.0, 0.92), 'ch6_020')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_033.png'),
    os.path.join(diagrams_dir, 'ch6_slide033_smps_ups.png'), (0, 0.05, 1.0, 0.90), 'ch6_033')
print('Done.')
