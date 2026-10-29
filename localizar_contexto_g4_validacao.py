"""
Localiza o contexto EXATO onde 0064 compara doc->'g4'->>'valid_from' com
clock_timestamp() -- nome da funcao, se cruza com uma linha de BD real
(policy_activations/policy_decisions) ou so verifica o valor embutido.
Procura no ficheiro real da migration 0064 e nos ficheiros ja gravados
desta sessao. So leitura.
"""
import re
from pathlib import Path

REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

section("A. Procurar literal \"g4'->>'valid_from\" no ficheiro real de 0064")
f = REPO / "migrations" / "candidates" / "0064_b02_g5_controlled_real_cas_CANDIDATE.py"
text = f.read_text(encoding="utf-8", errors="replace")
m = re.search(r'_SQL\s*=\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
sql_raw = m.group(1).encode().decode('unicode_escape') if m else text

idx = sql_raw.find("g4'->>'valid_from")
if idx == -1:
    idx = sql_raw.find("'g4'")
log(f"Primeira ocorrencia de \"g4\" na string _SQL: index {idx}")
if idx != -1:
    # mostra 2500 chars antes para capturar o nome da funcao e o contexto
    start = max(0, idx - 2500)
    log(sql_raw[start:idx+600])
else:
    log("NAO encontrado na string _SQL deste ficheiro -- pode estar noutra")
    log("parte do candidato (ex: funcao nao lida nesta sessao) ou nos")
    log("ficheiros de referencia (deploy_0064_candidate.py, ROOT_CONSTRAINTS).")

section("B. Procurar tambem nos outputs ja gravados desta sessao (partes do 0064)")
for fname in ["tracar_assinatura_g5_PARTE_A.txt", "tracar_assinatura_g5_OUTPUT.txt"]:
    fp = REPO / fname
    if fp.is_file():
        t = fp.read_text(encoding="utf-8", errors="replace")
        idx2 = t.find("valid_from")
        if idx2 != -1:
            log(f"\n--- {fname} (primeira ocorrencia 'valid_from') ---")
            log(t[max(0,idx2-1500):idx2+800])

section("C. Confirmar: a verificacao cruza com policy_activations/policy_decisions, ou e so valor embutido vs relogio?")
# procura por padroes de cruzamento perto da ocorrencia g4
for keyword in ["policy_activations", "policy_decisions", "SELECT.*INTO.*policy_activations", "operational_interval"]:
    hits = [m.start() for m in re.finditer(re.escape(keyword) if "SELECT" not in keyword else keyword, sql_raw)]
    log(f"Ocorrencias de '{keyword}' na SQL completa: {len(hits)}")

Path(r"C:\dev\saas-fiscal-demo-a1\contexto_g4_validacao_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado em: C:\\dev\\saas-fiscal-demo-a1\\contexto_g4_validacao_OUTPUT.txt")
