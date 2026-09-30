param(
    [ValidateSet("docs", "catalog", "media", "xlsx-images")]
    [string]$Type = "docs",
    [string]$Path = "/data"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

switch ($Type) {
    "docs" { docker compose --env-file .env -f docker-compose.yml exec -T backend python -m app.cli.import_docx $Path --infer-artifact-from-path }
    "catalog" { docker compose --env-file .env -f docker-compose.yml exec -T backend python -m app.cli.import_artifact_catalog $Path --knowledge-root /data }
    "media" { docker compose --env-file .env -f docker-compose.yml exec -T backend python -m app.cli.import_media $Path --types image audio video --report /data/media-import-report.json }
    "xlsx-images" { docker compose --env-file .env -f docker-compose.yml exec -T backend python -m app.cli.import_xlsx_images $Path --report /data/xlsx-image-import-report.json }
}
