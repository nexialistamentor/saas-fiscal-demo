# MISSION-013 — ADR-020 — Intenção 9B4 — FK Directa NormativeActivation–ActivationExecution NOT VALID — Versão 1.0

## 1. Identificação

- Documento: `MISSION-013-ADR-020-INTENCAO-9B4-FK-DIRETA-NORMATIVE-ACTIVATION-EXECUTION-NOT-VALID-V1.0`
- Versão: `1.0`
- Data: `2026-08-05`
- Intenção: `ADR-020 9B4`
- Natureza: missão documental para futura protecção prospectiva
- Estado: **RATIFICADA DOCUMENTALMENTE — IMPLEMENTAÇÃO TÉCNICA PROVADA — AGUARDA PUBLICAÇÃO CANÓNICA**

Esta missão regista a intenção técnica 9B4 ratificada por Miguel e a ratificação documental concluída em 2026-08-06. A implementação técnica foi executada e provada dentro da fronteira aprovada. Permanecem proibidos deploy, operação de produção, validação histórica, ampliação de escopo e qualquer autoridade não prevista nesta missão; a publicação canónica será realizada em commits separados conforme o precedente da MISSION-012.

## 2. Objectivo futuro único

A futura implementação deverá criar uma FK composta directa em `normative_activations` para garantir que a execução e a decisão exacta declaradas por uma nova activação correspondem cumulativamente ao mesmo registo existente em `activation_executions`.

A FK terá as colunas locais, nesta ordem exacta:

1. `activation_execution_id`;
2. `activation_decision_id`;
3. `activation_decision_record_hash`.

A tabela autoridade será `activation_executions`, com as colunas referenciadas na mesma ordem exacta:

1. `activation_execution_id`;
2. `activation_decision_id`;
3. `activation_decision_record_hash`.

## 3. Chave candidata existente

A FK deverá utilizar exclusivamente a chave candidata tripla já existente:

`uq_activation_executions_exact_decision_binding`

É proibido criar nova `UNIQUE`, novo índice explícito ou chave candidata alternativa para esta intenção.

## 4. Contrato físico obrigatório

A futura FK composta terá obrigatoriamente o nome exacto:

`fk_normative_activations_exact_execution_decision`

A futura FK deverá possuir cumulativamente:

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID`.

`NOT VALID` preserva o histórico não auditado e protege prospectivamente novas escritas. A futura implementação não poderá executar `VALIDATE CONSTRAINT`.

## 5. Preservação integral

A futura alteração deverá preservar integralmente, sem remover, renomear, substituir, recriar ou enfraquecer:

- `fk_normative_activations_execution`;
- `fk_normative_activations_activation_generation`;
- todas as constraints introduzidas ou preservadas pelas migrations `0038`, `0039` e `0040`;
- todas as FKs simples e compostas já existentes.

A nova FK será adicional e directa. Não substituirá a FK simples entre `normative_activations` e `activation_executions`, nem a FK entre `normative_activations` e `activation_generations`, nem as garantias exactas já existentes entre decisão, geração e execução.

## 6. Histórico

Esta missão não autoriza auditar, reparar, actualizar, remover ou declarar coerentes dados históricos. Não autoriza backfill, saneamento retroactivo ou validação retroactiva.

O estado obrigatório do histórico permanece:

`HISTORICO_NAO_VALIDADO`

A auditoria histórica e eventual `VALIDATE CONSTRAINT` pertencem a missão futura independente, com autoridade própria. A existência ou ausência de incoerências históricas não é declarada neste documento.

## 7. Migration futura reservada

Fica reservada como candidata técnica, sem autorização presente para criação:

- ficheiro: `migrations/versions/0041_adr020_norm_exec_dec_fk.py`;
- revision: `0041_adr020_norm_exec_dec_fk`;
- down revision: `0040_adr020_norm_gen_decision_fk`.

O `downgrade()` deverá ser bloqueado por `RuntimeError`, seguindo o precedente soberano das migrations anteriores. Não poderá remover silenciosamente a garantia.

Esta missão documental não cria a migration `0041` e não autoriza DDL.

## 8. RED estrutural futuro

Após nova ordem expressa e dentro da sequência vinculada, deverá ser criado no ficheiro existente `tests/test_adr020_activation_postgresql.py` exactamente o teste:

`test_normative_activation_has_direct_exact_execution_decision_fk_not_valid`

O RED estrutural deverá provar inicialmente a ausência da constraint directa. Depois da implementação, o mesmo teste deverá provar cumulativamente:

1. existência da FK;
2. tabela local `normative_activations` e tabela referenciada `activation_executions`;
3. três colunas locais e referenciadas na ordem exacta definida nesta missão;
4. `MATCH SIMPLE`;
5. `ON UPDATE RESTRICT`;
6. `ON DELETE RESTRICT`;
7. `NOT DEFERRABLE`;
8. `INITIALLY IMMEDIATE`;
9. `convalidated = false`;
10. preservação das FKs e constraints existentes;
11. utilização da chave candidata tripla existente `uq_activation_executions_exact_decision_binding`.

O RED e o GREEN serão exclusivamente provas estruturais da ausência e da posterior presença do contrato físico exacto. Não é exigido um segundo teste comportamental autónomo. Nenhuma divergência pode satisfazer simultaneamente as constraints das migrations `0038`, `0039` e `0040` e violar apenas a FK directa. Atribuir uma rejeição exclusivamente à nova FK exigiria desactivar ou remover constraints soberanas existentes; esse cenário artificial é proibido. A protecção prospectiva será provada pela identidade física da FK PostgreSQL, pelo seu estado `NOT VALID` e pela introspecção integral do contrato. Nenhum cenário comportamental inexistente será inventado.

## 9. Fronteira técnica futura

Somente poderão ser autorizados por nova ordem expressa:

1. `migrations/versions/0041_adr020_norm_exec_dec_fk.py`;
2. `tests/test_adr020_activation_postgresql.py`.

Ficam fora do escopo:

- `app/models.py`;
- endpoints;
- services;
- workers;
- schedulers;
- dispatcher;
- frontend;
- agentes;
- migrations anteriores;
- dados históricos.

`app/models.py` somente poderá entrar no escopo por reabertura explícita desta missão com evidência nova.

## 10. Locking e operação

`ADD FOREIGN KEY NOT VALID` ainda adquire locks de DDL. A futura execução PostgreSQL deverá observar e documentar o locking efectivo e não poderá afirmar que o custo operacional é irrelevante.

Permanece o estado:

`CUSTO_OPERACIONAL_NAO_QUANTIFICADO`

Esta missão não autoriza execução em Railway ou produção, nem quantifica duração, impacto ou janela operacional.

## 11. Sequência futura obrigatória

Após auditoria e ratificação desta missão, a sequência será:

1. criar somente o RED estrutural;
2. provar RED;
3. congelar identidade do RED;
4. pedir autorização de implementação;
5. criar somente a migration `0041`;
6. executar GREEN estreito;
7. inspeccionar o contrato físico PostgreSQL;
8. executar gates progressivas;
9. auditar o diff;
10. criar `REPORT-031` e bundle somente após GREEN integral;
11. realizar commit e push apenas mediante autorização separada.

Nenhuma etapa posterior poderá antecipar ou substituir a anterior.

## 12. Limites absolutos desta missão documental

Neste passo é proibido:

- implementar qualquer alteração técnica;
- criar ou alterar testes;
- criar a migration `0041` ou alterar migrations anteriores;
- criar `REPORT-031`;
- criar bundle;
- executar testes, Alembic ou DDL;
- executar `VALIDATE CONSTRAINT`;
- fazer `git add`, commit ou push;
- fazer deploy;
- executar operações Railway ou de produção;
- activar o motor ADR-020;
- tocar em `MIGRATION-BOOTSTRAP-0000-0001`;
- tocar em `docs/ROADMAP_OPS_AGENTES.md`;
- modificar evidência histórica;
- reabrir 9B2;
- criar, editar, apagar, mover ou formatar qualquer ficheiro além deste documento.

## 13. Critérios de futura conformidade

A implementação futura somente poderá ser considerada conforme se a introspecção física PostgreSQL provar integralmente o contrato das secções 2 a 5, a FK permanecer não validada, nenhuma nova `UNIQUE` for criada e todas as garantias existentes forem preservadas.

Nenhum resultado de teste, hash, commit, execução técnica ou estado GREEN é declarado nesta missão.

## 14. Integridade documental

- Codificação: UTF-8 sem BOM.
- Finais de linha: LF.
- O documento não contém auto-hash.
- Qualquer hash deverá ser calculado externamente após congelamento dos bytes.

## Ratificação documental

- Autoridade ratificadora: Miguel.
- Data: 2026-08-06.
- Ratificação: RATIFICO DOCUMENTALMENTE A MISSION-013 DA ADR-020, INTENÇÃO 9B4, COM A FRONTEIRA, CONTRATO FÍSICO, RED ESTRUTURAL E LIMITES NELA DEFINIDOS.

A ratificação confirma a fronteira, o contrato físico, o RED estrutural e os limites já definidos.

A ratificação não amplia escopo, não altera autoridade e não autoriza deploy ou produção.

A implementação permanece vinculada à publicação canónica em commits separados, conforme o precedente da MISSION-012.

## 15. Estado final

`MISSION_013_9B4_RATIFICADA_DOCUMENTALMENTE_APTA_PARA_PUBLICACAO_CANONICA`
