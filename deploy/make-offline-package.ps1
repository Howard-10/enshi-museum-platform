param(
    [string]$Version = "1.0.0",
    [string]$OutputDirectory = "release"
)

$ErrorActionPreference = "Stop"
$deployRoot = $PSScriptRoot
Set-Location $deployRoot

$archive = Join-Path $deployRoot "enshi-museum-images-$Version.tar"
if (-not (Test-Path $archive)) { throw "Image archive not found: $archive" }

$packageRoot = Join-Path $deployRoot "$OutputDirectory\enshi-museum-offline-$Version"
New-Item -ItemType Directory -Force -Path "$packageRoot\postgres-init" | Out-Null

Copy-Item docker-compose.yml, .env.example, $archive -Destination $packageRoot -Force
Copy-Item offline-deploy.sh, OFFLINE_DEPLOYMENT.md -Destination $packageRoot -Force
Copy-Item postgres-init\* -Destination "$packageRoot\postgres-init" -Force

Write-Host "Offline deployment directory created: $packageRoot"
