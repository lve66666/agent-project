param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-Location $ProjectRoot

Write-Output '== Pine Agent status =='
if (Test-Path 'docs/PROGRESS.md') {
    Get-Content 'docs/PROGRESS.md' -Encoding UTF8 | Select-String '^\| P[0-9]' | ForEach-Object { $_.Line }
}

$branch = git branch --show-current 2>$null
$changes = git status --short
$remotes = @(git remote)
$remote = if ($remotes -contains 'origin') { git remote get-url origin } else { $null }
$head = git log -1 --oneline 2>$null

Write-Output "Branch: $(if ($branch) { $branch } else { '(no commit yet)' })"
Write-Output "HEAD: $(if ($head) { $head } else { '(no commit yet)' })"
Write-Output "Worktree: $(if ($changes) { 'changed' } else { 'clean' })"
Write-Output "Origin: $(if ($remote) { $remote } else { '(not configured)' })"

if ($remote -and $branch) {
    git fetch origin --quiet
    $aheadBehind = git rev-list --left-right --count "origin/$branch...HEAD" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "Remote divergence (behind ahead): $aheadBehind"
    } else {
        Write-Output 'Remote branch: not established yet'
    }
}
