"""
Prepara o conteudo sucessor G5 completo para submissao ao revisor.
Usa o gerador ja aprovado (mesma logica do commit 93932837).
Datas propostas: concretas, marcadas SEM EFICACIA OPERACIONAL ate auditoria
+ ratificacao. Preserva o predecessor intocado. Nao fabrica aceitacao do
revisor nem resultado de auditoria.
"""
import json, hashlib, copy, difflib
from pathlib import Path
from datetime import datetime, timezone, timedelta

DOWNLOADS = Path.home() / "Downloads"
REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

# ---------------------------------------------------------------------
# 1. Datas propostas CONCRETAS -- dentro do mandato aprovado
#    (2026-10-29T12:00Z .. 2026-11-08T00:00Z), com buffer para auditoria
#    e ratificacao ocorrerem ANTES do inicio proposto. Duracao <=24h.
#    Marcadas SEM EFICACIA OPERACIONAL -- so efeito apos ratificacao.
# ---------------------------------------------------------------------
PROPOSED_START_UTC = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
PROPOSED_END_UTC   = datetime(2026, 11, 4, 7, 56, 30, 910737, tzinfo=timezone.utc)
assert (PROPOSED_END_UTC - PROPOSED_START_UTC).total_seconds() <= 86400
MANDATE_START = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
MANDATE_END   = datetime(2026, 11, 8, 0, 0, 0, tzinfo=timezone.utc)
assert MANDATE_START <= PROPOSED_START_UTC < PROPOSED_END_UTC <= MANDATE_END

section("0. Datas propostas -- CONCRETAS, SEM EFICACIA OPERACIONAL ate ratificacao")
log(f"Proposta operacional: {PROPOSED_START_UTC.isoformat()} .. {PROPOSED_END_UTC.isoformat()}")
log(f"Dentro do mandato aprovado ({MANDATE_START.isoformat()} .. {MANDATE_END.isoformat()})? True")
log("Buffer antes do inicio proposto para auditoria+ratificacao ocorrerem: ~5 dias")
log("ESTA PROPOSTA NAO ABRE A JANELA OPERACIONAL G5. So produz efeito apos")
log("auditoria do revisor e ratificacao expressa de Miguel sobre o hash exato.")

# ---------------------------------------------------------------------
# 1. Original preservado
# ---------------------------------------------------------------------
section("1. Original -- intocado, verificado")
orig_path = DOWNLOADS / "SOLVERIS_B02_G5_AUTORIZADO_5f59188a48b749e2921217c2f880d73e" / "POLICY_G5_CANONICAL.json"
orig_raw = orig_path.read_bytes()
orig_hash = hashlib.sha256(orig_raw).hexdigest()
assert orig_hash == "57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa"
log(f"Confirmado: {orig_hash}")
orig_data = json.loads(orig_raw.decode("utf-8"))

# ---------------------------------------------------------------------
# 2. Candidato com datas concretas -- campos institucionais isolados
#    e rotulados como pertencentes ao PREDECESSOR (mesma logica do v2).
# ---------------------------------------------------------------------
section("2. Candidato sucessor -- datas concretas aplicadas")
candidate_body = copy.deepcopy(orig_data)
policy_node = candidate_body.get("policy", candidate_body)
old_from = policy_node["declared_material_applicability"]["from"]
old_until = policy_node["declared_material_applicability"]["until"]
policy_node["declared_material_applicability"]["from"] = PROPOSED_START_UTC.isoformat()
policy_node["declared_material_applicability"]["until"] = PROPOSED_END_UTC.isoformat()
log(f"from:  {old_from}  ->  {PROPOSED_START_UTC.isoformat()}")
log(f"until: {old_until}  ->  {PROPOSED_END_UTC.isoformat()}")

if "subject" in candidate_body:
    candidate_body["subject"].pop("policy_hash", None)

full_candidate = {
    "__AVISO_CAMPOS_INSTITUCIONAIS__": (
        "Campos de ator/ratificacao/auditoria/decisao/assinatura dentro de "
        "'policy_candidate_body' pertencem ao PREDECESSOR (policy_hash "
        "57982f46...) e NAO constituem submissao, auditoria, ratificacao ou "
        "assinatura deste objeto sucessor."
    ),
    "status": "CANDIDATO_PARA_AUDITORIA_SEM_EFICACIA_OPERACIONAL",
    "predecessor_policy_hash": orig_hash,
    "mandato_base": "aprovado por Miguel, intervalo 2026-10-29T12:00Z a 2026-11-08T00:00Z",
    "proposed_window_note": "Datas propostas pelo proponente; sem eficacia ate ratificacao de Miguel sobre este hash exato.",
    "policy_candidate_body": candidate_body,
}
candidate_raw = json.dumps(full_candidate, indent=2, ensure_ascii=False).encode("utf-8")
candidate_hash = hashlib.sha256(candidate_raw).hexdigest()

cand_path = REPO / "POLICY_G5_CANDIDATO_PARA_AUDITORIA.json"
cand_path.write_text(candidate_raw.decode("utf-8"), encoding="utf-8")
log(f"\nGravado: {cand_path.name}")
log(f"SHA-256 do candidato (objeto exato para auditoria): {candidate_hash}")

# ---------------------------------------------------------------------
# 3. Diff minimo
# ---------------------------------------------------------------------
section("3. Diff -- original vs candidato")
orig_lines = json.dumps(orig_data, indent=2, ensure_ascii=False).splitlines(keepends=True)
cand_lines = json.dumps(candidate_body, indent=2, ensure_ascii=False).splitlines(keepends=True)
diff = list(difflib.unified_diff(orig_lines, cand_lines, fromfile="ORIGINAL_57982f46.json", tofile="CANDIDATO_PARA_AUDITORIA_body.json"))
diff_text = "".join(diff)
log(diff_text)
diff_path = REPO / "DIFF_POLICY_G5_PARA_AUDITORIA.diff"
diff_path.write_text(diff_text, encoding="utf-8")
log(f"Diff gravado: {diff_path.name}")

# ---------------------------------------------------------------------
# 4. Dossie de submissao -- referencia aos 4 vinculos ja recuperados,
#    SEM reconstruir o conteudo (so id+hash+limite, ja conhecidos).
# ---------------------------------------------------------------------
section("4. Dossie de submissao")
submission = {
    "schema": "B02_G5_SUCCESSOR_SUBMISSION_PACKAGE_V1",
    "status": "SUBMISSAO_PREPARADA_AGUARDA_ACEITACAO_DO_REVISOR",
    "candidato": {
        "ficheiro": "POLICY_G5_CANDIDATO_PARA_AUDITORIA.json",
        "sha256": candidate_hash,
        "predecessor_policy_hash": orig_hash,
    },
    "diff": "DIFF_POLICY_G5_PARA_AUDITORIA.diff",
    "janela_proposta": {
        "from": PROPOSED_START_UTC.isoformat(),
        "until": PROPOSED_END_UTC.isoformat(),
        "eficacia": "NENHUMA ate ratificacao de Miguel sobre este hash exato",
    },
    "evidencias_reutilizadas_do_predecessor": [
        {"id": "B02-G5-MANDATES-AND-COMMIT-PURPOSE-1", "sha256": "11ad4a27cce80380659b94a54404877e7b7b65eb9431b7acc5a07e96299b97fe",
         "limite": "manifestacao documental, nao assinatura criptografica, sem valid_from/until proprios"},
        {"id": "B02-G5-METHOD-TECHNICAL-REVIEW-1", "sha256": "4bbbd811d7cc6434e9e4ecdf9d33a2f1cac46bee1e004e54d88dd9a2a2c83c5d",
         "limite": "exame previo, sanitizacao operacional INCONCLUSIVA, nao auditoria completa"},
        {"id": "B02-G5-PROPONENT-ACCEPTANCE-1", "sha256": "a9dfd277eaf1b750bc23388c10d6adb1c8b9966f47d324954e41efc7212db424",
         "limite": "aceitacao historica do predecessor; condicao para o sucessor exige nova aceitacao (ver pedido ao revisor em paralelo)"},
        {"id": "B02-G5-REVIEWER-ACCEPTANCE-1", "sha256": "6a6ad0f34d8ef879f1a264ac7691cd0376ce124d898e71e4824fa41252bc4035",
         "limite": "aceitacao historica do predecessor; NAO transferida automaticamente para o sucessor"},
    ],
    "limites_explicitos": [
        "nao e assinatura transacional real",
        "nao abre janela operacional G5",
        "nao instala", "nao ativa", "nao escreve no PostgreSQL protegido",
        "se as datas mudarem, novo hash e novo delta serao apresentados -- este objeto fica imutavel",
    ],
    "questoes_para_parecer_do_revisor": [
        "O metodo referenciado em 'c79d8916...' (funcional proposto) permanece sem alteracoes desde o exame previo (4bbbd811...)? Exige confirmacao atual.",
        "A sanitizacao operacional, marcada INCONCLUSIVA no exame previo, tem desde entao resultado atualizado?",
        "A janela proposta (03/11 12:00Z a 04/11 07:56:30Z) e compativel com o tempo necessario para auditoria completa antes do inicio proposto?",
    ],
}
sub_path = REPO / "SUBMISSAO_G5_SUCESSOR_PARA_REVISOR.json"
sub_path.write_text(json.dumps(submission, indent=2, ensure_ascii=False), encoding="utf-8")
log(f"Gravado: {sub_path.name}")

# ---------------------------------------------------------------------
# 5. Pedido de identificacao/aceitacao/conflitos ao revisor -- VAZIO,
#    nao preenchido por ninguem em nome dele.
# ---------------------------------------------------------------------
section("5. Pedido de identificacao/aceitacao ao revisor -- campos vazios")
reviewer_request = {
    "schema": "B02_G5_REVIEWER_IDENTIFICATION_REQUEST_V1",
    "endereco_a": "execucao revisora segregada designada por Miguel para apreciar o sucessor G5",
    "objeto_a_rever": {
        "candidato_sha256": candidate_hash,
        "diff": "DIFF_POLICY_G5_PARA_AUDITORIA.diff",
        "predecessor_policy_hash": orig_hash,
    },
    "campos_que_a_propria_execucao_revisora_deve_preencher": {
        "identificacao_propria": None,
        "aceitacao_ou_recusa_do_papel": None,
        "declaracao_de_conflitos_de_interesse": None,
        "confirmacao_de_segregacao_funcional_do_proponente": None,
        "parecer_sobre_as_questoes_listadas_na_submissao": None,
    },
    "aviso": "Nenhum destes campos e preenchido pelo proponente, pelo executor ou por Miguel. Aguarda manifestacao propria da execucao designada.",
}
req_path = REPO / "PEDIDO_IDENTIFICACAO_REVISOR_G5.json"
req_path.write_text(json.dumps(reviewer_request, indent=2, ensure_ascii=False), encoding="utf-8")
log(f"Gravado: {req_path.name}")

Path(r"C:\dev\saas-fiscal-demo-a1\preparar_submissao_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado em: C:\\dev\\saas-fiscal-demo-a1\\preparar_submissao_OUTPUT.txt")
print(f"\nRESUMO: candidato_sha256={candidate_hash}")
