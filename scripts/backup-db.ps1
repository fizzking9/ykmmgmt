# Backup the production PostgreSQL database (custom-format dump), prune old
# backups, and print restore instructions.
#
# Usage:  .\scripts\backup-db.ps1 [-KeepDays 30]
# Requires: Docker Desktop running and the ykmmgmt-prod-db container up.
#
# Schedule daily via Windows Task Scheduler (see README: "Backups").

param(
    [string]$Container = "ykmmgmt-prod-db",
    [string]$User = "ykmmgmt",
    [string]$Db = "ykmmgmt",
    [int]$KeepDays = 30,
    [string]$OutDir = "$PSScriptRoot\..\backups"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$containerPath = "/tmp/ykmmgmt-$stamp.dump"

Write-Host "Dumping database to $containerPath ..." -ForegroundColor Cyan
docker exec $Container pg_dump -U $User -d $Db -Fc -f $containerPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_dump failed — is the $Container container running?"
}

$localPath = Join-Path $OutDir "ykmmgmt-$stamp.dump"
docker cp "${Container}:$containerPath" $localPath
docker exec $Container rm $containerPath

$size = "{0:N1}" -f ((Get-Item $localPath).Length / 1MB)
Write-Host "Backup written: $localPath ($size MB)" -ForegroundColor Green

# Prune backups older than $KeepDays days
$cutoff = (Get-Date).AddDays(-$KeepDays)
$old = Get-ChildItem $OutDir -Filter "ykmmgmt-*.dump" | Where-Object { $_.LastWriteTime -lt $cutoff }
if ($old) {
    $old | Remove-Item
    Write-Host "Pruned $($old.Count) backup(s) older than $KeepDays days." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Restore into a scratch database with:" -ForegroundColor Cyan
Write-Host "  docker run -d --name ykmmgmt-restore -e POSTGRES_PASSWORD=restore -e POSTGRES_DB=ykmmgmt postgres:16"
Write-Host "  docker cp `"$localPath`" ykmmgmt-restore:/tmp/restore.dump"
Write-Host "  docker exec ykmmgmt-restore pg_restore -U postgres -d ykmmgmt --clean --if-exists --no-owner --no-privileges /tmp/restore.dump"
Write-Host "  # compare row counts, then: docker rm -f ykmmgmt-restore"
