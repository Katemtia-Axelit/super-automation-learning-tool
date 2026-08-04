# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import shutil
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
    print(f'  [{desc}] -> {os.path.basename(dst_path)} ({os.path.getsize(dst_path)//1024}KB)')

# ======== Ch4: 集成运算放大器应用 (for Note 13) ========
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_003.png'),
    os.path.join(diagrams_dir, 'ch4_slide003_opamp_structure.png'), (0, 0.05, 1.0, 0.90), 'ch4_003')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_004.png'),
    os.path.join(diagrams_dir, 'ch4_slide004_voltage_transfer.png'), (0, 0.05, 1.0, 0.92), 'ch4_004')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_005.png'),
    os.path.join(diagrams_dir, 'ch4_slide005_virtual_short_open.png'), (0, 0.05, 1.0, 0.90), 'ch4_005')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_008.png'),
    os.path.join(diagrams_dir, 'ch4_slide008_inverting_noninverting.png'), (0, 0.05, 1.0, 0.90), 'ch4_008')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_009.png'),
    os.path.join(diagrams_dir, 'ch4_slide009_diff_amplifier.png'), (0, 0.05, 1.0, 0.90), 'ch4_009')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_010.png'),
    os.path.join(diagrams_dir, 'ch4_slide010_integrator_differentiator.png'), (0, 0.05, 1.0, 0.90), 'ch4_010')
crop_and_save(os.path.join(ppt_dir, '第4章__集成运算放大器应用', 'slide_016.png'),
    os.path.join(diagrams_dir, 'ch4_slide016_filter.png'), (0, 0.05, 1.0, 0.90), 'ch4_016')

# ======== Ch7: 门电路与组合逻辑 (for Note 08-11) ========
# Use manually named images first
ch7_dir = os.path.join(ppt_dir, '第7章__门电路与组合逻辑电路')
for f in os.listdir(ch7_dir):
    if not f.startswith('slide_'):
        src = os.path.join(ch7_dir, f)
        sz = os.path.getsize(src)
        if sz > 20000:
            dst = os.path.join(diagrams_dir, f'ch7_{f}')
            shutil.copy2(src, dst)
            print(f'  ch7: {f} ({sz//1024}KB)')

# Crop key slide pages
crop_and_save(os.path.join(ppt_dir, '第7章__门电路与组合逻辑电路', 'slide_004.png'),
    os.path.join(diagrams_dir, 'ch7_slide004_logic_gates.png'), (0, 0.05, 1.0, 0.90), 'ch7_004')
crop_and_save(os.path.join(ppt_dir, '第7章__门电路与组合逻辑电路', 'slide_063.png'),
    os.path.join(diagrams_dir, 'ch7_slide063_sequential_logic.png'), (0, 0.05, 1.0, 0.90), 'ch7_063')
crop_and_save(os.path.join(ppt_dir, '第7章__门电路与组合逻辑电路', 'slide_065.png'),
    os.path.join(diagrams_dir, 'ch7_slide065_combinational.png'), (0, 0.05, 1.0, 0.90), 'ch7_065')
crop_and_save(os.path.join(ppt_dir, '第7章__门电路与组合逻辑电路', 'slide_069.png'),
    os.path.join(diagrams_dir, 'ch7_slide069_kmap.png'), (0, 0.05, 1.0, 0.90), 'ch7_069')
crop_and_save(os.path.join(ppt_dir, '第7章__门电路与组合逻辑电路', 'slide_087.png'),
    os.path.join(diagrams_dir, 'ch7_slide087_encoder_decoder.png'), (0, 0.05, 1.0, 0.90), 'ch7_087')

# ======== Ch8: 触发器与时序逻辑 (for Note 08-11) ========
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_029.png'),
    os.path.join(diagrams_dir, 'ch8_slide029_sequential_circuits.png'), (0, 0.05, 1.0, 0.90), 'ch8_029')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_031.png'),
    os.path.join(diagrams_dir, 'ch8_slide031_flip_flop.png'), (0, 0.05, 1.0, 0.90), 'ch8_031')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_032.png'),
    os.path.join(diagrams_dir, 'ch8_slide032_flip_flop_types.png'), (0, 0.05, 1.0, 0.90), 'ch8_032')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_058.png'),
    os.path.join(diagrams_dir, 'ch8_slide058_counter.png'), (0, 0.05, 1.0, 0.90), 'ch8_058')
crop_and_save(os.path.join(ppt_dir, '第8章__触发器与时序逻辑电路', 'slide_091.png'),
    os.path.join(diagrams_dir, 'ch8_slide091_register.png'), (0, 0.05, 1.0, 0.90), 'ch8_091')

# ======== Ch9: 半导体存储器件 (for Note 08-11) ========
crop_and_save(os.path.join(ppt_dir, '第9章__半导体存储器件与可编程逻辑器件', 'slide_003.png'),
    os.path.join(diagrams_dir, 'ch9_slide003_memory.png'), (0, 0.05, 1.0, 0.90), 'ch9_003')
crop_and_save(os.path.join(ppt_dir, '第9章__半导体存储器件与可编程逻辑器件', 'slide_004.png'),
    os.path.join(diagrams_dir, 'ch9_slide004_ram_rom.png'), (0, 0.05, 1.0, 0.90), 'ch9_004')

print('\nDone.')
