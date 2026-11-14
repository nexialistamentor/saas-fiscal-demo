# Verificação ADR-020 — compatibilidade das migrações

**Data:** 14/11/2026
**Repositório:** `nexialistamentor/saas-fiscal-demo`
**Branch examinada:** `cobertura-nacional-jurisdicoes-fase4-cest-remetente`

Conclusão principal: os gates de 0025 e 0062 não são exclusivos da base `solveris_b02_r4g_test`. Aplicam-se às tabelas e funções da base PostgreSQL onde as respetivas migrações tenham sido executadas. Não se propagam automaticamente a outras bases.

## 1. A função de 0062 está limitada ao B02?

Não pelo nome da base; sim pelas tabelas e pelo esquema SQL.

A migração 0062:
- Nas linhas 365–396, executa `CREATE OR REPLACE FUNCTION adr020_require_sanitized_acquisition()`.
- Nas linhas 367–369, referencia explicitamente `public.acquisition_executions`, `public.normative_artifacts` e as tabelas de aquisição B02.
- Nas linhas 406–413, instala triggers adicionais diretamente em `acquisition_executions` e `normative_artifacts`.

Os triggers originais que invocam essa função foram instalados pela migração 0025, nas linhas 38–43, sobre `acquisition_executions` e `extraction_runs`.

Logo, a substituição da função em 0062 altera o comportamento desses triggers na base onde ambos existirem. Não depende de uma verificação de `current_database() = 'solveris_b02_r4g_test'`.

Isto é diferente do serviço Python `stage_completion`, que possui uma restrição explícita de identidade da base e do utilizador.

Limite importante: não se aplica automaticamente a qualquer tabela criada com estrutura semelhante. O trigger precisa estar instalado nessa tabela; a função de 0062 referencia objetos no esquema `public`.

Fonte: Migração 0062, linhas 363–415.

## 2. Numa base nova, sem 0062, o gate de 0025 continua aplicável?

Sim, se 0025 tiver sido instalado. Não, se a base estiver apenas em 0020.

| Migrações instaladas | Função de sanitização | Gate de sanitização |
|---|---|---|
| 0018–0020 | Não criada por essas migrações | Não instalado por 0025 |
| Até 0025 | Versão original de 0025 | Aplicável |
| Até 0062 | Versão substituída por 0062 | Aplicável, com as condições adicionais |

Evidência:
- 0025, linhas 38–43: cria a função e instala os dois triggers.
- 0062, linha 365: substitui a função existente, em vez de criar uma instalação exclusivamente B02.
- 0018–0020: criam as estruturas fundacionais e os seus próprios validadores, sem instalar a função de sanitização de 0025.

Portanto, a ausência de 0062 não elimina o gate de 0025 caso este já exista.

Uma base limitada a 0020 continua sujeita às restrições originais: aquisição efetivamente concluída, verificações documentais exigidas, extração concluída, vínculos exatos e imutabilidade. A ausência do gate de sanitização posterior não elimina esses requisitos.

Fonte: Migração 0025, linhas 22–43.

## 3. Qual é o Alembic head e pode uma base permanecer em 0020?

No código da branch, a revisão final identificada é `0063_adr020_policy_activation_atomicity`. A cadeia relevante é:

`0018 → 0019 → 0020` (Fundações ADR-020)
`0021–0024 → 0025` (Introdução dos gates de sanitização)
`0026–0061 → 0062 → 0063` (Substituição da função e continuação B02)

| Revisão | down_revision |
|---|---|
| 0018_adr020_acq_foundation | 0017_alertas_resolucao |
| 0019_adr020_extraction | 0018_adr020_acq_foundation |
| 0020_adr020_rule_foundation | 0019_adr020_extraction |
| 0025_adr020_credentials | 0024_adr020_activation |
| 0062_adr020_noncredential_acquisition | 0061_enterprise_documental_checkout_intent |
| 0063_adr020_policy_activation_atomicity | 0062_adr020_noncredential_acquisition |

Sim, é possível uma base PostgreSQL ter como revisão aplicada `0020_adr020_rule_foundation`, sem 0025 ou 0062, desde que tenha sido migrada até essa revisão, incluindo os predecessores desde a baseline.

Distinção essencial:
- Head do repositório: revisão terminal do histórico de migrações identificado no código.
- Revisão aplicada numa base: valor efetivamente registado na tabela `alembic_version` dessa base.

A configuração `migrations/env.py`, linhas 9–20 e 59–78, obtém a conexão a partir de `DATABASE_URL`; não fixa a revisão 0063 como revisão instalada em todas as bases.

Não foi consultada a tabela `alembic_version` de nenhuma base; não se afirma qual revisão está efetivamente instalada no B02 ou noutro PostgreSQL.

Fontes: Migração 0063, linhas 1–14 e Configuração Alembic, linhas 9–20.

**Resultado da verificação:** 0062 não é exclusivo do nome da base B02; 0025 continua ativo sem 0062 quando instalado; e uma base PostgreSQL pode parar em 0020, sem ambos os gates posteriores.

Nenhuma escrita, alteração de migração, execução SQL, teste de base ou mudança arquitetural foi realizada.
