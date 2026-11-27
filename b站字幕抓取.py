import json
import re
import sys
import os
import random
from typing import List, Dict, Any

# 设置控制台编码为UTF-8（Windows）
if sys.platform == 'win32':
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

# 目标保存目录
SAVE_DIR = r"D:\Axelit\工作\trae\超级自动化学习工具\app\未分类"


def repair_json(json_str: str) -> str:
    """修复常见的B站字幕JSON格式问题"""
    # 移除BOM头
    if json_str.startswith('\ufeff'):
        json_str = json_str[1:]

    # 移除末尾多余逗号（在]或}之前）
    json_str = re.sub(r',\s*([\]}])', r'\1', json_str)

    # 修复连续逗号
    json_str = re.sub(r',\s*,', ',', json_str)

    return json_str


def split_json_objects(json_str: str) -> List[str]:
    """
    将可能包含多个拼接JSON对象的字符串分割成独立的JSON字符串
    处理类似 {...}{...} 或 {...}\n{...} 的情况
    """
    objects = []
    bracket_count = 0
    start_idx = None
    in_string = False
    escape_next = False

    for i, ch in enumerate(json_str):
        # 处理字符串内的转义和引号
        if escape_next:
            escape_next = False
            continue

        if ch == '\\':
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if ch == '{':
                if bracket_count == 0:
                    start_idx = i
                bracket_count += 1
            elif ch == '}':
                bracket_count -= 1
                if bracket_count == 0 and start_idx is not None:
                    objects.append(json_str[start_idx:i + 1])
                    start_idx = None

    return objects


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    # Windows文件名不允许的字符
    illegal_chars = r'[<>:"/\\|?*]'
    filename = re.sub(illegal_chars, '', filename)
    # 移除首尾空格和点
    filename = filename.strip('. ')
    # 限制长度
    if len(filename) > 50:
        filename = filename[:50]
    # 如果文件名为空，使用默认名称
    if not filename:
        filename = "subtitle"
    return filename


def parse_subtitle_json(json_str: str) -> List[Dict[str, Any]]:
    """解析B站字幕JSON，支持单段或多段拼接，返回合并后的body列表"""
    all_body_items = []

    # 先修复格式
    json_str = repair_json(json_str)

    # 尝试分割多个JSON对象
    json_objects = split_json_objects(json_str)

    if not json_objects:
        # 如果没有找到完整的JSON对象，尝试直接解析整个字符串
        json_objects = [json_str]

    for obj_str in json_objects:
        try:
            data = json.loads(obj_str)
            if isinstance(data, dict) and "body" in data:
                all_body_items.extend(data["body"])
            elif isinstance(data, list):
                all_body_items.extend(data)
            elif isinstance(data, dict) and "from" in data and "content" in data:
                # 单个字幕条目
                all_body_items.append(data)
            else:
                # 尝试更宽松的解析：提取所有带from和content的对象
                def extract_body(obj):
                    if isinstance(obj, dict):
                        if "from" in obj and "content" in obj and "to" in obj:
                            all_body_items.append(obj)
                        for value in obj.values():
                            extract_body(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            extract_body(item)

                extract_body(data)
        except json.JSONDecodeError as e:
            # 如果单个对象解析失败，尝试更宽松的方式
            # 使用正则提取所有字幕条目
            pattern = r'"from":\s*([\d.]+),\s*"to":\s*([\d.]+),\s*"sid":\s*\d+,\s*"content":\s*"([^"]*)"'
            matches = re.findall(pattern, obj_str)
            for match in matches:
                all_body_items.append({
                    "from": float(match[0]),
                    "to": float(match[1]),
                    "content": match[2]
                })

    # 去重（基于from和content）
    seen = set()
    unique_items = []
    for item in all_body_items:
        key = (item.get("from", 0), item.get("content", ""))
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    # 按时间排序
    unique_items.sort(key=lambda x: x.get("from", 0))

    return unique_items


def get_random_sentence(body: List[Dict[str, Any]]) -> str:
    """随机获取一条字幕作为文件名"""
    if body:
        # 随机选择一条字幕
        random_item = random.choice(body)
        content = random_item.get("content", "")
        # 移除标点符号和特殊字符
        content = re.sub(r'[，,。！？；：""''！？\s]', '', content)
        # 限制长度
        if len(content) > 30:
            content = content[:30]
        return content if content else "subtitle"
    return "subtitle"


def generate_plain_text(body: List[Dict[str, Any]]) -> str:
    """生成纯文本（每行一句，只保留content）"""
    lines = []
    for item in body:
        content = item.get("content", "").strip()
        if content:
            lines.append(content)
    return "\n".join(lines)


def ensure_save_dir():
    """确保保存目录存在，如果不存在则创建"""
    if not os.path.exists(SAVE_DIR):
        try:
            os.makedirs(SAVE_DIR)
            print(f"✓ 已创建目录: {SAVE_DIR}")
        except Exception as e:
            print(f"✗ 创建目录失败: {e}")
            return False
    return True


def check_file_exists(filepath: str) -> bool:
    """检查文件是否已存在"""
    return os.path.exists(filepath)


def get_user_overwrite_choice(filename: str) -> bool:
    """询问用户是否覆盖已有文件"""
    while True:
        choice = input(f"\n⚠ 文件 '{filename}' 已存在，是否覆盖？(y=覆盖/n=取消/输入新文件名): ").strip().lower()
        if choice == 'y':
            return True
        elif choice == 'n':
            return False
        elif choice:
            # 用户输入了新文件名
            return choice
        else:
            print("请输入 y、n 或新文件名")


def save_file(content: str, filename: str) -> bool:
    """保存文件，支持覆盖提示和自定义文件名"""
    # 确保文件名有正确的扩展名
    if not filename.endswith('.txt'):
        filename += '.txt'

    # 获取完整路径
    filepath = os.path.join(SAVE_DIR, filename)

    # 检查文件是否已存在
    if check_file_exists(filepath):
        choice = get_user_overwrite_choice(filename)
        if choice is False:  # 用户选择取消
            print("✗ 已取消保存")
            return False
        elif isinstance(choice, str) and choice != 'y':  # 用户输入了新文件名
            # 递归调用，使用新文件名
            return save_file(content, choice)

    try:
        # 保存文件（使用utf-8-sig确保中文正确显示）
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        print(f"\n✓ 文件已保存到: {filepath}")
        print(f"✓ 文件大小: {len(content)} 字符")
        return True
    except Exception as e:
        print(f"✗ 保存失败: {e}")
        return False


def process_subtitle(json_text: str) -> bool:
    """处理单个字幕JSON，返回是否成功"""
    if not json_text.strip():
        print("警告：未输入任何内容，已跳过")
        return False

    print("\n正在解析JSON...")

    # 解析JSON
    try:
        body = parse_subtitle_json(json_text)
        if not body:
            print("警告：未找到任何字幕条目")
            return False
        print(f"✓ 成功解析到 {len(body)} 条字幕")
    except Exception as e:
        print(f"✗ 解析失败: {e}")
        return False

    # 随机获取一条字幕作为文件名
    random_sentence = get_random_sentence(body)
    print(f"\n自动生成文件名（随机选择）: {random_sentence}")

    # 预览前几条
    print("\n" + "-" * 60)
    print("预览前5条字幕：")
    for i, item in enumerate(body[:5], 1):
        content = item.get("content", "")[:60]
        print(f"  {i}. {content}")
    if len(body) > 5:
        print(f"  ... 共{len(body)}条")

    # 生成纯文本
    output = generate_plain_text(body)
    lines_count = len(output.split('\n'))
    print(f"\n✓ 已生成纯文本，共 {lines_count} 行")

    # 保存文件
    print("\n" + "=" * 60)
    print("保存文件...")

    # 确保保存目录存在
    if not ensure_save_dir():
        print("✗ 无法创建或访问保存目录")
        return False

    filename = sanitize_filename(random_sentence)

    if save_file(output, filename):
        print("\n✓ 完成！")
        return True
    else:
        # 如果保存失败，显示内容
        print("\n" + "=" * 60)
        print("生成结果：")
        print("=" * 60)

        # 显示结果（如果太长则只显示前后部分）
        lines_output = output.split('\n')
        if len(lines_output) > 50:
            print("\n".join(lines_output[:25]))
            print(f"\n... 中间省略 {len(lines_output) - 50} 行 ...\n")
            print("\n".join(lines_output[-25:]))
        else:
            print(output)
        return False


def main():
    # 设置控制台编码
    if sys.platform == 'win32':
        try:
            # 尝试设置控制台为UTF-8
            os.system('chcp 65001 > nul')
        except:
            pass

    print("=" * 60)
    print("B站字幕JSON还原工具 v5.0 - 纯文本版")
    print("=" * 60)
    print("说明：")
    print("  - 支持粘贴多段JSON（如 {...}{...} 格式）")
    print(f"  - 自动保存到: {SAVE_DIR}")
    print("  - 自动用随机一条字幕命名文件")
    print("  - 粘贴完成后，输入 '1' 确认并处理")
    print("  - 输入 'q' 或 'quit' 退出程序")
    print("=" * 60)

    while True:
        print("\n" + "=" * 60)
        print("请输入字幕JSON（可多行粘贴）：")
        print("-" * 60)
        print("提示：粘贴完成后，在新的一行输入 '1' 并回车确认")
        print("-" * 60)

        # 读取多行输入
        lines = []
        while True:
            try:
                line = input()
                # 检查是否退出
                if line.strip().lower() in ['q', 'quit', 'exit']:
                    print("\n退出程序...")
                    input("\n按回车键退出...")
                    return

                # 检查是否确认输入（单独的"1"）
                if line.strip() == "1" and lines:  # 只有在已经有输入内容时，"1"才表示确认
                    break
                elif line.strip() == "1" and not lines:  # 刚开始就输入"1"，忽略并继续
                    print("提示：请先粘贴JSON内容，然后再输入'1'确认")
                    continue
                else:
                    lines.append(line)
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n\n退出程序...")
                input("\n按回车键退出...")
                return

        json_text = "\n".join(lines)

        # 处理字幕
        process_subtitle(json_text)

        print("\n" + "=" * 60)
        print("✅ 处理完成！可以继续输入下一个字幕")
        print("提示：粘贴JSON后输入'1'确认，或输入'q'退出程序")
        print("=" * 60)


if __name__ == "__main__":
    main()