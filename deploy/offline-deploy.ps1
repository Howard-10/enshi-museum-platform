$ErrorActionPreference = "Stop"
$deployRoot = $PSScriptRoot
Set-Location $deployRoot

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env. Configure its passwords and public addresses, then run this command again."
    exit 1
}

$archive = if ($env:IMAGE_ARCHIVE) { $env:IMAGE_ARCHIVE } else { ".\enshi-museum-images-1.0.0.tar" }
$requiredImages = @(
    "enshi-museum/backend:1.0.0",
    "enshi-museum/frontend:1.0.0",
    "pgvector/pgvector:pg17",
    "redis:7-alpine",
    "quay.io/minio/minio:latest"
)

if (Test-Path $archive) {
    docker load -i $archive
} else {
    foreach ($image in $requiredImages) {
        docker image inspect $image *> $null
        if ($LASTEXITCODE -ne 0) { throw "Missing $image and no image archive was found at $archive" }
    }
}

New-Item -ItemType Directory -Force -Path .\data, .\volumes\postgres, .\volumes\redis, .\volumes\minio | Out-Null
docker compose --env-file .env -f docker-compose.yml up -d --pull never --remove-orphans
docker compose --env-file .env -f docker-compose.yml ps
