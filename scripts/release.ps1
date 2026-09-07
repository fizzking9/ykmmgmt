# Release a new version end-to-end in one command — starting from push.
#
# Covers the CI/CD workflow after the work is already committed on main:
#   1. Preflight checks (Docker reachable, prod env file present)
#   2. Push main  ->  triggers GitHub Actions: CI, then Deploy (build & push images)
#   3. Wait for both workflows to succeed (GitHub API, no auth needed)
#   4. Pull the fresh images and restart the local production stack (deploy.ps1)
#   5. Health check (frontend :8080 + backend /api/health)
#
# Usage:
#   .\scripts\release.ps1              # push main, watch CI, deploy, verify
#   .\scripts\release.ps1 -Yes         # answer yes to every confirmation
#   .\scripts\release.ps1 -NoPush      # skip the push (workflows already running)
#
# Notes:
#   - Commit your work (and update CHANGELOG.md / specs) BEFORE running —
#     this script only pushes what is already committed on main.
#   - Requires: git, Docker Desktop running, deploy/.env.prod configured, and
#     the repo's GitHub visibility public (unauthenticated API calls are used
#     to watch workflow runs).

param(
    [switch]$Yes,
    [switch]$NoPush,
    [int]$TimeoutMinutes = 25
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$ProdCompose = Join-Path $Root "docker-compose.prod.yml"
$ProdEnv = Join-Path $Root "deploy\.env.prod"

# git writes progress ("From https://...", "To https://...") to stderr; with
# $ErrorActionPreference = "Stop" PowerShell 5.1 turns that into a terminating
# error. Redirecting git's stderr into stdout avoids the whole class of bugs.
$env:GIT_REDIRECT_STDERR = "2>&1"

function Write-Step([string]$Msg) { Write-Host "`n$Msg" -ForegroundColor Cyan }
function Write-Ok([string]$Msg)   { Write-Host "  $Msg" -ForegroundColor Green }
function Write-Info([string]$Msg) { Write-Host "  $Msg" -ForegroundColor Yellow }

function Confirm-Action([string]$Question) {
    if ($Yes) { return $true }
    $answer = Read-Host "$Question [y/N]"
    return ($answer -match '^[Yy]')
}

# ── Preflight ────────────────────────────────────────────────────────────────
Write-Step "[1/5] Preflight"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not reachable - start Docker Desktop first."
}
if (-not (Test-Path $ProdEnv)) {
    Write-Error "Missing $ProdEnv - copy deploy/.env.prod.example and fill it in."
}

$branch = (git branch --show-current).Trim()
if ($branch -ne "main") {
    Write-Error "You are on '$branch', not main - commit and merge your work first, then re-run this script."
}

$dirty = (git status --porcelain) -join "`n"
if ($dirty) {
    Write-Host $dirty -ForegroundColor DarkGray
    Write-Info "Warning: working tree has uncommitted changes - they will NOT be released."
}

# Repo slug ("owner/name") from the origin URL — https or ssh both work.
$remote = git remote get-url origin
if ($remote -match "github\.com[:/](.+?)(\.git)?$") { $RepoSlug = $Matches[1] }
else { Write-Error "Cannot parse a GitHub repo from origin URL: $remote" }

# ── Push ────────────────────────────────────────────────────────────────────
Write-Step "[2/5] Push main to origin"

git fetch origin main *> $null
$ahead = git rev-list --count origin/main..main
$Sha = (git rev-parse HEAD).Trim()
$ShortSha = $Sha.Substring(0, 7)

if ($NoPush) {
    Write-Info "skipped (-NoPush) - assuming workflows for $ShortSha are already running"
}
elseif ($ahead -eq 0) {
    Write-Info "main is already up to date on origin - skipping push"
}
else {
    if (-not (Confirm-Action "Push main ($ShortSha, $ahead commit(s) ahead) to origin? This triggers CI + image build.")) {
        Write-Error "Aborted by user."
    }
    git push origin main
    if ($LASTEXITCODE -ne 0) { Write-Error "git push failed." }
    Write-Ok "pushed $ShortSha to origin/main"
}

# ── Wait for CI and the image-build workflow ────────────────────────────────
Write-Step "[3/5] Wait for GitHub Actions (timeout: $TimeoutMinutes min)"

function Wait-WorkflowRun {
    param([string]$WorkflowFile, [string]$Label)
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    # Optional auth: set GITHUB_TOKEN (env var) to raise the API limit from
    # 60 requests/hour (unauthenticated, shared per IP) to 5,000/hour.
    $headers = @{ "User-Agent" = "ykmmgmt-release-script" }
    if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $($env:GITHUB_TOKEN)" }
    while ((Get-Date) -lt $deadline) {
        try {
            $runs = Invoke-RestMethod `
                -Uri "https://api.github.com/repos/$RepoSlug/actions/runs?branch=main&per_page=20" `
                -Headers $headers `
                -TimeoutSec 30
        }
        catch {
            Write-Info "GitHub API unreachable ($($_.Exception.Message)) - retrying in 60s"
            Start-Sleep -Seconds 60
            continue
        }
        $run = $runs.workflow_runs |
            Where-Object { $_.head_sha -eq $Sha -and $_.path -eq ".github/workflows/$WorkflowFile" } |
            Select-Object -First 1
        if ($run) {
            if ($run.status -eq "completed") {
                if ($run.conclusion -eq "success") {
                    Write-Ok "$Label succeeded ($($run.html_url))"
                    return
                }
                Write-Error "$Label failed ($($run.conclusion)): $($run.html_url)"
            }
            Write-Info "$Label is $($run.status)..."
        }
        else {
            Write-Info "waiting for $Label to start..."
        }
        # 30s cadence: an unauthenticated IP shares a 60 requests/hour budget,
        # so polling must stay well under ~2 requests/minute to survive a
        # full timeout window.
        Start-Sleep -Seconds 30
    }
    Write-Error "$Label did not finish within $TimeoutMinutes minutes - check https://github.com/$RepoSlug/actions"
}

Wait-WorkflowRun -WorkflowFile "ci.yml" -Label "CI (tests)"
Wait-WorkflowRun -WorkflowFile "deploy.yml" -Label "Deploy (build & push images)"

# ── Pull and restart the local production stack ─────────────────────────────
Write-Step "[4/5] Deploy (pull images + restart stack)"

& (Join-Path $PSScriptRoot "deploy.ps1")
if ($LASTEXITCODE -ne 0) { Write-Error "deploy.ps1 failed - check the output above." }

# ── Health check ────────────────────────────────────────────────────────────
Write-Step "[5/5] Health check"

function Wait-Healthy {
    param([string]$Url, [string]$Label, [int]$Attempts = 15)
    for ($i = 1; $i -le $Attempts; $i++) {
        # curl.exe (built into Windows) instead of Invoke-WebRequest: the
        # latter honors the system proxy, which can time out on localhost.
        $code = & curl.exe -s -o NUL -w "%{http_code}" --max-time 5 $Url
        if ($LASTEXITCODE -eq 0 -and $code -eq "200") {
            Write-Ok "$Label healthy ($Url)"
            return
        }
        Write-Info "$Label not ready yet (attempt $i/$Attempts)..."
        Start-Sleep -Seconds 4
    }
    Write-Error "$Label did not become healthy - run: docker compose -f `"$ProdCompose`" --env-file `"$ProdEnv`" ps"
}

Wait-Healthy -Url "http://localhost:8080/api/health" -Label "Backend"
Wait-Healthy -Url "http://localhost:8080/" -Label "Frontend"

# ── Done ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Release $ShortSha is live." -ForegroundColor Cyan
Write-Host "  Local   http://localhost:8080"
Write-Host "  Actions https://github.com/$RepoSlug/actions"
