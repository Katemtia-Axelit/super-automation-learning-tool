@echo off
REM Phase 1 收紧版 - 创建临时 venv + 跑 import 自测
REM 注意：任务规格禁止后台启 Flask；此处只跑 import 不启服务
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

if not exist ".venv" (
    echo [INFO] Creating .venv (one-time) ...
    "C:\Users\wn\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv
    if errorlevel 1 goto :err
)

call .venv\Scripts\activate.bat
python -m pip install -q -r requirements-web.txt
if errorlevel 1 (
    python -m pip install -q -r requirements-web.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 goto :err
)

set "PYTHONPATH=%CD%"
python scripts\phase1_smoke.py
exit /b %errorlevel%

:err
echo [ERROR] venv setup or import failed
exit /b 1
