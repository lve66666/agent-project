param(
    [Parameter(Mandatory = $true)]
    [string]$Message,
    [string[]]$Paths = @('src', 'tests', 'docs', 'tools', 'README.md', 'README.txt', '.gitignore'),
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

if (-not (git diff --cached --quiet)) {
    git commit -m $Message
    Write-Output 'Created checkpoint commit.'
} else {
    Write-Output 'No selected changes to commit.'
    exit 0
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
