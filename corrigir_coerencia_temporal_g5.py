"""
Corrige a incoerencia temporal encontrada no candidato fd5920cd... --
sincroniza TODA a cadeia de campos temporais, nao so o campo de topo.
NAO prolonga datas de validade G4 sem ato real -- identifica exatamente
o que falta em vez de fabricar.
Preserva o commit 598186fd intocado. Preserva os exames G4 favoraveis
como evidencia historica, distintos de qualquer ato de atualizacao.
NAO instala, NAO ativa, NAO assina, NAO escreve na base.
"""
import json, hashlib, copy, difflib, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DOWNLOADS = Path.home() / "Downloads"
REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

PROPOSED_START_UTC = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
PROPOSED_END_UTC   = datetime(2026, 11, 4, 7, 56, 30, 910737, tzinfo=timezone.utc)

# ---------------------------------------------------------------------
# 1. Original preservado
# ---------------------------------------------------------------------
section("1. Original -- intocado, verificado")
orig_path = DOWNLOADS / "SOLVERIS_B02_G5_AUTORIZADO_5f59188a48b749e2921217c2f880d73e" / "POLICY_G5_CANONICAL.json"
orig_raw = orig_path.read_bytes()
orig_hash = hashlib.sha256(orig_raw).hexdigest()
assert orig_hash == "57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa"
orig_data = json.loads(orig_raw.decode("utf-8"))
log(f"Confirmado: {orig_hash}")

# ---------------------------------------------------------------------
# 2. AUDITORIA EXAUSTIVA -- encontrar TODOS os campos temporais,
#    nao so os que ja conheciamos.
# ---------------------------------------------------------------------
section("2. Auditoria exaustiva de TODOS os campos temporais na cadeia")
TIME_KEY_PATTERN = re.compile(r"^(from|until|valid_from|valid_until)$")
ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

temporal_fields = []
def scan_temporal(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_path = f"{path}.{k}" if path else k
            if TIME_KEY_PATTERN.match(k) and isinstance(v, str) and ISO_PATTERN.match(v):
                temporal_fields.append((full_path, v))
            scan_temporal(v, full_path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_temporal(v, f"{path}[{i}]")

scan_temporal(orig_data)
log(f"Campos temporais encontrados: {len(temporal_fields)}")
for path, val in temporal_fields:
    log(f"  {path} = {val}")

# ---------------------------------------------------------------------
# 3. Classificar cada campo: sincronizavel diretamente, ou exige ato real
# ---------------------------------------------------------------------
section("3. Classificacao -- sincronizavel vs exige ato real externo")

# Campos que podem ser sincronizados diretamente com a janela proposta
# (sao a propria proposta operacional, nao dependem de ato externo):
SYNC_DIRECT_PREFIXES = [
    "declared_material_applicability",
    "rules.b02_noncredential.security.g5_release",
]
# Campos de validade G4 por documento -- NAO sincronizados diretamente.
# Dependem de um ATO REAL de atualizacao/confirmacao de validade G4,
# distinto de repetir o exame de origem (que ja foi favoravel e fica
# preservado como esta).
G4_VALIDITY_SUFFIX_PATTERN = re.compile(r"documents\[\d+\]\.g4\.(valid_from|valid_until)$")

sync_direct = []
requires_real_act = []
for path, val in temporal_fields:
    if G4_VALIDITY_SUFFIX_PATTERN.search(path):
        requires_real_act.append((path, val))
    elif any(path.startswith(p) for p in SYNC_DIRECT_PREFIXES):
        sync_direct.append((path, val))
    else:
        log(f"  NAO CLASSIFICADO (requer revisao manual): {path} = {val}")

log(f"\nSincronizaveis diretamente com a proposta operacional: {len(sync_direct)}")
for p, v in sync_direct:
    log(f"  {p}")
log(f"\nExigem ato real externo (NAO sincronizados por este script): {len(requires_real_act)}")
for p, v in requires_real_act:
    log(f"  {p} (atual: {v})")

# ---------------------------------------------------------------------
# 4. Construir candidato corrigido
# ---------------------------------------------------------------------
section("4. Candidato corrigido -- sincronizacao completa + marcacao explicita")
candidate_body = copy.deepcopy(orig_data)

def set_by_path(obj, path, value):
    parts = re.split(r"\.(?![^\[]*\])", path)
    cur = obj
    for i, part in enumerate(parts):
        m = re.match(r"^([a-zA-Z_0-9]+)(\[(\d+)\])?$", part)
        key, idx = m.group(1), m.group(3)
        if idx is not None:
            cur = cur[key][int(idx)]
        else:
            if i == len(parts) - 1:
                cur[key] = value
            else:
                cur = cur[key]

for path, _ in sync_direct:
    if path.endswith(".from"):
        set_by_path(candidate_body, path, PROPOSED_START_UTC.isoformat())
    elif path.endswith(".until"):
        set_by_path(candidate_body, path, PROPOSED_END_UTC.isoformat())

for path, old_val in requires_real_act:
    marker = "REQUIRES_CURRENT_G4_VALIDITY_ACT_NOT_PRESENT"
    set_by_path(candidate_body, path, marker)
    log(f"Marcado (nao fabricado): {path} -> {marker}  (era: {old_val})")

log("\nIMPORTANTE: 'origin_report_binding' (o exame de origem favoravel) de")
log("cada documento NAO foi alterado -- preservado como evidencia historica,")
log("distinta da janela de validade operacional que requer ato novo.")

if "subject" in candidate_body:
    candidate_body["subject"].pop("policy_hash", None)

full_candidate = {
    "__AVISO_CAMPOS_INSTITUCIONAIS__": (
        "Campos de ator/ratificacao/auditoria/decisao/assinatura em "
        "'policy_candidate_body' pertencem ao PREDECESSOR (57982f46...) e "
        "NAO constituem atos sobre este sucessor."
    ),
    "__AVISO_VALIDADE_G4__": (
        "Os campos g4.valid_from/valid_until por documento estao marcados "
        "REQUIRES_CURRENT_G4_VALIDITY_ACT_NOT_PRESENT. Isto NAO e repeticao "
        "do exame de origem (que permanece favoravel e preservado via "
        "origin_report_binding, inalterado). E a ausencia de um ato real "
        "de confirmacao/atualizacao de validade operacional G4 cobrindo a "
        "janela proposta. Ver secao 5 do relatorio para o que falta exatamente."
    ),
    "status": "CANDIDATO_COM_LACUNA_G4_IDENTIFICADA_SEM_EFICACIA_OPERACIONAL",
    "predecessor_policy_hash": orig_hash,
    "supersedes_blocked_candidate": "fd5920cd3268d12d1c0e78e9b50fca9fd1ef102cd937a6e377a3064d782631ab",
    "policy_candidate_body": candidate_body,
}
candidate_raw = json.dumps(full_candidate, indent=2, ensure_ascii=False).encode("utf-8")
candidate_hash = hashlib.sha256(candidate_raw).hexdigest()
cand_path = REPO / "POLICY_G5_CANDIDATO_V2_COERENTE.json"
cand_path.write_text(candidate_raw.decode("utf-8"), encoding="utf-8")
log(f"\nGravado: {cand_path.name}")
log(f"SHA-256 novo: {candidate_hash}")

# ---------------------------------------------------------------------
# 5. Diff causal completo (vs original, nao vs candidato bloqueado)
# ---------------------------------------------------------------------
section("5. Diff causal completo -- original vs candidato v2")
orig_lines = json.dumps(orig_data, indent=2, ensure_ascii=False).splitlines(keepends=True)
cand_lines = json.dumps(candidate_body, indent=2, ensure_ascii=False).splitlines(keepends=True)
diff = list(difflib.unified_diff(orig_lines, cand_lines, fromfile="ORIGINAL_57982f46.json", tofile="CANDIDATO_V2_body.json", n=1))
diff_text = "".join(diff)
log(diff_text)
diff_path = REPO / "DIFF_CAUSAL_COMPLETO_G5_V2.diff"
diff_path.write_text(diff_text, encoding="utf-8")

# ---------------------------------------------------------------------
# 6. Propagacao operador/header -- mesma fonte, agora com os 2 campos
#    sincronizados diretamente.
# ---------------------------------------------------------------------
section("6. Propagacao operador/header -- mesma fonte unica")
brt = timezone(timedelta(hours=-3))
op_valid_until_brt = PROPOSED_END_UTC.astimezone(brt)
log(f"Operador VALID_UNTIL (-03:00): {op_valid_until_brt.isoformat()}")
log(f"Header g5_policy_binding janela: from={PROPOSED_START_UTC.isoformat()} until={PROPOSED_END_UTC.isoformat()}")
log("Header decision_hash/decision_id: REQUIRED_REAL_ACT_NOT_PRESENT (inalterado desde a preparacao anterior)")

# ---------------------------------------------------------------------
# 7. O que falta exatamente -- ato externo identificado
# ---------------------------------------------------------------------
section("7. Ato externo em falta -- identificado, nao fabricado")
log("Para CADA um dos 2 documentos, falta um ATO REAL que confirme ou renove")
log("a validade operacional G4 (campo g4.valid_from/valid_until) cobrindo a")
log("janela proposta (03-04/11). Este ato:")
log("  - NAO repete o exame de origem (origin_report_binding permanece o mesmo,")
log("    ja favoravel, preservado sem alteracao)")
log("  - E uma confirmacao/renovacao de que essa origem favoravel CONTINUA")
log("    aplicavel/atual na nova janela -- tipicamente um novo registo de")
log("    'policy_activations.operational_interval' real para a politica G4")
log("    (05ede0f8...), ou um ato equivalente que Miguel/auditor emita")
log("    confirmando vigencia atual sem reexaminar a origem do zero.")
log("  - Sem esse ato, o candidato fica honestamente marcado como incompleto")
log("    nesses 2 campos -- este script NAO inventa valores para eles.")

Path(r"C:\dev\saas-fiscal-demo-a1\correcao_coerencia_temporal_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado em: C:\\dev\\saas-fiscal-demo-a1\\correcao_coerencia_temporal_OUTPUT.txt")
print(f"\nRESUMO: novo_candidato_sha256={candidate_hash}")
