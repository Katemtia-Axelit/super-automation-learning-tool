import subprocess
import os
import glob
import sys

base_dir = r"d:\Axelit\工作\trae\超级自动化学习工具\src\notes\Radiances Of Wisdom\哲学探索篇附件——与同学的一次微型辩论"

png_files = sorted(glob.glob(os.path.join(base_dir, "*.png")))

# Write a PowerShell script with proper encoding
ps_script_path = os.path.join(os.path.dirname(__file__), "ocr_script.ps1")

with open(ps_script_path, 'w', encoding='utf-8-sig') as f:
    f.write('''
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]

$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocrEngine) {
    Write-Host "OCR engine creation failed"
    exit 1
}
''')

print("PowerShell script written successfully")
print("Running PowerShell script...")

# Run each file individually
for png_file in png_files:
    filename = os.path.basename(png_file)
    print(f"\n{'='*80}")
    print(f"File: {filename}")
    print(f"{'='*80}")
    
    # Build the PowerShell command
    ps_cmd = f'''
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]

$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocrEngine) {{
    Write-Host "OCR engine creation failed"
    exit 1
}}

$stream = [System.IO.File]::OpenRead("{png_file}")
$decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
$bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
$result = $ocrEngine.RecognizeAsync($bitmap).GetAwaiter().GetResult()
foreach ($line in $result.Lines) {{
    Write-Host $line.Text
}}
$stream.Close()
'''
    
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"Error (exit code {result.returncode}):")
            print(result.stderr)
    except Exception as e:
        print(f"Failed: {e}")

print("\n\nDone!")