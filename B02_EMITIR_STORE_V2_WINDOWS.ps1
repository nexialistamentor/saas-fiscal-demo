# B02 — emissao prospectiva da store local; PostgreSQL sempre somente leitura.
# Nao emite ROOT, nao faz SQL DML, nao cria autorizacao institucional.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Inspecionar','Emitir')]
    [string]$Etapa,

    [Parameter(Mandatory=$true)]
    [string]$PastaBundleAssinado,

    [string]$Repositorio = 'C:\dev\solveris-b02-g5-v5-publicacao',
    [string]$Plano = (Join-Path $env:USERPROFILE 'Downloads\B02_STORE_V2_PLANO.json'),
    [string]$Custodia = (Join-Path $env:LOCALAPPDATA 'SOLVERIS\B02Trust\SUCCESSOR_V3'),
    [string]$NomeVariavelDSN = 'SOLVERIS_B02_READER_DSN',
    [string]$HashPlanoAprovado
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Repositorio -PathType Container)) {
    throw 'STOP_B02_STORE_CHECKOUT_MISSING'
}
if (-not (Test-Path -LiteralPath $PastaBundleAssinado -PathType Container)) {
    throw 'STOP_B02_STORE_SIGNED_BUNDLE_MISSING'
}
if (-not (Test-Path -LiteralPath (Join-Path $PastaBundleAssinado 'signature.bin') -PathType Leaf)) {
    throw 'STOP_B02_STORE_SIGNATURE_MISSING'
}
if (-not [Environment]::GetEnvironmentVariable($NomeVariavelDSN, 'Process')) {
    throw 'STOP_B02_STORE_RESTRICTED_DSN_MISSING'
}
if ($Etapa -eq 'Emitir' -and $HashPlanoAprovado -cnotmatch '^[a-f0-9]{64}$') {
    throw 'STOP_B02_STORE_EXACT_MIGUEL_PLAN_AUTHORIZATION_REQUIRED'
}
Push-Location -LiteralPath $Repositorio
try {
    $ramo = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $ramo -cne 'candidate/g5-v5-publicacao-local') {
        throw 'STOP_B02_STORE_WRONG_BRANCH'
    }
    $argsB02 = @(
        '-m', 'tools.b02_store_emission_v2_windows',
        '--mode', $(if ($Etapa -eq 'Inspecionar') { 'preview' } else { 'emit' }),
        '--repo', $Repositorio,
        '--signed-bundle', $PastaBundleAssinado,
        '--plan-file', $Plano,
        '--custody-root', $Custodia,
        '--dsn-env', $NomeVariavelDSN
    )
    if ($Etapa -eq 'Emitir') {
        $argsB02 += @('--authorized-plan-sha256', $HashPlanoAprovado)
    }
    & python @argsB02
    if ($LASTEXITCODE -ne 0) {
        throw "STOP_B02_STORE_PYTHON_EXIT_$LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
