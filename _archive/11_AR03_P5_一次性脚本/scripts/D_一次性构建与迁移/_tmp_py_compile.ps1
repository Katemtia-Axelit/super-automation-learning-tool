Set-Location -LiteralPath 'd:\Axelit\.工作\trae\超级自动化学习工具'
$dirs = @('server', 'scripts')
$pyFiles = foreach ($d in $dirs) {
  if (Test-Path $d) { Get-ChildItem -Path $d -Recurse -File -Filter '*.py' -Exclude '__pycache__' }
}
$fail = 0
$root = 'd:\Axelit\.工作\trae\超级自动化学习工具'
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
