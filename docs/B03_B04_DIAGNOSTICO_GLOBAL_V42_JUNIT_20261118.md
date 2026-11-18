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
2. `tests/test_canonical_source_hash.py` reprova leitura/sha256 bruto de fontes no conjunto de testes. Existe caso novo em `tests/test_enterprise_recovery_test_gate.py::test_baseline_junit_digest_is_immutable` usando `hashlib.sha256(path.read_bytes())`; o alvo é XML temporário, mas a análise estática pode considerá-lo desconhecido. É hipótese de causa, ainda não demonstrada pela lista `violations=[...]`; não fazer alteração sem a prova.
3. `tests/test_solveris_mei_vercel_routing_contract_red.py` exige `frontend-dashboard/vercel.json.git.deploymentEnabled == {"main": false}`, enquanto o candidato adicionou `"recovery/enterprise-b00-b04-20261117": false`. É conflito explícito entre uma asserção de rota legada e o hold de deploy do branch. **Não remover o hold para esverdear o teste** sem outra prova de não deploy.
4. O `GLOBAL_TEST_EXIT=1` e `ENTERPRISE_RECOVERY_STATUS=BLOCKED` continuam corretos. Ainda que o JUnit seja reinterpretado com contabilização segura de subtestes, as **71 novas falhas** bloqueiam o gate por mérito.

## Decisão pendente

Preparar escopo separado V4.3 com testes negativos sobre adaptação JUnit e a guarda B01, documentando expressamente os conflitos de hash-canónico e release hold. Proibido alterar os controles originais silenciosamente, editar MEI, falsificar contagens, promover `GLOBAL_GREEN` ou apagar os recibos/artefactos Windows.
