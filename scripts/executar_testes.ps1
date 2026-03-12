# Execução dos Testes Operacionais - SaaS Fiscal
# =============================================
# Execute em 4 terminais separados, nesta ordem:
#
# Terminal 1: redis-server
# Terminal 2: python -m app.workers.analysis_worker
# Terminal 3: python -m uvicorn app.main:app --reload
# Terminal 4: .\scripts\executar_testes.ps1
#
# Uso: .\scripts\executar_testes.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Ativar venv se existir
$venvScript = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"
if (Test-Path $venvScript) {
    & $venvScript
}

Write-Host "=== Preparando ambiente ===" -ForegroundColor Cyan
python scripts/preparar_testes.py
if ($LASTEXITCODE -ne 0) { exit 1 }

# IMPORTANTE: Teste 3 usa limite@teste.com (plano com limite_analises=2)
# Se não definir, usa teste@teste.com (plano Basico, limite 100) e o Teste 3 falha
$env:USER_LIMITE = "limite@teste.com"
$env:USER_LIMITE_PASS = "senha123"
$env:USER_A_EMAIL = "teste@teste.com"
$env:USER_A_PASS = "senha123"
$env:USER_B_EMAIL = "outro@teste.com"
$env:USER_B_PASS = "senha123"

Write-Host "`n=== Executando testes operacionais ===" -ForegroundColor Cyan
python scripts/testes_operacionais.py
exit $LASTEXITCODE
