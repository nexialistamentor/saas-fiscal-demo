# SOLVERIS B03/B04 — execução do candidato transacional V2 no Windows isolado

**Situação:** patch de código **NÃO APLICADO nem COMMITADO** no branch Git.
Somente dois patches e os manifestos estão versionados em `docs/` para custódia.
Não operar em `C:\dev\saas-fiscal-demo-a1`, `main`, Railway ou Vercel.

## Fontes com proveniência

- Base `main@a6a2da6c`; worktree de teste Windows
  `C:\dev\saas-fiscal-demo-b06-green-20261118`.
- Fonte original `c9a17fd1bc21f5abc50450e258cce490f3d196c6`:
  **36 blobs idênticos**, listados no manifesto V1.
- Patch do candidato: `docs/B03_B04_PATCH_TX_CANDIDATO_20261118.patch`,
  blob Git `1ffce9965c313b788fe00e84d1ac576ab6fbac49`.
- Patch da catraca: `docs/B03_B04_PATCH_GATE_V2_20261118.patch`,
  conferido via `git apply --cached --reverse --check` na origem.
- Manifesto novo: `docs/B03_B04_BASELINE_ESCOPO_TRANSACIONAL_V2_20261118.json`.
  Não modifica o manifesto ratificado V1 nem as 13 falhas de baseline.

## Preparação, sem desvio para o MEI

Operação deliberadamente separada da suite global. O responsável deve primeiro
confirmar no PowerShell Windows que o worktree possui somente as duas alterações
ratificadas de infraestrutura de teste. Não sobrescrever modificações alheias.

```powershell
Set-Location 'C:\dev\saas-fiscal-demo-b06-green-20261118'
git status --short --branch
git cat-file -e 'a6a2da6c^{commit}'
if ($LASTEXITCODE -ne 0) { throw 'STOP_BASE_MISSING' }
git fetch --no-tags origin 'refs/heads/recovery/enterprise-b00-b04-20261117'
if ($LASTEXITCODE -ne 0) { throw 'STOP_REMOTE_CUSTODY' }
git cat-file -e 'c9a17fd1^{commit}'
if ($LASTEXITCODE -ne 0) { throw 'STOP_SOURCE_C9_MISSING' }

$sslBlob = git hash-object tests/test_adr020_activation_postgresql.py
$astBlob = git hash-object tests/test_agent_contract_architecture.py
if ($sslBlob -ne 'b7e551df23c3f2ec60bcf95d1a1c3c9be9a68d50') { throw 'STOP_SSL_HARNESS' }
if ($astBlob -ne '0d24fd62d66277d0107af182e035059523d72dae') { throw 'STOP_AST_HARNESS' }

if ((git branch --show-current) -ne '') { throw 'STOP_EXPECTED_DETACHED_BASE' }
if ((git rev-parse HEAD) -ne 'a6a2da6cbf07c7b9922f8571bf2e6016376304d5') { throw 'STOP_WRONG_BASE' }
if (git branch --list 'recovery/enterprise-b00-b04-20261117') { throw 'STOP_LOCAL_RECOVERY_BRANCH_EXISTS' }

git switch -c 'recovery/enterprise-b00-b04-20261117' --track 'origin/recovery/enterprise-b00-b04-20261117'
if ($LASTEXITCODE -ne 0) { throw 'STOP_SWITCH_RECOVERY_BRANCH' }
$manifest = Get-Content 'docs/B03_B04_BLOB_PROVENIENCE_20261118.json' -Raw | ConvertFrom-Json
$paths = @($manifest.items | ForEach-Object { $_.path })
if ($paths.Count -ne 36) { throw 'STOP_SOURCE_COUNT' }
foreach ($path in $paths) {
    if (Test-Path -LiteralPath $path) { throw "STOP_EXISTING_SOURCE: $path" }
}
git restore --source=c9a17fd1 --worktree -- @paths
if ($LASTEXITCODE -ne 0) { throw 'STOP_SOURCE_RESTORE' }
foreach ($item in $manifest.items) {
    if ((git hash-object $item.path) -ne $item.git_blob) { throw "STOP_SOURCE_BLOB: $($item.path)" }
}

if ((git hash-object docs/B03_B04_PATCH_TX_CANDIDATO_20261118.patch) -ne '1ffce9965c313b788fe00e84d1ac576ab6fbac49') { throw 'STOP_CANDIDATE_PATCH_HASH' }
git apply --check 'docs/B03_B04_PATCH_TX_CANDIDATO_20261118.patch'
if ($LASTEXITCODE -ne 0) { throw 'STOP_CANDIDATE_PATCH_CONTEXT' }
git apply --check 'docs/B03_B04_PATCH_GATE_V2_20261118.patch'
if ($LASTEXITCODE -ne 0) { throw 'STOP_GATE_PATCH_CONTEXT' }
git apply 'docs/B03_B04_PATCH_TX_CANDIDATO_20261118.patch'
if ($LASTEXITCODE -ne 0) { throw 'STOP_CANDIDATE_PATCH' }
git apply 'docs/B03_B04_PATCH_GATE_V2_20261118.patch'
if ($LASTEXITCODE -ne 0) { throw 'STOP_GATE_PATCH' }
python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q
if ($LASTEXITCODE -ne 0) { throw 'STOP_GATE_UNIT_TESTS' }
```

**Não executar mais passos** se houver conflito, alteração alheia ou falha.
Nunca remover/excluir arquivos para forçar teste positivo. Em especial, não
recriar `g1_reference_engine.py` em falta nem mudar testes RED do MEI.

## Etapa 1 — testes dirigidos, bloqueantes

```powershell
python -m pytest -q --tb=short --disable-warnings tests/test_enterprise_b03_item_reconciliation.py tests/test_enterprise_b04_icms_st_integral_bridge.py tests/test_solveris_b01_circuit.py tests/test_enterprise_b01_atomic_rollback_contract.py
if ($LASTEXITCODE -ne 0) { throw 'STOP_ENTERPRISE_TARGETED_RED' }
```

São **31 testes obrigatórios** (25 originais e 6 de atomicidade nova).
Isso ainda não constitui GREEN global nem autoriza commit de código.

## Etapa 2 — somente depois dos testes dirigidos aprovados

Executar uma única suite completa no mesmo worktree isolado, guardando JUnit:

```powershell
python -m pytest -q --tb=short --disable-warnings --junitxml=.pytest_cache/b03b04_candidate_tx_v2.xml
$candidateExit = $LASTEXITCODE
python tools/enterprise_recovery_test_gate.py --baseline-junit .pytest_cache/b03b04_baseline_main.xml --candidate-junit .pytest_cache/b03b04_candidate_tx_v2.xml --approved-manifest docs/B03_B04_BASELINE_ESCOPO_TRANSACIONAL_V2_20261118.json --output .pytest_cache/b03b04_gate_tx_v2.json
$gateExit = $LASTEXITCODE
"CANDIDATE_EXIT=$candidateExit"
"GATE_EXIT=$gateExit"
Get-Content .pytest_cache/b03b04_gate_tx_v2.json -Raw
```

O exit da suite pode ser 1 **somente** devido às mesmas 13 falhas baselined;
o gate exige causas iguais, nenhum novo RED, nenhum novo skip, os 25+6 GREEN,
os hashes imutáveis de quatro contratos MEI e os dois harness originais.

**Não commitar nem publicar código** até prova integral. Se passar, preservar
o recibo sanitizado em Git numa intenção separada antes de avaliar promoção.
Não aplicar migrações 0060–0066 e não iniciar B06 Fase 1.
