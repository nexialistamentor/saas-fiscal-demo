# SOLVERIS Enterprise — diagnóstico diferencial global V4.2 (18/11/2026)

Aditamento ao STOP `docs/B03_B04_STOP_V42_GLOBAL_20261118.md`; sem autorizar V4.2, deploy, `main`, novas regras fiscais ou alterações MEI.

## Leitura exclusiva dos JUnit originais (Miguel/Windows)

| JUnit | `tests` declarado | `testcase` direto | Diferença | Identidades duplicadas | Subtestes do pytest |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline `b03b04_baseline_main.xml` | 4136 | 4102 | 34 | 0 | 34 |
| Candidato `b03b04_candidate_g12_v42.xml` | 4683 | 4643 | 40 | 0 | 40 |

A diferença coincide **exatamente** com os subtestes em ambas as execuções. Em `tools/enterprise_recovery_test_gate.py::parse_junit`, `declared` acumula `testsuite.tests`, `results` conta somente `testcase` diretos, e `if declared != len(results)` lança `JUNIT_INCOMPLETE_OR_DUPLICATED`. Nenhum ID duplicado foi observado. Logo, o nome de STOP inclui `DUPLICATED`, mas **o dado observado é descompasso de contagem**; os 34 e 40 subtestes explicam a diferença. Isso não autoriza relaxar o controlo de truncamento: um futuro parser V4.3 tem de provar independentemente os subtestes contabilizados.

## Cotejo das falhas com os 13 IDs ratificados

Leitura local do texto da execução entregue por Miguel, cruzando os 84 IDs `FAILED tests/...` com `accepted_failure_ids` de `docs/B03_B04_BASELINE_ESCOPO_TRANSACIONAL_V2_20261118.json`:

- **84 falhas distintas** reportadas.
- **13/13 IDs históricos** também presentes.
- **71 novos IDs RED**: **69** sob `tests.test_mei_publication_reachability_*`, **1** `tests.test_canonical_source_hash::test_no_absolute_source_text_hash_bypasses_canonical_helper`, **1** `tests.test_solveris_mei_vercel_routing_contract_red::test_legacy_mei_route_is_not_reopened`.
- A saída apresenta **61 ocorrências** do motivo `MEI_REACHABILITY_UNRESOLVED_FISCAL_XML:empresa_guard`; nem todas as 69 novas falhas desse conjunto necessariamente se reduzem a essa mensagem.

A certidão por JUnit deve permanecer a fonte final de classificação, mas a saída textual cobre 84 IDs únicos e os 13 ratificados.

## Relações causais de fonte lida

1. `app/scripts/mei_publication_reachability_census.py` exige `ast.If(test=ast.Name(id='empresa_id'))` que contenha importação, criação e chamada `InsightEngine`. O B01 candidato alterou a condição histórica `if empresa_id:` para `if empresa_id and not enterprise_opt_in:`. O segundo produz `ast.BoolOp`, quebrando a forma comprovada pelo scanner. O delta original está em `app/services/registro_analise_service.py`. Uma V4.3 pode **avaliar** guarda externa `if empresa_id` com subcondição interna `if not enterprise_opt_in`, preservando a exclusão de insights durante a transação empresarial e sem tocar no scanner MEI.
2. **Causa canónica confirmada em leitura estática local:** a função de deteção `_find_violations` do teste `tests/test_canonical_source_hash.py` devolve **exatamente dois locais**: `tests/test_enterprise_g19_local_cas_custody.py:267` (SHA-256 direto de PDF temporário) e `tests/test_enterprise_recovery_test_gate.py:205` (SHA-256 direto de XML temporário). O primeiro pode comparar os bytes esperados; no segundo, pode-se calcular o hash a partir do literal XML enquanto a verificação do conteúdo do ficheiro permanece no helper canónico. Estas são opções para teste-only versionado, nunca exclusão do teste ou exceção genérica ao scanner.
3. `tests/test_solveris_mei_vercel_routing_contract_red.py` exige `frontend-dashboard/vercel.json.git.deploymentEnabled == {"main": false}`, enquanto o candidato adicionou `"recovery/enterprise-b00-b04-20261117": false`. É conflito explícito entre uma asserção de rota legada e o hold de deploy do branch. **Não remover o hold para esverdear o teste** sem outra prova de não deploy.
4. O `GLOBAL_TEST_EXIT=1` e `ENTERPRISE_RECOVERY_STATUS=BLOCKED` continuam corretos. Ainda que o JUnit seja reinterpretado com contabilização segura de subtestes, as **71 novas falhas** bloqueiam o gate por mérito.

## Decisão pendente

Preparar escopo separado V4.3 com testes negativos sobre adaptação JUnit e a guarda B01, documentando expressamente os conflitos de hash-canónico e release hold. Proibido alterar os controles originais silenciosamente, editar MEI, falsificar contagens, promover `GLOBAL_GREEN` ou apagar os recibos/artefactos Windows.

## Inventário real JUnit V4.3 confirmado por Miguel/Windows (18/11/2026)

Ferramenta documental de leitura `docs/B03_B04_JUNIT_INVENTARIO_V43_20261118.py` (blob `93764e9de753f641573bc29c5dcee76387acb271`) passou o autoteste e cotejou ambos os XMLs existentes, sem executar novamente `pytest`.

| Medida criptográfica | Baseline V2 | Candidato V4.2 |
| --- | --- | --- |
| SHA-256 JUnit | `798a14e3a2c6c517dd179559395a12e7fc370cdb49eb2fa3bd674b1599523692` | `a6fca42e30dcfce0266dfdfeb815f43c064c1ae3d10de1efddce3a93d778c40c` |
| SHA-256 dos IDs ordenados | `cbe90815208fe583e305f2f409e53a75ee658e50def7d30378834bf528fcdea3` | `74df9a9d8cddb7aa5db88cec1493a2b2446a4a4dad72787910b1580b286378ca` |
| SHA-256 dos IDs RED ordenados | `ccd8df42d4b24e30f789cba46695422fbd97e8678134449be0e0590aa7a5fd8d` | `f79bd83bc5d1cd6155ffab65f22f21f457e00fb2b5e00fe671eff080e8decf3c` |

SHA-256 dos 71 IDs RED adicionais: `fff5f2073f20a082328f33eed8d0110ca4477361633604e131ddd98d5d79d9bd`.

`baseline_ids_subconjunto=true`, `historic_red=13`, `new_red=71`, `testes_duplicados=0`, `status=DIAGNOSTIC_ONLY_NOT_GREEN`. Mantém-se `subtestes_nao_provados_pelo_xml=true`: igualdade aritmética 34/40 com a contagem da saída pytest não é prova autónoma de completude. A correção V4.3 e o parser derivado continuam subordinados aos gates específicos; **nenhum GLOBAL_GREEN**.

