# Start Dev Stack: Redis + Worker + API
# Uso: .\scripts\start_dev.ps1

$ErrorActionPreference = "Stop"

# Caminho do projeto
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Tentar localizar Redis
$redisExe = $null
$redis = Get-Command redis-server -ErrorAction SilentlyContinue
if ($redis) {
    $redisExe = $redis.Source
} else {
    $redisPath = Get-ChildItem "C:\Program Files\Redis*\redis-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($redisPath) { $redisExe = $redisPath.FullName }
}

if (-not $redisExe) {
    Write-Host "Redis nao encontrado. Instale Redis ou use Docker." -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando Redis..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& `"$redisExe`""

Start-Sleep -Seconds 2

Write-Host "Iniciando Worker..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$ProjectRoot`"; python -m app.workers.analysis_worker"

Start-Sleep -Seconds 2

Write-Host "Iniciando API..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$ProjectRoot`"; uvicorn app.main:app --reload"

Write-Host ""
Write-Host "Ambiente iniciado." -ForegroundColor Green
Write-Host "API: http://localhost:8000"
Write-Host "Docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "Testes (opcional): .\scripts\executar_testes.ps1" -ForegroundColor Yellow
