# PowerShell script: Use Windows built-in OCR API
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]

$baseDir = "d:\Axelit\工作\trae\超级自动化学习工具\src\notes\Radiances Of Wisdom\哲学探索篇附件——与同学的一次微型辩论"

$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocrEngine) {
    Write-Host "OCR engine creation failed"
    exit 1
}

Get-ChildItem -Path $baseDir -Filter "*.png" | Sort-Object Name | ForEach-Object {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "File: $($_.Name)"
    Write-Host "========================================"
    
    try {
        $stream = [System.IO.File]::OpenRead($_.FullName)
        $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
        $bitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
        
        $result = $ocrEngine.RecognizeAsync($bitmap).GetAwaiter().GetResult()
        
        foreach ($line in $result.Lines) {
            Write-Host $line.Text
        }
        
        $stream.Close()
    } catch {
        Write-Host "Error: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "Done!"