# AR02 safe synthetic baseline. Never starts the real project server on :5000.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$py = Join-Path $root '.venv\Scripts\python.exe'
$pw = Join-Path $root 'node_modules\.bin\playwright.cmd'
if (!(Test-Path -LiteralPath $py) -or !(Test-Path -LiteralPath $pw)) {
    throw 'AR02 requires the project .venv and local Playwright installation.'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$tests = @(
    'test_m02_behavior_frontend_core',
    'test_gacha_frontend_a11y',
    'test_gacha_frontend_multidraw_contract',
    'test_gacha_replace_no_repeat',
    'test_free_card_care_draw_contract',
    'test_card_type_frontend',
    'test_m02_behavior_event_ingest',
    'test_ar02_factory_instance_isolation',
    'test_route_inventory',
    'test_agent_policy_publisher',
    'test_discard_cycle_recovery',
    'test_agent_policy_status'
)
Push-Location (Join-Path $root 'tests\characterize')
try {
    & $py -B -m unittest @tests -q
    if ($LASTEXITCODE -ne 0) { throw 'AR02 Python synthetic unittest failed.' }
    & $py -B -m pytest test_free_task_events.py -q
    if ($LASTEXITCODE -ne 0) { throw 'AR02 isolated event-ledger pytest failed.' }
} finally {
    Pop-Location
}
Push-Location $root
try {
    foreach ($name in @('factory', 'bootstrap')) {
        $config = if ($name -eq 'factory') {
            'tests\e2e\playwright.factory-safe.config.js'
        } else {
            'tests\e2e\playwright.bootstrap-safe.config.js'
        }
        & $pw test --config $config --workers=1 --output (Join-Path $env:TEMP ('ar02_safe_' + $name))
        if ($LASTEXITCODE -ne 0) { throw ('AR02 isolated browser failed: ' + $name) }
    }
} finally {
    Pop-Location
}
Write-Output 'AR02_SAFE_BASELINE_PASSED (Python includes one documented expectedFailure)'
