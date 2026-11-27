@echo off
REM Phase 2 verification — start run_app.py and keep server alive for E2E
setlocal
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
set "PYTHONPATH=%CD%"
set "FLASK_DEBUG=0"
start "LearningTool" cmd /k "python run_app.py"
timeout /t 3 /nobreak >nul
exit /b 0
