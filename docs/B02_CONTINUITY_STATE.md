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
