param(
    [switch]$Build,
    [switch]$Pull
)

$ErrorActionPreference = "Stop"
$deployRoot = $PSScriptRoot
Set-Location $deployRoot

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example. Fill in passwords and public addresses, then run this script again."
    exit 1
}

New-Item -ItemType Directory -Force -Path .\data, .\volumes\postgres, .\volumes\redis, .\volumes\minio | Out-Null

if ($Build) { & "$PSScriptRoot\build-images.ps1" }

$pullArg = if ($Pull) { "--pull", "always" } else { @() }
docker compose --env-file .env -f docker-compose.yml up -d @pullArg
docker compose --env-file .env -f docker-compose.yml ps
