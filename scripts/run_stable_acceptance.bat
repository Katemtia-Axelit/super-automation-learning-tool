@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0\.."

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] .venv not found. Run: py -3 -m venv .venv
  exit /b 1
)

set FAILED=0
call :run scripts\inspect_db_schema.py || set FAILED=1
call :run scripts\check_portability.py || set FAILED=1
call :run scripts\p0_test_deps.py || set FAILED=1
call :run scripts\p0_acceptance_http.py || set FAILED=1
call :run scripts\p1_acceptance_existing_backend.py || set FAILED=1
call :run scripts\p1_2_acceptance_prompt_sleep.py || set FAILED=1
call :run scripts\p1_2_e2e_prompt_sleep.py || set FAILED=1
call :run scripts\p1_3_acceptance_prompt_activity.py || set FAILED=1
call :run scripts\p1_3_e2e_prompt_activity.py || set FAILED=1
call :run scripts\p1_4_acceptance_discard_pile.py || set FAILED=1
call :run scripts\p1_4_e2e_discard_pile.py || set FAILED=1
call :run scripts\p1_5_acceptance_state_timer.py || set FAILED=1
call :run scripts\p1_5_e2e_state_timer.py || set FAILED=1
call :run scripts\p1_5b_acceptance_task_feedback.py || set FAILED=1
call :run scripts\p1_5b_e2e_task_feedback.py || set FAILED=1
call :run scripts\p1_6_acceptance_agent_readonly.py || set FAILED=1
call :run scripts\p1_6_e2e_agent_readonly.py || set FAILED=1
call :run scripts\p1_visual_1_acceptance_card_ui.py || set FAILED=1
call :run scripts\p1_visual_1_e2e_card_ui.py || set FAILED=1

if %FAILED%==1 (
  echo.
  echo [FAIL] Stable acceptance had failures
  exit /b 1
)
echo.
echo ALL STABLE ACCEPTANCE PASSED
exit /b 0

:run
echo.
echo ========== %~1 ==========
"%PY%" %~1
if errorlevel 1 exit /b 1
exit /b 0
