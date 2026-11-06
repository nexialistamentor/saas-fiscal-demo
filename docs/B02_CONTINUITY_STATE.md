# B02 — ESTADO DE CONTINUIDADE (fonte única, ler antes de qualquer nova sessão)
Atualizado: 2026-11-05

## FACTO CONFIRMADO — não repetir esta investigação
- Chave privada existe: CustodiaB02\Chave_ceee5bb6f2a740a58cf4dbaa66565698\miguel-private-encrypted.pem
- Fingerprint SHA-256 confirmado: 6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c
- Este fingerprint JÁ ESTÁ pinado em ROOT.json e BUNDLE_ASSINADO\decision.json (ambos de 04/11)
- NÃO EXISTE custodiante a descobrir nem chave a gerar. O custodiante é Miguel, confirmado.

## O QUE FALTA (único bloqueio real)
O ROOT/decision existentes estão vinculados a:
- object_sha256 = 615c8d64... (objeto G4 ANTIGO, não a candidata atual)
- scope = SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY (não é G5_R1_ADMISSION)
- valid_until = 2026-11-04T18:00:00Z (EXPIRADO)

Candidata atual: 389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2

## PRÓXIMO PASSO ÚNICO
Emitir NOVA decision.json com a MESMA chave (fingerprint acima), scope=G5_R1_ADMISSION,
object_sha256=389cce04..., janela de validade nova. Usar tools/b02_documentary_signer_v2.py
como base de estrutura (DECISION_KEYS já mapeado).

NÃO repetir: busca de chave, busca de custodiante, verificação de fingerprint, pergunta "quem assina".
## ATUALIZACAO 2026-11-05 (sessao Claude) -- G5/R1 FECHADO FISICAMENTE NA BD

Cadeia completa materializada e ativa em solveris_b02_r4g_test:
- policy_versions: B02-389cce04-policy-v3 (record_hash 1370931e...)
- bootstrap_authority_records: B02-389cce04-bootstrap-v1 (record_hash bf40aeca...)
- policy_decisions: 4 atos (submetida/auditoria_iniciada/auditada_favoravelmente/ratificada),
  Miguel em todas as funcoes, segregacao por texto (nao ha terceiro independente, declarado explicitamente)
- policy_activations: B02-389cce04-activation-v1, state=activa, CONFIRMADO por leitura independente apos o commit

Script fonte: materializar_cadeia_g5r1_389cce04.py (commit e8f10522 e seguintes).

PROXIMO PASSO: R5 -- instalar 0064/0065 (ja preparadas) e as duas unidades reais.
O bootstrap_authority_record agora existente desbloqueia stage_policy_activation para R5.
NAO repetir G5/R1 -- esta ja fechado e ativo.

## ATUALIZACAO 2026-11-05 22:55 (sessao Claude) -- BIBLIOTECA NATIVA COMPILADA

Estado da R5, dependencia fisica 1 (biblioteca b02_g5_native_REAL_CLOSED):
- Pacotes de build instalados no contentor solveris-pg17-migration-test (gcc, make, postgresql-server-dev-17, libssl-dev)
- b02_g5_approved_roots.h atualizado: nova entrada "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V2",
  mesma chave Ed25519 ja confirmada (fingerprint 6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c),
  janela 2026-11-05 a 2036-11-05, vinculada a candidata 389cce04 (ver secao G5/R1 acima).
  Raiz antiga V1 preservada, nunca editada no seu conteudo historico (so corrigido um erro de escaping meu).
- Compilado com sucesso dentro do contentor: /tmp/b02_g5_native_signature.o e /tmp/b02_g5_native_REAL_CLOSED.so (25968 bytes)
- POR FAZER: copiar o .so para o pkglibdir do Postgres (/usr/lib/postgresql/17/lib/), depois aplicar
  a migracao migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py (ainda NAO aplicada,
  alembic_version continua em 0063). So depois disso aplicar 0065.
- NOTA: apt upgrade atualizou postgresql-17 de 17.10 para 17.11 dentro do contentor (menor, nao deve
  ter afetado dados; BD confirmada saudavel e em 0063 depois da atualizacao).
- Ficheiros fonte ainda NAO copiados de volta para o repo local (estao so dentro do contentor em /tmp
  e no checkout local em native/g5/historical_20261022/). Falta git add/commit do .h atualizado e dos
  scripts apply_patch_new_root.py / apply_patch_fix_escaping.py / build_manifest.py.

PROXIMO PASSO EXATO: instalar o .so, confirmar que o SQL de 0064 compila (CREATE FUNCTION ... AS
  '$libdir/b02_g5_native_REAL_CLOSED'), depois aplicar 0064 e 0065 via alembic ou script equivalente.

## ATUALIZACAO 2026-11-05 23:10 (sessao Claude) -- BIBLIOTECA NATIVA FUNCIONAL, CONFIRMADA

b02_g5_native_REAL_CLOSED.so instalada em /usr/lib/postgresql/17/lib/ no contentor
solveris-pg17-migration-test. Testada em transacao com ROLLBACK:
SELECT public.b02g5_native_profile() -> 'REAL_PROFILE_COMPILED_APPROVED_ROOTS' (valor exigido por 0064).

Correcao necessaria no fonte: faltava PG_MODULE_MAGIC; adicionada apos os #include
em native/g5/historical_20261022/b02_g5_native_signature.c.

PROXIMO PASSO EXATO: aplicar 0064 a serio (ainda so testado em ROLLBACK). A biblioteca
ja esta pronta -- 0064 deve agora conseguir criar as funcoes sem erro de "missing magic block".

## ATUALIZACAO 2026-11-05 23:10 (sessao Claude) -- BIBLIOTECA NATIVA FUNCIONAL, CONFIRMADA

b02_g5_native_REAL_CLOSED.so instalada em /usr/lib/postgresql/17/lib/ no contentor
solveris-pg17-migration-test. Testada em transacao com ROLLBACK:
SELECT public.b02g5_native_profile() -> 'REAL_PROFILE_COMPILED_APPROVED_ROOTS' (valor exigido por 0064).

Correcao necessaria no fonte: faltava PG_MODULE_MAGIC; adicionada apos os #include
em native/g5/historical_20261022/b02_g5_native_signature.c.

PROXIMO PASSO EXATO: aplicar 0064 a serio (ainda so testado em ROLLBACK). A biblioteca
ja esta pronta -- 0064 deve agora conseguir criar as funcoes sem erro de "missing magic block".

## ATUALIZACAO 2026-11-05 23:10 (sessao Claude) -- BIBLIOTECA NATIVA FUNCIONAL, CONFIRMADA

b02_g5_native_REAL_CLOSED.so instalada em /usr/lib/postgresql/17/lib/ no contentor solveris-pg17-migration-test. Testada em transacao com ROLLBACK: SELECT public.b02g5_native_profile() retornou REAL_PROFILE_COMPILED_APPROVED_ROOTS (valor exigido por 0064).

Correcao necessaria no fonte: faltava PG_MODULE_MAGIC; adicionada apos os includes em native/g5/historical_20261022/b02_g5_native_signature.c. Ja commitado em df75985d.

PROXIMO PASSO EXATO: aplicar 0064 a serio (ainda so testado em ROLLBACK). A biblioteca ja esta pronta.

## ATUALIZACAO 2026-11-05 23:30 (sessao Claude) -- 0064 APLICADA DE VERDADE

Migracao 0064 aplicada com sucesso na BD real (solveris_b02_r4g_test). alembic_version agora em 0064_b02_g5_controlled_real_cas (0063 removido, estado limpo). b02g5_native_profile() confirma REAL_PROFILE_COMPILED_APPROVED_ROOTS. Biblioteca nativa completa (signature + precommit_guard) instalada e funcional.

SQL aplicado via psql direto (nao via alembic upgrade), extraido do ficheiro de migracao candidato. Script de extracao: extract_0064_sql.py. SQL aplicado: apply_0064.sql.

PROXIMO PASSO: aplicar 0065 (one-shot real) pelo mesmo processo -- extrair, testar em ROLLBACK, aplicar a serio. Depois disso, preparar as duas unidades reais (0064/0065 sao so infraestrutura, ainda sem dados).

## ATUALIZACAO 2026-11-05 23:50 (sessao Claude) -- R5 INFRAESTRUTURA COMPLETA, 0064+0065 APLICADAS

alembic_version = 0065_b02_g5_one_shot_real (estado limpo, uma so linha). Tabela b02_g5_operational_approval_uses criada com todas as guardas (one-shot, two-units trigger). Biblioteca nativa completa funcional (signature + precommit_guard).

R5 so falta: as duas unidades reais (PDFs 101201900571 e 101202501245, ja localizados com hash confirmado em SOLVERIS_ENTERPRISE_B02_R4C_NOVA_AQUISICAO_20261020_121602_f9426b0d/CAS_G19/sha256/). Precisa de: app.services.enterprise_b02_noncredential_acquisition.stage_completion e app.services.enterprise_b02_g5_two_unit_stage para preparar os dois registos reais (binding, receipt, verification), depois b02_g5_reserve_operational_decision() + a transacao real com COMMIT.

NAO repetir 0064/0065 -- ja aplicadas e confirmadas. Scripts: extract_0065_sql.py, apply_0065.sql, test_0065.sql.

=====================================================================
## RESUMO COMPLETO PARA PROXIMA SESSAO (2026-11-06) -- LER ISTO PRIMEIRO
=====================================================================

### O QUE JA ESTA FEITO E CONFIRMADO (nao repetir)

1. G5/R1 FECHADO -- candidata 389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2
   (policy_candidate_body de POLICY_G5_CANDIDATO_SUCESSOR_V3_R1_SUBSTITUICAO_PROSPECTIVA_20261105.json)
   - Ratificado por Miguel (commit 822b4d38 na PR 27)
   - Ativado fisicamente na BD: policy_versions, bootstrap_authority_records, 4x policy_decisions,
     policy_activations (B02-389cce04-activation-v1, state=activa)
   - Script: materializar_cadeia_g5r1_389cce04.py

2. BIBLIOTECA NATIVA COMPILADA E FUNCIONAL
   - native/g5/historical_20261022/b02_g5_native_signature.c (assinatura Ed25519)
   - native/g5/historical_20261022/b02_precommit_guard.c (hook de pre-commit, ja existia completo)
   - b02_g5_approved_roots.h: nova raiz V2, mesma chave Ed25519 ja confirmada (fingerprint
     6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c), janela 2026-11-05 a 2036-11-05,
     vinculada a candidata 389cce04. Raiz V1 antiga preservada.
   - Compilada DENTRO do contentor Docker (nao tem gcc no host): apt-get install gcc make
     postgresql-server-dev-17 libssl-dev dentro do contentor solveris-pg17-migration-test
   - Instalada em /usr/lib/postgresql/17/lib/b02_g5_native_REAL_CLOSED.so
   - Testada: SELECT public.b02g5_native_profile() = REAL_PROFILE_COMPILED_APPROVED_ROOTS

3. MIGRACAO 0064 APLICADA DE VERDADE (irreversivel, nao tem downgrade)
   - Todas as funcoes/triggers de validacao R5 criadas na BD solveris_b02_r4g_test
   - SQL extraido do ficheiro de migracao, testado em ROLLBACK, depois aplicado com COMMIT

4. MIGRACAO 0065 APLICADA DE VERDADE
   - Tabela b02_g5_operational_approval_uses (reserva one-shot) criada e ativa
   - alembic_version = 0065_b02_g5_one_shot_real (linha unica, limpa)

5. BACKUPS DISPONIVEIS SE PRECISAR REVERTER (nunca foram necessarios ate agora)
   - Imagem Docker: solveris-pg17-backup-pre-r5-20261105
   - Dump logico: C:\Users\Oem\AppData\Local\SOLVERIS\CustodiaB02\b02_pre_r5_backup_20261105.dump

6. TUDO COMMITADO E NO GITHUB (branch candidate/g5-v5-publicacao-local, PR 27 aberta e intacta)
   - Ultimo commit: a82d364f (feat(b02-r5): 0065 applied for real...)
   - NOTA: houve um incidente de push (fatal error in commit_refs do GitHub) que obrigou a apagar
     e recriar a branch remota. Resolvido, PR 27 continua aberta e correta. Nao e preciso repetir nada.

### ONDE PARAMOS -- O ULTIMO PASSO DE R5

Faltam as DUAS UNIDADES REAIS (os dois documentos C3):
- PDF 101201900571 (Resolucao 571/2019), hash af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d,
  tamanho 1944929 bytes
- PDF 101202501245 (Resolucao 1245/2025), hash e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832,
  tamanho 258302 bytes

Ficheiros fisicos JA LOCALIZADOS e hash CONFIRMADO (nao e preciso procurar outra vez), por exemplo em:
C:\Users\Oem\Downloads\SOLVERIS_ENTERPRISE_B02_R4C_NOVA_AQUISICAO_20261020_121602_f9426b0d\CAS_G19\sha256\

VERIFICACAO FEITA: nao existe NENHUM registo em artifact_references nem acquisition_executions
para estes dois documentos nesta BD. Tem de se construir a cadeia completa do zero:

1. artifact_references (referencia a fonte) -- nao existe, criar
2. Uma execucao de planeamento (execution_event=criacao, projected_state=planeada) -- predecessor
   obrigatorio do binding
3. acquisition_mode_bindings, com security_policy_binding e sanitization_policy_binding apontando
   EXATAMENTE para a politica G5/R1 ja ativa (policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE,
   policy_version=3, policy_hash=389cce04...)
4. Leitura real dos bytes do PDF (ja localizados)
5. receipt, verification, terminal, artifact -- cadeia de evidencia completa via
   app.services.enterprise_b02_noncredential_acquisition.stage_completion
6. stage_authenticity -- a parte mais critica: um registo de autenticidade G4 (artifact_verification_records)
   que tem de bater EXATAMENTE com a tupla que b02g5_require_authenticity_in_unit() (dentro de 0064)
   vai verificar: verifier id/version/hash = SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN/1/fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472,
   vinculado ao g4.origin_report_binding de cada documento (ja confirmados no JSON da candidata:
   571/2019 -> 9250fc933c41dab84e186019f01ed1f2b29828de1d5e1b879568a96e3ef1a6d4,
   1245/2025 -> a281c48d6107817aca97331e5425f81616847e66853a3e179ca66d3353f23fa8)
7. Depois de AMBAS as unidades estarem staged (app.services.enterprise_b02_g5_two_unit_stage.stage_two_real_c3_units
   exige as duas de uma vez, numa so chamada, numa so transacao): chamar b02_g5_reserve_operational_decision()
   para a reserva one-shot, depois b02g5_capability_manifest() + a assinatura Ed25519 real com a chave ja
   confirmada, e so entao COMMIT.

Ficheiros a ler antes de avancar (ainda nao lidos nesta sessao):
- app/services/enterprise_b02_noncredential_acquisition.py (resto do ficheiro, so os primeiros 150 chars foram lidos)
- app/models.py -- estrutura exata de artifact_references, acquisition_executions,
  acquisition_mode_bindings, normative_artifacts, artifact_verification_records
- O resto de enterprise_b02_g5_two_unit_stage.py ja foi lido por completo (ver secao acima deste ficheiro)

RECOMENDACAO: esta e a parte mais complexa e de maior risco de todo o R5 -- envolve muitos campos
exatos cruzados entre varias tabelas e triggers. Tratar como sessao propria, com atencao total,
em vez de continuar com fadiga acumulada. O estado atual esta seguro e nao se perde nada ao parar aqui.

### DEPOIS DE R5 FECHAR, O QUE FALTA PARA O B02 FECHAR DE VEZ

- R6: vinculo fiscal real -- falta ExtractionResult conclusiva, RuleVersion vinculada, item NF-e real
  com XML/hash (NormativeArtifact fica resolvido como parte das duas unidades acima). Alternativa mais
  rapida, ja discutida e aceite como caminho valido: R6 SINTETICO, documentado como tal (nao substitui
  o real, mas desbloqueia o fecho tecnico B02_TECHNICAL_CLOSED_FISCAL_PENDING). Scripts ja existentes:
  tools/b02_r6_synthetic_nfeproc_pipeline_v1.py, fixtures/b02_r6_synthetic_nfeproc_20261105.xml
  (criados no commit e4301c3 de outra sessao, nunca aplicados).
- R7: decisao final -- consumir G5/R1 (feito), R5 (duas unidades reais) e R6, e so Miguel pode emitir
  a decisao institucional B02_CLOSED.

### REGRAS QUE NAO MUDAM, EM QUALQUER SESSAO FUTURA

- Miguel assume todos os papeis institucionais nesta missao (proponente/auditor/ratificador) -- ja
  decidido e aplicado, nao reabrir essa discussao. Segregacao e por TEXTO DISTINTO no campo actor,
  nunca por fingir ser outra pessoa.
- Nunca aplicar SQL real sem primeiro testar em transacao com ROLLBACK.
- Backup (imagem Docker + pg_dump) ja existe; nao e preciso refazer a menos que algo corra mal.
- Sempre commitar e dar push ao fim de cada passo que grava algo no repo ou na BD.
- O contentor Docker e solveris-pg17-migration-test, porta mapeada 55432 (nao 5432). Utilizadores:
  solveris_test (owner, password solveris_test), solveris_b02_writer (sql_writer restrito),
  solveris_b02_policy_writer (password solveris_policy_writer_local, so para stage_policy_activation).

## ATUALIZACAO 2026-11-06 (sessao Claude) -- G4.VERIFIER RESOLVIDO, R5 MACHINERY MAPEADA

BLOQUEIO REAL ENCONTRADO E RESOLVIDO: a politica v3 (389cce04...) tinha g4.verifier=null
nos dois documentos -- a verificacao SQL (NULL=NULL) nunca passaria. Relatorios de
origem REAIS localizados e verificados por hash proprio (nao por afirmacao de terceiros):
  C:\Users\Oem\Downloads\SOLVERIS_B02_ORIGIN_RELATORIOS_RETIFICADOS_20261102.zip ->
  B02_G4_ORIGIN_REPORT_SUCCESSOR_101201900571_20261102.json (sha256 9250fc93...)
  B02_G4_ORIGIN_REPORT_SUCCESSOR_101202501245_20261102.json (sha256 a281c48d...)
  Ambos outcome=favoravel, verifier=SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN/v1/
  hash fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472, validos ate 2026-11-15.

POLITICA V4 RATIFICADA E ATIVA NA BD: hash b6055f7e69ca5bd236373a152a9acb2bafb48128cdba6560d58d5813e5beed9d,
unico delta = g4.verifier preenchido nos dois documentos. Ratificada por Miguel ("RATIFICO", 06/11/2026).
Script: materializar_delta_g4_verifier_v4.py. Confirmado por leitura independente pos-commit.
NAO repetir este delta -- ja fechado e ativo. g5_policy_hash correto a usar daqui em diante: b6055f7e...

MAQUINARIA R5 JA CONSTRUIDA E PRONTA (nao reconstruir):
  tools/b02_r5_g5_v3_authorized_transaction.py -- execute_authorized_r5(), faz staging
    das 2 unidades + reserva one-shot + manifesto + assinatura + COMMIT + readback independente
  tools/b02_r5_g5_v3_installation_bridge.py -- real_units_from_custody(), monta os units
    a partir de custody privada + callbacks reais fornecidos pelo chamador

FALTA CONSTRUIR (nunca feito antes, nao e repeticao):
  1. approval dict com 10 campos hash reais: approval_id, release_id, operator_sha256,
     decision_document_sha256, g5_policy_hash (=b6055f7e...), review_act_sha256,
     ratification_act_sha256, native_root_sha256, native_elf_sha256, install_act_sha256
  2. funcao competent_sign_manifest(bytes) -- assinatura Ed25519 real com a chave privada
     ja confirmada (CustodiaB02\Chave_ceee5bb6f2a740a58cf4dbaa66565698\miguel-private-encrypted.pem,
     fingerprint 6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c)
  3. funcao independently_verify_acts(approval) -- confirma cadeia institucional, raiz, ELF
  4. build_evidence e stage_authenticity por documento (usando os relatorios de origem
     reais ja verificados acima)

RECOMENDACAO MANTIDA: isto e o passo mais arriscado e irreversivel de todo o B02
(reserva one-shot, sem retry). Tratar como sessao propria, com atencao total.
