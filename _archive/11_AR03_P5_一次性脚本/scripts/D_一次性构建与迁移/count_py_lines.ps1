$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$dirs = @('server/app', 'server/blueprints', 'server/schema', 'server/services')
$pyFiles = @()
foreach ($d in $dirs) {
  if (Test-Path $d) {
    $pyFiles += Get-ChildItem -Path $d -Recurse -File -Filter '*.py'
  }
}
foreach ($f in $pyFiles) {
  $lines = ([System.IO.File]::ReadAllLines($f.FullName)).Count
  $rel = $f.FullName.Substring($root.Length + 1)
  Write-Host ("{0,-50} {1,5}" -f $rel, $lines)
}
