@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title 执行归档清理

set "PYTHON=.venv\Scripts\python.exe"
if not exist "!PYTHON!" set "PYTHON=python"

echo ============================================
echo   归档清理脚本
echo ============================================
echo.

cd /d "%~dp0"

echo [INFO] 执行归档清理...
"!PYTHON!" "执行归档清理.py"

echo.
echo 按任意键退出...
pause >nul
