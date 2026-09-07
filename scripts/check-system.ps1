param(
    [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot
Write-Host "Checking Docker services..."
docker compose ps

Write-Host "Checking backend health..."
$health = Invoke-RestMethod -Uri "$BackendUrl/api/v1/health" -TimeoutSec 10
$readiness = Invoke-RestMethod -Uri "$BackendUrl/api/v1/system/readiness" -TimeoutSec 10

if ($readiness.external_model_calls_enabled) {
    Write-Warning "External model calls are enabled. This script does not call a model, but review .env before testing."
}
if ($readiness.web_search_enabled) {
    Write-Warning "External web search is enabled. Review the Tavily budget and domain allowlist before testing."
}

[pscustomobject]@{
    BackendStatus = $health.status
    RetrievalMode = $readiness.retrieval_mode
    ExternalModelCallsEnabled = $readiness.external_model_calls_enabled
    WebSearchEnabled = $readiness.web_search_enabled
    WebSearchProvider = $readiness.web_search_provider
    WebSearchMonthlyLimit = $readiness.web_search_monthly_request_limit
    Documents = $readiness.documents
    ChildChunks = $readiness.child_chunks
    CatalogArtifacts = $readiness.catalog_artifacts
    MediaAssets = $readiness.media_assets
} | Format-List
