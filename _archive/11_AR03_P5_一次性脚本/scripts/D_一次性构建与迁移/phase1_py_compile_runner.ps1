# Avoid PS 5.1 + Chinese path issue: use short path via cmd
$tmpDir = Join-Path $env:TEMP "phase1_check"
if (-not (Test-Path $tmpDir)) { New-Item -ItemType Directory -Path $tmpDir | Out-Null }
$ps1 = Join-Path $tmpDir "py_compile.ps1"
$content = @'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$dirs = @('server', 'scripts')
$pyFiles = foreach ($d in $dirs) {
  if (Test-Path $d) { Get-ChildItem -Path $d -Recurse -File -Filter '*.py' -Exclude '__pycache__' }
}
$fail = 0
foreach ($f in $pyFiles) {
  $rel = $f.FullName.Substring($root.Length + 1)
  & python -m py_compile $f.FullName 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "OK $rel"
  } else {
    Write-Host "FAIL $rel"
    & python -m py_compile $f.FullName 2>&1 | Write-Host
    $fail = 1
  }
}
exit $fail
'@
Set-Content -Path $ps1 -Value $content -Encoding ASCII -Force
# Copy to root
$rootShort = (Get-Item (Split-Path -Parent $PSScriptRoot)).FullName
$shortPs1 = Join-Path $rootShort "scripts\_tmp_py_compile.ps1"
Copy-Item $ps1 $shortPs1 -Force
& $shortPs1
$rc = $LASTEXITCODE
Remove-Item $shortPs1 -Force
exit $rc
