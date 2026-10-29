"""
Preenche os 4 campos g4.valid_from/until com uma janela corrente candidata,
SEM persistir nem ratificar. Nao repete o exame de origem (origin_report_binding
inalterado). A legitimidade destes valores so existe apos a ratificacao real
de Miguel sobre este hash exato -- por isso o objeto fica explicitamente
marcado como proposta, nao facto consumado.
"""
import json, hashlib, copy, difflib
from pathlib import Path
from datetime import datetime, timezone

DOWNLOADS = Path.home() / "Downloads"
REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

# a janela G4 proposta cobre a mesma janela G5 operacional ja proposta
# (03-04/11), para que clock_timestamp() no momento de uso esteja dentro
# de ambas.
G4_VALID_FROM = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
G4_VALID_UNTIL = datetime(2026, 11, 4, 7, 56, 30, 910737, tzinfo=timezone.utc)

section("1. Carregar candidato v2 (a9893526) -- ja no repo")
v2_path = REPO / "POLICY_G5_CANDIDATO_V2_COERENTE.json"
v2_data = json.loads(v2_path.read_text(encoding="utf-8"))
body = v2_data["policy_candidate_body"]

section("2. Preencher os 4 campos g4 -- proposta, nao ato consumado")
docs = body["rules"]["b02_noncredential"]["security"]["g5_release"]["documents"]
for i, doc in enumerate(docs):
    old_from = doc["g4"]["valid_from"]
    old_until = doc["g4"]["valid_until"]
    doc["g4"]["valid_from"] = G4_VALID_FROM.isoformat()
    doc["g4"]["valid_until"] = G4_VALID_UNTIL.isoformat()
    log(f"documents[{i}].g4.valid_from:  {old_from} -> {G4_VALID_FROM.isoformat()}")
    log(f"documents[{i}].g4.valid_until: {old_until} -> {G4_VALID_UNTIL.isoformat()}")
    log(f"documents[{i}].g4.origin_report_binding: INALTERADO ({doc['g4']['origin_report_binding']['sha256'][:16]}...)")

v2_data["status"] = "CANDIDATO_COMPLETO_AGUARDA_RATIFICACAO_NAO_RATIFICADO"
v2_data["supersedes_blocked_candidate"] = "fc93605e654325d2bab1ceb75c5600ab2410d7e347b65644d22ccdef30b851a2"
v2_data["__AVISO_G4_PREENCHIDO__"] = (
    "Os valores g4.valid_from/until acima sao PROPOSTA do proponente, nao "
    "ato institucional consumado. A sua legitimidade depende inteiramente "
    "da ratificacao de Miguel sobre este policy_hash exato -- antes disso, "
    "nao tem efeito."
)

final_raw = json.dumps(v2_data, indent=2, ensure_ascii=False).encode("utf-8")
final_hash = hashlib.sha256(final_raw).hexdigest()
final_path = REPO / "POLICY_G5_CANDIDATO_V3_COMPLETO.json"
final_path.write_text(final_raw.decode("utf-8"), encoding="utf-8")
log(f"\nGravado: {final_path.name}")
log(f"SHA-256 novo (candidato completo, ainda nao ratificado): {final_hash}")

section("3. Diff -- v2 (placeholders) vs v3 (preenchido)")
v2_lines = v2_path.read_text(encoding="utf-8").splitlines(keepends=True)
v3_lines = final_raw.decode("utf-8").splitlines(keepends=True)
diff = list(difflib.unified_diff(v2_lines, v3_lines, fromfile="V2_fc93605e_placeholders.json", tofile="V3_preenchido.json", n=1))
diff_text = "".join(diff)
log(diff_text)
diff_path = REPO / "DIFF_V2_PARA_V3_G4_PREENCHIDO.diff"
diff_path.write_text(diff_text, encoding="utf-8")

Path(r"C:\dev\saas-fiscal-demo-a1\preencher_g4_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print(f"\nRESUMO: v3_sha256={final_hash}")
