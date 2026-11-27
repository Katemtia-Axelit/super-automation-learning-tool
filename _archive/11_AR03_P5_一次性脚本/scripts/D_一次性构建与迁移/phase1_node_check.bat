@echo off
setlocal
cd /d "%~dp0\.."
set FILES=static\core\state.js static\core\constants.js static\core\ui\modal.js static\core\ui\toast.js static\core\ui\theme.js static\core\ui\sandbox.js static\shared\timer.js static\shared\xss.js static\shared\formatters.js static\modules\gacha\index.js static\modules\tasks\index.js static\app.entry.js
set FAIL=0
for %%F in (%FILES%) do (
    node --check "%%F" >nul 2>&1
    if !errorlevel!==0 (
        echo OK %%F
    ) else (
        echo FAIL %%F
        set FAIL=1
    )
)
exit /b %FAIL%
