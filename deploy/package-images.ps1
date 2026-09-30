param(
    [string]$Tag = "1.0.0",
    [string]$Output = "enshi-museum-images-1.0.0.tar"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$deployRoot = $PSScriptRoot
Set-Location $projectRoot

& "$PSScriptRoot\build-images.ps1" -Tag $Tag
docker pull pgvector/pgvector:pg17
docker pull redis:7-alpine
docker pull quay.io/minio/minio:latest

$outputPath = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $deployRoot $Output }
docker save -o $outputPath `
    "enshi-museum/backend:$Tag" `
    "enshi-museum/frontend:$Tag" `
    "pgvector/pgvector:pg17" `
    "redis:7-alpine" `
    "quay.io/minio/minio:latest"

Write-Host "Image bundle written to $outputPath"
