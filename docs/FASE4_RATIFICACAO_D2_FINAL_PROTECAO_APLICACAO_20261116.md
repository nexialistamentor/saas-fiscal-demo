# SOLVERIS — Fase 4 — Ratificação D2 final (proteção de aplicação em vez de 0035/0036; ORM segregado)

**Data:** 16/11/2026
**Ratificado por:** Miguel
**Completa:** D2 revisto (docs/FASE4_RATIFICACAO_D2_REVISTO_0024_20261116.md)

## Contexto

A cadeia Alembic é linear: chegar a `0035`/`0036` exige passar por `0025`-`0034`, sem atalho pelo caminho normal. A lógica SQL desses dois gates não tem acoplamento B02, mas a mecânica Alembic forçaria a instalação de migrações intermédias (`0026`-`0034`) nunca examinadas quanto a acoplamento B02.

## Ratificado

**(a) Proteção de aplicação, não migração:** a validação equivalente a `0035` (sujeito corresponde exatamente a `RuleVersion`/`NormativeRelationVersion` por ID, versão e hash) e `0036` (existe parecer ligado ao mesmo sujeito, por identificador, hash e versão) é implementada como código de aplicação no serviço novo, não como trigger de base de dados herdado da cadeia Alembic. A base segregada permanece em `0024` (D2 revisto), sem instalar `0025`-`0036`.

**(b) ORM segregado:** o serviço novo usa um conjunto de mapeamentos Python próprio, específico do schema fundacional em `0024`, e nunca reutiliza `app.models` global — que já contém colunas e metadata B02 (`b02_completion_txid`, `b02_policy_txid`, `policy_decision_record_hash`, `policy_activation_generations`, entre outras) misturados nos modelos fundacionais.

## Estado dos requisitos da Tarefa B e da promoção soberana, após esta ratificação

Arquitetura e investigação completas: D1-D4, D2 revisto, D2 final (a+b), P1-P4. Nenhuma implementação, migração, conexão a base de dados ou escrita de código foi realizada em nenhuma destas ratificações. A próxima etapa é abrir a missão de implementação própria, incluindo o preflight em ambiente Postgres descartável.

## Estado

Decisão de arquitetura ratificada nesta data. Nenhum código, base de dados ou migração foi criado ou alterado.
