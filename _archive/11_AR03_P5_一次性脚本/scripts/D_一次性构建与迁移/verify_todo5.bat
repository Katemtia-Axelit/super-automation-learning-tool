@echo off
REM Phase 2 Todo 5 verify helper
setlocal
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
set "PYTHONPATH=%CD%"
python scripts\verify_p0_cleanup.py
exit /b %errorlevel%
