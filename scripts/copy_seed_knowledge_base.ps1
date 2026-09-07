param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [string]$TargetRoot = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $TargetRoot) {
    $TargetRoot = Join-Path $ProjectRoot "data\raw\seed-v1"
}

$ManifestPath = Join-Path $ProjectRoot "data\knowledge_seed_manifest.json"
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "找不到知识库清单：$ManifestPath"
}
if (-not (Test-Path -LiteralPath $SourceRoot)) {
    throw "找不到原始资料根目录：$SourceRoot"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$copied = 0
foreach ($item in $manifest.files) {
    $source = Join-Path $SourceRoot $item.relative_path
    if (-not (Test-Path -LiteralPath $source)) {
        throw "清单中的源文件不存在：$source"
    }
    $target = Join-Path $TargetRoot $item.relative_path
    $targetDirectory = Split-Path -Parent $target
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        Write-Host "[skip] 已存在：$($item.relative_path)"
        continue
    }
    Copy-Item -LiteralPath $source -Destination $target -Force:$Force
    $copied += 1
    Write-Host "[copy] $($item.relative_path)"
}

Write-Host "[ok] 本次复制 $copied 份资料到 $TargetRoot"
