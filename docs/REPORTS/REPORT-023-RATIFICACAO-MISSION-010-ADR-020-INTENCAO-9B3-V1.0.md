# REPORT-023 — Ratificação Humana da MISSION-010 — ADR-020 — Intenção 9B3 — Versão 1.0

## Estado

RATIFICAÇÃO HUMANA REGISTADA — AGUARDA PUBLICAÇÃO DOCUMENTAL — NÃO EXECUTÁVEL

## Registo documental

- Documento: `REPORT-023-RATIFICACAO-MISSION-010-ADR-020-INTENCAO-9B3-V1.0`
- Versão: `1.0`
- Estado: `RATIFICAÇÃO HUMANA REGISTADA — AGUARDA PUBLICAÇÃO DOCUMENTAL — NÃO EXECUTÁVEL`
- Data: `2026-08-04`
- Baseline: `8fe8620a26f3aecec6e981e69c2c68fcd8c057b5`

## MISSION ratificada

- Caminho: `docs/MISSIONS/MISSION-010-ADR-020-INTENCAO-9B3-GREEN-COERENCIA-DECISAO-EXECUCAO-V1.0.md`
- Versão: `1.0`
- SHA-256 exacto: `485E116AD20DE1BDCF2304059D121C909E491D2004E2712B7D55C7E329B38724`
- Tamanho exacto: `18708 bytes`
- Estado interno preservado nos bytes: `PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL`

Esse estado interno não será alterado porque os bytes foram congelados antes da ratificação. A ratificação e a publicação são provadas externamente por este REPORT e pelo histórico Git.

## Autor e declaração humana

O autor da ratificação é Miguel.

Miguel declarou humana e expressamente a ratificação da MISSION-010 V1.0, citando caminho, SHA-256, tamanho, mecanismo, migration, constraints, ficheiros e fronteiras exactas.

Este REPORT regista a ratificação; não é a fonte constitutiva da decisão humana.

## Mecanismo ratificado

Regista-se exclusivamente:

1. A UNIQUE constraint `uq_activation_executions_exact_decision_binding`, sobre, nesta ordem exacta:
   - `activation_execution_id`
   - `activation_decision_id`
   - `activation_decision_record_hash`

2. A FOREIGN KEY constraint `fk_activation_generations_exact_execution_decision`, com colunas locais, nesta ordem exacta:
   - `activation_execution_id`
   - `activation_decision_id`
   - `activation_decision_record_hash`

   referenciando, na mesma ordem exacta:
   - `activation_executions.activation_execution_id`
   - `activation_executions.activation_decision_id`
   - `activation_executions.activation_decision_record_hash`

## Propriedades ratificadas

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID` somente na base migrada;
- SQLSTATE nativo `23503`;
- nenhum token customizado.

## Migration ratificada

- Caminho: `migrations/versions/0039_adr020_activation_generation_decision_execution_fk.py`
- Revision: `0039_adr020_gen_exec_decision_fk`
- Down revision: `0038_adr020_generation_exec_gate`

## Guard ratificado

Antes de qualquer DDL:

```python
bind = op.get_bind()
if bind.dialect.name != "postgresql":
    raise RuntimeError(
        "ADR-020 migration 0039 requires PostgreSQL"
    )
```

Mensagem final exacta: `ADR-020 migration 0039 requires PostgreSQL`

Ficam registados:

- nenhum ramo SQLite;
- nenhum no-op;
- nenhuma criação parcial;
- `RuntimeError` antes de qualquer DDL.

## Downgrade ratificado

`downgrade()` deverá sempre levantar `RuntimeError`, sem DROP e sem no-op.

Mensagem final exacta: `ADR-020 migration 0039 is irreversible: exact generation-execution-decision binding cannot be removed`

## Objectos lógicos ratificados

Existem exactamente duas constraints lógicas:

1. `uq_activation_executions_exact_decision_binding`;
2. `fk_activation_generations_exact_execution_decision`.

O índice físico automático da UNIQUE:

- não constitui terceiro objecto lógico;
- não autoriza `CREATE INDEX` independente;
- não recebe autoridade soberana separada.

Permanecem proibidos:

- função PostgreSQL;
- trigger PostgreSQL;
- listener ORM;
- token customizado;
- `VALIDATE CONSTRAINT`;
- tabela nova;
- qualquer outro objecto físico.

## Ficheiros técnicos ratificados

Após registo, congelamento e publicação documental, somente:

1. `migrations/versions/0039_adr020_activation_generation_decision_execution_fk.py`
2. `app/models.py`
3. `tests/test_adr020_activation_postgresql.py`

Nenhum outro ficheiro técnico está autorizado.

## RED preservado

- Teste: `test_activation_generation_rejects_execution_from_different_exact_decision_via_core`
- Fixture: `postgresql_intention_9b3`
- SHA-256 do ficheiro actual: `1A83719467591FB902BA8823E3B88C18CCDDD1A654F1A650D1E618D720B6DA2E`
- Tamanho: `233737 bytes`

O corpo semântico do RED deve permanecer preservado.

## Testes ratificados

Criação exclusiva de:

- `test_activation_generation_decision_execution_fk_is_physical_and_not_valid`
- `test_activation_generation_decision_execution_fk_is_prospective`

A prova deverá abranger:

- revision e down_revision;
- guard e mensagem exactos;
- downgrade e mensagem exactos;
- ausência de DROP;
- ausência de no-op;
- ausência de `VALIDATE CONSTRAINT`;
- ausência de `CREATE INDEX` independente;
- exactamente duas constraints lógicas;
- nomes, colunas e ordem;
- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `convalidated false`;
- `condeferrable false`;
- `condeferred false`;
- SQLSTATE `23503`;
- diagnóstico estruturado do nome da constraint;
- preservação de linha histórica incoerente;
- rejeição de nova incoerência;
- aceitação de nova geração coerente.

## Histórico

- nenhuma auditoria histórica autorizada;
- nenhuma reparação histórica;
- nenhuma eliminação histórica;
- nenhuma actualização de linhas append-only;
- nenhuma validação da FK histórica;
- a existência de incoerências históricas permanece desconhecida;
- qualquer auditoria ou `VALIDATE` exigirá instrumento separado;
- `NOT VALID` permanece activa para linhas novas.

## Proibições ratificadas

Permanecem proibidos:

- qualquer ficheiro técnico não listado;
- alteração das migrations 0024–0038;
- triggers ou funções PostgreSQL;
- listener ORM;
- token customizado;
- `VALIDATE CONSTRAINT`;
- auditoria, reparação ou eliminação histórica;
- alterações destrutivas;
- tabelas novas;
- endpoints;
- workers;
- scheduler;
- dispatcher;
- deploy;
- Railway;
- produção;
- activação do motor ADR-020;
- abertura de gates;
- 9B2;
- 9B4;
- 9C;
- 8B2;
- MIGRATION-BOOTSTRAP-0000-0001;
- `docs/ROADMAP_OPS_AGENTES.md`;
- staging, commit ou push pelo Codex.

## Condição de executabilidade

Cumulativamente:

1. a ratificação humana já foi emitida;
2. este REPORT apenas a regista;
3. a MISSION-010 e este REPORT ainda precisam ser:
   - auditados;
   - congelados;
   - staged manualmente;
   - commitados manualmente;
   - publicados em `origin/main`;
4. somente após essa publicação a MISSION-010 poderá tornar-se executável;
5. até à publicação:
   - GREEN não autorizado;
   - migration 0039 inexistente e não autorizada;
   - motor desligado;
   - gates bloqueados.

## Publicação

A publicação futura:

- não altera os bytes congelados;
- fornece inclusão, cronologia e integridade documental;
- torna verificável o vínculo entre a declaração humana e a missão;
- não amplia o escopo ratificado;
- não autoriza matérias adjacentes.

## Integridade

- este documento não inclui self-hash;
- o SHA-256 será calculado externamente após auditoria;
- codificação UTF-8 sem BOM;
- finais de linha LF;
- zero CRLF;
- zero CR isolado;
- uma newline final;
- zero trailing whitespace.
