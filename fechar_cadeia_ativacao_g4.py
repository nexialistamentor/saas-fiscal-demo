"""
Fecha a cadeia de predecessores para a ativacao G4: corpo completo de
stage_policy_activation, campos de BootstrapAuthorityRecord e
PolicyActivationExecution, e confirma nomes reais de Generation/Outbox.
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

section("1. Corpo completo de stage_policy_activation")
f = REPO / "app" / "services" / "enterprise_b02_policy_activation_atomicity.py"
text = f.read_text(encoding="utf-8", errors="replace")
idx = text.find("def stage_policy_activation")
end = text.find("\ndef ", idx+10)
if end == -1: end = min(idx+3000, len(text))
log(text[idx:end])

section("2. Campos completos de BootstrapAuthorityRecord")
models_text = (REPO / "app" / "models.py").read_text(encoding="utf-8", errors="replace")
idx = models_text.find("class BootstrapAuthorityRecord(")
if idx != -1:
    end = models_text.find("\nclass ", idx+10)
    log(models_text[idx:min(idx+1800, end if end!=-1 else idx+1800)])
else:
    log("NAO encontrada -- procurar nome alternativo")
    for m in re.finditer(r"class (\w*[Bb]ootstrap\w*)\(", models_text):
        log(f"  candidato: {m.group(1)}")

section("3. Nomes reais das tabelas generation/outbox (tablename, nao nome de classe)")
for m in re.finditer(r'__tablename__\s*=\s*"(policy_activation_generation\w*|policy_activation_outbox\w*)"', models_text):
    idx = models_text.rfind("class ", 0, m.start())
    class_line = models_text[idx:models_text.find("(", idx)]
    log(f"  {class_line.replace('class ','')} -> tabela: {m.group(1)}")

section("4. Campos completos de PolicyActivationExecution (continuacao, FK ativacao)")
idx = models_text.find("class PolicyActivationExecution(")
end = models_text.find("\nclass ", idx+10)
log(models_text[idx:min(idx+2200, end if end!=-1 else idx+2200)])

section("5. Grants reais em policy_activations/policy_decisions -- quem tem INSERT (busca ampla)")
for fp in (REPO / "migrations" / "versions").glob("*.py"):
    try:
        t = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for i, line in enumerate(t.splitlines(), 1):
        if re.search(r"GRANT.*policy_(activations|decisions)|policy_(activations|decisions).*GRANT", line, re.IGNORECASE):
            log(f"  {fp.name}:{i}: {line.strip()[:200]}")

Path(r"C:\dev\saas-fiscal-demo-a1\fechar_cadeia_g4_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado.")
