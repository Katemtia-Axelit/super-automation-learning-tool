@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0\.."

set "TS=manual"
if exist ".venv\Scripts\python.exe" (
  for /f "delims=" %%i in ('".venv\Scripts\python.exe" -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d-%%H%%M'))"') do set TS=%%i
) else (
  for /f "delims=" %%i in ('py -3 -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d-%%H%%M'))"') do set TS=%%i
)

set "DEST=backups\%TS%"
mkdir "%DEST%" 2>nul
mkdir "%DEST%\data" 2>nul
mkdir "%DEST%\config" 2>nul
mkdir "%DEST%\src\notes\vault" 2>nul
mkdir "%DEST%\src\notes\prompts" 2>nul

echo ============================================
echo   User Data Backup
echo   Target: %DEST%
echo ============================================

if exist "data\task_publisher.db" (
  copy /Y "data\task_publisher.db" "%DEST%\data\" >nul
  echo [OK] data\task_publisher.db
) else (
  echo [WARN] data\task_publisher.db not found
)

if exist "config\config.json" (
  copy /Y "config\config.json" "%DEST%\config\" >nul
  echo [OK] config\config.json
) else (
  echo [WARN] config\config.json not found
)

if exist "src\notes\vault" (
  xcopy /E /I /Y "src\notes\vault" "%DEST%\src\notes\vault\" >nul
  echo [OK] src\notes\vault
) else (
  echo [WARN] src\notes\vault not found
)

if exist "src\notes\prompts" (
  xcopy /E /I /Y "src\notes\prompts" "%DEST%\src\notes\prompts\" >nul
  echo [OK] src\notes\prompts
) else (
  echo [WARN] src\notes\prompts not found
)

echo.
echo Backup completed: %CD%\%DEST%
echo.
pause
exit /b 0
