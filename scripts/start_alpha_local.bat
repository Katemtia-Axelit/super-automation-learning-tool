@echo off
setlocal
chcp 65001 >nul
title Learning Tool - Local Alpha
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [Alpha ERROR] Python virtual environment not found:
  echo %PY%
  echo Dependencies are NOT auto-installed. Existing project must be prepared first.
  pause
  exit /b 2
)
cd /d "%ROOT%"
"%PY%" -B "%~dp0launch_alpha_local.py" %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo [Alpha] Launcher returned exit code %RESULT%.
  if "%~1"=="" pause
)
exit /b %RESULT%
