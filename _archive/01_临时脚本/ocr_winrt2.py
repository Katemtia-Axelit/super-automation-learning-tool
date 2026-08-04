import asyncio
import os
import glob
from winrt.windows.storage import StorageFile, FileAccessMode
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine

async def ocr_image(file_path):
    filename = os.path.basename(file_path)
    print(f"\n{'='*80}")
    print(f"File: {filename}")
    print(f"{'='*80}")
    
    try:
        # Get StorageFile from path
        storage_file = await StorageFile.get_file_from_path_async(file_path)
        
        # Open stream
        stream = await storage_file.open_async(FileAccessMode.READ)
        
        # Create decoder
        decoder = await BitmapDecoder.create_async(stream)
        
        # Get bitmap
        bitmap = await decoder.get_software_bitmap_async()
        
        # Create OCR engine
        engine = OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            print("ERROR: Could not create OCR engine")
            return
        
        # Recognize
        result = await engine.recognize_async(bitmap)
        
        for line in result.lines:
            print(line.text)
        
        stream.close()
    except Exception as e:
        print(f"ERROR: {e}")

async def main():
    base_dir = r"d:\Axelit\工作\trae\超级自动化学习工具\src\notes\Radiances Of Wisdom\哲学探索篇附件——与同学的一次微型辩论"
    
    png_files = sorted(glob.glob(os.path.join(base_dir, "*.png")))
    
    for png_file in png_files:
        await ocr_image(png_file)
    
    print("\n\nDone!")

asyncio.run(main())