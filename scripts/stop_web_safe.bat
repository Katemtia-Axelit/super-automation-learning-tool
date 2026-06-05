@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0\.."

if exist ".run\server.pid" (
    set /p STOPPID=<.run\server.pid
    echo [INFO] Stopping server PID !STOPPID!...
    taskkill /PID !STOPPID! /T /F >nul 2>&1
    del .run\server.pid >nul 2>&1
    echo [INFO] Server stopped.
)

set "PY=.venv\Scripts\python.exe"
if exist "%PY%" (
    "%PY%" scripts\stop_server.py
    exit /b 0
)

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 scripts\stop_server.py 2>nul
)

echo [INFO] No running server PID file found.
exit /b 0
