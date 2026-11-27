@echo off
REM Phase 1 收紧版 - 一次性 import 自测包装
REM PS 5.1 中文路径会破坏 argv，故用 .bat 包装
set "PROJECT_ROOT=%~dp0.."
set "PYTHON_EXE=C:\Users\wn\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONPATH=%PROJECT_ROOT%"
"%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\phase1_smoke.py"
