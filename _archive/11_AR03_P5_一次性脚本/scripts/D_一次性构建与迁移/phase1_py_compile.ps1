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
