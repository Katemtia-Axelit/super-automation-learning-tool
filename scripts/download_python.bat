@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo ============================================
echo  Download Embedded Python 3.11
echo ============================================
echo.

if exist ".python\python.exe" (
    echo [OK] .python\python.exe already exists.
    goto :verify
)

set "URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
set "ZIP=.python\python-embed.zip"

echo [INFO] Downloading Python 3.11.9 embed from:
echo        %URL%
echo.

powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' }"
if errorlevel 1 (
    echo [ERROR] Download failed. Please manually download from:
    echo        https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
    echo        Extract to .python\ folder
    pause
    exit /b 1
)

echo [INFO] Extracting...
powershell -Command "& { Expand-Archive -Path '%ZIP%' -DestinationPath '.python' -Force }"
del "%ZIP%" 2>nul

echo [INFO] Patching python311._pth...
echo python311.zip>>.python\python311._pth
echo .>>.python\python311._pth
echo import site>>.python\python311._pth

:verify
echo.
echo [INFO] Testing embedded Python...
.python\python.exe --version
if errorlevel 1 (
    echo [ERROR] Embedded Python not working.
    pause
    exit /b 1
)

echo.
echo [OK] Embedded Python ready: .python\python.exe
echo [INFO] You can now run: scripts\start_web_safe.bat
pause
