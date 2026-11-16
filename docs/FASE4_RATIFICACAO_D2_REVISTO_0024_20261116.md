# SOLVERIS — Fase 4 — Ratificação D2 revisto (base segregada até 0024, não 0020)

**Data:** 16/11/2026
**Ratificado por:** Miguel
**Substitui parcialmente:** D2 em docs/FASE4_ETAPA3_TAREFAB_RATIFICACAO_D1_D4_20261114.md

## Ratificado

D2 revisto: a base PostgreSQL segregada do escritor ADR-020 pode migrar até `0024_adr020_activation_foundation` (em vez de parar em `0020`), para comportar as tabelas de ativação/decisão soberana (`ActivationDecision`, `ActivationExecution`, `NormativeActivation`, `ActivationGeneration`) necessárias à promoção soberana (P1-P4, docs/FASE4_RATIFICACAO_PROMOCAO_SOBERANA_P1_P4_20261116.md). Confirmado por verificação de código que `0021`-`0024` não têm acoplamento ao B02 (sem referência a `solveris_b02_r4g_test`, `solveris_b02_writer`, `stage_completion`, ou tabelas exclusivas de `0062`). D3 (nunca aplicar `0025`/`0062`, STOP em qualquer necessidade de subir além de `0024`) permanece válido, só o teto sobe de `0020` para `0024`.

## Ressalvas registadas, não resolvidas

1. Uma base parada em `0024` não tem os gates de revisão `0035`/`0036` — a proteção executável completa de P3 (promoção soberana) continua a exigir trabalho próprio antes de qualquer implementação real.
2. `app/models.py` atual contém colunas B02 no metadata dos modelos fundacionais que uma migração parada em `0024` não cria — risco de drift ORM-vs-schema, no mesmo padrão do incidente já registado (schema-drift-incident). Compatibilidade do ORM com esta revisão antiga não está demonstrada e fica pendente de verificação própria.

## Estado

Decisão de arquitetura ratificada nesta data. Nenhum código, base de dados ou migração foi criado ou alterado.
