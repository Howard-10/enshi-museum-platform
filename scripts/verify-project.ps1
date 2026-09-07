param(
    [switch]$SkipDockerConfig
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$Python = Join-Path $BackendRoot ".venv\\Scripts\\python.exe"

function Invoke-CheckedCommand {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Host "`n== $Label =="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Push-Location $BackendRoot
try {
    Invoke-CheckedCommand "Backend formatting" { & $Python -m ruff format --check app tests }
    Invoke-CheckedCommand "Backend lint" { & $Python -m ruff check app tests }
    Invoke-CheckedCommand "Backend tests" { & $Python -m pytest -q }
}
finally {
    Pop-Location
}

Push-Location $FrontendRoot
try {
    Invoke-CheckedCommand "Frontend production build" { & npm.cmd run build }
}
finally {
    Pop-Location
}

if (-not $SkipDockerConfig) {
    Push-Location $ProjectRoot
    try {
        Invoke-CheckedCommand "Docker Compose syntax" { & docker compose --profile app config --quiet }
    }
    finally {
        Pop-Location
    }
}

Write-Host "`nAll checks passed. This script never constructs a model or web-search client."
