# REPORT-024 — Encerramento Técnico da MISSION-010 — ADR-020 — Intenção 9B3 — Versão 1.0

## Estado

ENCERRAMENTO TÉCNICO PROPOSTO — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO

## 1. Identificação

- Documento: `REPORT-024-ENCERRAMENTO-MISSION-010-ADR-020-INTENCAO-9B3-V1.0`
- Versão: `1.0`
- Estado: `ENCERRAMENTO TÉCNICO PROPOSTO — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO`
- Data: `2026-08-04`
- Intenção: `ADR-020 9B3`
- Baseline publicada: `05c1ff4a522578cdbdc1c729fa0f6366d06c2afc`

Este relatório ainda não é canónico nem publicado.

## 2. Autoridade

A execução e o presente encerramento preservam os seguintes instrumentos de autoridade, sem alteração:

1. MISSION-010:
   - caminho: `docs/MISSIONS/MISSION-010-ADR-020-INTENCAO-9B3-GREEN-COERENCIA-DECISAO-EXECUCAO-V1.0.md`;
   - SHA-256: `485E116AD20DE1BDCF2304059D121C909E491D2004E2712B7D55C7E329B38724`.
2. REPORT-023:
   - caminho: `docs/REPORTS/REPORT-023-RATIFICACAO-MISSION-010-ADR-020-INTENCAO-9B3-V1.0.md`;
   - SHA-256: `8E6A7DBD98BC1BC56D3FC4B04770FD5EC83805497D751D561D742878304C58AD`.

Este relatório documenta a execução ratificada; não cria, altera, reinterpreta ou amplia autoridade, contratos canónicos, invariantes, política fiscal ou regras de negócio.

## 3. Objectivo encerrado

Ficou tecnicamente encerrado o GREEN da coerência exacta entre `ActivationGeneration` e `ActivationExecution`, vinculando cada geração à mesma decisão exacta já vinculada à execução por meio de identidade de execução, identidade de decisão e hash do registo da decisão.

A implementação 9B3 está tecnicamente concluída. O motor ADR-020 permanece desligado, nenhum gate foi aberto e a publicação deste encerramento ainda não ocorreu.

## 4. Baseline

No encerramento técnico, `HEAD` e `origin/main` correspondiam exactamente a:

`05c1ff4a522578cdbdc1c729fa0f6366d06c2afc`

Essa é a baseline publicada vinculante desta execução.

## 5. Escopo técnico

O escopo técnico encerrado contém exclusivamente:

1. `app/models.py`
   - tamanho: `229424 bytes`;
   - SHA-256: `629AE5A6A19F4A08DE9B1B9A1DD0ED0E1BA0086BF107D39F17ECB99CBC79C404`.
2. `tests/test_adr020_activation_postgresql.py`
   - tamanho: `247215 bytes`;
   - SHA-256: `6051D7FDE97EBCD2E593832910CAEB30614CE744EB019F303B9B4A18E539375D`.
3. `migrations/versions/0039_adr020_activation_generation_decision_execution_fk.py`
   - tamanho: `1492 bytes`;
   - SHA-256: `AF8BA3CA3FAAC48BD49D1A6B8B92C234B6226B134441E3C9A17058676F87EDA6`.

A migration 0039 é o único ficheiro técnico novo. Foram preservadas as migrations 0024–0038 e todos os demais ficheiros fora do escopo.

## 6. Mecanismo físico

A migration criada é `0039_adr020_activation_generation_decision_execution_fk.py`, com:

- revision: `0039_adr020_gen_exec_decision_fk`;
- down revision: `0038_adr020_generation_exec_gate`;
- guard exacto: `ADR-020 migration 0039 requires PostgreSQL`;
- downgrade exacto: `ADR-020 migration 0039 is irreversible: exact generation-execution-decision binding cannot be removed`.

Foram criadas exactamente duas constraints lógicas:

1. UNIQUE `uq_activation_executions_exact_decision_binding`, na ordem exacta:
   1. `activation_execution_id`;
   2. `activation_decision_id`;
   3. `activation_decision_record_hash`.
2. FOREIGN KEY `fk_activation_generations_exact_execution_decision`, com a tripla local e a tripla referenciada na mesma ordem exacta:
   1. `activation_execution_id`;
   2. `activation_decision_id`;
   3. `activation_decision_record_hash`.

Não foi criado índice independente, `VALIDATE CONSTRAINT`, trigger, função, listener, tabela, endpoint, worker, scheduler ou dispatcher.

## 7. Metadata

A migration e a metadata representam as mesmas propriedades ratificadas:

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID` na migration histórica;
- SQLSTATE nativo `23503`;
- ausência de token customizado.

A diferença deliberada de validação entre uma base histórica migrada e uma base nova criada por metadata permanece dentro do contrato ratificado: a migration histórica conserva a FK como `NOT VALID`, activa prospectivamente para novas linhas.

## 8. Testes e regressões

Foram registados os seguintes resultados exactos:

1. GREEN exacto:
   - teste: `test_activation_generation_rejects_execution_from_different_exact_decision_via_core`;
   - resultado: `1 passed in 7.17s`.
2. Prova física:
   - teste: `test_activation_generation_decision_execution_fk_is_physical_and_not_valid`;
   - resultado final: `1 passed in 5.88s`.
3. Prova prospectiva:
   - teste: `test_activation_generation_decision_execution_fk_is_prospective`;
   - resultado final: `1 passed in 5.68s`.
4. Regressão PostgreSQL ADR-020:
   - resultado: `175 passed in 494.60s (0:08:14)`.
5. Regressão ADR-020 completa:
   - resultado: `354 passed, 7 skipped in 468.53s (0:07:48)`.
6. Regressão global:
   - resultado: `2759 passed, 15 skipped, 5 warnings in 615.30s (0:10:15)`.
7. `git diff --check`:
   - passou sem saída.

Todos os testes e regressões autorizados ficaram verdes.

## 9. Prova prospectiva

A prova prospectiva demonstrou cumulativamente:

- base histórica na revision 0038;
- geração incoerente aceite antes da constraint;
- migration 0039 aplicada sem validação retrospectiva;
- linha histórica preservada;
- `convalidated = false`;
- nova incoerência rejeitada;
- `SQLSTATE = 23503`;
- `constraint_name = fk_activation_generations_exact_execution_decision`;
- nova geração coerente persistida;
- ausência de reparação ou remoção histórica.

Assim, a garantia física actua prospectivamente sobre novas escritas sem declarar auditado, reparar, remover ou validar retrospectivamente o histórico.

## 10. Correcções realizadas durante a validação

As ocorrências intermédias abaixo foram correcções mínimas dos testes e da sua invocação, não defeitos da migration.

### 10.1. Representação textual de MATCH SIMPLE

A primeira execução da prova física falhou porque `pg_get_constraintdef()` omitiu `MATCH SIMPLE`, por ser o padrão do PostgreSQL.

Correcção mínima aplicada:

- preservada a prova estática de `MATCH SIMPLE` no source;
- preservada a prova física `confmatchtype == "s"`;
- removida somente a exigência textual de `MATCH SIMPLE` em `pg_get_constraintdef()`.

### 10.2. Comprimento dos identificadores prospectivos

A primeira execução prospectiva falhou antes da migration 0039 porque o sufixo de dados de teste produziu identificadores maiores que `VARCHAR(64)`.

Correcção mínima aplicada:

- sufixo anterior: `prospective-exact-decision-execution-int9b3`;
- sufixo final: `prospective-9b3`;
- cenário e identidades semânticas preservados.

### 10.3. Wildcard no PowerShell

A primeira tentativa da regressão ADR-020 com `tests/test_adr020*.py` não executou testes porque o PowerShell não expandiu o wildcard.

A regressão foi repetida com enumeração explícita dos ficheiros e passou com `354 passed` e `7 skipped`.

## 11. Auditoria final

Veredicto exacto da auditoria:

`AUDITORIA_9B3_APROVADA_AGUARDA_RELATORIO_DE_ENCERRAMENTO`

A auditoria confirmou:

- baseline;
- escopo;
- ausência de staging;
- migration como único ficheiro técnico novo;
- constraints exactas;
- metadata exacta;
- preservação do RED;
- exactamente dois testes novos;
- migrations 0024–0038 inalteradas;
- MISSION-010 e REPORT-023 inalterados;
- UTF-8 sem BOM;
- LF;
- uma newline final;
- zero trailing whitespace;
- nenhuma divergência.

## 12. Integridade

Os tamanhos e hashes dos três ficheiros técnicos estão registados na secção 5. A MISSION-010 e o REPORT-023 preservam os hashes da autoridade indicados na secção 2.

Este documento não inclui hash próprio. O seu tamanho e SHA-256 devem ser calculados externamente após a escrita. A codificação exigida é UTF-8 sem BOM, com somente LF, exactamente uma newline final e zero trailing whitespace.

## 13. Proibições e não-alterações

Não foram executados:

- staging;
- commit;
- push;
- deploy;
- Railway;
- produção;
- activação do motor ADR-020;
- gates;
- 9B2;
- 9B4;
- 9C;
- 8B2;
- MIGRATION-BOOTSTRAP-0000-0001.

Não foram modificados a MISSION-010, o REPORT-023, qualquer relatório anterior, `docs/ROADMAP_OPS_AGENTES.md`, migrations 0024–0038 ou qualquer outro ficheiro fora do escopo autorizado. Nenhum commit técnico foi criado e nenhuma produção foi alterada.

O motor ADR-020 permanece desligado. A pendência MIGRATION-BOOTSTRAP-0000-0001 permanece separada e fora do escopo.

## 14. Estado final

- a implementação 9B3 está tecnicamente concluída;
- todos os testes e regressões autorizados estão verdes;
- a publicação ainda não ocorreu;
- nenhum commit técnico foi criado;
- nenhuma produção foi alterada.

## 15. Próximo acto autorizado

O próximo acto autorizado é auditar, congelar e publicar o REPORT-024 juntamente com o escopo técnico ratificado. Até esse acto, este relatório permanece não canónico e não publicado.

## Veredicto final do documento

`IMPLEMENTACAO_9B3_TECNICAMENTE_ENCERRADA_AGUARDA_PUBLICACAO`
