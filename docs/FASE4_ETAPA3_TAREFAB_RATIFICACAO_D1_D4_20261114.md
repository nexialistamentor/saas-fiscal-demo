# SOLVERIS — Fase 4 / Etapa 3 / Tarefa B — Ratificação D1–D4 (decisão de arquitetura)

**Data:** 14/11/2026
**Ratificado por:** Miguel
**Documento de referência:** docs/FASE4_ETAPA3_TAREFAB_PROPOSTA_ESCRITOR_ADR020_20261113.md
**Verificação de compatibilidade (base desta decisão):** docs/FASE4_ETAPA3_TAREFAB_VERIFICACAO_COMPATIBILIDADE_20261114.md

## Decisões ratificadas

- **D1 — Arquitetura:** ratificado serviço novo, operacional, independente de `stage_completion`, com motor de custódia ADR-020 fundacional próprio, sem ligação ao motor de cálculo.
- **D2 — Persistência de ensaio:** ratificado PostgreSQL segregado como alvo futuro de prova de escrita, migrado apenas até `0020_adr020_rule_foundation`, nunca aplicando `0025` ou `0062`. `test.db` SQLite permanece fora do caminho operacional ADR-020.
- **D3 — Fronteira B02:** ratificado que qualquer necessidade futura de subir essa base além de `0020` provoca STOP automático e novo parecer — nunca adaptação das restrições B02 nem fabrico de recibos de sanitização.
- **D4 — Escopo:** ratificado que o escritor atende, nesta fase, somente duas versões históricas documentais para CEST `0301001` + remetente distribuidor/atacadista (V1 Decreto 2.588/2022, V2 Decreto 2.931/2023), sem autoridade fiscal até as verificações específicas (secção 7 da proposta) ficarem completas.

## Limite explícito desta ratificação

Esta ratificação é de arquitetura, não de execução. NÃO autoriza, por si só:
- criar a base PostgreSQL segregada;
- escrever código do escritor;
- inserir qualquer registo em NormativeArtifact, ExtractionResult ou RuleVersion;
- interromper ou alterar qualquer cadeia de migrações existente.

Qualquer um destes passos exige missão própria, com escopo e ratificação específica, seguindo a disciplina de "uma branch por intenção".

## Pendências que continuam a bloquear a implementação

1. Hash SHA-256 real e custodiado dos PDFs (DOE-PA 30/08/2022 e 07/03/2023) — confirmação independente por segundo download ainda não realizada.
2. Prova de compatibilidade dos triggers `0018`–`0020` (não apenas `0025`/`0062`) em ambiente descartável real, antes de qualquer escrita.
3. Rotação de credenciais ainda pendente (Postgres Railway, INLABS_PASS/cookies) — sem relação direta com esta ratificação, mas continua aberta desde o handoff anterior.

## Fecho da missão (GPT, Fase 4 / Etapa 3 / Tarefa B, requisito 2)

Com esta ratificação, a missão de investigação do escritor ADR-020 fora do B02 está formalmente **fechada**. Qualquer trabalho a partir daqui (criar a base, implementar o escritor, resolver o requisito 1 de hash) é missão nova e separada, com escopo e ratificação próprios.

## Estado

Decisão de arquitetura ratificada nesta data. Nenhum código, base de dados, migração ou registo foi criado ou alterado.
