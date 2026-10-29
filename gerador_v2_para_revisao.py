"""
Gerador de sucessores G5 v2 -- CORRIGIDO para revisao segregada.
Diferenca face a v1: todo campo copiado do historico que e
ator/ratificacao/auditoria/decisao/assinatura e explicitamente anotado
como pertencente ao PREDECESSOR (57982f46...), nunca apresentado como
um ato emitido sobre o conteudo sucessor.

Janela de teste (ano 2099), nunca a real. Nao fixa nem abre a janela G5.
Nao instala, nao ratifica, nao ativa, nao escreve na base.
Produz: candidato + diff completo, para revisao segregada e commit Git
como candidato (nunca merge/instalacao).
"""
import json, hashlib, copy, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

DOWNLOADS = Path.home() / "Downloads"
REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

TEST_WINDOW_START_UTC = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
TEST_WINDOW_END_UTC   = datetime(2099, 1, 2, 7, 56, 30, 910737, tzinfo=timezone.utc)

section("1. Original -- localizado, verificado, intocado")
orig_path = DOWNLOADS / "SOLVERIS_B02_G5_AUTORIZADO_5f59188a48b749e2921217c2f880d73e" / "POLICY_G5_CANONICAL.json"
orig_raw = orig_path.read_bytes()
orig_hash = hashlib.sha256(orig_raw).hexdigest()
assert orig_hash == "57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa"
log(f"Original: {orig_path}")
log(f"sha256 confirmado: {orig_hash}")
orig_data = json.loads(orig_raw.decode("utf-8"))

section("2. FRONTEIRA do conteudo que gera o policy_hash -- distincao explicita")
log("O hash e calculado sobre TODO o ficheiro JSON tal como esta em disco")
log("(confirmado no turno anterior: sha256(bytes do ficheiro) == policy_hash).")
log("Isto inclui 'policy' (conteudo normativo) E qualquer metadado de topo")
log("(ex: 'ratification_record_sha256', 'ids', 'identity_proofs', 'subject',")
log("'schema', 'window_until') -- TUDO conta para o hash, nao so 'policy'.")
log("Metadados de PREPARACAO que o gerador adiciona (status, test_marker,")
log("predecessor_policy_hash) NAO existiam no original e por isso alteram")
log("o hash do sucessor -- o que e esperado e correto: um objeto novo tem")
log("hash novo. A fronteira e: ficheiro completo = conteudo hashed.")

# ---------------------------------------------------------------------
# 3. Identificar TODOS os campos institucionais copiados do historico,
#    e anota-los explicitamente como NAO aplicaveis ao sucessor.
# ---------------------------------------------------------------------
section("3. Anotacao explicita dos campos historicos copiados (nao atos sobre o sucessor)")

test_candidate = copy.deepcopy(orig_data)
policy_node = test_candidate.get("policy", test_candidate)

old_from = policy_node["declared_material_applicability"]["from"]
old_until = policy_node["declared_material_applicability"]["until"]
policy_node["declared_material_applicability"]["from"] = TEST_WINDOW_START_UTC.isoformat()
policy_node["declared_material_applicability"]["until"] = TEST_WINDOW_END_UTC.isoformat()

institutional_paths_found = []
def annotate(obj, path=""):
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            full_path = f"{path}.{k}" if path else k
            if k in ("ratification_record_sha256", "identity_proofs", "ids") or \
               any(term in full_path.lower() for term in ["actor", "ratif", "audit", "decision_id", "decision_hash", "signature", "mandate"]):
                institutional_paths_found.append(full_path)
            annotate(obj[k], full_path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            annotate(v, f"{path}[{i}]")

annotate(test_candidate)
log(f"Campos institucionais encontrados (copiados do predecessor): {len(set(institutional_paths_found))}")
for p in sorted(set(institutional_paths_found)):
    log(f"  {p}")

# Anotacao de topo, explicita e impossivel de ignorar
test_candidate = {
    "__AVISO_CAMPOS_INSTITUCIONAIS__": (
        "Os campos 'ids', 'identity_proofs', 'ratification_record_sha256' e "
        "quaisquer sub-campos de ator/ratificacao/auditoria/decisao/assinatura "
        "dentro de 'policy_candidate_body' abaixo pertencem ao PREDECESSOR "
        "(policy_hash 57982f46...) e NAO constituem submissao, auditoria, "
        "ratificacao ou assinatura deste objeto sucessor. Sao copiados apenas "
        "para referencia estrutural. O sucessor NAO tem nenhum ato real "
        "emitido sobre ele ate que submissao/auditoria/ratificacao proprias "
        "ocorram para este policy_hash especifico (ainda PENDENTE)."
    ),
    "status": "TESTE_ISOLADO_SEM_AUTORIDADE_OPERACIONAL_PARA_REVISAO_DO_GERADOR",
    "predecessor_policy_hash": orig_hash,
    "test_marker": "NAO_USAR_EM_PRODUCAO_JANELA_ANO_2099",
    "policy_candidate_body": test_candidate,
}
if "subject" in test_candidate["policy_candidate_body"]:
    test_candidate["policy_candidate_body"]["subject"].pop("policy_hash", None)

test_raw = json.dumps(test_candidate, indent=2, ensure_ascii=False).encode("utf-8")
test_hash = hashlib.sha256(test_raw).hexdigest()

out_path = REPO / "POLICY_G5_CANDIDATO_TESTE_ISOLADO_V2.json"
out_path.write_text(test_raw.decode("utf-8"), encoding="utf-8")
log(f"\nGravado: {out_path}")
log(f"sha256 do candidato (!= 57982f46...): {test_hash}")

# ---------------------------------------------------------------------
# 4. Diff completo original vs candidato
# ---------------------------------------------------------------------
section("4. Diff completo -- original vs candidato de teste")
import difflib
orig_lines = json.dumps(orig_data, indent=2, ensure_ascii=False).splitlines(keepends=True)
cand_lines = json.dumps(test_candidate["policy_candidate_body"], indent=2, ensure_ascii=False).splitlines(keepends=True)
diff = list(difflib.unified_diff(orig_lines, cand_lines, fromfile="ORIGINAL_57982f46.json", tofile="CANDIDATO_TESTE_body.json"))
diff_text = "".join(diff)
log(diff_text if diff_text else "(sem diferencas detetadas -- inesperado)")
diff_path = REPO / "DIFF_POLICY_G5_ORIGINAL_vs_CANDIDATO_TESTE.diff"
diff_path.write_text(diff_text, encoding="utf-8")
log(f"\nDiff gravado em: {diff_path}")

# ---------------------------------------------------------------------
# 5. Propagacao dos instantes para operador e header -- confirmacao
# ---------------------------------------------------------------------
section("5. Propagacao dos instantes -- politica / operador / header, mesma fonte")
brt = timezone(timedelta(hours=-3))
operator_valid_until_brt = TEST_WINDOW_END_UTC.astimezone(brt)
roundtrip = operator_valid_until_brt.astimezone(timezone.utc)
log(f"Politica  (from/until UTC): {TEST_WINDOW_START_UTC.isoformat()} / {TEST_WINDOW_END_UTC.isoformat()}")
log(f"Header    (from/until UTC): {TEST_WINDOW_START_UTC.isoformat()} / {TEST_WINDOW_END_UTC.isoformat()}  (decision_hash/id = REQUIRED_REAL_ACT_NOT_PRESENT)")
log(f"Operador  (VALID_UNTIL -03:00): {operator_valid_until_brt.isoformat()}  (roundtrip->UTC bate: {roundtrip == TEST_WINDOW_END_UTC})")

# ---------------------------------------------------------------------
# 6. Preparar para Git como CANDIDATO (nunca merge/instalacao)
# ---------------------------------------------------------------------
section("6. Preparacao Git -- candidato para revisao segregada, nunca instalacao")
log("Comandos a correr manualmente (nao executados por este script):")
log(f"  cd {REPO}")
log(f"  git checkout -b candidate/g5-successor-window-prep")
log(f"  git add POLICY_G5_CANDIDATO_SUCESSOR.json POLICY_G5_CANDIDATO_TESTE_ISOLADO_V2.json DIFF_POLICY_G5_ORIGINAL_vs_CANDIDATO_TESTE.diff gerador_v2_para_revisao.py gerador_sucessores_OUTPUT.txt")
log(f"  git commit -m 'G5 successor prep: test-window generator + diff, NOT ratified, NOT installed'")
log(f"  # NUNCA merge para branch principal antes de revisao segregada + atos institucionais reais")

Path(r"C:\dev\saas-fiscal-demo-a1\gerador_v2_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado em: C:\\dev\\saas-fiscal-demo-a1\\gerador_v2_OUTPUT.txt")
