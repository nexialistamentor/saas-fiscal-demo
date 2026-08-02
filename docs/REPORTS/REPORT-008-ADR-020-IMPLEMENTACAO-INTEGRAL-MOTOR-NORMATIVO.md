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
- Commit 11: `dd1bf973269613047bb9800c9fbaa8d823bb0dca`.

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
- suite global executada após o Commit 11: `2539 passed, 15 skipped, 5 warnings in 106.63s`;
- worktree permaneceu limpo após a suite global.

## Correcção posterior ao Commit 11

O primeiro deploy da cadeia integral revelou uma divergência física na migration `0026_adr020_consumption`: as foreign keys compostas de `generation_fence_records` exigiam chaves candidatas exactas em `activation_executions (activation_execution_id, record_hash)` e `outbox_event_records (outbox_event_id, record_hash)`, mas essas restrições compostas ainda não existiam.

A correcção preservou as foreign keys soberanas de identidade mais hash, acrescentou as duas chaves `UNIQUE` antes da criação de `generation_fence_records`, alinhou o metadata ORM e adicionou teste de regressão.

Commit correctivo:

- `c7c682bfb9ed8d5a2d52f94025d35eb1716fba85` — `fix(adr-020): add exact candidate keys for consumption fences`.

Validações locais posteriores:

- teste isolado de consumo: `8 passed in 0.30s`;
- cadeia ADR-020 completa: `135 passed, 7 skipped in 1.39s`;
- suite global: `2540 passed, 15 skipped, 5 warnings in 97.88s`;
- `git diff --check`: verde;
- integridade UTF-8, sem BOM, LF, sem CR e sem caracteres zero-width;
- worktree limpa após o commit.

## Validação em produção

O branch remoto `origin/main` foi confirmado no commit:

`c7c682bfb9ed8d5a2d52f94025d35eb1716fba85`

A Railway executou com PostgreSQL e DDL transacional a cadeia:

- `0021_adr020_relation_foundation -> 0022_adr020_policy`;
- `0022_adr020_policy -> 0023_adr020_coverage`;
- `0023_adr020_coverage -> 0024_adr020_activation`;
- `0024_adr020_activation -> 0025_adr020_credentials`;
- `0025_adr020_credentials -> 0026_adr020_consumption`;
- `0026_adr020_consumption -> 0027_adr020_calc_replay`.

A aplicação concluiu o startup, o Uvicorn ficou activo na porta `8080` e `GET /health` respondeu `200 OK`.

## Limitações e estado

A estrutura integral da ADR-020 está implementada, testada localmente e validada fisicamente em produção até ao Alembic head `0027_adr020_calc_replay`.

O motor permanece não operacional: sem endpoints operacionais, workers, scheduler, dispatcher, publicação real ou activação normativa autorizada. A validação de produção comprova migrations, startup e saúde da aplicação; não concede autoridade para activação ou consumo operacional.
