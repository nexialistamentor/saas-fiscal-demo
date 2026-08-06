# REPORT-031 — Fechamento Técnico da MISSION-013 — ADR-020 — Intenção 9B4 — Versão 1.0

## Estado

FECHAMENTO TÉCNICO LOCAL PROPOSTO — AGUARDA COMMIT DOCUMENTAL E PUBLICAÇÃO

## 1. Identificação

- Documento: `REPORT-031-FECHAMENTO-TECNICO-MISSION-013-ADR-020-INTENCAO-9B4-V1.0`
- Versão: `1.0`
- Estado: `FECHAMENTO TÉCNICO LOCAL PROPOSTO — AGUARDA COMMIT DOCUMENTAL E PUBLICAÇÃO`
- Intenção: `ADR-020 9B4`
- Branch: `main`
- HEAD técnico local validado: `1b36b1cc569648cf6eb011a66d316447fc32c96e`
- Commit documental pai: `c742d7ca88e3568cff7864f2c354ab230c4f1d89`
- Base de captura/origin-main: `4aee707a3d25490080397dde303bca1b5a693ef6`

Este relatório documenta exclusivamente o fechamento técnico local da implementação 9B4. Não cria, altera, reinterpreta ou amplia autoridade, contratos canónicos, invariantes, política fiscal ou regras de negócio. O REPORT-031 aguarda commit documental; os commits locais aguardam push.

## 2. Autoridade e cadeia documental preservada

Constituem autoridades deste fechamento:

1. `docs/REPORTS/REPORT-030-FECHAMENTO-TECNICO-MISSION-012-ADR-020-INTENCAO-9B2-V1.0.md`, como precedente de estrutura e rigor documental;
2. `docs/MISSIONS/MISSION-013-ADR-020-INTENCAO-9B4-FK-DIRETA-NORMATIVE-ACTIVATION-EXECUTION-NOT-VALID-V1.0.md`, ratificada;
3. `migrations/versions/0041_adr020_norm_exec_dec_fk.py`;
4. `tests/test_adr020_activation_postgresql.py`;
5. os 21 ficheiros de `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0/`;
6. `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0.zip`.

Ratificação exacta da MISSION-013:

`RATIFICO DOCUMENTALMENTE A MISSION-013 DA ADR-020, INTENÇÃO 9B4, COM A FRONTEIRA, CONTRATO FÍSICO, RED ESTRUTURAL E LIMITES NELA DEFINIDOS.`

- Autoridade ratificadora: Miguel.
- Data: `2026-08-06`.
- Estado final exacto da missão: `MISSION_013_9B4_RATIFICADA_DOCUMENTALMENTE_APTA_PARA_PUBLICACAO_CANONICA`.

A ratificação não amplia escopo, não altera autoridade e não autoriza deploy ou produção. A cadeia anterior, incluindo as migrations `0038`, `0039` e `0040` e as garantias 9B2, permanece preservada.

## 3. Identidade Git da implementação validada

HEAD técnico local:

`1b36b1cc569648cf6eb011a66d316447fc32c96e`

Identidade exacta:

- Author: `Miguel Moreira <mentoria.nexialista@gmail.com>`;
- AuthorDate: `Thu Aug 6 03:34:55 2026 -0300`;
- Commit: `Miguel Moreira <mentoria.nexialista@gmail.com>`;
- CommitDate: `Thu Aug 6 03:34:55 2026 -0300`;
- mensagem: `feat(adr020): enforce direct activation execution decision fk`.

Commit documental pai:

`c742d7ca88e3568cff7864f2c354ab230c4f1d89`

Identidade exacta:

- Author: `Miguel Moreira <mentoria.nexialista@gmail.com>`;
- AuthorDate: `Thu Aug 6 03:33:36 2026 -0300`;
- Commit: `Miguel Moreira <mentoria.nexialista@gmail.com>`;
- CommitDate: `Thu Aug 6 03:33:36 2026 -0300`;
- mensagem: `docs(adr020): ratify MISSION-013 intention 9B4`.

Na captura, `origin/main` permanecia em `4aee707a3d25490080397dde303bca1b5a693ef6` e a branch local estava `ahead 2`. Logo, os dois commits locais aguardam push. O REPORT-031 ainda não integra um commit documental.

## 4. Identidade da migration 0041

- Caminho: `migrations/versions/0041_adr020_norm_exec_dec_fk.py`;
- tamanho: `1201 bytes`;
- SHA-256: `3F27EDD712745DE9F47A187D7EBF9CAABDE681399A16FD75104F05819C84047D`;
- revision: `0041_adr020_norm_exec_dec_fk`;
- down revision: `0040_adr020_norm_gen_decision_fk`;
- dialecto exclusivo: PostgreSQL;
- FK composta: `fk_normative_activations_exact_execution_decision`;
- chave candidata referenciada: `uq_activation_executions_exact_decision_binding`.

Contrato físico exacto e machine-readable:

```text
constraint = fk_normative_activations_exact_execution_decision
local_table = normative_activations
local_columns = activation_execution_id | activation_decision_id | activation_decision_record_hash
referenced_table = activation_executions
referenced_columns = activation_execution_id | activation_decision_id | activation_decision_record_hash
referenced_unique = uq_activation_executions_exact_decision_binding
```

As mesmas três colunas e a mesma ordem são usadas nos dois lados. As colunas referenciadas não são `id | decision_id | decision_record_hash`.

O contrato físico é cumulativamente:

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID`.

A migration não executa `VALIDATE CONSTRAINT`, não cria nova `UNIQUE` nem novo índice, e preserva a chave candidata tripla existente. O `downgrade()` é irreversível e bloqueado por `RuntimeError` com a mensagem exacta:

`ADR-020 migration 0041 is irreversible: exact normative-execution-decision binding cannot be removed`

## 5. Identidade e prova do ficheiro de testes

- Caminho: `tests/test_adr020_activation_postgresql.py`;
- tamanho: `274224 bytes`;
- SHA-256: `E7F0D1E9A34CC5FD84711D4589E9BEA912774BAB8F1CA9F38654087B10FA0595`.

O teste estrutural 9B4 é:

`test_normative_activation_has_direct_exact_execution_decision_fk_not_valid`

Ele introspecciona a existência, tipo, tabelas, colunas locais e referenciadas na ordem exacta, chave candidata referenciada, `MATCH SIMPLE`, acções `RESTRICT`, não diferibilidade, estado inicialmente imediato e `convalidated = false`.

O RED é exclusivamente retrospectivo. O registo exacto disponível declara:

- resultado: `1 failed`;
- falha exclusiva: `assert foreign_key is not None`;
- causa: ausência da FK directa 9B4;
- o restante contrato estrutural ainda não foi alcançado.

`RED-RETROSPECTIVE.txt` declara expressamente `RED RETROSPECTIVO — NÃO É STDOUT BRUTO`. Não foram fabricados timestamps, duração ou stdout inexistente, e o teste antigo não foi reconstruído artificialmente.

## 6. Gates actuais capturadas

As quatro gates usaram SQLite temporário isolado, removido no fim. Os comandos abaixo são os comandos exactos persistidos nos metadados do bundle.

### 6.1. Gate 1 — GREEN estreito 9B4

Comando exacto:

```text
'C:\dev\saas-fiscal-demo\venv\Scripts\python.exe' '-m' 'pytest' '-q' '--tb=short' 'tests/test_adr020_activation_postgresql.py::test_normative_activation_has_direct_exact_execution_decision_fk_not_valid'
```

- início UTC: `2026-08-06T07:00:52.420548Z`;
- fim UTC: `2026-08-06T07:01:02.620956Z`;
- duração monotónica: `10.2003873s`;
- resultado pytest: `1 passed, 29 warnings in 4.96s`;
- exit code: `0`.

### 6.2. Gate 2 — preservação 9B2 e GREEN 9B4

Comando exacto:

```text
'C:\dev\saas-fiscal-demo\venv\Scripts\python.exe' '-m' 'pytest' '-q' '--tb=short' 'tests/test_adr020_activation_postgresql.py::test_normative_generation_decision_fk_is_physical_and_not_valid' 'tests/test_adr020_activation_postgresql.py::test_normative_activation_has_direct_exact_execution_decision_fk_not_valid'
```

- início UTC: `2026-08-06T07:01:02.623492Z`;
- fim UTC: `2026-08-06T07:01:15.211249Z`;
- duração monotónica: `12.587736s`;
- resultado pytest: `2 passed, 29 warnings in 8.12s`;
- exit code: `0`.

### 6.3. Gate 3 — regressão PostgreSQL ADR-020

Comando exacto:

```text
'C:\dev\saas-fiscal-demo\venv\Scripts\python.exe' '-m' 'pytest' '-q' '--tb=short' 'tests/test_adr020_activation_postgresql.py'
```

- início UTC: `2026-08-06T07:01:15.213372Z`;
- fim UTC: `2026-08-06T07:09:16.335155Z`;
- duração monotónica: `481.1217575s`;
- resultado pytest: `179 passed, 29 warnings in 476.31s (0:07:56)`;
- exit code: `0`.

### 6.4. Gate 4 — suíte global

Comando exacto:

```text
'C:\dev\saas-fiscal-demo\venv\Scripts\python.exe' '-m' 'pytest' '-q' '--tb=short'
```

- início UTC: `2026-08-06T07:09:16.337413Z`;
- fim UTC: `2026-08-06T07:18:01.321840Z`;
- duração monotónica: `524.9844052s`;
- resultado pytest: `2763 passed, 15 skipped, 970 warnings in 518.92s (0:08:38)`;
- exit code: `0`.

Todas as quatro gates cumpriram as contagens vinculantes e terminaram com exit code `0`. As durações pytest são distintas das durações monotónicas dos subprocessos.

## 7. Incidente retrospectivo separado do test.db persistente

O ficheiro `INCIDENT-TEST-DB-RETROSPECTIVE.txt` está marcado `INCIDENTE TEST.DB RETROSPECTIVO — NÃO É STDOUT BRUTO` e regista exactamente:

- uma suíte global anterior teve `2762 passed, 15 skipped, 1 failed`;
- falha: `tests/test_ops11_h4_l2_m4_contract.py::test_h4_analise_st_periodo_empresa_de_outro_usuario_bloqueia`;
- erro: `UNIQUE constraint failed: usuarios.cpf`;
- CPF em colisão: `76240319147`;
- o `test.db` persistente continha `55.030` utilizadores;
- o CPF já existia no utilizador id `45092`;
- o teste isolado passou;
- o ficheiro completo passou com `10 passed`;
- conclusão registada: colisão aleatória contra base SQLite persistente acumulada, não defeito da implementação 9B4;
- banco antigo arquivado fora do repositório;
- tamanho do banco antigo: `38985728 bytes`;
- SHA-256 do banco antigo: `FE4E1ECEE8A4B1BDBD7D220081688BEAED719D9B024B7069CD6A13CC78884DC8`.

O registo não inclui email, credenciais ou dados adicionais e não constitui stdout bruto. Este incidente retrospectivo é separado das quatro provas actuais, que usaram SQLite temporário isolado.

## 8. Bundle independente e ZIP associado

Identidade do bundle solto:

- caminho: `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0/`;
- `21 files`;
- tamanho total: `166074 bytes`;
- MANIFEST: `20 entries`;
- o MANIFEST exclui o próprio `MANIFEST.txt` e não contém auto-hash.

Identidade do ZIP:

- caminho: `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0.zip`;
- tamanho: `69805 bytes`;
- SHA-256: `2FAAB281AB926EBB19DA1EBAA3418AA310083C695AC697FCB59BAA980A8CD897`;
- contém 21 membros, incluindo `MANIFEST.txt`, sob o directório `BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0/`;
- não inclui a si próprio.

O capturador possui:

- caminho: `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B4-REPORT-031-V1.0/CAPTURE.py`;
- tamanho: `17269 bytes`;
- SHA-256: `A381373C288DFBBC1C0D1131D9F14C925DFC3F112D9E31C1E7E1E3193E7E332F`.

O bundle preserva stdout, stderr, argv, exit codes, timestamps UTC, durações monotónicas, ambiente, estado Git, inventários, tamanhos e SHA-256. Os quatro stderr estão vazios e possuem SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

Veredicto independente exacto:

`BUNDLE_9B4_AUDITADO_E_APTO_PARA_REPORT_031`

## 9. Integridade observada e limites da evidência

As fotografias Git antes e depois preservam o mesmo HEAD, pai, origin/main, identidades da migration 0041 e do ficheiro de testes. `git diff --check` e `git diff --name-only` terminaram com exit code `0`. Os artefactos do bundle eram untracked durante a captura; esta condição é documental e não equivale a publicação.

A captura começou ambientalmente em `2026-08-06T07:00:51.900822Z`, no directório `C:\dev\saas-fiscal-demo`, com Python `3.14.2`, pytest `9.0.3` e Git `2.53.0.windows.1`. Railway não foi acedido, credenciais externas não foram usadas e o cliente PostgreSQL não estava disponível como comando autónomo.

Este relatório não reivindica detectar alterações transitórias restauradas fora das fotografias nem transforma reconstruções retrospectivas em stdout bruto.

## 10. Prova técnica encerrada

A implementação demonstra a presença física prospectiva da FK directa exacta entre:

```text
NormativeActivation(
    activation_execution_id,
    activation_decision_id,
    activation_decision_record_hash
)
```

e:

```text
ActivationExecution(
    activation_execution_id,
    activation_decision_id,
    activation_decision_record_hash
)
```

A FK utiliza a chave candidata existente `uq_activation_executions_exact_decision_binding`. O estado `NOT VALID` protege novas escritas prospectivamente sem declarar validado, reparar, remover ou validar retroactivamente o histórico. As FKs simples e compostas anteriores permanecem cumulativas.

## 11. Fronteira operacional

O GREEN documentado é exclusivamente técnico, local e de teste. Não houve nem se autoriza:

- migration em Railway ou produção;
- deploy;
- `VALIDATE CONSTRAINT`;
- auditoria, reparação, backfill ou validação histórica;
- operação sobre dados reais;
- endpoint, worker, scheduler ou dispatcher;
- activação do motor ADR-020 ou abertura de gates operacionais;
- ampliação de autoridade ou escopo.

O estado do histórico permanece `HISTORICO_NAO_VALIDADO`.

## 12. Estado Git e pendências documentais

O fechamento alcançado é apenas técnico e local. Na base da captura:

- HEAD local: `1b36b1cc569648cf6eb011a66d316447fc32c96e`;
- commit documental pai: `c742d7ca88e3568cff7864f2c354ab230c4f1d89`;
- origin/main: `4aee707a3d25490080397dde303bca1b5a693ef6`;
- branch: `main`, `ahead 2`.

O REPORT-031 aguarda commit documental. Os commits locais aguardam push. Este relatório não executa nem autoriza `git add`, commit, push ou deploy.

## 13. Integridade documental

Este documento não contém auto-hash. A sua identidade deve ser calculada externamente após a fixação dos bytes.

A codificação é UTF-8 sem BOM, somente com finais de linha LF, exactamente uma newline final e zero trailing whitespace.

## 14. Estado final

- GREEN técnico integral local para a intenção 9B4;
- contrato físico exacto execução↔decisão provado;
- chave candidata existente utilizada sem nova `UNIQUE`;
- `NOT VALID` preservado, sem `VALIDATE CONSTRAINT`;
- downgrade irreversível bloqueado por `RuntimeError`;
- preservação 9B2 e regressões confirmadas;
- bundle independente capturado, congelado, auditado e apto;
- nenhuma migração Railway/produção, deploy, validação histórica ou ampliação de autoridade;
- REPORT-031 aguarda commit documental;
- commits locais aguardam push.

## Veredicto final do documento

GREEN_TECNICO_9B4_INTEGRAL_IMPLEMENTACAO_APTA_PARA_FECHAMENTO_DOCUMENTAL_AGUARDA_PUBLICACAO
