# SOLVERIS Enterprise — execução V4.3 dirigida (18/11/2026)

**CANDIDATO / NÃO GLOBAL GREEN.** Miguel ratificou o escopo V4.3. Esta etapa repara a regressão B01/MEI e dois controlos test-only, sem tocar no scanner MEI, G12, G1 partilhado, ALEMBIC, `main` ou deploy. Os patches test-only estão em commits documentais **separados** do patch de produção.

## Artefactos versionados

| Tipo | Patch em `docs/` | Blob Git |
| --- | --- | --- |
| Produto B01 | `B03_B04_PATCH_V43_B01_GUARDA_20261118.patch` | `cff561548a56d22cb4f95a03547343955ca94cb4` |
| Test-only canónico | `B03_B04_PATCH_V43_TEST_ONLY_HASH_CANONICO_20261118.patch` | `58d8fc3a48a154dee16d559d7700ffd2bb1caa9e` |
| Test-only hold Vercel | `B03_B04_PATCH_V43_TEST_ONLY_VERCEL_HOLD_20261118.patch` | `8909879e3c49136ca25ddabc63b6193d5ac3b7f2` |
| Test-only sucessão histórica + 5 negativos | `B03_B04_PATCH_V43_TEST_ONLY_HISTORICO_NEGATIVOS_20261118.patch` | `9d16c32606cb88fc21652fffa32e08dfa0bce1b5` |

O novo teste do hold verifica `main=false` e **todos** os outros valores explicitamente configurados como `false`; não remove o hold de branch nem abre rota MEI. Os 5 controlos V4.3 testam guarda positiva, guarda BoolOp negativa, reconstrução do G19, adulteração de hash/bytes e hold Vercel negativo.

## Hashes de origem e saída

| Ficheiro | Origem V4.2 | Candidato V4.3 |
| --- | --- | --- |
| `app/services/registro_analise_service.py` | `4e889089049f5be38d28e8b36a9398a401b16a3c` | `381cd15087eee7f9aaa39ff9d5ddeb547fdf47a7` |
| `tests/test_enterprise_recovery_test_gate.py` | `6ff3c7206da426caaae571c8e3e28d94411c834d` | `f03ab21bfd9e5cc48d8f5bea8e23a131c2616360` |
| `tests/test_enterprise_g19_local_cas_custody.py` | `16904b0eaa38be105e94fe92723ec97dcd4be4f2` | `5207b5ac17c53435ebe62a100edd33f3f25ed3ad` |
| `tests/test_solveris_mei_vercel_routing_contract_red.py` | `bb5ef79896fe31e55826d933455c9924b45c7df5` | `f82c379765328a28b4307d089d1ba493adf9eeb2` |
| `tests/recovery_v3_snapshot_guard.py` | `0790c450cc9426ac68ec764faae9bfb6cbaa2c42` | `87deb47c5074cb428450d07c82e8dd7ce714a746` |
| `tests/test_enterprise_recovery_v43_delta_gate.py` | ausente | `d29b1f755eecfa91cbb17e0b2a159b64b80a918d` |

## Provas já realizadas em ambiente isolado Linux

- `python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q`: **78/78 OK** após V4.3 (73 predecessores + 5 novos).
- `python -m unittest -q tests.test_enterprise_g19_local_cas_custody`: **37/37 OK**.
- `python -m unittest -q tests.test_enterprise_recovery_test_gate`: **20/20 OK**.
- Guarda B01 AST reconhecida, antigo `BoolOp` explicitamente rejeitado; scanner canónico `_find_violations`: **lista vazia**.
- Teste Vercel passa em configuração real; com `main=true` ou branch `true` reprova.
- `git diff --check` e os quatro `git apply --reverse --check` passaram no sandbox já aplicado.

**Limitação:** estas provas isoladas não executam a suite de alcance MEI nem a prova global Windows; não declaramos cobertura global.

## PowerShell — aplicação e testes dirigidos, sem execução global

Executar uma única vez em `.venv-release`:

```powershell
& {
    Set-Location 'C:\dev\saas-fiscal-demo-b06-green-20261118'
    if ((git branch --show-current) -ne 'recovery/enterprise-b00-b04-20261117') { throw 'STOP_V43_BRANCH' }
    $origens = @{
        'app/services/registro_analise_service.py'='4e889089049f5be38d28e8b36a9398a401b16a3c'
        'tests/test_enterprise_recovery_test_gate.py'='6ff3c7206da426caaae571c8e3e28d94411c834d'
        'tests/test_enterprise_g19_local_cas_custody.py'='16904b0eaa38be105e94fe92723ec97dcd4be4f2'
        'tests/test_solveris_mei_vercel_routing_contract_red.py'='bb5ef79896fe31e55826d933455c9924b45c7df5'
        'tests/recovery_v3_snapshot_guard.py'='0790c450cc9426ac68ec764faae9bfb6cbaa2c42'
    }
    foreach ($e in $origens.GetEnumerator()) {
        if ((git hash-object $e.Key) -ne $e.Value) { throw "STOP_V43_ORIGEM:$($e.Key)" }
    }
    if (Test-Path 'tests/test_enterprise_recovery_v43_delta_gate.py') { throw 'STOP_V43_TESTE_EXISTENTE' }
    if ((git hash-object app/services/enterprise_g12_st_item_reconciliation.py) -ne '8fb2559b093d2435f7395936cedb6f7ad4186ca3') { throw 'STOP_V43_G12' }
    if ((git hash-object tests/test_solveris_b01_circuit.py) -ne 'eb961ee500de8a3dee76c0a6e4c4b4be577367e5') { throw 'STOP_V43_B01_CONTRATO' }
    if ((git hash-object tests/test_canonical_source_hash.py) -ne '2fcae0f0cb4d0f2ec53baf172e0c61cc293a2608') { throw 'STOP_V43_CANONICO_CONTRATO' }

    git fetch --no-tags origin 'refs/heads/recovery/enterprise-b00-b04-20261117'
    if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_FETCH' }
    git merge --ff-only origin/recovery/enterprise-b00-b04-20261117
    if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_MERGE' }

    $patches = @(
        'docs/B03_B04_PATCH_V43_B01_GUARDA_20261118.patch'
        'docs/B03_B04_PATCH_V43_TEST_ONLY_HASH_CANONICO_20261118.patch'
        'docs/B03_B04_PATCH_V43_TEST_ONLY_VERCEL_HOLD_20261118.patch'
        'docs/B03_B04_PATCH_V43_TEST_ONLY_HISTORICO_NEGATIVOS_20261118.patch'
    )
    foreach ($p in $patches) {
        git apply --check $p
        if ($LASTEXITCODE -ne 0) { throw "STOP_V43_PATCH_CONTEXT:$p" }
    }
    foreach ($p in $patches) {
        git apply $p
        if ($LASTEXITCODE -ne 0) { throw "STOP_V43_PATCH_APPLY:$p" }
    }

    $saidas = @{
        'app/services/registro_analise_service.py'='381cd15087eee7f9aaa39ff9d5ddeb547fdf47a7'
        'tests/test_enterprise_recovery_test_gate.py'='f03ab21bfd9e5cc48d8f5bea8e23a131c2616360'
        'tests/test_enterprise_g19_local_cas_custody.py'='5207b5ac17c53435ebe62a100edd33f3f25ed3ad'
        'tests/test_solveris_mei_vercel_routing_contract_red.py'='f82c379765328a28b4307d089d1ba493adf9eeb2'
        'tests/recovery_v3_snapshot_guard.py'='87deb47c5074cb428450d07c82e8dd7ce714a746'
        'tests/test_enterprise_recovery_v43_delta_gate.py'='d29b1f755eecfa91cbb17e0b2a159b64b80a918d'
    }
    foreach ($e in $saidas.GetEnumerator()) {
        if ((git hash-object $e.Key) -ne $e.Value) { throw "STOP_V43_RESULTADO:$($e.Key)" }
    }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_DIFF' }
    python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q
    if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_CATRACA_78' }
    $testes = @(
        'tests/test_enterprise_b03_item_reconciliation.py'
        'tests/test_enterprise_b04_icms_st_integral_bridge.py'
        'tests/test_solveris_b01_circuit.py'
        'tests/test_enterprise_b01_atomic_rollback_contract.py'
        'tests/test_enterprise_g1_private_original_contract.py'
        'tests/test_enterprise_g1_coexistence_gate.py'
        'tests/test_enterprise_g12_synthetic_observation_v4_gate.py'
        'tests/test_enterprise_g12_xml_parser_v41_contract.py'
        'tests/test_enterprise_g12_g1_xml_observation_v42_contract.py'
        'tests/test_enterprise_g19_local_cas_custody.py'
        'tests/test_enterprise_recovery_test_gate.py'
        'tests/test_canonical_source_hash.py'
        'tests/test_solveris_mei_vercel_routing_contract_red.py'
    )
    $mei = @(Get-ChildItem tests -Filter 'test_mei_publication_reachability*.py' -File | Select-Object -ExpandProperty FullName)
    python -m pytest -q --tb=short --disable-warnings @testes @mei
    if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_DIRIGIDOS' }
    Write-Host 'V43_CATRACA_78_E_DIRIGIDOS_OK_SEM_GLOBAL_GREEN'
}
```

### Inventário JUnit V4.2 existente (read-only; não espera os dirigidos)

Disponível desde o commit documental `0dec5d7e`: `docs/B03_B04_JUNIT_INVENTARIO_V43_20261118.py`, blob `93764e9de753f641573bc29c5dcee76387acb271`. Não cria ficheiro, não corrige a diferença 34/40 e não ratifica V4.3. Confronta digest baseline, contagens e IDs/RED no JUnit real e emite digests de roster para análise de completude. Executar sem novo pytest global:

```powershell
python docs/B03_B04_JUNIT_INVENTARIO_V43_20261118.py --self-test
if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_INVENTARIO_AUTOTESTE' }
python docs/B03_B04_JUNIT_INVENTARIO_V43_20261118.py --repo . --baseline .pytest_cache/b03b04_baseline_main.xml --candidate .pytest_cache/b03b04_candidate_g12_v42.xml
if ($LASTEXITCODE -ne 0) { throw 'STOP_V43_INVENTARIO_XML' }
```

### Próxima decisão após esta etapa

Somente se os dirigidos passarem: examinar o JUnit **já existente** em `.pytest_cache` para produzir identificação verificável de `testcase`, digests e subtestes antes de escrever o parser derivado V4.3. **Não correr novamente o pytest global ainda.** A catraca V4.2 original conserva a sua recusa quando os hashes vivos são V4.3; nunca invocá-la para afirmar que V4.3 foi ratificada.
