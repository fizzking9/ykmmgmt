# Pull the latest images from GHCR and restart the production stack.
#
# Usage:  .\scripts\deploy.ps1
# Requires: one-time `docker login ghcr.io` with a PAT (read:packages),
#           Docker Desktop running, and deploy/.env.prod configured.
#
# `docker compose pull` covers every service image, including the MCP
# server (MCP_IMAGE) added in Phase 14.

param(
    [string]$EnvFile = "$PSScriptRoot\..\deploy\.env.prod",
    [string]$ComposeFile = "$PSScriptRoot\..\docker-compose.prod.yml"
)

$ErrorActionPreference = "Stop"

# Fail fast if the Docker daemon is unreachable (Docker Desktop not started)
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not reachable — start Docker Desktop first."
}

if (-not (Test-Path $EnvFile)) {
    Write-Error "Missing $EnvFile — copy deploy/.env.prod.example and fill it in."
}

Write-Host "Pulling latest images..." -ForegroundColor Cyan
docker compose -f $ComposeFile --env-file $EnvFile pull

Write-Host "Restarting stack..." -ForegroundColor Cyan
docker compose -f $ComposeFile --env-file $EnvFile up -d

Write-Host "Pruning dangling images..." -ForegroundColor Cyan
docker image prune -f

Write-Host "Deployed. Stack status:" -ForegroundColor Green
docker compose -f $ComposeFile --env-file $EnvFile ps
