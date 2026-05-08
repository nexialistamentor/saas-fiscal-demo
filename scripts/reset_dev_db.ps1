# Reset do ambiente de desenvolvimento local
# SQLite é descartável — PostgreSQL Railway é a fonte de verdade

Set-Location $PSScriptRoot\..

Remove-Item -Force test.db -ErrorAction SilentlyContinue
Write-Host "BD local removida."

# Aplicar primeiro a baseline soberana
alembic upgrade 0000_baseline
if ($LASTEXITCODE -ne 0) { Write-Host "Baseline falhou"; exit 1 }

# Depois aplicar todas as migrações incrementais até ao head
alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Host "Upgrade head falhou"; exit 1 }

Write-Host "Migrações aplicadas."

python -m app.seed_data
if ($LASTEXITCODE -ne 0) { Write-Host "Seed falhou"; exit 1 }
Write-Host "Seed executado."

Write-Host "Reset completo."
