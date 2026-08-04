# -*- coding: utf-8 -*-
"""
生成电子技术笔记所需的所有AI绘制SVG图。
每张图均标注"AI绘制"。

使用方法:
    python generate_svg_diagrams.py
生成的文件保存在 src/notes/diagrams/ 下。
"""
import os
from pathlib import Path

OUT_DIR = Path(r'D:\Axelit\工作\trae\超级自动化学习工具\src\notes\diagrams')
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 600, 400
BG = '#ffffff'
LINE = '#222222'
TEXT = '#111111'
GATE_FILL = '#f5f5f5'
GATE_STROKE = '#334155'
WIRE = '#334155'
INPUT_A_COLOR = '#3b82f6'
INPUT_B_COLOR = '#ef4444'

def svg_header(w=W, h=H, bg=BG):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"
  width="{w}" height="{h}" font-family="Arial, sans-serif">
<rect width="{w}" height="{h}" fill="{bg}"/>
'''

def svg_footer():
    return '</svg>'

def box(x, y, w, h, fill=GATE_FILL, stroke=GATE_STROKE, stroke_w=2):
    return f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>\n'

def text(x, y, content, size=14, color=TEXT, anchor='middle', bold=False):
    fw = 'font-weight="bold"' if bold else ''
    return f'  <text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" {fw} fill="{color}">{content}</text>\n'

def line(x1, y1, x2, y2, color=WIRE, w=2):
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"/>\n'

def polyline(points, color=WIRE, w=2):
    pts = ' '.join([f'{x},{y}' for x,y in points])
    return f'  <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{w}"/>\n'

def circle(x, y, r, fill='#334155', stroke=None):
    if stroke:
        return f'  <circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
    return f'  <circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>\n'

def path(d, color=WIRE, w=2, fill='none'):
    return f'  <path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{w}"/>\n'

def and_gate(x, y, w=50, h=40, label=None):
    """与门符号"""
    cx, cy = x + w, y + h/2
    # 矩形+右半圆
    p = f'M{x},{y} L{x+w*0.55},{y} A{w*0.45},{h/2} 0 0 1 {x+w*0.55},{y+h} L{x},{y+h} Z'
    s = f'  <path d="{p}" fill="{GATE_FILL}" stroke="{GATE_STROKE}" stroke-width="2"/>\n'
    s += line(x, y+h*0.5, x, y+h*0.5, w=1.5)  # 输入线已在外部
    if label:
        s += text(cx+5, cy+5, label, 12)
    return s

def or_gate(x, y, w=50, h=40, label=None):
    """或门符号"""
    cx, cy = x + w, y + h/2
    p = f'M{x},{y+h*0.2} Q{x+w*0.5},{y} {x+w},{cy} Q{x+w*0.5},{y+h} {x},{y+h*0.8} Z'
    s = f'  <path d="{p}" fill="{GATE_FILL}" stroke="{GATE_STROKE}" stroke-width="2"/>\n'
    if label:
        s += text(cx, cy, label, 12)
    return s

def not_gate(x, y, w=40, h=30, label=None):
    """非门/反相器符号"""
    cx, cy = x + w, y + h/2
    p = f'M{x},{y} L{x+w*0.75},{cy} L{x},{y+h} Z'
    s = f'  <path d="{p}" fill="{GATE_FILL}" stroke="{GATE_STROKE}" stroke-width="2"/>\n'
    s += circle(cx+w*0.3, cy, 4, fill=BG, stroke=GATE_STROKE)
    if label:
        s += text(cx+w*0.15, cy+4, label, 11)
    return s

def nand_gate(x, y, w=55, h=40):
    """与非门"""
    cx, cy = x + w*0.45, y + h/2
    p = f'M{x},{y} L{x+w*0.45},{y} A{w*0.45},{h/2} 0 0 1 {x+w*0.45},{y+h} L{x},{y+h} Z'
    s = f'  <path d="{p}" fill="{GATE_FILL}" stroke="{GATE_STROKE}" stroke-width="2"/>\n'
    s += circle(cx+10, cy, 4, fill=BG, stroke=GATE_STROKE)
    return s

def nor_gate(x, y, w=55, h=40):
    """或非门"""
    cx, cy = x + w*0.45, y + h/2
    p = f'M{x},{y+h*0.2} Q{x+w*0.4},{y} {x+w*0.45},{cy} Q{x+w*0.4},{y+h} {x},{y+h*0.8} Z'
    s = f'  <path d="{p}" fill="{GATE_FILL}" stroke="{GATE_STROKE}" stroke-width="2"/>\n'
    s += circle(cx+10, cy, 4, fill=BG, stroke=GATE_STROKE)
    return s

def xor_gate(x, y, w=55, h=40):
    """异或门"""
    cx, cy = x + w*0.4, y + h/2
    p = f'M{x+8},{y+h*0.2} Q{x+w*0.4},{y} {x+w*0.4},{cy} Q{x+w*0.4},{y+h} {x+8},{y+h*0.8} Z'
    s = f'  <path d="{p}" fill="{GATE_FILL}" stroke="{GATE_STROKE}" stroke-width="2"/>\n'
    s += path(f'M{x},{y+h*0.2} Q{x+w*0.15},{y+h*0.5} {x},{y+h*0.8}', GATE_STROKE, 2)
    return s

def opamp_symbol(x, y, w=80, h=100):
    """运放符号"""
    cx = x + w/2
    s = ''
    s += polyline([(x, y), (x+w, y+h*0.5), (x, y+h)], GATE_STROKE, 2)
    s += text(cx-18, y+h*0.32, '−', 20, '#ef4444', 'middle')
    s += text(cx+5, y+h*0.32, '+', 18, '#22c55e', 'middle')
    # 输入端口线
    s += line(x-30, y+h*0.25, x, y+h*0.25, INPUT_A_COLOR, 2)
    s += line(x-30, y+h*0.75, x, y+h*0.75, INPUT_B_COLOR, 2)
    s += line(x+w, y+h*0.5, x+w+30, y+h*0.5, WIRE, 2)
    # 电源引脚
    s += line(cx, y, cx, y-20, WIRE, 1.5)
    s += line(cx+25, y, cx+25, y-20, WIRE, 1.5)
    s += line(cx, y+h, cx, y+h+20, WIRE, 1.5)
    s += line(cx+25, y+h, cx+25, y+h+20, WIRE, 1.5)
    s += text(cx-18, y+h*0.18, 'v−', 10, TEXT)
    s += text(cx+5, y+h*0.18, 'v+', 10, TEXT)
    s += text(cx+18, y+h*0.58, 'vo', 10, TEXT)
    return s

def diode_symbol(x, y, w=40, h=60, vertical=True):
    """二极管符号"""
    if vertical:
        cx = x + w/2
        s = line(cx, y, cx, y+h*0.3, WIRE, 2)
        s += polyline([(cx-12, y+h*0.3), (cx, y+h*0.55), (cx+12, y+h*0.3)], GATE_STROKE, 2)
        s += line(cx-12, y+h*0.55, cx+12, y+h*0.55, GATE_STROKE, 2)
        s += line(cx, y+h*0.55, cx, y+h, WIRE, 2)
    else:
        cy = y + h/2
        s = line(x, cy, x+w*0.3, cy, WIRE, 2)
        s += polyline([(x+w*0.3, cy-12), (x+w*0.55, cy), (x+w*0.3, cy+12)], GATE_STROKE, 2)
        s += line(x+w*0.3, cy-12, x+w*0.3, cy+12, GATE_STROKE, 2)
        s += line(x+w*0.55, cy, x+w, cy, WIRE, 2)
    return s

def waveform(x, y, w, h, freq=3, amp=1, duty=0.5, color='#3b82f6'):
    """绘制波形"""
    # 简化正弦波/方波路径
    if freq == 0:  # 直流
        mid = y + h/2
        return line(x, mid, x+w, mid, color, 2)
    return ''


# =====================================================================
# 图08-01: 模拟信号 vs 数字信号
# =====================================================================
def make_analog_vs_digital():
    W2, H2 = 560, 220
    s = svg_header(W2, H2, BG)
    s += text(60, 30, '模拟信号', 14, TEXT, 'start', bold=True)
    s += text(60, H2-15, '数字信号', 14, TEXT, 'start', bold=True)

    # 模拟信号（正弦波）
    amp = 55; cy = 70
    pts = []
    for i in range(0, 281, 5):
        v = amp * (1 - 2*(i%180)/180) if i%180 < 90 else amp*(2*(i%180-90)/180-1)
        v = amp * (1 if i%360 < 180 else -1) * (i%180)/90 if i%360 < 180 else amp*(1-(i%180)/90)
        # 简化为分段线
        pass
    # 正弦曲线用path
    sine_pts = []
    for i in range(0, 361, 5):
        x_pos = 60 + i/360 * 380
        y_pos = cy - amp * (1 if i%360 < 180 else -1) * abs((i%180) - 90)/90
        sine_pts.append((x_pos, y_pos))
    pts_str = ' '.join([f'{x:.1f},{y:.1f}' for x,y in sine_pts])
    s += f'  <polyline points="{pts_str}" fill="none" stroke="#3b82f6" stroke-width="2.5"/>\n'
    # 轴
    s += line(60, cy-amp-10, 60, cy+amp+10, '#aaa', 1)
    s += line(60, cy, 440, cy, '#aaa', 1)
    s += text(440, cy-8, 't', 12, '#666', 'start')

    # 数字信号（方波）
    amp2 = 50; cy2 = 165
    digital_pts = [(60, cy2+amp2), (60, cy2-amp2), (180, cy2-amp2), (180, cy2+amp2),
                   (300, cy2+amp2), (300, cy2-amp2), (420, cy2-amp2), (420, cy2+amp2)]
    pts_str2 = ' '.join([f'{x},{y}' for x,y in digital_pts])
    s += f'  <polyline points="{pts_str2}" fill="none" stroke="#ef4444" stroke-width="2.5"/>\n'
    # 轴
    s += line(60, cy2-amp2-10, 60, cy2+amp2+10, '#aaa', 1)
    s += line(60, cy2, 440, cy2, '#aaa', 1)
    s += text(440, cy2-8, 't', 12, '#666', 'start')
    # 电平标注
    s += text(20, cy-amp+5, '1', 11, '#3b82f6', 'start')
    s += text(20, cy+amp+5, '0', 11, '#3b82f6', 'start')
    s += text(20, cy2-amp2+5, '1', 11, '#ef4444', 'start')
    s += text(20, cy2+amp2+5, '0', 11, '#ef4444', 'start')

    s += text(250, 18, '时间连续、幅值连续', 12, '#666', 'middle')
    s += text(250, 205, '时间离散、幅值离散（高电平=1，低电平=0）', 12, '#666', 'middle')
    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '08_01_analog_vs_digital.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 08_01_analog_vs_digital.svg')

# =====================================================================
# 图08-02: 基本门符号（与门、或门、非门）
# =====================================================================
def make_basic_gates():
    W2, H2 = 600, 200
    s = svg_header(W2, H2, BG)
    s += text(300, 22, '三种基本逻辑门符号', 16, TEXT, 'middle', bold=True)

    # 与门
    gx, gy = 70, 65
    s += text(gx+25, gy-8, 'AND', 13, TEXT, 'middle', bold=True)
    s += line(gx, gy+20, gx, gy+20)  # 输入A
    s += line(gx-30, gy+15, gx, gy+15)  # A线
    s += line(gx-30, gy+25, gx, gy+25)  # B线
    s += text(gx-42, gy+19, 'A', 12, INPUT_A_COLOR, 'end')
    s += text(gx-42, gy+29, 'B', 12, INPUT_B_COLOR, 'end')
    s += and_gate(gx, gy, 55, 40)
    s += line(gx+55, gy+20, gx+110, gy+20)  # 输出线
    s += text(gx+113, gy+24, 'Y=AB', 12, TEXT, 'start')
    s += text(gx+25, gy+65, '与门', 11, '#666', 'middle')
    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')

    # 或门
    gx2, gy2 = 270, 65
    s += text(gx2+25, gy2-8, 'OR', 13, TEXT, 'middle', bold=True)
    s += line(gx2-30, gy2+15, gx2, gy2+15)
    s += line(gx2-30, gy2+25, gx2, gy2+25)
    s += text(gx2-42, gy2+19, 'A', 12, INPUT_A_COLOR, 'end')
    s += text(gx2-42, gy2+29, 'B', 12, INPUT_B_COLOR, 'end')
    s += or_gate(gx2, gy2, 55, 40)
    s += line(gx2+55, gy2+20, gx2+110, gy2+20)
    s += text(gx2+113, gy2+24, 'Y=A+B', 12, TEXT, 'start')
    s += text(gx2+25, gy2+65, '或门', 11, '#666', 'middle')

    # 非门
    gx3, gy3 = 470, 75
    s += text(gx3+20, gy3-8, 'NOT', 13, TEXT, 'middle', bold=True)
    s += line(gx3-30, gy3+20, gx3, gy3+20)
    s += text(gx3-42, gy3+24, 'A', 12, INPUT_A_COLOR, 'end')
    s += not_gate(gx3, gy3, 45, 40)
    s += line(gx3+60, gy3+20, gx3+110, gy3+20)
    s += text(gx3+113, gy3+24, 'Y=Ā', 12, TEXT, 'start')
    s += text(gx3+25, gy3+60, '非门/反相器', 11, '#666', 'middle')

    s += svg_footer()
    with open(OUT_DIR / '08_02_basic_gates.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 08_02_basic_gates.svg')

# =====================================================================
# 图08-03: 复合门符号
# =====================================================================
def make_composite_gates():
    W2, H2 = 620, 200
    s = svg_header(W2, H2, BG)
    s += text(310, 22, '复合逻辑门符号', 16, TEXT, 'middle', bold=True)

    gates = [
        ('与非门 NAND', 50, 65, 'Ā·B̄' if False else 'Y=AB̄', INPUT_A_COLOR),
        ('或非门 NOR', 180, 65, 'Y=A+B̄', INPUT_A_COLOR),
        ('异或门 XOR', 310, 65, 'Y=A⊕B', INPUT_A_COLOR),
        ('同或门 XNOR', 440, 65, 'Y=A⊙B', INPUT_A_COLOR),
    ]
    for name, gx, gy, ylabel, c in gates:
        s += text(gx+25, gy-8, name, 12, TEXT, 'middle', bold=True)
        s += line(gx-30, gy+15, gx, gy+15)
        s += line(gx-30, gy+25, gx, gy+25)
        s += text(gx-42, gy+19, 'A', 12, INPUT_A_COLOR, 'end')
        s += text(gx-42, gy+29, 'B', 12, INPUT_B_COLOR, 'end')
        if 'NAND' in name:
            s += nand_gate(gx, gy, 55, 40)
        elif 'NOR' in name:
            s += nor_gate(gx, gy, 55, 40)
        elif 'XOR' in name:
            s += xor_gate(gx, gy, 55, 40)
        else:
            s += xor_gate(gx, gy, 55, 40)
            s += not_gate(gx+55, gy+5, 25, 30)
        s += line(gx+55, gy+20, gx+110, gy+20)
        s += text(gx+113, gy+24, ylabel, 12, TEXT, 'start')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '08_03_composite_gates.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 08_03_composite_gates.svg')

# =====================================================================
# 图09-01: 2/3/4变量卡诺图
# =====================================================================
def make_karnaugh_2var():
    W2, H2 = 380, 240
    s = svg_header(W2, H2, BG)
    s += text(190, 22, '2变量卡诺图', 15, TEXT, 'middle', bold=True)

    # 画网格
    bx, by, cw, ch = 80, 50, 80, 70
    for r in range(3):
        for c in range(3):
            s += box(bx+c*cw, by+r*ch, cw, ch, '#fafafa', '#aaa', 1)
    # 标注
    s += text(bx+cw*1.5, by-15, 'A', 13, TEXT, 'middle', bold=True)
    s += text(bx+cw*2.5, by-15, '', 13, TEXT, 'middle', bold=True)
    s += text(by-15, by+ch*0.5, 'B̄', 12, TEXT, 'end')
    s += text(by-15, by+ch*1.5, 'B', 12, TEXT, 'end')
    s += text(bx-35, by-15, 'A\\B', 11, '#666', 'end')
    # 格雷码标注
    s += text(bx+cw*0.5, by+ch*3+12, '0', 11, '#666', 'middle')
    s += text(bx+cw*1.5, by+ch*3+12, '1', 11, '#666', 'middle')
    s += text(bx+cw*2.5, by+ch*3+12, '0', 11, '#666', 'middle')
    s += text(bx+cw*3.5, by+ch*3+12, '1', 11, '#666', 'middle')
    # 填入最小项编号
    items = [('0', 0, 0), ('1', 0, 1), ('2', 1, 0), ('3', 1, 1)]
    for label, r, c in items:
        s += text(bx+cw*(0.5+c), by+ch*(0.5+r)+5, label, 13, TEXT, 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '09_01_kmap_2var.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 09_01_kmap_2var.svg')

def make_karnaugh_3var():
    W2, H2 = 480, 280
    s = svg_header(W2, H2, BG)
    s += text(240, 22, '3变量卡诺图（典型填法示例）', 15, TEXT, 'middle', bold=True)

    bx, by, cw, ch = 80, 50, 65, 55
    for r in range(4):
        for c in range(4):
            s += box(bx+c*cw, by+r*ch, cw, ch, '#fafafa', '#aaa', 1)
    # 列头格雷码
    s += text(bx+cw*0.5, by-15, 'A', 12, TEXT, 'middle', bold=True)
    s += text(bx+cw*1.5, by-15, 'A', 12, TEXT, 'middle', bold=True)
    s += text(bx+cw*2.5, by-15, 'Ā', 12, TEXT, 'middle', bold=True)
    s += text(bx+cw*3.5, by-15, 'Ā', 12, TEXT, 'middle', bold=True)
    s += text(by-15, by+ch*0.5, 'BC̄', 11, TEXT, 'end')
    s += text(by-15, by+ch*1.5, 'BC', 11, TEXT, 'end')
    s += text(by-15, by+ch*2.5, 'BC', 11, TEXT, 'end')
    s += text(by-15, by+ch*3.5, 'BC̄', 11, TEXT, 'end')
    # 行头格雷码
    for i, label in enumerate(['0', '1', '1', '0']):
        s += text(bx-35, by+ch*(i+0.5)+5, 'C='+label, 10, '#666', 'end')
    # 最小项
    items = [
        (0,'0'),(1,'1'),(3,'3'),(2,'2'),
        (4,'4'),(5,'5'),(7,'7'),(6,'6'),
        (12,'12'),(13,'13'),(15,'15'),(14,'14'),
        (8,'8'),(9,'9'),(11,'11'),(10,'10'),
    ]
    for idx, (r,c) in enumerate([(0,0),(0,1),(0,2),(0,3),(1,0),(1,1),(1,2),(1,3),(2,0),(2,1),(2,2),(2,3),(3,0),(3,1),(3,2),(3,3)]):
        label = items[idx][1]
        s += text(bx+cw*(0.5+c), by+ch*(0.5+r)+5, label, 11, TEXT, 'middle')

    # 示例：画一个圈（假设填了1的位置）
    s += f'  <rect x="{bx}" y="{by}" width="{cw*2}" height="{ch*2}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="4,2"/>\n'
    s += text(bx+cw, by+ch+5, '圈1: CD̄̄', 10, '#3b82f6', 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '09_02_kmap_3var.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 09_02_kmap_3var.svg')

# =====================================================================
# 图10-01: 半加器
# =====================================================================
def make_half_adder():
    W2, H2 = 500, 200
    s = svg_header(W2, H2, BG)
    s += text(250, 22, '半加器（Half Adder）', 16, TEXT, 'middle', bold=True)

    # 输入
    ax, ay = 50, 60
    bx, by = 50, 90
    # XOR -> S
    s += xor_gate(150, ay-15, 55, 40)
    s += line(ax, ay, 150, ay)
    s += line(bx, by, 150, by)
    s += text(ax-5, ay+4, 'A', 13, INPUT_A_COLOR, 'end')
    s += text(bx-5, by+4, 'B', 13, INPUT_B_COLOR, 'end')
    # 输出S
    s += line(205, ay+5, 280, ay+5)
    s += text(290, ay+9, 'S (本位和)', 12, TEXT, 'start')

    # AND -> C
    s += and_gate(150, by+15, 55, 40)
    s += line(ax, ay, 150, ay+20)  # A连到AND上边
    s += line(bx, by, 150, by+35)   # B连到AND下边
    s += line(205, by+35, 280, by+35)
    s += text(290, by+39, 'C (进位)', 12, TEXT, 'start')

    # 真值表
    s += text(360, 55, '真值表', 13, TEXT, 'middle', bold=True)
    s += box(350, 65, 120, 110, '#fafafa', '#aaa', 1)
    headers = ['A', 'B', 'S', 'C']
    for i, h in enumerate(headers):
        s += text(365+i*30, 80, h, 11, TEXT, 'middle', bold=True)
    rows = [(0,0,0,0),(0,1,1,0),(1,0,1,0),(1,1,0,1)]
    for ri, (a,b,s_val,c_val) in enumerate(rows):
        s += text(365, 100+ri*22, str(a), 11, TEXT, 'middle')
        s += text(395, 100+ri*22, str(b), 11, TEXT, 'middle')
        s += text(425, 100+ri*22, str(s_val), 11, TEXT, 'middle')
        s += text(455, 100+ri*22, str(c_val), 11, TEXT, 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '10_01_half_adder.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 10_01_half_adder.svg')

# =====================================================================
# 图10-02: 全加器
# =====================================================================
def make_full_adder():
    W2, H2 = 560, 220
    s = svg_header(W2, H2, BG)
    s += text(280, 22, '全加器（Full Adder）', 16, TEXT, 'middle', bold=True)

    ax, ay = 50, 60
    bx, by = 50, 100
    cx, cy = 50, 140
    s += text(ax-5, ay+4, 'Aᵢ', 13, INPUT_A_COLOR, 'end')
    s += text(bx-5, by+4, 'Bᵢ', 13, INPUT_B_COLOR, 'end')
    s += text(cx-5, cy+4, 'Cᵢ₋₁', 13, '#22c55e', 'end')

    # XOR1
    s += xor_gate(150, ay-5, 55, 40)
    s += line(ax, ay, 150, ay+15)
    s += line(bx, by, 150, by+5)

    # XOR2 -> S
    s += xor_gate(230, ay+15, 55, 40)
    s += line(205, ay+15, 230, ay+35)
    s += line(cx, cy, 230, cy)
    s += line(285, ay+35, 380, ay+35)
    s += text(390, ay+39, f'Sᵢ = A⊕B⊕C', 12, TEXT, 'start')

    # AND1
    s += and_gate(230, by+5, 45, 35)
    s += line(205, ay+15, 230, by+22)
    s += line(bx, by, 230, by+20)
    # AND2
    s += and_gate(230, by+40, 45, 35)
    s += line(cx, cy, 230, cy+57)
    s += line(205, ay+15, 230, by+57)
    # OR -> C
    s += or_gate(310, by+30, 45, 40)
    s += line(275, by+22, 310, by+50)
    s += line(275, by+57, 310, by+60)
    s += line(355, by+50, 380, by+50)
    s += text(390, by+54, f'Cᵢ = AB+AC+BC', 12, TEXT, 'start')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '10_02_full_adder.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 10_02_full_adder.svg')

# =====================================================================
# 图13-01: 运放符号与基本特性
# =====================================================================
def make_opamp_symbol():
    W2, H2 = 520, 260
    s = svg_header(W2, H2, BG)
    s += text(260, 22, '集成运算放大器符号', 15, TEXT, 'middle', bold=True)

    # 运放三角形
    cx, cy = 160, 80
    tw, th = 80, 110
    s += polyline([(cx, cy), (cx+tw, cy+th/2), (cx, cy+th), (cx, cy)], GATE_STROKE, 2.5)
    # 内部标注
    s += text(cx+40, cy+th/2-8, '−', 22, '#ef4444', 'middle')
    s += text(cx+40, cy+th/2+15, '+', 18, '#22c55e', 'middle')

    # 引脚线
    s += line(cx-50, cy+25, cx, cy+25, INPUT_A_COLOR, 2.5)
    s += line(cx-50, cy+85, cx, cy+85, INPUT_B_COLOR, 2.5)
    s += line(cx+tw, cy+55, cx+tw+50, cy+55, WIRE, 2.5)
    # 电源
    s += line(cx+20, cy, cx+20, cy-25, WIRE, 1.5)
    s += line(cx+60, cy, cx+60, cy-25, WIRE, 1.5)
    s += line(cx+20, cy+th, cx+20, cy+th+25, WIRE, 1.5)
    s += line(cx+60, cy+th, cx+60, cy+th+25, WIRE, 1.5)

    # 标注
    s += text(cx-55, cy+20, 'v−（反相）', 11, INPUT_A_COLOR, 'end')
    s += text(cx-55, cy+90, 'v+（同相）', 11, INPUT_B_COLOR, 'end')
    s += text(cx+tw+55, cy+58, 'vo', 12, TEXT, 'start')
    s += text(cx+20, cy-28, '+Vcc', 10, '#666', 'middle')
    s += text(cx+60, cy-28, '−Vcc', 10, '#666', 'middle')

    # 理想参数表
    s += text(400, 55, '理想运放参数', 13, TEXT, 'middle', bold=True)
    params = [
        ('开环增益 Avo', '→ ∞'),
        ('输入电阻 rid', '→ ∞'),
        ('输出电阻 ro', '→ 0'),
        ('共模抑制比', '→ ∞'),
    ]
    for i, (pname, pval) in enumerate(params):
        s += text(340, 80+i*28, pname, 11, TEXT, 'start')
        s += text(470, 80+i*28, pval, 11, '#ef4444', 'middle', bold=True)

    # 虚短/虚断
    s += box(320, 195, 180, 50, '#fffbeb', '#eab308', 1.5)
    s += text(410, 215, '虚短: v+ ≈ v−', 12, '#92400e', 'middle', bold=True)
    s += text(410, 232, '虚断: i+ ≈ i− ≈ 0', 12, '#92400e', 'middle', bold=True)

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '13_01_opamp_symbol.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 13_01_opamp_symbol.svg')

# =====================================================================
# 图13-02: 反相/同相放大器
# =====================================================================
def make_opamp_circuits():
    W2, H2 = 580, 250
    s = svg_header(W2, H2, BG)
    s += text(290, 22, '两种基本放大电路', 16, TEXT, 'middle', bold=True)

    # --- 反相放大器 ---
    s += text(130, 50, '反相放大器', 13, TEXT, 'middle', bold=True)
    # 运放
    ax, ay = 80, 70
    tw, th = 70, 95
    s += polyline([(ax, ay), (ax+tw, ay+th/2), (ax, ay+th), (ax, ay)], GATE_STROKE, 2)
    s += text(ax+35, ay+th/2-5, '−', 18, '#ef4444', 'middle')
    s += text(ax+35, ay+th/2+12, '+', 14, '#22c55e', 'middle')
    # 输入
    s += line(ax-45, ay+30, ax, ay+30, INPUT_A_COLOR, 2)
    s += line(ax-45, ay+65, ax, ay+65, INPUT_B_COLOR, 2)
    # 反馈
    s += line(ax+tw, ay+th/2, ax+tw+30, ay+th/2, WIRE, 2)
    s += line(ax+tw+30, ay+th/2, ax+tw+30, ay+th+30)
    s += line(ax+tw+30, ay+th+30, ax+30, ay+th+30)
    s += line(ax+30, ay+th+30, ax+30, ay+65)
    # Rf
    s += text(ax+tw+38, ay+th/2-8, 'Rf', 11, '#666', 'start')
    # Rin
    s += text(ax-50, ay+25, 'Rin', 10, '#666', 'end')
    # 输出
    s += line(ax+tw, ay+th/2, ax+tw+30, ay+th/2)
    s += text(ax+tw+35, ay+th/2+5, 'vo', 11, TEXT, 'start')
    # 接地
    s += line(ax+30, ay+th, ax+30, ay+th+20, WIRE, 1.5)
    s += polyline([(ax+25, ay+th+20),(ax+30, ay+th+25),(ax+35, ay+th+20)], WIRE, 2)
    # 公式
    s += box(60, 190, 160, 45, '#f0f9ff', '#3b82f6', 1)
    s += text(140, 207, 'Au = −Rf / Rin', 13, '#1e40af', 'middle', bold=True)
    s += text(140, 222, '（输出反相）', 11, '#666', 'middle')

    # --- 同相放大器 ---
    s += text(410, 50, '同相放大器', 13, TEXT, 'middle', bold=True)
    bx, by = 360, 70
    s += polyline([(bx, by), (bx+tw, by+th/2), (bx, by+th), (bx, by)], GATE_STROKE, 2)
    s += text(bx+35, by+th/2-5, '−', 18, '#ef4444', 'middle')
    s += text(bx+35, by+th/2+12, '+', 14, '#22c55e', 'middle')
    # 输入+
    s += line(bx-45, by+65, bx, by+65, INPUT_B_COLOR, 2)
    # 接地到-
    s += line(bx-45, by+30, bx, by+30, INPUT_A_COLOR, 2)
    s += line(bx-45, by+30, bx-45, by+th+30)
    s += line(bx-45, by+th+30, bx+30, by+th+30)
    s += line(bx+30, by+th+30, bx+30, by+th)
    # 反馈
    s += line(bx+tw, by+th/2, bx+tw+30, by+th/2, WIRE, 2)
    s += line(bx+tw+30, by+th/2, bx+tw+30, by+th+30)
    s += line(bx+tw+30, by+th+30, bx+30, by+th+30)
    s += text(bx+tw+38, by+th/2-8, 'Rf', 11, '#666', 'start')
    s += text(bx-50, by+25, 'GND', 10, '#666', 'end')
    # 输出
    s += line(bx+tw, by+th/2, bx+tw+30, by+th/2)
    s += text(bx+tw+35, by+th/2+5, 'vo', 11, TEXT, 'start')
    # 接地
    s += line(bx+30, by+th, bx+30, by+th+20, WIRE, 1.5)
    s += polyline([(bx+25, by+th+20),(bx+30, by+th+25),(bx+35, by+th+20)], WIRE, 2)
    # 公式
    s += box(340, 190, 160, 45, '#f0fdf4', '#16a34a', 1)
    s += text(420, 207, 'Au = 1 + Rf/R1', 13, '#166534', 'middle', bold=True)
    s += text(420, 222, '（输出同相）', 11, '#666', 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '13_02_opamp_circuits.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 13_02_opamp_circuits.svg')

# =====================================================================
# 图14-01: 直流电源系统框图
# =====================================================================
def make_power_supply_block():
    W2, H2 = 560, 200
    s = svg_header(W2, H2, BG)
    s += text(280, 22, '直流稳压电源系统框图', 16, TEXT, 'middle', bold=True)

    blocks = [
        ('交流电网', '~220V', 50, 60, 80, 50, '#fef3c7', '#d97706'),
        ('变压器', '降压', 160, 60, 80, 50, '#dbeafe', '#1d4ed8'),
        ('整流电路', 'AC→脉动DC', 270, 60, 80, 50, '#fce7f3', '#be185d'),
        ('滤波电路', '平滑波形', 380, 60, 80, 50, '#d1fae5', '#047857'),
        ('稳压电路', '稳定DC输出', 490, 60, 80, 50, '#ede9fe', '#6d28d9'),
    ]

    for label, sub, bx, by, bw, bh, bg_c, border in blocks:
        s += box(bx, by, bw, bh, bg_c, border, 2)
        s += text(bx+bw/2, by+bh/2-6, label, 12, border, 'middle', bold=True)
        s += text(bx+bw/2, by+bh/2+10, sub, 10, '#666', 'middle')

    # 箭头
    for i in range(4):
        ax = 130 + i*110
        ay = 85
        s += line(ax, ay, ax+30, ay, '#666', 2)
        s += polyline([(ax+25, ay-5), (ax+30, ay), (ax+25, ay+5)], '#666', 2)

    # 下方信号示意
    waves_coords = [(70, 160), (180, 160), (290, 160), (400, 160), (510, 160)]
    wave_labels = ['~正弦波', '低压正弦', '单方向脉动', '较平滑', '+12V稳定']
    # 正弦（简化：分段线近似）
    sine_pts = [(70,130),(88,130),(105,160),(122,160),(140,130),(158,130),(175,160),(192,160),(210,130)]
    s += '  <polyline points="'+' '.join([f'{x},{y}' for x,y in sine_pts])+'" fill="none" stroke="#3b82f6" stroke-width="1.5"/>\n'
    # 低压正弦
    sine2 = [(180,140),(198,140),(215,160),(232,160),(250,140),(268,140),(285,160),(302,160),(320,140)]
    s += '  <polyline points="'+' '.join([f'{x},{y}' for x,y in sine2])+'" fill="none" stroke="#3b82f6" stroke-width="1.5"/>\n'
    # 整流波形（只有上半正弦）
    half = ' '.join([f'{290+i*30},{160-25*max(0,(1 if i%2==0 else 0))}' for i in range(9)])
    s += f'  <polyline points="{half}" fill="none" stroke="#ef4444" stroke-width="1.5"/>\n'
    # 平滑（衰减波）
    smooth = ' '.join([f'{400+i*30},{160-20*(0.8 if i%2==1 else 0.1)}' for i in range(9)])
    s += f'  <polyline points="{smooth}" fill="none" stroke="#22c55e" stroke-width="1.5"/>\n'
    # 直流
    s += line(510, 160-15, 540, 160-15, '#6d28d9', 2)
    s += line(510, 160-15, 510, 160+5, '#6d28d9', 2)
    s += line(510, 160+5, 540, 160+5, '#6d28d9', 2)
    for lx, lbl in zip(waves_coords, wave_labels):
        s += text(lx[0]+40, 175, lbl, 9, '#666', 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '14_01_power_supply_block.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 14_01_power_supply_block.svg')

# =====================================================================
# 图14-02: 整流电路对比
# =====================================================================
def make_rectifier_circuits():
    W2, H2 = 580, 300
    s = svg_header(W2, H2, BG)
    s += text(290, 22, '半波整流 vs 全波桥式整流', 16, TEXT, 'middle', bold=True)

    # --- 半波整流 ---
    s += text(120, 52, '半波整流', 13, TEXT, 'middle', bold=True)
    # 变压器
    s += box(40, 70, 60, 30, '#fef3c7', '#d97706', 1.5)
    s += text(70, 89, '~AC', 11, '#d97706', 'middle')
    # 二极管
    s += diode_symbol(105, 70, 30, 30, vertical=True)
    # 负载
    s += box(145, 70, 60, 30, '#d1fae5', '#047857', 1.5)
    s += text(175, 89, 'RL', 11, '#047857', 'middle')
    # 连接线
    s += line(100, 85, 105, 85)
    s += line(135, 85, 145, 85)
    s += line(175, 100, 175, 115)
    s += line(175, 115, 40, 115)
    s += line(40, 115, 40, 100)
    s += line(40, 70, 40, 100)
    # 波形
    wave_pts = [(50,200),(90,200),(90,175),(130,175),(130,200),(170,200),(170,175),(210,175),(210,200)]
    pts_str = ' '.join([f'{x},{y}' for x,y in wave_pts])
    s += f'  <polyline points="{pts_str}" fill="none" stroke="#3b82f6" stroke-width="2"/>\n'
    s += line(50, 200, 220, 200, '#aaa', 1)
    s += text(230, 200, 't', 11, '#666', 'start')
    s += text(70, 220, '效率 ≈ 40.6%', 10, '#666', 'middle')

    # --- 全波桥式整流 ---
    s += text(400, 52, '全波桥式整流', 13, TEXT, 'middle', bold=True)
    cx, cy = 360, 85
    r = 30
    # 四边形桥式
    s += line(cx-2*r, cy-r, cx, cy, WIRE, 2)
    s += line(cx, cy, cx+2*r, cy-r, WIRE, 2)
    s += line(cx+2*r, cy-r, cx, cy+2*r, WIRE, 2)
    s += line(cx, cy+2*r, cx-2*r, cy, WIRE, 2)
    # D1 (左上)
    s += diode_symbol(cx-r-5, cy-r-12, 20, 24, vertical=False)
    # D2 (左下)
    s += diode_symbol(cx-r-5, cy+r-12, 20, 24, vertical=False)
    # D3 (右上)
    s += diode_symbol(cx+r-15, cy-r-12, 20, 24, vertical=False)
    # D4 (右下)
    s += diode_symbol(cx+r-15, cy+r-12, 20, 24, vertical=False)
    # RL
    s += box(cx-20, cy+r+8, 40, 25, '#d1fae5', '#047857', 1.5)
    s += text(cx, cy+r+22, 'RL', 11, '#047857', 'middle')
    # 标注
    s += text(cx-2*r-10, cy-5, 'AC', 10, '#d97706', 'end')
    s += text(cx+2*r+8, cy-5, 'AC', 10, '#d97706', 'start')
    # 波形（全波）
    wave_pts2 = [(300,200),(330,175),(360,200),(390,175),(420,200),(450,175),(480,200)]
    pts_str2 = ' '.join([f'{x},{y}' for x,y in wave_pts2])
    s += f'  <polyline points="{pts_str2}" fill="none" stroke="#ef4444" stroke-width="2"/>\n'
    s += line(300, 200, 490, 200, '#aaa', 1)
    s += text(495, 200, 't', 11, '#666', 'start')
    s += text(395, 220, '效率 ≈ 81.2%', 10, '#666', 'middle')
    # 标注D1-D4
    s += text(cx-r, cy-r*2, 'D1', 10, '#666', 'middle')
    s += text(cx-r, cy+r*2-5, 'D2', 10, '#666', 'middle')
    s += text(cx+r, cy-r*2, 'D3', 10, '#666', 'middle')
    s += text(cx+r, cy+r*2-5, 'D4', 10, '#666', 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '14_02_rectifier_circuits.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 14_02_rectifier_circuits.svg')

# =====================================================================
# 图14-03: 电容滤波效果
# =====================================================================
def make_capacitor_filter():
    W2, H2 = 560, 260
    s = svg_header(W2, H2, BG)
    s += text(280, 22, '电容滤波效果示意', 16, TEXT, 'middle', bold=True)

    # 整流后波形
    s += text(80, 52, '整流后', 12, TEXT, 'middle', bold=True)
    wave1 = [(30,90),(50,60),(70,90),(90,90),(110,60),(130,90),(150,90),(170,60),(190,90)]
    s += '  <polyline points="'+' '.join([f'{x},{y}' for x,y in wave1])+'" fill="none" stroke="#ef4444" stroke-width="2"/>\n'
    s += line(30, 90, 210, 90, '#aaa', 1)
    s += text(215, 90, '→', 12, '#666', 'start')

    # 电容滤波后
    s += text(360, 52, '电容滤波后', 12, TEXT, 'middle', bold=True)
    # 充电-放电曲线
    filter_pts = [
        (250,60),(260,60),(280,63),(300,68),(320,75),(330,90),
        (340,60),(350,60),(370,63),(390,68),(410,75),(420,90),
        (430,60),(440,60),(460,63),(480,68),(500,75),(510,90)
    ]
    s += '  <polyline points="'+' '.join([f'{x},{y}' for x,y in filter_pts])+'" fill="none" stroke="#3b82f6" stroke-width="2.5"/>\n'
    s += line(250, 90, 530, 90, '#aaa', 1)
    s += text(535, 90, 't', 11, '#666', 'start')

    # 说明文字
    s += box(80, 110, 120, 65, '#fffbeb', '#eab308', 1)
    s += text(140, 128, '峰值充电', 11, '#92400e', 'middle', bold=True)
    s += text(140, 146, '二极管导通时', 11, '#666', 'middle')
    s += text(140, 162, '电容快速充电', 11, '#666', 'middle')

    s += box(380, 110, 140, 65, '#f0fdf4', '#16a34a', 1)
    s += text(450, 128, '指数放电', 11, '#166534', 'middle', bold=True)
    s += text(450, 146, '二极管截止时', 11, '#666', 'middle')
    s += text(450, 162, '电容对RL放电', 11, '#666', 'middle')

    # 电路图
    s += text(280, 200, '电容滤波电路', 12, TEXT, 'middle', bold=True)
    # 简化的整流+电容+负载示意
    s += box(150, 210, 50, 25, '#fef3c7', '#d97706', 1)
    s += text(175, 225, '整流', 10, '#d97706', 'middle')
    s += line(200, 222, 240, 222, WIRE, 2)
    # 电容（并联）
    s += text(265, 210, 'C', 14, '#3b82f6', 'middle', bold=True)
    s += line(250, 222, 280, 222, WIRE, 2)
    s += line(280, 222, 320, 222, WIRE, 2)
    # 负载
    s += box(320, 210, 40, 25, '#d1fae5', '#047857', 1.5)
    s += text(340, 225, 'RL', 11, '#047857', 'middle')
    # 接地
    s += line(340, 235, 340, 245, WIRE, 1.5)
    s += polyline([(335,245),(340,250),(345,245)], WIRE, 2)

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '14_03_capacitor_filter.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 14_03_capacitor_filter.svg')


# =====================================================================
# 图14-04: 串联型稳压电路
# =====================================================================
def make_series_regulator():
    W2, H2 = 540, 260
    s = svg_header(W2, H2, BG)
    s += text(270, 22, '串联型稳压电路原理', 15, TEXT, 'middle', bold=True)

    # 核心组件
    # 调整管（CE组态三极管）
    s += text(80, 60, '调整管VT', 11, TEXT, 'middle', bold=True)
    tx, ty = 50, 70
    s += polyline([(tx, ty), (tx+45, ty+20), (tx+45, ty+55), (tx, ty+75), (tx, ty)], GATE_STROKE, 2)
    s += text(tx+22, ty+40, 'NPN', 10, '#666', 'middle')
    # 输入输出
    s += line(tx-30, ty+20, tx, ty+20, INPUT_A_COLOR, 2)
    s += text(tx-35, ty+24, 'vi', 11, INPUT_A_COLOR, 'end')
    s += line(tx-30, ty+55, tx, ty+55, INPUT_B_COLOR, 2)
    s += text(tx-35, ty+59, 'vb', 11, INPUT_B_COLOR, 'end')
    s += line(tx+45, ty+37, tx+45+30, ty+37, WIRE, 2)
    s += text(tx+80, ty+41, 'vo', 11, TEXT, 'start')
    # 箭头（集电极电流）
    s += text(tx+15, ty+25, 'C', 10, '#666', 'middle')
    s += text(tx+15, ty+60, 'E', 10, '#666', 'middle')

    # 反馈网络
    s += text(240, 60, '反馈网络', 11, TEXT, 'middle', bold=True)
    s += box(195, 70, 90, 50, '#f0fdf4', '#16a34a', 1.5)
    s += text(240, 92, 'R1+RW+R2', 11, '#166534', 'middle', bold=True)
    s += text(240, 108, '分压器', 10, '#666', 'middle')

    # 比较放大
    s += text(370, 60, '比较放大', 11, TEXT, 'middle', bold=True)
    s += box(320, 70, 90, 50, '#ede9fe', '#6d28d9', 1.5)
    s += text(365, 92, '误差放大', 11, '#6d28d9', 'middle', bold=True)
    s += text(365, 108, '+ 基准', 10, '#666', 'middle')

    # 基准源
    s += box(320, 140, 90, 35, '#fef3c7', '#d97706', 1)
    s += text(365, 161, '基准源Vz', 11, '#d97706', 'middle', bold=True)

    # 连线
    # 输出→分压
    s += line(tx+75, ty+37, 195, 95)
    s += line(195, 95, 195, 115)
    s += line(195, 115, 320, 115)
    s += line(320, 115, 320, 120)
    # 分压→比较
    s += line(285, 95, 320, 95)
    # 比较→调整管基极
    s += line(320, 95, 320, 75)
    s += line(320, 75, tx+45, 75)
    # 基准→比较
    s += line(365, 140, 365, 120)
    # 地线
    s += line(340, 175, 340, 185, WIRE, 1.5)
    s += polyline([(335,185),(340,190),(345,185)], WIRE, 2)

    # 稳压过程说明
    s += box(60, 190, 200, 55, '#fffbeb', '#eab308', 1)
    s += text(160, 208, '↓ vo因负载/输入变化而变化', 11, '#92400e', 'middle')
    s += text(160, 224, '→ 比较放大器检测误差', 11, '#92400e', 'middle')
    s += text(160, 240, '→ 调整管改变内阻', 11, '#92400e', 'middle')

    s += box(300, 190, 200, 55, '#f0fdf4', '#16a34a', 1)
    s += text(400, 208, '负反馈自动调节机制:', 11, '#166534', 'middle', bold=True)
    s += text(400, 224, 'vo↑ → Vb↑ → Vbe↓ → Ic↓', 11, '#166534', 'middle')
    s += text(400, 240, '→ 管压降↑ → vo↓（恢复）', 11, '#166534', 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '14_04_series_regulation.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 14_04_series_regulation.svg')


# =====================================================================
# 图11-01: 8-3优先编码器示意
# =====================================================================
def make_encoder():
    W2, H2 = 500, 280
    s = svg_header(W2, H2, BG)
    s += text(250, 22, '8-3线优先编码器（74148）功能示意', 15, TEXT, 'middle', bold=True)

    # 输入框
    s += box(30, 55, 120, 170, '#fafafa', '#aaa', 1)
    s += text(90, 72, '输入 (I₀~I₇)', 11, TEXT, 'middle', bold=True)
    s += text(90, 87, '0=有效, 1=无效', 9, '#666', 'middle')
    for i in range(8):
        s += text(40, 105+i*16, f'I{7-i}', 11, '#3b82f6', 'end')
        s += line(45, 100+i*16, 60, 100+i*16, WIRE, 1.5)
        # 高电平(无效)示意
        s += line(60, 100+i*16, 60, 93+i*16, WIRE, 1.5)
        s += text(65, 100+i*16, '1', 10, '#ef4444', 'start')

    # 优先级标签
    s += text(155, 100, '优先级:', 10, '#666', 'end')
    s += text(165, 100, 'I₇ > I₆ > ... > I₀', 10, '#3b82f6', 'start')

    # 输出框
    s += box(200, 100, 100, 90, '#f0f9ff', '#3b82f6', 1)
    s += text(250, 118, '输出', 11, '#1e40af', 'middle', bold=True)
    s += text(250, 134, '(反码)', 9, '#666', 'middle')
    for i, bit in enumerate(['Ȳ₂', 'Ȳ₁', 'Ȳ₀']):
        s += text(210, 152+i*20, bit, 12, '#1e40af', 'end')
        s += line(215, 148+i*20, 290, 148+i*20, WIRE, 1.5)
        s += text(295, 152+i*20, '(取反)', 9, '#666', 'start')

    # 典型工作示例
    s += box(30, 240, 270, 35, '#fffbeb', '#eab308', 1)
    s += text(165, 256, '例: I₅=0, 其余=1 → 输出 Ȳ₂Ȳ₁Ȳ₀=010（即编码5的反码）', 11, '#92400e', 'middle')
    s += text(165, 270, '优先级使 I₇~I₆ 为1时，编码结果为000（优先响应更高优先级）', 10, '#92400e', 'middle')

    s += text(W2-10, H2-5, 'AI绘制', 9, '#999', 'end')
    s += svg_footer()
    with open(OUT_DIR / '11_01_encoder.svg', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Created: 11_01_encoder.svg')


# =====================================================================
# 主函数
# =====================================================================
def main():
    make_analog_vs_digital()
    make_basic_gates()
    make_composite_gates()
    make_karnaugh_2var()
    make_karnaugh_3var()
    make_half_adder()
    make_full_adder()
    make_opamp_symbol()
    make_opamp_circuits()
    make_power_supply_block()
    make_rectifier_circuits()
    make_capacitor_filter()
    make_series_regulator()
    make_encoder()
    print(f'\nAll diagrams saved to: {OUT_DIR}')
    print(f'Total: {len(list(OUT_DIR.glob("*.svg")))} files')

if __name__ == '__main__':
    main()
