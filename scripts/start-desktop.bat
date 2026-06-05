@echo off
chcp 65001 >nul
echo ======================================
echo Task Randomizer - Starting...
echo ======================================
echo.

cd /d "%~dp0\.."

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found, please install Python 3.8+ first
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
pip install PySide6 -q >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Failed to install, trying mirror...
    pip install PySide6 -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)

python main.py
if errorlevel 1 (
    echo.
    echo [Error] Failed to start! Please check if dependencies are installed.
    echo.
    pause
)
