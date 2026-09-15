# Backup the production PostgreSQL database (custom-format dump), prune old
# backups, and print restore instructions.
#
# The prod DB runs on the prod host (srx@192.168.10.25); the dump is taken
# there over SSH and copied back into backups/ on this machine.
#
# Usage:  .\scripts\backup-db.ps1 [-KeepDays 30]
# Requires: SSH key access to the prod host and the ykmmgmt-prod-db container up.
#
# Schedule daily via Windows Task Scheduler (see README: "Backups").

param(
    [string]$RemoteHost = "srx@192.168.10.25",
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

Write-Host "Dumping database on ${RemoteHost} to $containerPath ..." -ForegroundColor Cyan
ssh $RemoteHost "docker exec $Container pg_dump -U $User -d $Db -Fc -f $containerPath"
if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_dump failed on the prod host - is the $Container container running?"
}

# Copy the dump out of the container onto the prod host's /tmp, then here
ssh $RemoteHost "docker cp ${Container}:$containerPath /tmp/ykmmgmt-$stamp.dump && docker exec $Container rm $containerPath"
$localPath = Join-Path $OutDir "ykmmgmt-$stamp.dump"
scp "${RemoteHost}:/tmp/ykmmgmt-$stamp.dump" $localPath
ssh $RemoteHost "rm /tmp/ykmmgmt-$stamp.dump"
if ($LASTEXITCODE -ne 0) {
    Write-Error "scp of the dump failed."
}

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
