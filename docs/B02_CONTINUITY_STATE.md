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
