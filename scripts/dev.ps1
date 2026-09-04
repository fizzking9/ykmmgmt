# Start the full dev environment in one go: db (Docker) + backend + frontend
# + MCP server (all three Python/Node parts run natively in the background).
#
# Usage:
#   .\scripts\dev.ps1                 # start everything
#   .\scripts\dev.ps1 -NoMcp         # skip the MCP server
#   .\scripts\dev.ps1 -NoFrontend    # skip the frontend dev server
#   .\scripts\dev.ps1 -Stop          # stop backend/frontend/mcp (db keeps running)
#
# Logs land in logs\dev\<name>.out.log / .err.log; PIDs in logs\dev\<name>.pid.
# The MCP server's credentials come from the repo-root .env (YKM_* keys �?
# see .env.example); the backend picks .env up itself via pydantic settings.

param(
    # Conda Python used for the backend and the MCP server
    [string]$Python = "C:\Users\chixiao\anaconda3\envs\ykmmgmt\python.exe",
    [switch]$NoMcp,
    [switch]$NoFrontend,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$LogDir = Join-Path $Root "logs\dev"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-PortListening([int]$Port) {
    return ($null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue))
}

function Start-DevProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [hashtable]$EnvVars = @{}
    )
    $outLog = Join-Path $LogDir "$Name.out.log"
    $errLog = Join-Path $LogDir "$Name.err.log"
    # Child processes inherit the current shell's env �?set what the component
    # needs, then restore whatever was there before.
    $saved = @{}
    foreach ($key in $EnvVars.Keys) {
        $existing = Get-Item "Env:$key" -ErrorAction SilentlyContinue
        if ($existing) { $saved[$key] = $existing.Value }
        Set-Item "Env:$key" $EnvVars[$key]
    }
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
            -WorkingDirectory $WorkingDirectory -WindowStyle Hidden `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
    }
    finally {
        foreach ($key in $EnvVars.Keys) {
            if ($saved.ContainsKey($key)) { Set-Item "Env:$key" $saved[$key] }
            else { Remove-Item "Env:$key" -ErrorAction SilentlyContinue }
        }
    }
    Set-Content -Path (Join-Path $LogDir "$Name.pid") -Value $proc.Id
    Write-Host "  started $Name (PID $($proc.Id), logs\dev\$Name.out.log)" -ForegroundColor Green
    return $proc
}

function Wait-HttpStatus {
    param([string]$Url, [int[]]$AcceptStatuses, [int]$TimeoutSeconds = 45)
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        Start-Sleep -Milliseconds 1000
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -in $AcceptStatuses) { return $true }
        }
        catch {
            $code = $null
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($code -in $AcceptStatuses) { return $true }
        }
    }
    return $false
}

# ── Stop mode ─────────────────────────────────────────────────────────────
if ($Stop) {
    foreach ($name in @("backend", "frontend", "mcp")) {
        $pidFile = Join-Path $LogDir "$name.pid"
        if (Test-Path $pidFile) {
            $trackedPid = Get-Content $pidFile
            $proc = Get-Process -Id $trackedPid -ErrorAction SilentlyContinue
            if ($proc) {
                # Kill the tree: uvicorn --reload and npm spawn children
                taskkill /PID $trackedPid /T /F *> $null
                Write-Host "  stopped $name (PID $trackedPid)" -ForegroundColor Yellow
            }
            Remove-Item $pidFile -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Dev processes stopped. The db container keeps running (docker compose stop db to stop it)." -ForegroundColor Yellow
    return
}

# ── Sanity checks ─────────────────────────────────────────────────────────
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not reachable - start Docker Desktop first."
}
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at '$Python' - pass -Python <path to conda env python>."
}

# ── 1. Database ───────────────────────────────────────────────────────────
Write-Host "[1/4] Database (Docker)" -ForegroundColor Cyan
docker compose -f (Join-Path $Root "docker-compose.yml") up -d
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    docker compose -f (Join-Path $Root "docker-compose.yml") exec -T db pg_isready -U ykmmgmt *> $null
    if ($LASTEXITCODE -eq 0) { $healthy = $true; break }
    Start-Sleep -Seconds 1
}
if ($healthy) { Write-Host "  db is ready (localhost:15432)" -ForegroundColor Green }
else { Write-Warning "  db did not become ready in 30s - check docker compose ps" }

# ── 2. Backend ────────────────────────────────────────────────────────────
Write-Host "[2/4] Backend (uvicorn, :8000)" -ForegroundColor Cyan
if (Test-PortListening 8000) {
    Write-Host "  already running on :8000 - skipping" -ForegroundColor Yellow
}
else {
    $null = Start-DevProcess -Name "backend" -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "main:app", "--reload", "--port", "8000") `
        -WorkingDirectory (Join-Path $Root "ykmmgmt\backend")
    if (Wait-HttpStatus -Url "http://127.0.0.1:8000/api/health" -AcceptStatuses 200) {
        Write-Host "  backend healthy (http://localhost:8000, docs at /docs)" -ForegroundColor Green
    }
    else { Write-Warning "  backend did not answer /api/health in 45s - check logs\dev\backend.err.log" }
}

# ── 3. Frontend ───────────────────────────────────────────────────────────
Write-Host "[3/4] Frontend (Vite, :5173)" -ForegroundColor Cyan
if ($NoFrontend) {
    Write-Host "  skipped (-NoFrontend)" -ForegroundColor DarkGray
}
elseif (Test-PortListening 5173) {
    Write-Host "  already running on :5173 - skipping" -ForegroundColor Yellow
}
else {
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npm) {
        Write-Warning "  npm not found on PATH - start the frontend manually (cd ykmmgmt\frontend; npm run dev)"
    }
    else {
        $null = Start-DevProcess -Name "frontend" -FilePath $npm `
            -ArgumentList @("run", "dev") `
            -WorkingDirectory (Join-Path $Root "ykmmgmt\frontend")
        Write-Host "  frontend starting (http://localhost:5173, logs\dev\frontend.out.log)" -ForegroundColor Green
    }
}

# ── 4. MCP server ─────────────────────────────────────────────────────────
Write-Host "[4/4] MCP server (streamable HTTP, :8001)" -ForegroundColor Cyan
if ($NoMcp) {
    Write-Host "  skipped (-NoMcp)" -ForegroundColor DarkGray
}
elseif (Test-PortListening 8001) {
    Write-Host "  already running on :8001 - skipping" -ForegroundColor Yellow
}
else {
    # Credentials come from the repo-root .env (git-ignored)
    $dotEnv = @{}
    if (Test-Path (Join-Path $Root ".env")) {
        foreach ($line in Get-Content (Join-Path $Root ".env")) {
            $trimmed = $line.Trim()
            if ($trimmed -and -not $trimmed.StartsWith("#") -and $trimmed.Contains("=")) {
                $key, $value = $trimmed -split "=", 2
                $dotEnv[$key.Trim()] = $value.Trim()
            }
        }
    }
    $svcUser = $dotEnv["YKM_SERVICE_USERNAME"]
    $svcPass = $dotEnv["YKM_SERVICE_PASSWORD"]
    $apiKey = $dotEnv["YKM_MCP_API_KEY"]
    if (-not ($svcUser -and $svcPass -and $apiKey)) {
        Write-Warning "  YKM_SERVICE_USERNAME / YKM_SERVICE_PASSWORD / YKM_MCP_API_KEY missing in .env - skipping MCP server"
        Write-Warning "  (create a backend account, then add the YKM_* keys - see .env.example)"
    }
    else {
        $null = Start-DevProcess -Name "mcp" -FilePath $Python `
            -ArgumentList @("-m", "mcp_server") `
            -WorkingDirectory (Join-Path $Root "ykmmgmt") `
            -EnvVars @{
                YKM_BACKEND_URL      = "http://127.0.0.1:8000"
                YKM_SERVICE_USERNAME = $svcUser
                YKM_SERVICE_PASSWORD = $svcPass
                YKM_MCP_API_KEY      = $apiKey
                YKM_MCP_HOST         = "127.0.0.1"
                YKM_MCP_PORT         = "8001"
            }
        Write-Host "  MCP endpoint: http://127.0.0.1:8001/mcp (clients send: Authorization: Bearer <YKM_MCP_API_KEY from .env>)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Dev environment is up:" -ForegroundColor Cyan
Write-Host "  Frontend    http://localhost:5173"
Write-Host "  Backend     http://localhost:8000  (docs: /docs)"
Write-Host "  MCP server  http://127.0.0.1:8001/mcp"
Write-Host "Stop with: .\scripts\dev.ps1 -Stop" -ForegroundColor Cyan

