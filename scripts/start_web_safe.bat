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

where py >nul 2>&1
if !errorlevel!==0 (
    py -3 --version >nul 2>&1
    if !errorlevel!==0 (
        echo [INFO] Creating .venv with: py -3
        py -3 -m venv .venv
        if errorlevel 1 goto :no_python
        set "PY=.venv\Scripts\python.exe"
        set "PY_LABEL=.venv (created via py -3)"
        goto :have_python
    )
)

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
echo [ERROR] 未找到可用的 Python 3.10+
echo.
echo 请安装 Python 3.10 或更高版本，并勾选 "Add python.exe to PATH"
echo 下载: https://www.python.org/downloads/
echo.
echo 若已安装但仍报错，可能是 Microsoft Store 占位 python。
echo 请关闭 "应用执行别名" 中的 python.exe 别名，或使用 py -3。
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
