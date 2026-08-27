param(
    [Parameter(Mandatory = $true)]
    [string]$Message,
    [string[]]$Paths = @('src', 'tests', 'docs', 'tools', 'demo_project', 'README.md', 'README.txt', '.gitignore', 'pyproject.toml'),
    [switch]$Push
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

foreach ($path in $Paths) {
    if (Test-Path -LiteralPath $path) {
        git add -- $path
    }
}

$hasStagedChanges = $false
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    $hasStagedChanges = $true
}

if ($hasStagedChanges) {
    git commit -m $Message
    Write-Output 'Created checkpoint commit.'
} else {
    Write-Output 'No selected changes to commit; keeping the current HEAD.'
}

if ($Push) {
    $remotes = @(git remote)
    $origin = if ($remotes -contains 'origin') { git remote get-url origin } else { $null }
    if (-not $origin) {
        throw 'No origin remote configured; commit was created locally but was not pushed.'
    }
    $branch = git branch --show-current
    git push -u origin $branch
} else {
    Write-Output 'Not pushed. Re-run with -Push after reviewing the commit and configuring origin.'
}
