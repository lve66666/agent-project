param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
Set-Location $ProjectRoot
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
python -m unittest discover -s tests -v
git diff --check
if (Test-Path 'README.txt') {
    $count = (Get-Content README.txt -Encoding UTF8 -Raw).Length
    if ($count -gt 1000) { throw "README.txt exceeds 1000 characters: $count" }
    Write-Output "README.txt characters: $count"
}
Write-Output 'Verification passed.'
