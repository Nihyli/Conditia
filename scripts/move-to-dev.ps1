# Move all current work onto the dev branch.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== git status ==="
git status

Write-Host "`n=== branches ==="
git branch -a

$branch = "dev"
$exists = git show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) {
    git checkout $branch
} else {
    git checkout -b $branch
}

git add -A
if (Test-Path "backend\.env") {
    git reset HEAD -- backend/.env 2>$null
}

$status = git status --porcelain
if (-not $status) {
    Write-Host "`nNothing to commit — working tree clean on $branch"
} else {
    git commit -m @"
dev: auth roles, sidebar, seed tools, truck fix

Auth/login with roles, sidebar views, seed/unseed, truck silhouette fix, Supabase/local auth config.
"@
}

Write-Host "`n=== result ==="
Write-Host "Branch: $(git rev-parse --abbrev-ref HEAD)"
Write-Host "Commit: $(git rev-parse HEAD)"
git log -1 --oneline
git status --short
