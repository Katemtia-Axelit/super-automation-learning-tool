@echo off

setlocal EnableDelayedExpansion

chcp 65001 >nul

title Verify Transferred Project

cd /d "%~dp0\.."



echo ============================================

echo   Transfer / Migration Verification

echo ============================================

echo Project root: %CD%

echo.



set "PY="

where py >nul 2>&1

if %errorlevel%==0 (

  py -3 --version >nul 2>&1

  if !errorlevel!==0 set "PY=py -3"

)

if not defined PY (

  where python >nul 2>&1

  if !errorlevel!==0 set "PY=python"

)



if not defined PY (

  echo [FAIL] Python not found. Install Python 3.10+ and add to PATH.

  goto :end_fail

)

echo [OK] Python available: %PY%

%PY% --version



if exist ".venv\Scripts\python.exe" (

  set "VPY=.venv\Scripts\python.exe"

  echo [OK] .venv exists

) else (

  echo [WARN] .venv not found

  echo        Run: py -3 -m venv .venv

  echo        Then: .venv\Scripts\python.exe -m pip install -r requirements-web.txt

  goto :end_fail

)



if not exist "data\task_publisher.db" (

  echo [FAIL] data\task_publisher.db missing

  echo        Restore from backups\YYYYMMDD-HHMM\ or copy from old machine.

  goto :end_fail

)

echo [OK] database file exists



if not exist "static\app.js" (

  echo [FAIL] static\app.js missing

  goto :end_fail

)

echo [OK] static\app.js exists



echo.

echo Running portability check...

"%VPY%" scripts\check_portability.py

if errorlevel 1 goto :end_fail



echo.

echo Starting server for health check...

call "%~dp0stop_web_safe.bat" >nul 2>&1

for /f "tokens=1,* delims==" %%a in ('"%VPY%" scripts\launch_server.py') do (

  if "%%a"=="SERVER_PID" set SERVER_PID=%%b

)

if not defined SERVER_PID (

  echo [FAIL] server failed to start. See .run\server.log

  goto :end_fail

)



set PORT=5000

for /f "delims=" %%i in ('"%VPY%" -c "import json; c=json.load(open('config/config.json',encoding='utf-8')); print(c.get('server',{}).get('port',5000))"') do set PORT=%%i



set /a RETRY=0

:wait_health

timeout /t 1 /nobreak >nul

"%VPY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:%PORT%/api/health', timeout=2)" >nul 2>&1

if !errorlevel!==0 goto :health_ok

set /a RETRY+=1

if !RETRY! lss 15 goto :wait_health

echo [FAIL] health check timeout http://127.0.0.1:%PORT%/api/health

call "%~dp0stop_web_safe.bat" >nul 2>&1

goto :end_fail



:health_ok

echo [OK] /api/health responded

echo.

echo ============================================

echo  Migration verification PASSED

echo  Open: http://127.0.0.1:%PORT%/

echo  Stop: scripts\stop_web_safe.bat

echo ============================================

start http://127.0.0.1:%PORT%/

echo.

echo Server is running (PID %SERVER_PID%). Press any key to stop...

pause >nul

call "%~dp0stop_web_safe.bat"

exit /b 0



:end_fail

echo.

echo Migration verification FAILED. See docs/一周稳定使用与换电脑迁移说明.md

pause

exit /b 1

