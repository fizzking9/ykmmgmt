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

$ErrorActionPreference = "Stop"
$ComposeFile = "$PSScriptRoot\..\docker-compose.prod.yml"
$FrpcToml = "$PSScriptRoot\..\deploy\frpc.toml"

function Write-Step([string]$Msg) { Write-Host "`n$Msg" -ForegroundColor Cyan }
function Write-Ok([string]$Msg)   { Write-Host "  $Msg" -ForegroundColor Green }

if (-not (Test-Path $EnvFile)) {
    Write-Error "Missing $EnvFile - copy deploy/.env.prod.example and fill it in."
}

# Fail fast if the prod host is unreachable (wrong network / no key auth yet)
Write-Step "[1/5] Checking SSH access to $RemoteHost"
ssh -o BatchMode=yes -o ConnectTimeout=10 $RemoteHost "true"
if ($LASTEXITCODE -ne 0) {
    Write-Error "SSH key auth to $RemoteHost failed - set up key access (see deploy/README.md) or check the network."
}

Write-Step "[2/5] Syncing compose file and deploy configs"
ssh $RemoteHost "mkdir -p $RemoteDir/deploy"
scp $ComposeFile "${RemoteHost}:$RemoteDir/docker-compose.prod.yml"
if ($LASTEXITCODE -ne 0) { Write-Error "scp of docker-compose.prod.yml failed." }
scp $EnvFile $FrpcToml "${RemoteHost}:$RemoteDir/deploy/"
if ($LASTEXITCODE -ne 0) { Write-Error "scp of deploy configs failed." }

Write-Step "[3/5] Pulling latest images on the prod host"
ssh $RemoteHost "cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod pull"

Write-Step "[4/5] Restarting the stack"
ssh $RemoteHost "cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d --remove-orphans && docker image prune -f"

Write-Step "[5/5] Health check"
$healthy = $false
for ($i = 1; $i -le 15; $i++) {
    $code = ssh $RemoteHost 'curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080/api/health'
    if ($LASTEXITCODE -eq 0 -and $code -eq "200") {
        $healthy = $true
        break
    }
    Write-Host "  backend not ready yet (attempt $i/15)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 4
}
if (-not $healthy) {
    Write-Error "Backend did not become healthy - check: ssh $RemoteHost 'cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod ps'"
}
Write-Ok "backend healthy"

Write-Host ""
Write-Ok "Deployed. Stack status:"
ssh $RemoteHost "cd $RemoteDir && docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod ps"
