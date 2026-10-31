# SOLVERIS B02 — Encaminhamento focal A2 V4 ao revisor técnico segregado

**Corte:** 2026-10-30. **Natureza:** pedido de reapreciação estritamente técnica; **não constitui parecer do revisor, autorização G5, aprovação de migrations ou fecho B02**.

## Predecessor preservado e objeto

- Revisão segregada original: `SOLVERIS_B02_RCV31_R3_PARECER_SEGREGADO_20261025.md` (25/10/2026). A1 favorável no âmbito descartável; A2 parcial pela necessidade de comprovar observação independente das raízes e cadeia persistida; não anula os pareceres anteriores.
- RCV31-R3 físico anterior: ZIP `B02_RCV31_R3_ENTREGA_DEFINITIVA_A2 (1)(1).zip`, SHA-256 `474d99de34a1817f94b85ffe86d2b549df7c12a0edc2a830cca19bf427b647d8`.
- Observador real pré-existente: `B02_RCV31_R3_OBSERVADOR_PROCESSO_SEPARADO.py`, SHA-256 `4dc2b18af2942353b788b43bf41a2b6ef37b406bb16c942f335c94f6bc369e2e`. Executa consultas de leitura com `psycopg2`, sessão e papel independentes, verifica assinaturas Ed25519 da decisão, testemunhos por unidade e manifesto, reconstrói relações a partir de tabelas persistidas e verifica perfil de raízes sintéticas pinado. **A revisão deve distinguir raízes de ensaio de autoridade institucional real.**
- Delta 4 V3 histórico e respetivo negativo de adulteração já foram executados em PG17 descartável em 25/10. Não repetir.

## Delta V4 submetido

- Patch: `evidence/b02/rcv31/a2/B02_RCV31_R3_DELTA4_V3_A2_SNAPSHOT_V4.patch`, SHA-256 `bfd8b397bb245923a7cff10b0b1c06480bef29aa8e2c707691bcc992c5f8ce7e`.
- Fonte V3 de partida: `B02_RCV31_R3_CONCRETE_PATH_DELTA4_V3_SOBRE_REAL.py`, SHA-256 `1fae5b1aefe9630e077eae9c98b44c91d4f9dd99f9e4560a6dab83b74e5e7779`.
- Candidato V4 materializado **em ambiente descartável**, SHA-256 `2fd9c8b9fdae373ec7622971a6d5efdca0f3d18f5082769065f7cd1f0e6bda11`. Capture os bytes do observador antes de `operate()`, valide SHA-256 original, envie os mesmos bytes ao processo independente por stdin; o filho valida novamente o hash e compila esses bytes em memória (`python -I -c`), em vez de reabrir o ficheiro no disco.
- Suite Windows local `evidence/b02/rcv31/a2/test_b02_rcv31_r3_delta4_v4_a2.py`: **5/5 PASS**; verificador `b02_rcv31_a2_snapshot_verify.py` conferiu os três SHA-256 e rejeitou divergências não triviais. A diferença CRLF do Windows foi normalizada, preservando pin canónico.

## Ensaio físico específico novo (sem replay de negativos)

- Executável: `evidence/b02/rcv31/a2/b02_rcv31_a2_pg17_focal.py`, commit `94d3141d4c75c2f17a7a33f5482398249a6a14b2`.
- PostgreSQL 17 descartável, cenário **positive** único, em 30/10/2026 às 22:27 UTC. Branch histórica `candidate/g5-successor-window-prep`, commit `56d8b23c8af5f8a9b7fdf1eb8fb01a9f008dc9f8`, sem checkout destrutivo.
- JSON primário: `B02_RCV31_R3_DIAGNOSTICO_CAUSAL_20261030T222721Z.json`, tamanho **313542 bytes**, SHA-256 **`99d544143e1155c1cc50f9d71d11ccfa333fe06dcc8bb7e98e1f5d68a4651f16`**. **Não enviado para o GitHub; recebido e analisado como anexo da conversa.**
- Campos confirmados: `status=PASS_DIAGNOSTIC_POSITIVE`; `result_status=PASS_CONCRETE_STAGE_AND_SEPARATE_READ_ONLY_PROCESS`; `cleanup=REMOVED`; `primary_exception=null`; catálogo de 28 triggers; 1057 instruções SQL instrumentadas, 19 INSERT; hashes de ambos PDFs C3 coincidentes. `protected_writes=0` declarado pelo executor do ensaio.
- **Limites da instrumentação:** `correspondence_checkpoints=[]`; `observer_field_diagnostics=null`. Não declarar 8 comparações nem prova detalhada de assinaturas a partir deste JSON isoladamente. O código do observador contém verificações criptográficas, e o resultado COMMITTED + leitura separada é reportado pela integração, mas faltam resultados de nível de campo discriminados neste JSON. O próprio V7 reconhece que `--final-operator` é um portão separado do módulo realmente importado; a cópia descartável recebe os deltas 1/2/3, SHA-256 comunicado **`50352fcdcb42b8e063c6b73189e87866e34f2988cebdb8fd6834033c4a1765d5`**. Não usar a expressão `copiado verbatim` da nota de diagnóstico para negar os deltas efetivamente aplicados.
- Os 4 `unit_checkpoints` têm rótulo indistinto mas, correlacionados por timestamp com `statement_log_summary.full_log`, correspondem a **2** `SET CONSTRAINTS z_b02_complete_unit DEFERRED` e **2** `SET CONSTRAINTS ALL IMMEDIATE`. Não representam 4 unidades independentes.

## Delimitação exata para decisão do revisor ORIGINAL

1. Confirmar pelo diff V3→V4 se o processo filho executa exclusivamente os bytes previamente verificados, sem *TOCTOU* de reabertura do ficheiro observador, no escopo do cenário descartável provado.
2. Confrontar a origem das raízes de confiança, o `observer` real e as assinaturas/relações persistidas com a reserva A2 do parecer anterior. Separar **prova sintética técnica** de autorização institucional G5.
3. Confrontar a proveniência do **operador efetivamente importado**, o log do candidato 3 deltas, o desligamento de `--final-operator` e os limites de `observer_field_diagnostics`. Uma lacuna não deve ser mascarada por um PASS genérico.
4. Emitir resultado **próprio** (favorável, condicional ou desfavorável), apenas para A2, com ressalvas exatas e evidência já existente. Não repetir V13–V30, RCV31-R3, V7, R4 ou A2 positivo; novos ensaios só em resposta a defeito concreto ainda não provado.

**Gates separados e não executados:** parecer institucional G5 V5 original; aprovação temporal G5 válida; DLL/ELF nativo sucessor assinado, migrations 0064/0065, duas unidades reais sob autoridade operacional, R6 e R7. `B02_OPEN_B03_BLOCKED`. O MEI permanece intocado.

## Releitura adicional do JSON primário, sem novo ensaio

- Fonte original recebida na Biblioteca da conversa: `B02_RCV31_R3_DIAGNOSTICO_CAUSAL_20261030T222721Z.json`. Releitura direta dos **bytes do ficheiro** nesta execução confirmou 313542 bytes e SHA-256 `99d544143e1155c1cc50f9d71d11ccfa333fe06dcc8bb7e98e1f5d68a4651f16`, equivalente à identidade já comunicada. Não houve repetição do teste PostgreSQL nem nova escrita protegida.
- Instrumentação efetivamente presente: `statement_log_summary.total_statements=1057`, `by_category.INSERT=19`, `unit_checkpoints=4`, `correspondence_checkpoints=[]`, `observer_field_diagnostics=null`, `primary_exception=null`. A lista `full_log` inclui 2 entradas `SET CONSTRAINTS z_b02_complete_unit DEFERRED` e 2 entradas `SET CONSTRAINTS ALL IMMEDIATE`, nas posições zero-based 21, 526, 531 e 1036 (naquela ordem). Estes quatro pontos são duas sequências de unidade, não quatro unidades.
- Classificando **apenas os cabeçalhos SQL registrados**, 18 das 19 linhas `INSERT` identificam as seguintes tabelas e contagens: `artifact_references=2`, `acquisition_executions=6`, `acquisition_mode_bindings=2`, `noncredential_acquisition_receipts=2`, `noncredential_sanitization_verifications=2`, `normative_artifacts=2`, `artifact_verification_records=2`. A 19ª linha tem apenas o cabeçalho genérico `INSERT INTO` e não permite inferir tabela ou unidade. Nenhuma linha instrumentada identifica explicitamente `COMMIT` como categoria; isto não invalida o resultado superior do ensaio, mas **o log SQL isolado não é prova independente do COMMIT**.
- O `operator_hash_note` declara que `--final-operator` é um portão de proveniência separado do operador realmente importado; não prova por si que ambos são o mesmo objeto. Confrontar com o código V4 e os três deltas do operador efetivo. `cas_sha256_verified` registra os dois SHA-256 C3 já fixados, não autentica autonomamente origem institucional nem cadeia de revogação.
- Fonte V3→V4 conferida estaticamente no patch Git pinado: o caminho `run_pinned_observer_source` passa `input=verified_source` ao filho `python -I -c`, que verifica SHA-256 antes do `exec(compile(...))`. Isto suporta o **mecanismo focal anti-TOCTOU do observador**; ainda requer apreciação própria do revisor original e não substitui raízes de confiança ou assinaturas reais.

**Decisão do revisor não emitida por este aditamento.** O resultado próprio A2 continua reservado ao revisor técnico segregado, sem se confundir com o evento SQL institucional G5 V5 `auditada_*`. Os gates operacionais e R7 permanecem independentes.
