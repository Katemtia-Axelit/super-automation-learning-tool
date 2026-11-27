$ErrorActionPreference = 'Continue'
$PY = 'D:\Axelit\.工作\trae\超级自动化学习工具\.venv\Scripts\python.exe'
$SCRIPT = 'D:\Axelit\.工作\trae\超级自动化学习工具\scripts\verify_p0_cleanup.py'
& $PY $SCRIPT
Write-Host ('EXITCODE=' + $LASTEXITCODE)
