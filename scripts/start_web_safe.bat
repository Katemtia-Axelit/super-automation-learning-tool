@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Learning Tool - Web (Safe Start)
cd /d "%~dp0\.."

echo ============================================
echo   Learning Tool - Safe Web Start
echo ============================================
echo.

set "PY="
set "PY_LABEL="

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    set "PY_LABEL=.venv"
    goto :have_python
)

:: Priority 1: embedded .python\python.exe
if exist ".python\python.exe" (
    echo [INFO] Creating .venv with embedded .python\python.exe
    .python\python.exe -m venv .venv
    if !errorlevel!==0 (
        .venv\Scripts\python.exe -m pip install -q pip --upgrade 2>nul
        set "PY=.venv\Scripts\python.exe"
        set "PY_LABEL=.venv (via .python/python.exe)"
        goto :have_python
    )
)

:: Priority 2: py launcher
where py >nul 2>&1
if !errorlevel!==0 (
    py -3 --version >nul 2>&1
    if !errorlevel!==0 (
        echo [INFO] Creating .venv with: py -3
        py -3 -m venv .venv
        if errorlevel 1 goto :find_system_python
        set "PY=.venv\Scripts\python.exe"
        set "PY_LABEL=.venv (created via py -3)"
        goto :have_python
    )
)

:find_system_python
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        "%%P" --version >nul 2>&1
        if !errorlevel!==0 (
            echo [INFO] Creating .venv with: %%P
            "%%P" -m venv .venv
            if !errorlevel!==0 (
                set "PY=.venv\Scripts\python.exe"
                set "PY_LABEL=.venv (created via %%P)"
                goto :have_python
            )
        )
    )
)

:no_python
echo.
echo [ERROR] No Python 3.10+ found.
echo.
echo Options:
echo   1. Run scripts\download_python.bat to download embedded Python
echo   2. Or install Python and add to PATH
echo   3. Or manually download python-3.11.9-embed-amd64.zip to .python\
echo      from https://www.python.org/ftp/python/3.11.9/
echo.
pause
exit /b 1

:have_python
echo [INFO] Python: !PY_LABEL!
"!PY!" --version
if errorlevel 1 (
    echo [ERROR] Python 无法运行
    pause
    exit /b 1
)

echo.
echo ============================================
echo   PREFLIGHT CHECK
echo ============================================
echo [PREFLIGHT] Running portability check...
"!PY!" scripts\check_portability.py
set PF_RC=!ERRORLEVEL!
if !PF_RC! EQU 1 (
    echo.
    echo [PREFLIGHT] BLOCKER found - startup BLOCKED.
    echo [PREFLIGHT] Fix the BLOCKER items listed above before retrying.
    pause
    exit /b 1
)
if !PF_RC! EQU 2 (
    echo.
    echo [PREFLIGHT] PASS_WITH_WARNINGS - issues found but startup will proceed.
    echo.
) else if !PF_RC! EQU 0 (
    echo.
    echo [PREFLIGHT] PASS - all checks passed.
    echo.
)

echo [INFO] Installing web dependencies...
"!PY!" -m pip install -q -r requirements-web.txt
if errorlevel 1 (
    echo [WARN] pip 默认源失败，尝试清华镜像...
    "!PY!" -m pip install -q -r requirements-web.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [ERROR] 依赖安装失败，请检查网络或 pip 配置
        pause
        exit /b 1
    )
)

if exist ".run\server.pid" (
    echo [INFO] Stopping previous server instance...
    call "%~dp0stop_web_safe.bat"
)

echo [INFO] Loading port from config...
for /f "delims=" %%i in ('"!PY!" -c "import json; c=json.load(open('config/config.json',encoding='utf-8')); print(c['server']['port'])"') do set PORT=%%i
if not defined PORT set PORT=5000

echo [INFO] Starting server on port !PORT!...
for /f "tokens=1,* delims==" %%a in ('"!PY!" scripts\launch_server.py') do (
    if "%%a"=="SERVER_PID" set SERVER_PID=%%b
)

if not defined SERVER_PID (
    echo [ERROR] 服务器启动失败，请查看 .run\server.log
    pause
    exit /b 1
)

echo [INFO] Server PID: !SERVER_PID!
echo [INFO] Waiting for health check...
set /a RETRY=0
:wait_health
timeout /t 1 /nobreak >nul
"!PY!" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:!PORT!/api/health', timeout=2)" >nul 2>&1
if !errorlevel!==0 goto :health_ok
set /a RETRY+=1
if !RETRY! lss 15 goto :wait_health
echo [ERROR] 健康检查失败: http://127.0.0.1:!PORT!/api/health
echo 请查看 .run\server.log
pause
exit /b 1

:health_ok
echo [INFO] Health check OK
echo [INFO] Opening browser...
start http://127.0.0.1:!PORT!/

echo.
echo ============================================
echo  Running: http://127.0.0.1:!PORT!/
echo  PID: !SERVER_PID!  (only this process)
echo  Log: .run\server.log
echo  Stop: scripts\stop_web_safe.bat
echo ============================================
echo.
echo Press any key to STOP server and exit...
pause >nul

call "%~dp0stop_web_safe.bat"
exit /b 0
