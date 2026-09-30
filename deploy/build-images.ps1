param(
    [string]$Tag = "1.0.0",
    [string]$Registry = "",
    [switch]$Push
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$prefix = if ([string]::IsNullOrWhiteSpace($Registry)) { "" } else { "$Registry/" }
$backendImage = "${prefix}enshi-museum/backend:$Tag"
$frontendImage = "${prefix}enshi-museum/frontend:$Tag"

Write-Host "Building $backendImage"
docker build --tag $backendImage .\backend
if ($LASTEXITCODE -ne 0) { throw "Backend image build failed" }

Write-Host "Building $frontendImage"
docker build --build-arg VITE_API_BASE_URL=/api/v1 --tag $frontendImage .\frontend
if ($LASTEXITCODE -ne 0) { throw "Frontend image build failed" }

if ($Push) {
    if ([string]::IsNullOrWhiteSpace($Registry)) {
        throw "-Push requires -Registry, for example registry.cn-hangzhou.aliyuncs.com/namespace"
    }
    docker push $backendImage
    if ($LASTEXITCODE -ne 0) { throw "Backend image push failed" }
    docker push $frontendImage
    if ($LASTEXITCODE -ne 0) { throw "Frontend image push failed" }
}

Write-Host "Images ready: $backendImage and $frontendImage"
