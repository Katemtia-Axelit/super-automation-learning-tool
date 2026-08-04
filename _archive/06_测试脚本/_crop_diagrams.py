# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
import shutil

base = r'D:\Axelit\工作\trae\超级自动化学习工具'
ppt_dir = os.path.join(base, 'src', 'notes', 'PPT提取')
diagrams_dir = os.path.join(base, 'src', 'notes', 'vault', 'diagrams', '电子技术')
os.makedirs(diagrams_dir, exist_ok=True)

def crop_and_save(src_img, dst_path, crop_box, desc=""):
    """Crop a region from src_img and save to dst_path."""
    img = Image.open(src_img)
    w, h = img.size
    # crop_box is (left, top, right, bottom) as fractions of image size
    left = int(crop_box[0] * w)
    top = int(crop_box[1] * h)
    right = int(crop_box[2] * w)
    bottom = int(crop_box[3] * h)
    cropped = img.crop((left, top, right, bottom))
    cropped.save(dst_path)
    print(f'  [{desc}] {w}x{h} -> cropped ({left},{top})-({right},{bottom}) -> {os.path.basename(dst_path)} ({os.path.getsize(dst_path)//1024}KB)')

# ====== Note 01 images ======
# slide003: covalent bond crystal structure (pure diagram, upper portion)
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide003.png'),
    os.path.join(diagrams_dir, 'ch1_slide003_covalent_bond.png'),
    (0, 0.05, 1.0, 0.75),
    'ch1_slide003'
)
# slide004: intrinsic excitation (pure diagram)
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide004.png'),
    os.path.join(diagrams_dir, 'ch1_slide004_intrinsic_excitation.png'),
    (0, 0.05, 1.0, 0.80),
    'ch1_slide004'
)
# slide005: PN junction formation (pure diagram, has circuit diagrams)
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide005.png'),
    os.path.join(diagrams_dir, 'ch1_slide005_pn_junction.png'),
    (0, 0.05, 1.0, 0.95),
    'ch1_slide005'
)
# slide007: diode structure types (pure diagrams)
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide007.png'),
    os.path.join(diagrams_dir, 'ch1_slide007_diode_types.png'),
    (0, 0.05, 1.0, 0.90),
    'ch1_slide007'
)
# slide008: V-I characteristic curve (has the key chart)
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide008.png'),
    os.path.join(diagrams_dir, 'ch1_slide008_diode_iv_curve.png'),
    (0, 0.05, 1.0, 0.95),
    'ch1_slide008'
)

# ====== Note 03 images ======
# slide018: transistor structure (NPN/PNP symbols and structures)
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide018.png'),
    os.path.join(diagrams_dir, 'ch1_slide018_transistor_structure.png'),
    (0, 0.05, 1.0, 0.95),
    'ch1_slide018'
)
# slide019: transistor characteristics and parameters
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide019.png'),
    os.path.join(diagrams_dir, 'ch1_slide019_transistor_characteristics.png'),
    (0, 0.05, 1.0, 0.90),
    'ch1_slide019'
)
# slide020: transistor characteristics continued
crop_and_save(
    os.path.join(ppt_dir, '第1章__半导体基础知识', 'slide020.png'),
    os.path.join(diagrams_dir, 'ch1_slide020_transistor_iv.png'),
    (0, 0.05, 1.0, 0.90),
    'ch1_slide020'
)

# ====== Note 03 / 06 images from Chapter 2 ======
# slide003: basic CE amplifier circuit structure (diagram area)
crop_and_save(
    os.path.join(ppt_dir, '第2章__基本放大电路', 'slide003.png'),
    os.path.join(diagrams_dir, 'ch2_slide003_ce_circuit.png'),
    (0, 0.05, 1.0, 0.75),
    'ch2_slide003'
)
# slide004: CE amplifier analysis methods
crop_and_save(
    os.path.join(ppt_dir, '第2章__基本放大电路', 'slide004.png'),
    os.path.join(diagrams_dir, 'ch2_slide004_amplifier_params.png'),
    (0, 0.05, 1.0, 0.80),
    'ch2_slide004'
)
# slide005: CE amplifier DC/AC analysis
crop_and_save(
    os.path.join(ppt_dir, '第2章__基本放大电路', 'slide005.png'),
    os.path.join(diagrams_dir, 'ch2_slide005_static_analysis.png'),
    (0, 0.05, 1.0, 0.90),
    'ch2_slide005'
)
# slide008: voltage divider bias circuit
crop_and_save(
    os.path.join(ppt_dir, '第2章__基本放大电路', 'slide008.png'),
    os.path.join(diagrams_dir, 'ch2_slide008_voltage_divider_bias.png'),
    (0, 0.05, 1.0, 0.95),
    'ch2_slide008'
)
# slide019: transistor output characteristics
crop_and_save(
    os.path.join(ppt_dir, '第2章__基本放大电路', 'slide019.png'),
    os.path.join(diagrams_dir, 'ch2_slide019_transistor_output_curve.png'),
    (0, 0.05, 1.0, 0.90),
    'ch2_slide019'
)

print('\nDone. All cropped diagrams saved to:', diagrams_dir)
