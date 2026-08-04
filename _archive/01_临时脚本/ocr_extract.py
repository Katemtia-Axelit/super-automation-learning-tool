import easyocr
import os
import glob

# 初始化 EasyOCR reader，指定中文和英文
print("正在初始化 EasyOCR（首次运行会下载模型，请稍候）...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)

base_dir = r"d:\Axelit\工作\trae\超级自动化学习工具\src\notes\Radiances Of Wisdom\哲学探索篇附件——与同学的一次微型辩论"

# 获取所有 PNG 文件，按名称排序
png_files = sorted(glob.glob(os.path.join(base_dir, "*.png")))

for png_file in png_files:
    filename = os.path.basename(png_file)
    print(f"\n{'='*80}")
    print(f"文件: {filename}")
    print(f"{'='*80}")
    
    try:
        results = reader.readtext(png_file, detail=0)
        # 合并所有检测到的文本
        text = '\n'.join(results)
        print(text)
    except Exception as e:
        print(f"读取失败: {e}")

print("\n\n完成！")