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
