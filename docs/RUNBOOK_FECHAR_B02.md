# RUNBOOK_FECHAR_B02.md — SEGUIR SEM PARAR PARA REVISOR

## Regra de ouro
Nao criar decision_document/review_act/ratification_act novos nem invocar
qualquer "revisor segregado". O unico mecanismo institucional valido e o ja
provado: policy_versions -> policy_decisions (submetida/auditoria_iniciada/
auditada_favoravelmente/ratificada, Miguel em todos os papeis, segregacao por
texto) -> policy_activations, via materializar_cadeia_g5r1_389cce04.py como
MODELO (nao reexecutar esse ficheiro, adaptar os parametros).

Testar sempre em transacao com ROLLBACK antes de qualquer COMMIT real.
Git commit + push apos cada passo que grava algo (repo ou BD).
Nunca parar para perguntar "confirmas?" exceto nos dois pontos marcados
EXPLICITAMENTE como PARAGEM MIGUEL abaixo — tudo o resto e autonomo.

## PASSO 0 — Confirmar estado atual, sem assumir nada
docker start solveris-pg17-migration-test
docker exec solveris-pg17-migration-test pg_isready
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "SELECT version_num FROM alembic_version;"
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "SELECT policy_version, policy_hash FROM policy_versions WHERE policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE' ORDER BY policy_version;"
# Esperado: alembic em 0065, v3 (389cce04...) ja presente. Se v4 (b6055f7e...)
# ja existir, saltar para PASSO 2.

## PASSO 1 — Materializar a política v4 (delta g4.verifier)
# Adaptar materializar_cadeia_g5r1_389cce04.py: copiar para
# materializar_v4_g4_verifier.py, trocar:
#   - POLICY_VERSION = 4
#   - POLICY_HASH = "b6055f7e69ca5bd236373a152a9acb2bafb48128cdba6560d58d5813e5beed9d"
#   - body = ler do ficheiro da candidata v4 (localizar primeiro: procurar por
#     "b6055f7e" em C:\dev\solveris-b02-g5-v5-publicacao, deve ja existir do
#     trabalho preparatorio referido na memoria)
#   - decision_id prefixos trocar de "389cce04" para "b6055f7e" (ou v4)
#   - previous policy_version continua a mesma logica: nova linhagem na mesma
#     policy_id, policy_version=4
# Rodar primeiro em dry-run (sem --execute), confirmar REUSED/novos hashes,
# so depois --execute. Mesma disciplina de transacao explicita (nunca usar
# "with session, session.begin():" junto — causa commit implicito, ja visto).

## PASSO 2 — Confirmar g4.verifier deixou de ser null
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "SELECT rules#>'{b02_noncredential,security,g5_release,documents}' FROM policy_versions WHERE policy_hash='b6055f7e69ca5bd236373a152a9acb2bafb48128cdba6560d58d5813e5beed9d';"
# Verificar visualmente: g4.verifier != null para ambos os documentos,
# g4.outcome idealmente conclusivo_favoravel (se nao, e o proximo bloqueio
# real a resolver — nao contornar, ler o SQL de 0064 outra vez para saber
# exatamente o que falta, igual ao que ja fizemos hoje).

## PASSO 3 — Ler schemas exatos antes de construir INSERTs (nao adivinhar)
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "\d artifact_references"
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "\d acquisition_executions"
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "\d acquisition_mode_bindings"
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "\d normative_artifacts"
docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "\d artifact_verification_records"
Get-Content "C:\dev\solveris-b02-g5-v5-publicacao\app\services\enterprise_b02_noncredential_acquisition.py" -TotalCount 300
Get-Content "C:\dev\solveris-b02-g5-v5-publicacao\app\models.py" | Select-String -Pattern "class ArtifactReference|class AcquisitionExecution|class AcquisitionModeBinding|class NormativeArtifact|class ArtifactVerificationRecord" -Context 0,40

## PASSO 4 — Construir as duas unidades reais, script único
# materializar_r5_duas_unidades.py:
#   - artifact_references: criar um por documento (source_id="SEFA-PR-B02-DOCUMENTAL",
#     exact_locator = URL ja confirmada em b02g5_require_real_release:
#     https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/<id>.pdf)
#   - acquisition_executions planeamento (execution_event=criacao,
#     projected_state=planeada) por documento
#   - read_cas: ler bytes reais de
#     C:\Users\Oem\Downloads\SOLVERIS_ENTERPRISE_B02_R4C_NOVA_AQUISICAO_20261020_121602_f9426b0d\CAS_G19\sha256\<hash prefix>\<hash>.pdf
#   - binding security_policy_binding / sanitization_policy_binding: ambos
#     apontam para a v4 (policy_hash b6055f7e...), nao a v3
#   - stage_authenticity: inserir artifact_verification_records com
#     verifier_id=SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN, verifier_version=1,
#     verifier_hash=fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472,
#     verification_type=authenticity, outcome=conclusivo_favoravel,
#     evidence com synthetic_only=false e g4_origin_report_binding igual ao
#     que esta no JSON da politica (a281c48d... / 9250fc93...)
#   - chamar stage_two_real_c3_units(connection, units=[unit1, unit2]) dentro
#     de UMA transacao solveris_b02_writer
# Testar em ROLLBACK primeiro (sempre). So --execute depois de limpo.

## PASSO 5 — Reserva one-shot + assinatura + COMMIT real
# Na mesma transacao real (ou logo a seguir, mesma ligacao):
#   1. SELECT b02_g5_reserve_operational_decision(approval_id, release_id,
#      operator_sha256, decision_document_sha256) como solveris_test
#      (session_user solveris_b02_writer) — usar hashes ja calculados hoje:
#      operator_sha256=062489ef..., decision_document_sha256= hash do
#      ficheiro de ratificacao v4 que Miguel ja escreveu ("RATIFICO...")
#   2. SELECT b02g5_capability_manifest() — devolve o manifesto canonico
#   3. Assinar esse manifesto com a chave issuer (Ed25519, ja gerada,
#      G5R1Chaves\issuer-private-encrypted.pem) — reaproveitar o padrao de
#      assinatura ja usado para o mandato G5/R1
#   4. SET LOCAL solveris.g5_signed_capability = '<envelope JSON>'
#   5. COMMIT
# Confirmar por leitura independente pos-commit: normative_artifacts,
# artifact_verification_records, b02_g5_operational_approval_uses — as duas
# linhas devem existir.

## PASSO 6 — Git: commitar tudo, atualizar continuidade
git -C C:\dev\solveris-b02-g5-v5-publicacao add -A
git -C C:\dev\solveris-b02-g5-v5-publicacao commit -m "feat(b02-r5): two real C3 units staged and committed, R5 closed"
git -C C:\dev\solveris-b02-g5-v5-publicacao push origin candidate/g5-v5-publicacao-local
# Atualizar docs/B02_CONTINUITY_STATE.md: R5 fechado, hashes das duas
# unidades, confirmar por leitura independente.

## PASSO 7 — R6: ir direto pelo caminho sintetico ja preparado
# NAO tentar R6 real agora (mais trabalho, mais pontos de falha). Usar o que
# ja existe, nunca aplicado:
Get-Content "C:\dev\solveris-b02-g5-v5-publicacao\tools\b02_r6_synthetic_nfeproc_pipeline_v1.py"
# Ler, adaptar se preciso aos hashes reais dos dois NormativeArtifact criados
# no PASSO 4-5, testar em ROLLBACK, aplicar a serio, documentar que R6 fica
# B02_TECHNICAL_CLOSED_FISCAL_PENDING (sintetico, nao substitui real).

## PASSO 8 — PARAGEM MIGUEL (unica paragem legitima, nao e "revisor")
# Apresentar a Miguel o resumo final: G5/R1 fechado, R5 fechado (duas
# unidades reais), R6 fechado no ambito sintetico. Pedir SO a decisao R7:
# "Miguel, autoridade constitucional final, ratifica B02 CLOSED?" — sim/nao.
# Isto nao e pedir aprovacao de terceiro: e a autoridade que o proprio
# dev-workflow ja define como dele, nao delegavel.

=====================================================================
## CORRECAO URGENTE 2026-11-06 (apos sessao com desvio de repositorio)
=====================================================================

### GUARDA 1 — UM SO REPOSITORIO, SEMPRE
Trabalhar EXCLUSIVAMENTE em C:\dev\solveris-b02-g5-v5-publicacao,
branch candidate/g5-v5-publicacao-local. NUNCA escrever, testar ou
commitar em C:\dev\saas-fiscal-demo-a1 nem em qualquer outro checkout
(saas-fiscal-demo, saas-fiscal-demo-mei, etc.) — existem varios
checkouts antigos na maquina, alguns com centenas de commits locais
nunca empurrados. Antes de qualquer git add/commit, confirmar sempre:
git -C C:\dev\solveris-b02-g5-v5-publicacao rev-parse --show-toplevel
(tem de devolver exatamente esse caminho). Se uma sessao anterior
tocou noutro repo por engano, NAO dar push la — deixar como esta e
ignorar, nunca tentar "limpar" ou reconciliar esse outro repo.

### GUARDA 2 — O "bug" planeada->concluida provavelmente nao existe
Uma sessao anterior testou um INSERT sintetico que ia direto de
planeada para concluida (2 linhas) e concluiu que stage_completion()
tem um bug de ordem. Isto E QUASE CERTAMENTE um erro no teste, nao no
codigo: stage_completion() (em
app/services/enterprise_b02_noncredential_acquisition.py) insere a
linha 'start' (ja em_execucao, nao planeada) e depois a linha
'terminal' (concluida) -- dentro da propria funcao, DUAS linhas. A
linha 'planeada' tem de ser criada pelo CALLER, ANTES de chamar
stage_completion, como predecessora de 'start'. Total real: 3 linhas
(planeada -> em_execucao -> concluida), nao 2. Antes de assumir bug
real, reler stage_completion() linha a linha e confirmar isto com um
teste sintetico CORRIGIDO (3 inserts, nao 2) em ROLLBACK. So se esse
teste corrigido tambem falhar e que ha um bug real a corrigir no
codigo -- nesse caso documentar com precisao e so entao patchar.

### GUARDA 3 — Testes sinteticos sao uteis, mas tem destino proprio
Scripts de teste sintetico (tipo _teste_stage_completion_sintetico.py)
sao bons -- SEMPRE testar em ROLLBACK antes de dados reais, isso ja
e boa pratica desta missao. Mas guardar esses scripts de teste dentro
de uma pasta propria (tests_scratch/ ou tools/diagnostics/), nunca na
raiz do repo, e sempre no repositorio certo (Guarda 1).

### GUARDA 4 — Nao reabrir o que ja fechou
G5/R1: fechado, nao reabrir.
0064/0065: aplicadas de verdade, nao reabrir, nao re-testar do zero.
Politica v4 (g4.verifier, hash b6055f7e...): se outra sessao ja a
materializou e confirmou por leitura independente (SELECT direto na
BD, nao so o output de um script), aceitar como feito e avancar. Se
nao houver confirmacao por leitura independente, reconfirmar com UMA
leitura, nao refazer a materializacao.

### PRIMEIRO PASSO DE QUALQUER SESSAO NOVA A PARTIR DE AGORA
1. git -C C:\dev\solveris-b02-g5-v5-publicacao rev-parse --show-toplevel
   (confirmar que e este o repo antes de tocar em qualquer coisa)
2. docker start solveris-pg17-migration-test ; docker exec ... pg_isready
3. SELECT version_num FROM alembic_version (confirmar 0065)
4. SELECT policy_version, policy_hash FROM policy_versions WHERE
   policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE ORDER BY
   policy_version (ver se v4 ja existe e esta correta)
5. SELECT rules#>'{b02_noncredential,security,g5_release,documents}'
   da v4 -- confirmar g4.verifier != null para os dois documentos
6. SO DEPOIS disto, seguir para o PASSO 4 do runbook original
   (construir as duas unidades reais), com a Guarda 2 em mente.

=====================================================================
## CORRECAO 2026-11-06 v2 (Guarda 5 reescrita com prova literal)
=====================================================================

### GUARDA 5 — 0064/0065 FORAM aplicadas; prova literal, nao alegacao
Os ficheiros em migrations/candidates/0064_*_CANDIDATE.py e
0065_*_CANDIDATE.py contem comentarios "CANDIDATE ONLY, not
installed" e vivem fora de migrations/versions/ -- isso descreve o
FICHEIRO antes de ser aplicado, nao o estado atual da base de dados.
O SQL desses ficheiros foi extraido e aplicado diretamente (nao via
alembic upgrade); alembic_version foi atualizado manualmente.

PROVA LITERAL, corrida e colada em 2026-11-06 (nao e alegacao, e o
output real destes comandos, confirmavel por qualquer sessao
repetindo-os):

  docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "SELECT public.b02g5_native_profile();"
    ->          b02g5_native_profile
      --------------------------------------
       REAL_PROFILE_COMPILED_APPROVED_ROOTS
      (1 row)

  docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "\d public.b02_g5_operational_approval_uses"
    -> tabela existe, colunas approval_id/release_id/assigned_txid/
       decision_document_sha256/operator_sha256/writer_name/
       database_name/reserved_at; trigger
       trg_b02_g5_one_shot_requires_two_units AFTER INSERT DEFERRABLE
       INITIALLY DEFERRED EXECUTE FUNCTION b02_g5_assert_reserved_two_units()

  docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "SELECT proname FROM pg_proc WHERE proname IN ('b02g5_capability_manifest','b02g5_precommit_validate','b02g5_require_real_release','b02_require_complete_unit') ORDER BY proname;"
    -> as 4 funcoes existem: b02_require_complete_unit,
       b02g5_capability_manifest, b02g5_precommit_validate,
       b02g5_require_real_release

  docker exec solveris-pg17-migration-test psql -U solveris_test -d solveris_b02_r4g_test -c "SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE tgname LIKE 'trg_b02g5%' OR tgname LIKE '%complete_unit%' ORDER BY tgname;"
    -> trg_b02g5_real_binding_precommit em acquisition_mode_bindings
       trg_b02g5_real_receipt_precommit em noncredential_acquisition_receipts
       trg_b02g5_real_verification_precommit em noncredential_sanitization_verifications
       z_b02_complete_unit em acquisition_executions, acquisition_mode_bindings,
       normative_artifacts, noncredential_acquisition_receipts,
       noncredential_sanitization_verifications (8 linhas no total)

NOTA RESOLVIDA: z_b02_complete_unit (mencionado na memoria sobre o
incidente RCV31-R3) e o MESMO trigger confirmado acima -- nao ha dois
mecanismos distintos, era a mesma coisa vista de angulos diferentes.

NAO EXISTE um "ficheiro real" diferente em migrations/versions/ para
procurar -- esta e a unica cadeia 0064/0065 que existe e foi aplicada.

DISCIPLINA PARA SESSOES FUTURAS (nao "nunca verificar de novo"):
se tiveres duvida sobre se 0064/0065 estao mesmo instaladas, CORRE as
4 queries acima tu mesmo -- sao baratas, rapidas, e dao prova direta.
So nao as reaplique nem procure um ficheiro alternativo: reconfirmar
com leitura, nunca reaplicar, exatamente a disciplina da Guarda 4.
