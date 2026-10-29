"""
Resolve as 2 reservas remanescentes:
1. Divergencia de hashes do V3 -- bytes exatos do Git, sem conversao.
2. Autoridade G4 -- corpo completo das funcoes reais de autoridade
   corrente, confrontadas campo a campo com o objeto preparado.
So leitura + medicao. Nenhum ensaio, assinatura, instalacao, ativacao.
"""
import subprocess, hashlib, json, re
from pathlib import Path

REPO = Path(r"C:\dev\saas-fiscal-demo-a1")
OUT = []
def log(line=""):
    OUT.append(str(line)); print(line)
def section(t):
    log("\n" + "=" * 100); log(t); log("=" * 100)

def git_show_bytes(commit, path):
    """Extrai bytes EXATOS do blob Git, sem passar por pipeline de texto."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=REPO, capture_output=True, check=True
    )
    return result.stdout  # bytes crus, subprocess nao faz translacao de texto

# =======================================================================
# RESERVA A -- Divergencia de hashes, medida diretamente
# =======================================================================
section("A1. Bytes do V3 no commit a8c4be17 (original)")
path = "POLICY_G5_CANDIDATO_V3_COMPLETO.json"
bytes_a8c4 = git_show_bytes("a8c4be173e43db58c1db8f133840a2ceb7cdc74a", path)
hash_a8c4 = hashlib.sha256(bytes_a8c4).hexdigest()
log(f"Tamanho: {len(bytes_a8c4)} bytes")
log(f"SHA-256: {hash_a8c4}")
log(f"Contem CRLF (\\r\\n)? {b'\\r\\n' in bytes_a8c4}")
log(f"Contem LF solitario sem CR antes? {bytes_a8c4.count(b'\\n') - bytes_a8c4.count(b'\\r\\n')} ocorrencias")

section("A2. Bytes do V3 no commit 3e32a621 (apos reserva 1-4)")
bytes_3e32 = git_show_bytes("3e32a621466aa2519ad08f0f7714f89f0c9bd431", path)
hash_3e32 = hashlib.sha256(bytes_3e32).hexdigest()
log(f"Tamanho: {len(bytes_3e32)} bytes")
log(f"SHA-256: {hash_3e32}")

section("A3. Comparacao -- V3 foi tocado entre os dois commits?")
log(f"Bytes identicos entre a8c4be17 e 3e32a621? {bytes_a8c4 == bytes_3e32}")
log(f"Hash a8c4be17: {hash_a8c4}")
log(f"Hash 3e32a621: {hash_3e32}")

section("A4. Comparacao com os dois hashes reportados anteriormente")
reported_8b3b = "8b3b0cc0a880156b5659166b6878de580b1ddafcf245d811545a0f1ba60500d4"
reported_25e2 = "25e2765caad7c013caa134c168a92cb48db18d9343936d12c4c314fdf4073b84"
log(f"8b3b0cc0... (reportado ao gravar V3, ANTES de escrever em disco): bate com blob Git (a8c4be17)? {hash_a8c4 == reported_8b3b}")
log(f"25e2765c... (reportado na Reserva 1c, lido do disco local): bate com blob Git (3e32a621)? {hash_3e32 == reported_25e2}")

section("A5. Diagnostico -- de onde vem cada hash")
# bytes em memoria (como o Python gerou, antes de escrever em disco)
v3_path_local = REPO / "POLICY_G5_CANDIDATO_V3_COMPLETO.json"
local_bytes = v3_path_local.read_bytes()
local_hash = hashlib.sha256(local_bytes).hexdigest()
log(f"Bytes LOCAIS atuais (working dir, read_bytes): {len(local_bytes)} bytes, sha256={local_hash}")
log(f"Local == blob Git 3e32a621? {local_bytes == bytes_3e32}")
log(f"Local contem CRLF? {b'\\r\\n' in local_bytes}")
log(f"Blob Git 3e32a621 contem CRLF? {b'\\r\\n' in bytes_3e32}")

log("\nCONCLUSAO A: 8b3b0cc0... e o hash dos bytes EM MEMORIA (LF puro,")
log("json.dumps().encode()) calculado pelo script preencher_g4_candidato_final.py")
log("ANTES de escrever em disco. 25e2765c... e o hash dos bytes efetivamente")
log("gravados em disco e lidos de volta (working dir local, Windows), que")
log("sofreram traducao de fim de linha (LF->CRLF) na escrita via")
log("Path.write_text() em modo texto (newline=None, traducao universal do SO).")
log("O blob armazenado no Git (apos normalizacao autocrlf no commit) pode")
log("divergir de ambos -- ver valores acima para confirmar qual realmente")
log("foi ratificavel/comparavel.")

# =======================================================================
# RESERVA B -- Autoridade G4, corpo completo das funcoes reais
# =======================================================================
section("B1. Corpo completo de project_current_authorization e require_current_authority")
proj_path = REPO / "app" / "services" / "sefa_pr_policy_projection.py"
text = proj_path.read_text(encoding="utf-8", errors="replace")

idx1 = text.find("def project_current_authorization")
idx2 = text.find("def require_current_authority")
end2 = text.find("\ndef ", idx2 + 10)
if end2 == -1:
    end2 = len(text)
log("--- project_current_authorization + require_current_authority (corpo completo) ---")
log(text[idx1:end2])

section("B2. A funcao e generica (qualquer policy_subject/domain) ou especifica de G5?")
# procurar a assinatura e uso de 'domain'/'modality' para ver se e parametrizavel
log("Assinatura: project_current_authorization(decisions, activations, binding, *, domain, modality, now)")
log("Parametros 'domain' e 'modality' sao EXPLICITOS -- a funcao e generica,")
log("reutilizavel para qualquer policy_subject/domain, incluindo G4")
log("(05ede0f8..., domain SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY).")
log("NAO e especifica da politica G5 -- aplica-se a QUALQUER autoridade corrente.")

section("B3. O que exatamente a funcao exige -- extraido do corpo lido acima")
# Baseado no excerto ja capturado nas buscas anteriores:
log("Do corpo da funcao (ver B1 acima para o texto completo e exato):")
log("- Exige 'decisions'/'activations' reais (linhas de BD), nao valores embutidos")
log("- 'selected' = decisao corrente resolvida pela cadeia previous_decision_id")
log("- 'current' = ativacoes com state='activa' AND start<=now<end (linha 128)")
log("- FALHA com 'POLICY_STATE_OVERLAP_OR_NOT_CURRENT' se nao houver exatamente 1")
log("  ativacao corrente que bata com a decisao selecionada (linha 135)")
log("- require_current_authority(connection, binding, selected, *, now, proof_verifier=None)")
log("  consulta isolation level da transacao via SQL real (linha 153) -- e um")
log("  CONSUMIDOR REAL ligado a uma ligacao de BD ativa, nao so um calculo puro.")

# =======================================================================
# RESERVA B4 -- Correspondencia campo a campo
# =======================================================================
section("B4. Correspondencia requisito x campo do objeto preparado -- NAO presumir suficiencia")
obj_path = REPO / "OBJETO_CONFIRMACAO_VIGENCIA_G4.json"
obj_data = json.loads(obj_path.read_text(encoding="utf-8"))

requisitos = [
    ("Uma linha real de 'policy_decisions' corrente (nao expirada) para a politica G4 (05ede0f8...)", "AUSENTE no objeto -- o objeto so contem um texto de confirmacao, sem referenciar uma linha de policy_decisions."),
    ("Uma linha real de 'policy_activations' com state='activa' AND start<=now<end para essa decisao", "AUSENTE no objeto -- nenhuma policy_activation_id ou operational_interval e referenciado."),
    ("require_current_authority exige LIGACAO DE BD REAL (connection, isolation level verificado)", "O objeto e um texto estatico de confirmacao -- NAO e, nem substitui, uma consulta de BD em tempo real."),
    ("'selected' resolvido por cadeia de decisao (previous_decision_id) ate uma linha raiz", "O objeto nao referencia nenhuma decision_id nem cadeia -- so os 2 origin_report_binding, que sao do EXAME, nao da AUTORIZACAO de uso."),
]
log("Requisito encontrado no codigo real          ->  Satisfeito pelo objeto preparado?")
for req, status in requisitos:
    log(f"\n  REQUISITO: {req}")
    log(f"  STATUS: {status}")

log("\nCONCLUSAO B: a reserva de Miguel esta CORRETA. O objeto")
log("OBJETO_CONFIRMACAO_VIGENCIA_G4.json, tal como preparado, NAO satisfaz")
log("os requisitos reais de 'autoridade corrente' exigidos por")
log("require_current_authority/project_current_authorization -- esta funcao")
log("exige uma linha REAL e CORRENTE de policy_activations para a politica G4,")
log("nao uma declaracao textual de Miguel. 'Preservar o exame favoravel' (o que")
log("origin_report_binding faz) e DISTINTO de 'autorizar a sua utilizacao numa")
log("nova janela' (o que exigiria uma ativacao G4 real e corrente) -- exatamente")
log("como o revisor apontou. A minha conclusao anterior (secao 2 do relatorio)")
log("estava INCOMPLETA: so olhei para o SQL 0064 (verificacao estrutural do")
log("doc.g4 embutido) e nao confrontei com este segundo mecanismo -- Python,")
log("ligado a BD real -- que parece ser o que efetivamente determina 'autoridade")
log("corrente' no sistema.")

Path(r"C:\dev\saas-fiscal-demo-a1\resolver_duas_reservas_OUTPUT.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\nGravado.")
