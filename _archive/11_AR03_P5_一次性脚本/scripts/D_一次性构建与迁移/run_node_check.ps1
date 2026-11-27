# run_node_check.ps1
# Phase 1 JS syntax check (PS 5.1 + Chinese path safe)
Set-Location -LiteralPath $PSScriptRoot\..
$files = @(
  'static/core/state.js',
  'static/core/constants.js',
  'static/core/ui/modal.js',
  'static/core/ui/toast.js',
  'static/core/ui/theme.js',
  'static/core/ui/sandbox.js',
  'static/shared/timer.js',
  'static/shared/xss.js',
  'static/shared/formatters.js',
  'static/modules/gacha/index.js',
  'static/modules/tasks/index.js',
  'static/app.entry.js'
)
$fail = 0
foreach ($f in $files) {
  & node --check $f 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "OK $f"
  } else {
    Write-Host "FAIL $f"
    & node --check $f 2>&1 | Write-Host
    $fail = 1
  }
}
exit $fail
