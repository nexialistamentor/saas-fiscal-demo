"""
Identifica o SERVICO REAL que cria (nao so le) linhas de policy_activations/
policy_decisions -- predecessores, registos e permissoes exigidos.
So leitura. Nenhuma escrita, nenhuma ativacao.
"""
import re
from pathlib import Path

REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

# ---------------------------------------------------------------------
section("1. Quem CRIA policy_activations (INSERT, nao SELECT)")
for fp in (REPO / "app").rglob("*.py"):
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"INSERT INTO.*policy_activations|policy_activations\s*\(", line) and "SELECT" not in line.upper():
            log(f"  {fp.relative_to(REPO)}:{i}: {line.strip()[:200]}")
        if re.search(r"class PolicyActivation\b", line):
            log(f"  [MODELO] {fp.relative_to(REPO)}:{i}: {line.strip()[:200]}")

section("2. Funcoes de servico com 'activation' ou 'ativar' no nome, fora de testes/candidatos")
for fp in (REPO / "app" / "services").rglob("*.py"):
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"^def\s+\w*activat\w*|^def\s+\w*ativa\w*", line, re.IGNORECASE):
            log(f"  {fp.relative_to(REPO)}:{i}: {line.strip()[:200]}")

section("3. Quem chama require_current_authority -- para ver 'selected' (technical_actor/activated_at)")
for fp in (REPO / "app").rglob("*.py"):
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if "require_current_authority(" in text and "def require_current_authority" not in text:
        log(f"\n--- {fp.relative_to(REPO)} ---")
        idx = text.find("require_current_authority(")
        log(text[max(0,idx-600):idx+400])

section("4. Modelo PolicyActivation/PolicyDecision -- campos obrigatorios (app/models.py)")
models_text = (REPO / "app" / "models.py").read_text(encoding="utf-8", errors="replace")
for cls_name in ["PolicyActivation", "PolicyDecision", "PolicyActivationExecution", "PolicyActivationGeneration", "PolicyActivationOutboxEvent"]:
    idx = models_text.find(f"class {cls_name}(")
    if idx != -1:
        end = models_text.find("\nclass ", idx+10)
        if end == -1: end = idx + 1500
        log(f"\n--- class {cls_name} (primeiros campos) ---")
        log(models_text[idx:min(idx+900, end)])
    else:
        log(f"\nclass {cls_name}: NAO encontrada em app/models.py")

section("5. Grants/permissoes do writer que cria estas linhas (quem tem INSERT)")
for fp in (REPO / "migrations" / "versions").glob("00*.py"):
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if "policy_activations" in line and ("GRANT" in line.upper() or "grant" in line):
            log(f"  {fp.name}:{i}: {line.strip()[:200]}")

Path(r"C:\dev\saas-fiscal-demo-a1\identificar_servico_g4_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado.")
