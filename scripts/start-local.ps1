param(
    [switch]$WithFrontend
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已创建 .env，请先修改其中的密码和模型配置。"
}

docker compose up -d
Write-Host "基础服务已启动。后端请按 docs/SETUP.md 的第 3 步启动。"

if ($WithFrontend) {
    Write-Host "前端请在另一个 PowerShell 窗口中运行 npm run dev。"
}
