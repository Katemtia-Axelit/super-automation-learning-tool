const fs = require('fs');
const path = require('path');
const content = `Set-Location -LiteralPath 'd:\\\\Axelit\\\\.\\\\u5DE5\\\\u4F5C\\\\trae\\\\u8D85\\\\u7EA7\\\\u81EA\\\\u52A8\\\\u5316\\\\u5B66\\\\u4E60\\\\u5DE5\\\\u5177'
$dirs = @('server', 'scripts')
$pyFiles = foreach ($d in $dirs) {
  if (Test-Path $d) { Get-ChildItem -Path $d -Recurse -File -Filter '*.py' -Exclude '__pycache__' }
}
$fail = 0
$root = 'd:\\\\Axelit\\\\.\\\\u5DE5\\\\u4F5C\\\\trae\\\\u8D85\\\\u7EA7\\\\u81EA\\\\u52A8\\\\u5316\\\\u5B66\\\\u4E60\\\\u5DE5\\\\u5177'
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
`;
const dest = path.join(process.env.TEMP, 'phase1_py_compile.ps1');
fs.writeFileSync(dest, content, { encoding: 'utf8' });
console.log('Wrote', dest, 'length', content.length);
