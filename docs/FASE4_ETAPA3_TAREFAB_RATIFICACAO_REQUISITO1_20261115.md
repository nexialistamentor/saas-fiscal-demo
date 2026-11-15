# SOLVERIS — Fase 4 / Etapa 3 / Tarefa B — Ratificação do requisito 1 (custódia dos decretos)

**Data:** 15/11/2026
**Ratificado por:** Miguel
**Documento de referência:** docs/FASE4_ETAPA3_TAREFAB_REQUISITO1_VALIDACAO_ITI_20261115.md

## Ratificado

A evidência de custódia dos dois decretos (V1 — Decreto 2.588/2022, DOE-PA nº 35.096; V2 — Decreto 2.931/2023, DOE-PA nº 35.315 extra) é aceite como suficiente para o requisito 1 da Tarefa B:

- Hash SHA-256 real de ambos os ficheiros, após correção do incidente de download corrompido do V2.
- Validação estrutural e de SignatureDictionary aprovadas pelo serviço oficial ITI nos dois ficheiros.
- "Status de assinatura: Reprovado" nos dois aceite como explicado pela ausência de LTV/timestamp em certificados já expirados, não como indício de adulteração — consistente entre duas cadeias de certificação distintas.
- Conteúdo normativo (CEST 03.010.01, MVA 40%) corroborado por fonte secundária independente (PGE-PA).

## Estado dos dois requisitos da Tarefa B após esta ratificação

- Requisito 1 (custódia e hash dos decretos): **ratificado nesta data**.
- Requisito 2 (escritor ADR-020 fora do B02): ratificado em 14/11/2026 (D1-D4, docs/FASE4_ETAPA3_TAREFAB_RATIFICACAO_D1_D4_20261114.md).

Com os dois requisitos ratificados, a Tarefa B (Fase 4, Etapa 3) está concluída no âmbito de investigação e decisão de arquitetura. Implementação do escritor, criação da base PostgreSQL segregada, ou qualquer escrita em NormativeArtifact/ExtractionResult/RuleVersion continuam a exigir missão nova e própria, com escopo e ratificação específica.

## Estado

Nenhum código, base de dados ou migração foi criado ou alterado nesta ratificação.
