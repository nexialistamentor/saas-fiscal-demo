# Setup Redis no Windows - SaaS Fiscal Demo
# Execute este script para instalar Redis e rodar os testes operacionais
# Uso: .\scripts\setup-redis.ps1

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-RedisRunning {
    try {
        $conn = New-Object System.Net.Sockets.TcpClient("localhost", 6379)
        $conn.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-RedisPath {
    $paths = @(
        "C:\Program Files\Redis\redis-server.exe",
        "C:\Program Files (x86)\Redis\redis-server.exe",
        "$env:LOCALAPPDATA\Programs\Redis\redis-server.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    $found = Get-ChildItem -Path "C:\" -Filter "redis-server.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

Write-Host "=== Setup Redis para Testes Operacionais ===" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar se Redis já está rodando
if (Test-RedisRunning) {
    Write-Host "[OK] Redis ja esta rodando em localhost:6379" -ForegroundColor Green
    Write-Host "     Continue com os 4 terminais conforme INSTRUCOES_TESTES.md" -ForegroundColor Gray
    exit 0
}

# 2. Verificar se redis-server existe
$redisPath = Get-RedisPath
if ($redisPath) {
    Write-Host "[OK] Redis encontrado: $redisPath" -ForegroundColor Green
    Write-Host "     Iniciando redis-server em background..." -ForegroundColor Gray
    Start-Process -FilePath $redisPath -WindowStyle Normal
    Start-Sleep -Seconds 2
    if (Test-RedisRunning) {
        Write-Host "[OK] Redis iniciado com sucesso!" -ForegroundColor Green
        exit 0
    }
}

# 3. Redis não encontrado - opções de instalação
Write-Host "[AVISO] Redis nao encontrado ou nao iniciou." -ForegroundColor Yellow
Write-Host ""
Write-Host "Escolha uma das opcoes abaixo para instalar Redis:" -ForegroundColor Cyan
Write-Host ""
Write-Host "OPCAO 1 - Winget (mais simples, Windows 10/11):" -ForegroundColor White
Write-Host "  winget install Redis.Redis --accept-package-agreements --accept-source-agreements -h" -ForegroundColor Gray
Write-Host "  Depois reinicie o terminal e execute novamente: .\scripts\setup-redis.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "OPCAO 2 - Chocolatey (requer PowerShell como Administrador):" -ForegroundColor White
Write-Host "  1. Instale o Chocolatey: https://chocolatey.org/install" -ForegroundColor Gray
Write-Host "  2. choco install redis-64 -y" -ForegroundColor Gray
Write-Host "  3. redis-server" -ForegroundColor Gray
Write-Host ""
Write-Host "OPCAO 3 - Docker (se tiver Docker Desktop):" -ForegroundColor White
Write-Host "  docker run -d -p 6379:6379 --name redis-saas redis" -ForegroundColor Gray
Write-Host ""
Write-Host "OPCAO 4 - WSL (Ubuntu):" -ForegroundColor White
Write-Host "  wsl -d Ubuntu" -ForegroundColor Gray
Write-Host "  sudo apt update && sudo apt install redis-server -y" -ForegroundColor Gray
Write-Host "  sudo service redis-server start" -ForegroundColor Gray
Write-Host ""
Write-Host "Deseja tentar instalar via winget agora? (S/N): " -NoNewline
$r = Read-Host
if ($r -eq "S" -or $r -eq "s") {
    Write-Host "Executando winget install Redis.Redis..." -ForegroundColor Gray
    winget install Redis.Redis --accept-package-agreements --accept-source-agreements -h
    Write-Host "Instalacao concluida. Reinicie o terminal e execute novamente:" -ForegroundColor Yellow
    Write-Host "  .\scripts\setup-redis.ps1" -ForegroundColor White
}
exit 1
