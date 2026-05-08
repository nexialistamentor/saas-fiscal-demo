# Reset do ambiente de desenvolvimento local
# SQLite é descartável — PostgreSQL Railway é a fonte de verdade

Set-Location $PSScriptRoot\..

Remove-Item -Force test.db -ErrorAction SilentlyContinue
Write-Host "BD local removida."

alembic upgrade baseline@head
if ($LASTEXITCODE -ne 0) {
    Write-Error "alembic upgrade baseline@head falhou (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Migrações aplicadas."

python -m app.seed_data
if ($LASTEXITCODE -ne 0) {
    Write-Error "seed_data falhou (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Seed executado."

Write-Host "Reset completo."
