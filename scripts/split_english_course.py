# -*- coding: utf-8 -*-
"""
英语急救班网课资料分割脚本
将大文件平均分割成5份，便于AI分批处理
"""

import os
import math
import sys

# 确保输出正确编码
sys.stdout.reconfigure(encoding='utf-8')

def split_file(input_path, output_dir, num_parts=5):
    """将文件分割成指定份数"""
    
    filename = os.path.basename(input_path)
    name_without_ext = os.path.splitext(filename)[0]
    
    # 读取原始文件
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    lines_per_part = math.ceil(total_lines / num_parts)
    
    print(f"\n{'='*60}")
    print(f"文件: {filename}")
    print(f"总行数: {total_lines}")
    print(f"分割份数: {num_parts}")
    print(f"每份约: {lines_per_part} 行")
    print(f"{'='*60}")
    
    # 创建分割逻辑说明
    split_info = []
    split_info.append(f"# {filename} 分割说明")
    split_info.append("")
    split_info.append(f"## 原始文件信息")
    split_info.append(f"- 文件名: {filename}")
    split_info.append(f"- 总行数: {total_lines}")
    split_info.append(f"- 分割份数: {num_parts}")
    split_info.append("")
    split_info.append(f"## 分割方案")
    split_info.append("")
    
    for i in range(num_parts):
        start_line = i * lines_per_part + 1  # 1-indexed
        end_line = min((i + 1) * lines_per_part, total_lines)
        actual_lines = end_line - start_line + 1
        
        # 创建输出文件名
        part_filename = f"{name_without_ext}_第{i+1}部分.txt"
        output_path = os.path.join(output_dir, part_filename)
        
        # 写入分割内容
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines[start_line - 1:end_line])
        
        # 记录分割信息
        split_info.append(f"### 第{i+1}部分: {part_filename}")
        split_info.append(f"- 行数范围: 第{start_line}行 ~ 第{end_line}行")
        split_info.append(f"- 实际行数: {actual_lines} 行")
        split_info.append(f"- 内容概要: 承接第{i}部分的内容，继续...")
        split_info.append("")
        
        print(f"[OK] 第{i+1}部分: {part_filename} ({start_line}-{end_line}, {actual_lines}行)")
    
    # 写入分割说明文件
    info_filename = f"{name_without_ext}_分割说明.md"
    info_path = os.path.join(output_dir, info_filename)
    with open(info_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(split_info))
    
    print(f"[OK] 分割说明已保存: {info_filename}")
    return split_info

def main():
    # 未分类文件夹路径
    base_dir = r"D:\Axelit\工作\trae\超级自动化学习工具\src\notes\未分类"
    output_dir = base_dir  # 直接在原文件夹处理
    
    # 需要分割的文件
    files = [
        "Learntheweakforms.txt",
        "Simplytopassanexam.txt",
        "第一个是上来是称呼.txt"
    ]
    
    print("=" * 60)
    print("英语急救班网课资料分割脚本")
    print("=" * 60)
    
    all_split_info = []
    
    for filename in files:
        input_path = os.path.join(base_dir, filename)
        if os.path.exists(input_path):
            info = split_file(input_path, output_dir, num_parts=5)
            all_split_info.extend(info)
            all_split_info.append("")  # 空行分隔
        else:
            print(f"[WARN] 文件不存在: {filename}")
    
    print("\n" + "=" * 60)
    print("分割完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
