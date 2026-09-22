# Deploy the production stack to the prod host over SSH.
#
# The stack runs on the LAN prod machine (Ubuntu, srx@192.168.10.25); this
# script syncs the compose file + deploy configs there, pulls the latest GHCR
# images, restarts the stack, and health-checks it. No local Docker needed.
#
# Usage:
#   .\scripts\deploy.ps1
#   .\scripts\deploy.ps1 -RemoteHost srx@192.168.10.25 -RemoteDir "~/ykmmgmt"
#
# One-time setup on the prod host (see deploy/README.md):
#   - Docker Engine + compose plugin installed
#   - SSH key auth from this machine:
#       type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh srx@192.168.10.25 "cat >> ~/.ssh/authorized_keys"
#
# GHCR images are public, so no registry login is needed on the prod host.

param(
    [string]$RemoteHost = "srx@192.168.10.25",
    [string]$RemoteDir = "~/ykmmgmt",
    [string]$EnvFile = "$PSScriptRoot\..\deploy\.env.prod"
)

# ssh, scp and `docker compose` write their progress to stderr. With "Stop",
# PowerShell 5.1 promotes every such line into a terminating error, which killed a
# perfectly successful image pull on the first release that went through this path
# (compose prints "Image … Pulling" on stderr even when nothing is wrong). Native
# exit codes are checked explicitly below instead, so progress output is harmless.
$ErrorActionPreference = "Continue"
$ComposeFile = "$PSScriptRoot\..\docker-compose.prod.yml"
$FrpcToml = "$PSScriptRoot\..\deploy\frpc.toml"

function Write-Step([string]$Msg) { Write-Host "`n$Msg" -ForegroundColor Cyan }
function Write-Ok([string]$Msg)   { Write-Host "  $Msg" -ForegroundColor Green }

# A failure here must actually stop the script. With $ErrorActionPreference
# lowered to "Continue" (see above), a plain Write-Error only prints a red line
# and execution falls through - which let `up -d` restart the stack after a
# failed pull, putting containers on stale images while the release reported
# success. `exit 1` stops this script and hands release.ps1 a non-zero
# $LASTEXITCODE, which it already checks.
function Fail([string]$Msg) {
    Write-Host "  $Msg" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $EnvFile)) {
    Fail "Missing $EnvFile - copy deploy/.env.prod.example and fill it in."
}

# Fail fast if the prod host is unreachable (wrong network / no key auth yet)
Write-Step "[1/5] Checking SSH access to $RemoteHost"
ssh -o BatchMode=yes -o ConnectTimeout=10 $RemoteHost "true"
if ($LASTEXITCODE -ne 0) {
    Fail "SSH key auth to $RemoteHost failed - set up key access (see deploy/README.md) or check the network."
}

Write-Step "[2/5] Syncing compose file and deploy configs"
ssh $RemoteHost "mkdir -p $RemoteDir/deploy"
scp $ComposeFile "${RemoteHost}:$RemoteDir/docker-compose.prod.yml"
if ($LASTEXITCODE -ne 0) { Fail "scp of docker-compose.prod.yml failed." }
scp $EnvFile $FrpcToml "${RemoteHost}:$RemoteDir/deploy/"
if ($LASTEXITCODE -ne 0) { Fail "scp of deploy configs failed." }

Write-Step "[3/5] Pulling latest images on the prod host"
ssh $RemoteHost "cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod pull"
if ($LASTEXITCODE -ne 0) {
    Fail "Image pull failed or was interrupted (exit $LASTEXITCODE) - NOT restarting the stack, prod keeps running the previous images. Check the build at https://github.com/fizzking9/ykmmgmt/actions"
}

Write-Step "[4/5] Restarting the stack"
ssh $RemoteHost "cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d --remove-orphans && docker image prune -f"
if ($LASTEXITCODE -ne 0) { Fail "Stack restart failed (exit $LASTEXITCODE) - check: ssh $RemoteHost 'cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod ps'" }

Write-Step "[5/5] Health check"
$healthy = $false
for ($i = 1; $i -le 15; $i++) {
    # ssh may prepend warnings to the body of the reply; the status code is the last line.
    $code = ((ssh $RemoteHost 'curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080/api/health') | Select-Object -Last 1)
    if ($LASTEXITCODE -eq 0 -and "$code" -eq "200") {
        $healthy = $true
        break
    }
    Write-Host "  backend not ready yet (attempt $i/15)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 4
}
if (-not $healthy) {
    Fail "Backend did not become healthy - check: ssh $RemoteHost 'cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod ps'"
}
Write-Ok "backend healthy"

# The health endpoint alone cannot tell a fresh deploy from a stale one: the old
# backend answers /api/health just as happily. Print which image is actually
# running so "deployed" can be read off the same line.
Write-Host ""
Write-Ok "Deployed. Stack status:"
ssh $RemoteHost "cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod ps"
