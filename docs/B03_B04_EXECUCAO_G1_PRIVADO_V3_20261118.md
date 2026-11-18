# SOLVERIS — ensaio G1 privado V3 no worktree Windows isolado

**Corte:** 18/11/2026. **Autoridade:** Miguel ratificou o G1 privado, registo explícito da coexistência, dívida rastreada e exceção estrita da catraca. **Não há aprovação para merge `main`, publicação, mudança MEI, migração ou Fase 1 B06.**

## Cadeia de custódia

- `main` de referência: `a6a2da6cbf07c7b9922f8571bf2e6016376304d5`.
- Branch de recuperação: `recovery/enterprise-b00-b04-20261117` (auto-deploy bloqueado).
- Estado de entrada: V2 já aplicada em `C:\dev\saas-fiscal-demo-b06-green-20261118`, com 36 blobs de `c9a17fd1`, três módulos compartilhados ajustados por opt-in e dois ajustes de harness. Não partir de novo da `main` nem tocar o worktree `C:\dev\saas-fiscal-demo-a1`.
- G1 original: commit `ee1007562836378e2addb50f9af0a09b609aef88`, blob `543f19b4b777ecaaa107d699dd13c002b378e8a2`; a implementação privada tem AST funcional equivalente, exceto classe e docstring.
- 22 contratos G1: blob original `45a2080a8adead467aa4b00275e3a33616b0966c`, preservado como `tests/enterprise_g1_contract_origin.py`. O coletor de testes importa esse contrato sem alterar asserções e executa contra o novo símbolo privado.
- Manifesto ratificado V2 **inalterado**: Git blob `4eafb57b917a3910ef873d0b8ca30145a0940b09`; extensão apenas em `docs/B03_B04_BASELINE_ESCOPO_G1_V3_20261118.json`.
- Novo patch incremental: `docs/B03_B04_PATCH_G1_PRIVADO_V3_20261118.patch`. Não reaplicar V2.

## Passo 1 — conferir base e aplicar só o delta V3

```powershell
Set-Location 'C:\dev\saas-fiscal-demo-b06-green-20261118'
$branch = git branch --show-current
if ($branch -ne 'recovery/enterprise-b00-b04-20261117') { throw "STOP_BRANCH: $branch" }
git status --short --branch
if ((git rev-parse origin/main) -ne 'a6a2da6cbf07c7b9922f8571bf2e6016376304d5') { throw 'STOP_MAIN_DRIFT' }
if ((git hash-object app/services/tax_consistency/tax_consistency_engine.py) -ne '9f7a5ddf144293fe3591989c784c8ec6d875cd07') { throw 'STOP_SHARED_G1_CHANGED' }
if ((git hash-object docs/B03_B04_BASELINE_ESCOPO_TRANSACIONAL_V2_20261118.json) -ne '4eafb57b917a3910ef873d0b8ca30145a0940b09') { throw 'STOP_V2_MANIFEST' }
if ((git hash-object tests/test_enterprise_b01_atomic_rollback_contract.py) -ne 'bd7caf7e9a1de68a604b1d22cdaac92704950219') { throw 'STOP_V2_ATOMIC_FIXTURE' }
git fetch --no-tags origin 'refs/heads/recovery/enterprise-b00-b04-20261117'
if ($LASTEXITCODE -ne 0) { throw 'STOP_FETCH_V3' }
git merge --ff-only origin/recovery/enterprise-b00-b04-20261117
if ($LASTEXITCODE -ne 0) { throw 'STOP_FF_ONLY_V3_DOCS' }
git apply --check 'docs/B03_B04_PATCH_G1_PRIVADO_V3_20261118.patch'
if ($LASTEXITCODE -ne 0) { throw 'STOP_V3_PATCH_CONTEXT' }
git apply 'docs/B03_B04_PATCH_G1_PRIVADO_V3_20261118.patch'
if ($LASTEXITCODE -ne 0) { throw 'STOP_V3_PATCH' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'STOP_WHITESPACE' }
if ((git hash-object tests/enterprise_g1_contract_origin.py) -ne '45a2080a8adead467aa4b00275e3a33616b0966c') { throw 'STOP_ORIGINAL_G1_TEST' }
```

## Passo 2 — prova dirigida, sem suite global antecipada

```powershell
$env:ENVIRONMENT = 'test'
$env:DATABASE_URL = 'sqlite:///./b06_main_baseline.sqlite'
python tools/check_duplicacao.py --repo . --registro docs/REGISTRO_CANONICO.json
if ($LASTEXITCODE -ne 0) { throw 'STOP_DUPLICATION_G1' }
python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q
if ($LASTEXITCODE -ne 0) { throw 'STOP_RECOVERY_GATES' }
python -m unittest discover -s tests -p 'test_enterprise_g1_private_original_contract.py' -q
if ($LASTEXITCODE -ne 0) { throw 'STOP_G1_22' }
python -m unittest discover -s tests -p 'test_enterprise_g1_coexistence_gate.py' -q
if ($LASTEXITCODE -ne 0) { throw 'STOP_COEXISTENCE_8' }
python -m pytest -q --tb=short --disable-warnings tests/test_enterprise_b03_item_reconciliation.py tests/test_enterprise_b04_icms_st_integral_bridge.py tests/test_solveris_b01_circuit.py tests/test_enterprise_b01_atomic_rollback_contract.py tests/test_enterprise_g1_private_original_contract.py tests/test_enterprise_g1_coexistence_gate.py
if ($LASTEXITCODE -ne 0) { throw 'STOP_G1_V3_DIRECTED_RED' }
Write-Host 'G1_V3_DIRIGIDOS_OK_SEM_GREEN_GLOBAL'
```

São **25 contratos originais B01/B03/B04 + 6 de atomicidade + 22 G1 de origem + 8 de coexistência = 61 testes dirigidos esperados**, sem os 12 B01 duplicados acidentalmente. Se a recolha não for 61, parar e reportar. Os 9 controlos novos V3 estão incluídos na execução independente dos testes do gate (38 testes).

## Passo 3 — somente se 61 dirigidos GREEN

```powershell
python -m pytest -q --tb=short --disable-warnings --junitxml=.pytest_cache/b03b04_candidate_g1_v3.xml
$candidateExit = $LASTEXITCODE
python tools/enterprise_recovery_test_gate_v3.py --repo . --baseline-junit .pytest_cache/b03b04_baseline_main.xml --candidate-junit .pytest_cache/b03b04_candidate_g1_v3.xml --approved-manifest docs/B03_B04_BASELINE_ESCOPO_G1_V3_20261118.json --output .pytest_cache/b03b04_gate_g1_v3.json
$gateExit = $LASTEXITCODE
Write-Host "CANDIDATE_EXIT=$candidateExit"
Write-Host "GATE_EXIT=$gateExit"
Get-Content .pytest_cache/b03b04_gate_g1_v3.json -Raw
```

A suite integral pode retornar exit 1 **somente** pelas mesmas 13 falhas da baseline `main@a6a2da6c`, sem mudança de causa, novos RED ou skipped. O gate diferencial exige os 4.102 casos anteriores, os 61 dirigidos e todos os controlos novos. Só poderá declarar `PASS_WITH_BASELINE_RED` com `GLOBAL_GREEN=false` se todas as garantias passarem.

**Se falhar qualquer passo:** preservar o estado e o JUnit no worktree isolado, devolver apenas resumo dos novos node IDs/falhas causais, sem novos commits de produto. Não alterar MEI, contratos de testes, G13, hook, migrações ou a `main` para forçar GREEN.
