import subprocess
import os
import glob

base_dir = r"d:\Axelit\工作\trae\超级自动化学习工具\src\notes\Radiances Of Wisdom\哲学探索篇附件——与同学的一次微型辩论"

png_files = sorted(glob.glob(os.path.join(base_dir, "*.png")))

# PowerShell script content
ps_script = '''
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]

$baseDir = "{base_dir}"
$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocrEngine) {{
    Write-Host "OCR_FAILED"
    exit 1
}}

Get-ChildItem -Path $baseDir -Filter "*.png" | Sort-Object Name | ForEach-Object {{
    Write-Host "FILE_START: $($_.Name)"
    try {{
        $stream = [System.IO.File]::OpenRead($_.FullName)
        $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
        $bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
        $result = $ocrEngine.RecognizeAsync($bitmap).GetAwaiter().GetResult()
        foreach ($line in $result.Lines) {{
            Write-Host $line.Text
        }}
        $stream.Close()
    }} catch {{
        Write-Host "ERROR: $($_.Exception.Message)"
    }}
    Write-Host "FILE_END"
}}
Write-Host "DONE"
'''

for png_file in png_files:
    filename = os.path.basename(png_file)
    print(f"\n{'='*80}")
    print(f"File: {filename}")
    print(f"{'='*80}")
    
    # Process each file individually
    script = f'''
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]

$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocrEngine) {{
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
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True, text=True, timeout=60, encoding='utf-8'
        )
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"Error (exit code {result.returncode}): {result.stderr}")
    except Exception as e:
        print(f"Failed: {e}")

print("\n\nDone!")