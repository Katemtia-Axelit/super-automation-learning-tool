# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
ppt_dir = os.path.join(base, 'src', 'notes', 'PPT提取')
diagrams_dir = os.path.join(base, 'src', 'notes', 'vault', 'diagrams', '电子技术')
os.makedirs(diagrams_dir, exist_ok=True)

def crop_and_save(src_img, dst_path, crop_box, desc=""):
    img = Image.open(src_img)
    w, h = img.size
    left = int(crop_box[0] * w)
    top = int(crop_box[1] * h)
    right = int(crop_box[2] * w)
    bottom = int(crop_box[3] * h)
    cropped = img.crop((left, top, right, bottom))
    cropped.save(dst_path)
    print(f'  [{desc}] {w}x{h} -> {os.path.basename(dst_path)} ({os.path.getsize(dst_path)//1024}KB)')

# Ch5: DC Power Supply
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_003.png'),
    os.path.join(diagrams_dir, 'ch5_slide003_power_supply_block.png'), (0, 0.05, 1.0, 0.92), 'ch5_003')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_005.png'),
    os.path.join(diagrams_dir, 'ch5_slide005_bridge_rectifier.png'), (0, 0.05, 1.0, 0.90), 'ch5_005')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_006.png'),
    os.path.join(diagrams_dir, 'ch5_slide006_capacitor_filter_waveform.png'), (0, 0.05, 1.0, 0.92), 'ch5_006')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_008.png'),
    os.path.join(diagrams_dir, 'ch5_slide008_lc_filter.png'), (0, 0.05, 1.0, 0.90), 'ch5_008')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_010.png'),
    os.path.join(diagrams_dir, 'ch5_slide010_zener_regulator.png'), (0, 0.05, 1.0, 0.90), 'ch5_010')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_011.png'),
    os.path.join(diagrams_dir, 'ch5_slide011_series_regulator.png'), (0, 0.05, 1.0, 0.92), 'ch5_011')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_012.png'),
    os.path.join(diagrams_dir, 'ch5_slide012_lm317.png'), (0, 0.05, 1.0, 0.92), 'ch5_012')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_014.png'),
    os.path.join(diagrams_dir, 'ch5_slide014_three_phase_rectifier.png'), (0, 0.05, 1.0, 0.90), 'ch5_014')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_015.png'),
    os.path.join(diagrams_dir, 'ch5_slide015_rectifier_comparison.png'), (0, 0.05, 1.0, 0.90), 'ch5_015')
crop_and_save(os.path.join(ppt_dir, '第5章__直流电源', 'slide_016.png'),
    os.path.join(diagrams_dir, 'ch5_slide016_filter_params.png'), (0, 0.05, 1.0, 0.90), 'ch5_016')

# Ch6: Power Electronics
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_003.png'),
    os.path.join(diagrams_dir, 'ch6_slide003_buck_converter.png'), (0, 0.05, 1.0, 0.90), 'ch6_003')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_004.png'),
    os.path.join(diagrams_dir, 'ch6_slide004_buck_circuit.png'), (0, 0.05, 1.0, 0.90), 'ch6_004')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_005.png'),
    os.path.join(diagrams_dir, 'ch6_slide005_boost_converter.png'), (0, 0.05, 1.0, 0.90), 'ch6_005')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_007.png'),
    os.path.join(diagrams_dir, 'ch6_slide007_sepic.png'), (0, 0.05, 1.0, 0.90), 'ch6_007')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_010.png'),
    os.path.join(diagrams_dir, 'ch6_slide010_boost_waveform.png'), (0, 0.05, 1.0, 0.92), 'ch6_010')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_012.png'),
    os.path.join(diagrams_dir, 'ch6_slide012_buck_boost.png'), (0, 0.05, 1.0, 0.92), 'ch6_012')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_014.png'),
    os.path.join(diagrams_dir, 'ch6_slide014_boost_buck.png'), (0, 0.05, 1.0, 0.92), 'ch6_014')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_015.png'),
    os.path.join(diagrams_dir, 'ch6_slide015_boost_buck_waveform.png'), (0, 0.05, 1.0, 0.92), 'ch6_015')
crop_and_save(os.path.join(ppt_dir, '第6章__电力电子技术', 'slide_016.png'),
    os.path.join(diagrams_dir, 'ch6_slide016_vsi.png'), (0, 0.05, 1.0, 0.90), 'ch6_016')

print('\nAll Ch5/Ch6 diagrams cropped successfully.')
