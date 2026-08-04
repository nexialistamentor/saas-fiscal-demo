# MISSION-010 — ADR-020 — Intenção 9B3 — GREEN da Coerência Exacta entre ActivationGeneration e ActivationExecution — Versão 1.0

## Estado

**PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL**

## 1. Registo documental

- Documento: `MISSION-010-ADR-020-INTENCAO-9B3-GREEN-COERENCIA-DECISAO-EXECUCAO-V1.0`
- Versão: `1.0`
- Estado: `PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL`
- Data: `2026-08-04`
- Baseline: `8fe8620a26f3aecec6e981e69c2c68fcd8c057b5`
- Intenção: `ADR-020 9B3`
- RED: `RED_9B3_VALIDO_LACUNA_FISICA_PROVADA`
- Diagnóstico: `DIAGNOSTICO_9B3_CONCLUIDO_AGUARDA_INSTRUMENTO_GREEN`
- Mecanismo proposto: `FK composta PostgreSQL prospectiva NOT VALID`
- Migration proposta: `0039_adr020_gen_exec_decision_fk`
- Estado GREEN: `NÃO AUTORIZADO`

HEAD e `origin/main` vinculantes:

`8fe8620a26f3aecec6e981e69c2c68fcd8c057b5`

## 2. Autoridade anterior

Esta proposta depende dos seguintes instrumentos, que devem permanecer inalterados:

1. MISSION-009B V1.0: `docs/MISSIONS/MISSION-009B-ADR-020-INTENCAO-9B3-RED-DIAGNOSTICO-V1.0.md`
   - SHA-256: `1F2B7DCE4C599D76B140F8C13CEAC6157F614D1AB7384BF72E68627C8418CF50`
2. REPORT-021: `docs/REPORTS/REPORT-021-RATIFICACAO-MISSION-009B-ADR-020-INTENCAO-9B3-V1.0.md`
   - SHA-256: `42149C981A277AD180F446ED3CD220781CCAEBB5E0911BB6CC5A1B8AC0ABB0BF`
3. REPORT-022: `docs/REPORTS/REPORT-022-ENCERRAMENTO-MISSION-009B-RED-DIAGNOSTICO-9B3-V1.0.md`
   - SHA-256: `91876D15C4CF19D3E5073ACCE19AF7DDFC5F0DF8FFBB488ABF3320C2170A7A84`

## 3. RED vinculante

- Fixture: `postgresql_intention_9b3`
- Teste: `test_activation_generation_rejects_execution_from_different_exact_decision_via_core`
- Ficheiro: `tests/test_adr020_activation_postgresql.py`
- SHA-256 exacto: `1A83719467591FB902BA8823E3B88C18CCDDD1A654F1A650D1E618D720B6DA2E`
- Tamanho exacto: `233737 bytes`
- Comando vinculante:

```text
python -m pytest tests/test_adr020_activation_postgresql.py::test_activation_generation_rejects_execution_from_different_exact_decision_via_core -q
```

- Resultado registado: `1 failed in 7.03s`
- Falha exacta: `Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>`

O corpo semântico deste RED deve permanecer inalterado.

## 4. Lacuna física provada

O PostgreSQL aceita actualmente uma `ActivationGeneration` G com decisão exacta D2 e execução E2, quando E2 pertence exactamente a D1 e D1 é diferente de D2.

As garantias existentes validam separadamente:

- G → D exacta;
- G → E simples;
- E → D exacta.

Não existe garantia física cumulativa que imponha a tripla:

```text
(
  G.activation_execution_id,
  G.activation_decision_id,
  G.activation_decision_record_hash
)
```

como o mesmo vínculo exacto existente em E.

## 5. Decisão de mecanismo proposta

Propõe-se, sem concessão de autoridade para implementação, uma garantia declarativa composta nativa do PostgreSQL. Trigger, função procedural ou listener ORM não podem ser o mecanismo soberano principal.

### 5.1. Chave candidata exacta

Adicionar em `activation_executions`:

- nome: `uq_activation_executions_exact_decision_binding`;
- colunas, nesta ordem exacta:
  1. `activation_execution_id`;
  2. `activation_decision_id`;
  3. `activation_decision_record_hash`.

A chave candidata pode ser criada validada porque `activation_execution_id` já possui identidade única, pelo que a composição tripla não pode gerar duplicidade entre execuções existentes. Ainda assim, custo de DDL, índice e locking deve ser observado durante uma execução devidamente autorizada.

### 5.2. Foreign key composta exacta

Adicionar em `activation_generations`:

- nome: `fk_activation_generations_exact_execution_decision`;
- colunas locais, nesta ordem exacta:
  1. `activation_execution_id`;
  2. `activation_decision_id`;
  3. `activation_decision_record_hash`;
- referência exacta em `activation_executions`, nesta ordem exacta:
  1. `activation_execution_id`;
  2. `activation_decision_id`;
  3. `activation_decision_record_hash`.

A FK proposta deve ser PostgreSQL, prospectiva, `NOT VALID` na base migrada, `MATCH SIMPLE`, `ON UPDATE RESTRICT`, `ON DELETE RESTRICT`, `NOT DEFERRABLE` e `INITIALLY IMMEDIATE`. Deve operar fail-closed para todos os novos `INSERT`s e preservar linhas históricas não auditadas. Nenhuma destas acções referenciais poderá ficar implícita ao executor.

`NOT VALID` não significa constraint inactiva para novas linhas. A FK deve verificar imediatamente todas as linhas novas, sem escanear nem declarar coerente o histórico. Deve permanecer não validada nesta missão; é proibido executar `VALIDATE CONSTRAINT`, reparar ou remover dados históricos.

## 6. Justificação

A FK composta proposta:

- impõe cumulativamente execution ID, decision ID e decision hash;
- cobre ORM, SQLAlchemy Core, SQL cru, `COPY` e bulk inserts por construção;
- usa integridade referencial nativa do PostgreSQL;
- não depende de listeners nem de consulta procedural;
- evita ordem alfabética e máscara entre triggers;
- preserva os triggers históricos;
- não usa `CREATE OR REPLACE`;
- permite política histórica separada;
- produz violação referencial nativa.

Não se deve criar listener ORM adicional nem duplicar testes de cada API apenas para provar uma propriedade já imposta pela mesma FK física, salvo se a implementação revelar uma lacuna.

## 7. Erro esperado

A rejeição deve produzir:

- excepção SQLAlchemy compatível com `DBAPIError`;
- violação PostgreSQL nativa de foreign key;
- SQLSTATE nativo `23503`;
- constraint identificada como `fk_activation_generations_exact_execution_decision`;
- nenhum token soberano customizado;
- nenhuma função ou trigger novo.

O teste GREEN deverá capturar a excepção como `exc_info` e provar cumulativamente:

```python
isinstance(exc_info.value, DBAPIError)
exc_info.value.orig.sqlstate == "23503"
exc_info.value.orig.diag.constraint_name == (
    "fk_activation_generations_exact_execution_decision"
)
```

Permite-se somente adaptação mínima caso o driver exponha `sqlstate` por atributo equivalente documentado. É proibida validação baseada apenas em busca textual da mensagem. O nome da constraint deverá ser provado pelo diagnóstico estruturado do driver.

## 8. Cardinalidade preservada

- Uma `ActivationExecution` continua pertencendo exactamente a uma `ActivationDecision`.
- Uma `ActivationGeneration` continua referenciando exactamente uma `ActivationExecution`.
- `UNIQUE(activation_generations.activation_execution_id)` permanece.
- A nova FK não altera cardinalidade.
- A nova FK apenas impede que G declare uma decisão diferente daquela carregada por E.

## 9. Objectos históricos preservados

É proibido remover, renomear, substituir ou recriar:

- FK exacta G → D;
- FK simples G → E;
- FK exacta E → D;
- `UNIQUE`s existentes;
- checks;
- triggers append-only;
- `trg_activation_generations_validate_insert`;
- funções históricas;
- migrations 0024–0038.

## 10. Migration proposta

- Caminho exacto: `migrations/versions/0039_adr020_activation_generation_decision_execution_fk.py`
- Revision exacta: `0039_adr020_gen_exec_decision_fk`
- Down revision exacta: `0038_adr020_generation_exec_gate`

A migration futura será PostgreSQL e prospectiva e criará exactamente duas constraints lógicas:

1. UNIQUE constraint `uq_activation_executions_exact_decision_binding`;
2. FOREIGN KEY constraint `fk_activation_generations_exact_execution_decision`.

O índice físico criado automaticamente pelo PostgreSQL para suportar a UNIQUE não constitui terceiro objecto lógico, não recebe nome soberano adicional, não autoriza `CREATE INDEX` independente e é consequência física da UNIQUE constraint. Nenhuma outra constraint, índice explícito, função, trigger, tabela ou objecto poderá ser criado.

O início exacto de `upgrade()` deverá possuir:

```python
bind = op.get_bind()
if bind.dialect.name != "postgresql":
    raise RuntimeError(
        "ADR-020 migration 0039 requires PostgreSQL"
    )
```

Não haverá ramo SQLite, no-op ou criação parcial. O `RuntimeError` com a mensagem exacta `ADR-020 migration 0039 requires PostgreSQL` ocorrerá antes de qualquer DDL.

A ordem exacta da migration será:

1. executar o guard PostgreSQL-only;
2. criar `uq_activation_executions_exact_decision_binding`;
3. criar `fk_activation_generations_exact_execution_decision` com `NOT VALID`;
4. terminar sem `VALIDATE CONSTRAINT`.

A UNIQUE deverá existir antes da FK. Toda a execução ocorrerá na transacção Alembic normal. A migration não validará a FK histórica, não auditará nem corrigirá dados, não alterará migrations anteriores e não criará trigger, função, token ou tabela.

O downgrade seguirá a política irreversível ADR-020 já estabelecida e não removerá silenciosamente garantias soberanas.

## 11. Alinhamento de modelo

Ficheiro futuro proposto: `app/models.py`.

Alterações futuras estritamente limitadas a:

- metadata da chave candidata exacta em `ActivationExecution`;
- metadata da FK composta em `ActivationGeneration`;
- preservação integral dos listeners e contratos existentes.

A metadata SQLAlchemy futura deverá declarar explicitamente na FK:

```python
onupdate="RESTRICT"
ondelete="RESTRICT"
deferrable=False
initially="IMMEDIATE"
```

A migration deverá emitir as mesmas propriedades exactas, incluindo `MATCH SIMPLE`. Metadata e migration deverão ser idênticas quanto a nomes, colunas, ordem, `MATCH SIMPLE`, `ON UPDATE RESTRICT`, `ON DELETE RESTRICT`, `NOT DEFERRABLE`, `INITIALLY IMMEDIATE` e schema corrente.

Em bases novas criadas directamente por `metadata.create_all`, a FK nasce validada porque não existe histórico anterior. Em bases migradas, a migration permanece a fonte da propriedade `NOT VALID`. Esta é a única diferença deliberada e não autoriza divergência em qualquer outra propriedade.

## 12. Testes futuros propostos

Ficheiro: `tests/test_adr020_activation_postgresql.py`.

A autorização GREEN futura poderá modificar somente o necessário para:

1. introduzir a constante exacta da revision 0039;
2. fazer a fixture `postgresql_intention_9b3` alcançar a revision 0039;
3. manter o RED existente com o mesmo cenário, controlo positivo, falsidade única e `pytest.raises(DBAPIError)`;
4. adicionar prova física da chave candidata e da FK composta;
5. adicionar prova de que a FK está `NOT VALID`;
6. adicionar prova prospectiva antes/depois da migration.

Preservar exactamente:

`test_activation_generation_rejects_execution_from_different_exact_decision_via_core`

Adicionar com nomes exactos:

- `test_activation_generation_decision_execution_fk_is_physical_and_not_valid`;
- `test_activation_generation_decision_execution_fk_is_prospective`.

### 12.1. Prova física

Sem criar quarto teste, `test_activation_generation_decision_execution_fk_is_physical_and_not_valid` deverá exigir:

1. revision exacta `0039_adr020_gen_exec_decision_fk`;
2. down revision exacta `0038_adr020_generation_exec_gate`;
3. guard PostgreSQL-only antes do DDL;
4. `RuntimeError` exacto do guard;
5. `downgrade()` que sempre levanta o `RuntimeError` exacto;
6. ausência de `DROP` no downgrade;
7. ausência de no-op no downgrade;
8. ausência de `VALIDATE CONSTRAINT`;
9. ausência de `CREATE INDEX` explícito;
10. exactamente as duas constraints lógicas autorizadas;
11. `MATCH SIMPLE`;
12. `ON UPDATE RESTRICT`;
13. `ON DELETE RESTRICT`;
14. `NOT DEFERRABLE`;
15. `INITIALLY IMMEDIATE`;
16. UNIQUE com nome, colunas e ordem exactos;
17. FK com nome, colunas locais, colunas referenciadas e ordem exactos;
18. `convalidated false`;
19. `condeferrable false`;
20. `condeferred false`.

A prova poderá combinar leitura estática da migration, importação controlada da revision e introspecção do catálogo PostgreSQL.

### 12.2. Prova prospectiva

O teste deve:

1. migrar somente até 0038;
2. criar uma cadeia coerente de controlo;
3. criar uma geração historicamente incoerente aceite em 0038;
4. migrar para 0039;
5. confirmar preservação dessa linha histórica;
6. confirmar que a FK continua não validada;
7. tentar nova incoerência exacta e exigir `DBAPIError`;
8. confirmar SQLSTATE `23503` e o nome exacto da constraint;
9. inserir nova geração coerente;
10. confirmar persistência do controlo positivo.

IDs, `record_hashes`, `idempotency_keys`, `scope_hashes`, `composition_hashes` e execution IDs deverão ser distintos entre controlo, linha histórica e novas linhas, evitando colisões alheias. A nova incoerência deverá falhar exclusivamente pela constraint `fk_activation_generations_exact_execution_decision`. A nova geração coerente deverá usar uma execução ainda não consumida por `UNIQUE(activation_execution_id)`.

A prova vinculante mínima será RED/GREEN por SQLAlchemy Core, introspecção física exacta no catálogo PostgreSQL e cenário prospectivo antes/depois da migration.

## 13. Histórico

- Não há auditoria histórica nesta missão.
- Não há `VALIDATE CONSTRAINT`.
- Não há reparação histórica.
- Não há exclusão ou actualização de linhas append-only.
- A existência de incoerências históricas continua desconhecida.
- Eventual auditoria e validação exigem instrumento separado.
- A FK `NOT VALID` permanece activa para novas linhas.

## 14. Downgrade

A decisão proposta é de migration soberana irreversível. `downgrade()` deverá ser exactamente irreversível, nunca executar `DROP` ou no-op, e possuir o seguinte corpo semântico obrigatório:

```python
def downgrade() -> None:
    raise RuntimeError(
        "ADR-020 migration 0039 is irreversible: "
        "exact generation-execution-decision binding cannot be removed"
    )
```

A quebra física de linha da string poderá seguir formatação Python, mas a mensagem final deverá ser exactamente `ADR-020 migration 0039 is irreversible: exact generation-execution-decision binding cannot be removed`. Qualquer reversão exigirá instrumento soberano próprio.

## 15. Escopo técnico futuro exacto

Somente:

1. `migrations/versions/0039_adr020_activation_generation_decision_execution_fk.py`;
2. `app/models.py`;
3. `tests/test_adr020_activation_postgresql.py`.

Nenhum outro ficheiro técnico poderá ser alterado sem nova autorização.

## 16. Sequência futura obrigatória

Após ratificação humana exacta, registada e publicada desta MISSION-010:

1. verificar baseline e hashes;
2. declarar GREEN exacto;
3. implementar somente migration e metadata autorizadas;
4. preservar semanticamente o RED;
5. executar primeiro somente `test_activation_generation_rejects_execution_from_different_exact_decision_via_core`;
6. exigir que passe pela nova FK exacta;
7. executar os dois testes físicos/prospectivos exactos;
8. executar a regressão PostgreSQL ADR-020 autorizada;
9. executar regressão ADR-020;
10. executar regressão global;
11. verificar integrity, diff e escopo;
12. produzir REPORT separado;
13. manter staging, commit e push manuais pelo utilizador.

Nenhuma etapa posterior pode começar antes da anterior ser validada.

Os comandos exactos das regressões devem ser confirmados contra os marcadores e a estrutura real antes da execução. Devem ocorrer, em etapas separadas: teste GREEN exacto; testes físicos/prospectivos 9B3; ficheiro PostgreSQL ADR-020; suite ADR-020; suite global.

Nenhum teste é executado nesta rodada documental.

## 17. Critérios de GREEN

GREEN válido somente se:

- G_control coerente persiste;
- G_false é rejeitada;
- a rejeição ocorre pela nova FK composta exacta;
- SQLSTATE é `23503`;
- o nome da constraint é exacto;
- nenhuma garantia anterior mascara a causa;
- a FK física possui as colunas e ordem exactas;
- a FK está `NOT VALID`;
- a linha histórica incoerente permanece preservada;
- a nova linha incoerente é rejeitada;
- a nova linha coerente é aceite;
- migrations 0024–0038 permanecem inalteradas;
- nenhum trigger ou listener novo é usado como autoridade principal.

GREEN inválido se causado por:

- `UNIQUE` não relacionada;
- FK G → D;
- FK simples G → E;
- FK E → D;
- check;
- trigger existente;
- campo ausente;
- hash inválido;
- fixture;
- Docker;
- conexão;
- erro de migration;
- segunda falsidade;
- alteração material do cenário RED.

## 18. Fronteiras

### 18.1. Permitido somente após ratificação

- somente os três ficheiros técnicos listados;
- migration 0039 exacta;
- metadata exacta;
- alteração mínima da fixture;
- preservação do teste RED;
- dois testes adicionais exactos;
- testes e regressões autorizados;
- REPORT final separado.

### 18.2. Proibido mesmo após ratificação

- triggers novos;
- funções PostgreSQL novas;
- `CREATE OR REPLACE` de objectos históricos;
- listener ORM novo;
- token customizado;
- alteração de migrations 0024–0038;
- `VALIDATE CONSTRAINT`;
- auditoria ou reparação histórica;
- alteração destrutiva;
- tabelas novas;
- endpoints;
- workers;
- scheduler;
- dispatcher;
- deploy;
- Railway;
- produção;
- activação do motor;
- abertura de gates;
- 9B2;
- 9B4;
- 9C;
- 8B2;
- MIGRATION-BOOTSTRAP-0000-0001;
- `docs/ROADMAP_OPS_AGENTES.md`;
- qualquer ficheiro não listado;
- staging, commit ou push pelo Codex.

### 18.3. Fronteira de privilégios

A cobertura ORM, SQLAlchemy Core, SQL cru, `COPY` e bulk inserts pressupõe operação PostgreSQL normal com constraints activas. Utilizadores privilegiados capazes de desactivar triggers internos, alterar `session_replication_role` ou modificar DDL estão fora da fronteira operacional normal e não constituem lacuna 9B3 da constraint. Isto não autoriza tais operações nem reduz a obrigação de controlo de privilégios.

## 19. Autoridade

Este documento é apenas uma proposta. A criação do ficheiro não autoriza implementação. Auditoria não autoriza implementação. Congelamento não autoriza implementação. Publicação não substitui ratificação humana.

Somente ratificação humana exacta, registada e publicada poderá tornar a missão executável. Qualquer divergência de bytes invalida a autoridade. A ratificação deve citar versão, SHA-256, mecanismo, migration, constraints, ficheiros e fronteiras exactas.

Até essa ratificação, o GREEN permanece não autorizado, o motor permanece inactivo e nenhum gate é aberto.

## 20. Integridade documental

- O documento não inclui self-hash.
- O SHA-256 será calculado externamente após auditoria.
- A codificação exigida é UTF-8 sem BOM.
- Os finais de linha exigidos são LF, com zero CRLF e zero CR isolado.
- Deve existir exactamente uma newline final.
- Deve existir zero trailing whitespace.

## 21. Veredicto documental

`MISSION_010_CORRIGIDA_AGUARDA_NOVA_AUDITORIA`
