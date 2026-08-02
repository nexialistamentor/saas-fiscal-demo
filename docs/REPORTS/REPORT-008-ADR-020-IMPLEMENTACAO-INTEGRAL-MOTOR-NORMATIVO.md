# REPORT-008 — ADR-020 — Implementação integral do motor normativo

## Missão executada

MISSION-008 — execução exclusiva do Commit 11: `test(adr-020): verify sovereign pipeline contracts end to end`.

Baseline inicial: `9eb3b72cacd573d566d1a295e78c1927fd9f021b`.

## Cadeia de commits

- Commit 5: `564b935f0715d9ee33b6538b4d1649bab4f6705b`.
- Commit 6: `55c8a050f064fc4f7d59063f7717fa7a6cd8d570`.
- Commit 7: `441ccb823c0bd90830fced56e49ba2376c969df1`.
- Commit 8: `d0e196277c245c3995a3fee6ec05cf7d0f28d614`.
- Commit 9: `f620f82b8ec4bf20a28f1811b476237d953cb8cc`.
- Commit 10: `9eb3b72cacd573d566d1a295e78c1927fd9f021b`.
- Commit correctivo entre os Commits 10 e 11: `28d604c` — correcção da validação exacta do predecessor de `ActivationGeneration`.
- Commit 11: ainda sem hash durante a criação do próprio relatório.

## Entidades e migrations implementadas

A cadeia ADR-020 existente até ao Commit 10 contém as entidades físicas de referência de artefacto, execução de aquisição, artefacto normativo, verificações do artefacto, execução e resultado de extracção, versões e revisões de regras, relações normativas e respectivas revisões, versões e decisões de políticas, autoridade de bootstrap, contrato, ledger e checkpoint de cobertura, execução e estado de activação de políticas, decisão e execução de activação normativa, activação normativa, geração de activação, evento outbox, versões e eventos de credenciais, acesso e uso de credenciais, recibo sanitizado e sua verificação, fence de geração, contrato consumidor, aplicação consumidora, checkpoint de réplica, bundle e execução de cálculo, resultado, execução de replay e verificação de replay.

As migrations incrementais correspondentes são `0018_adr020_acquisition_foundation` a `0027_adr020_calc_replay`. O Alembic head esperado e validado nesta missão é `0027_adr020_calc_replay`.

## Correcções históricas localizadas

Nos Commits 7–10 foram efectuadas correcções localizadas nos testes históricos de política, cobertura, activação, credenciais e consumo para remover expectativas de ausência de entidades que passaram legitimamente a existir nos commits seguintes e manter delimitado o envelope de cada fundação. Essas correcções não alteraram decisões ratificadas.

Durante a validação integrada do Commit 11 foi comprovada uma divergência física no validator de `ActivationGeneration`: uma comparação encadeada rejeitava incorrectamente a primeira geração, mesmo quando ambos os campos de predecessor estavam ausentes. A expressão foi corrigida localmente e recebeu teste de regressão no commit `28d604c`, sem alteração do contrato ratificado.

## Evidência anterior registada

- Testes do Commit 10: `53 passed, 29 warnings`.
- Cadeia ADR-020 até ao Commit 10: `127 passed, 7 skipped, 29 warnings`.

## Verificação integrada do Commit 11

O teste integrado comprova, usando os modelos, validators e contratos físicos existentes, a cadeia exacta: aquisição, recibo sanitizado, extracção, revisão, decisão, geração activa exacta, fence, contrato consumidor, aplicação consumidora, checkpoint de réplica, bundle de cálculo, execução de cálculo, resultado, execução de replay e verificação de replay.

Também verifica ligações exactas de identidade e hash, referências determinísticas, dependências fixadas, inexistência de resolução `current`/`latest`/`newest`, rejeição de rede, relógio corrente implícito e segredos, bloqueios de divergência, vencimento de fence, parcialidade e checkpoints divergentes, precondições do resultado, preservação do estado e resultado originais no replay, outcomes `match`, `mismatch` e `inconclusive`, impossibilidade de `match` parcial, append-only e ausência de autoridade operacional externa ao contrato ratificado.

Resultados exactos da validação do Commit 11:

- teste integrado: `7 passed in 0.32s`;
- cadeia ADR-020 completa: `134 passed, 7 skipped in 1.76s`;
- Alembic head: `0027_adr020_calc_replay (baseline) (head)`;
- `git diff --check`: verde;
- suite global não executada nesta missão.

## Limitações e estado

Estado local e não operacional. Sem endpoints, workers, scheduler, rede, publicação real, push, deploy ou produção. Não constitui validação de produção nem declaração de suite global verde.
