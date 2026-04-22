import io
import threading

import requests

BASE = "http://127.0.0.1:8000"


def login(username, password):
    r = requests.post(
        f"{BASE}/auth/login", data={"username": username, "password": password}
    )
    return r.json().get("access_token", "")


def headers(token):
    return {"Authorization": f"Bearer {token}"}


resultados = []


def log(teste, status, detalhe):
    simbolo = "OK" if status else "FALHOU"
    resultados.append((teste, simbolo, detalhe))
    print(f"[{simbolo}] {teste}: {detalhe}")


# ── SETUP ──────────────────────────────────────────────────────────────
print("\n=== SETUP ===")
# Registo CPF válido
r = requests.post(
    f"{BASE}/auth/register",
    json={
        "email": "stress_cpf@teste.com",
        "password": "senha1234",
        "tipo_usuario": "cpf",
        "documento": "98765432100",
    },
)
log("1. Registo CPF valido", r.status_code == 200, f"{r.status_code} {r.json()}")

# Registo CPF duplicado
r = requests.post(
    f"{BASE}/auth/register",
    json={
        "email": "stress_cpf@teste.com",
        "password": "senha1234",
        "tipo_usuario": "cpf",
        "documento": "98765432100",
    },
)
log("2. Registo CPF duplicado", r.status_code == 400, f"{r.status_code} {r.json()}")

# Registo MEI válido
r = requests.post(
    f"{BASE}/auth/register",
    json={
        "email": "stress_mei@teste.com",
        "password": "senha1234",
        "nome": "MEI Stress",
        "tipo_usuario": "mei",
        "documento": "11222333000181",
    },
)
log("3. Registo MEI valido", r.status_code == 200, f"{r.status_code} {r.json()}")

# Registo Empresa válida
r = requests.post(
    f"{BASE}/auth/register",
    json={
        "email": "stress_empresa@teste.com",
        "password": "senha1234",
        "nome": "Empresa Stress",
        "tipo_usuario": "empresa",
        "documento": "11222333000181",
    },
)
log("4. Registo Empresa valido", r.status_code == 200, f"{r.status_code} {r.json()}")

# Registo sem documento
r = requests.post(
    f"{BASE}/auth/register",
    json={
        "email": "stress_nodoc@teste.com",
        "password": "senha1234",
        "tipo_usuario": "cpf",
        "documento": None,
    },
)
log("5. Registo sem documento", r.status_code in (200, 422), f"{r.status_code} {r.json()}")

# Registo documento formato inválido
r = requests.post(
    f"{BASE}/auth/register",
    json={
        "email": "stress_baddoc@teste.com",
        "password": "senha1234",
        "tipo_usuario": "cpf",
        "documento": "ABC.DEF.GHI-XY",
    },
)
log("6. Registo documento invalido", r.status_code == 422, f"{r.status_code} {r.json()}")


# ── UPLOAD/CONFIRMAR ───────────────────────────────────────────────────
print("\n=== UPLOAD / CONFIRMAR ===")
token = login("stress_cpf@teste.com", "senha1234")
h = headers(token)

# Upload ficheiro vazio
r = requests.post(
    f"{BASE}/cpf/documentos/upload",
    headers=h,
    files={"file": ("vazio.pdf", io.BytesIO(b""), "application/pdf")},
)
log("7. Upload ficheiro vazio", r.status_code == 400, f"{r.status_code} {r.json()}")

# Upload ficheiro grande (6MB)
grande = b"x" * 6 * 1024 * 1024
r = requests.post(
    f"{BASE}/cpf/documentos/upload",
    headers=h,
    files={"file": ("grande.pdf", io.BytesIO(grande), "application/pdf")},
)
log("8. Upload ficheiro grande 6MB", r.status_code in (200, 413), f"{r.status_code}")

# Upload sem autenticação
r = requests.post(
    f"{BASE}/cpf/documentos/upload",
    files={"file": ("sem_auth.pdf", io.BytesIO(b"conteudo"), "application/pdf")},
)
log("9. Upload sem autenticacao", r.status_code == 401, f"{r.status_code}")

# Upload com token inválido
r = requests.post(
    f"{BASE}/cpf/documentos/upload",
    headers={"Authorization": "Bearer token_invalido"},
    files={"file": ("bad_token.pdf", io.BytesIO(b"conteudo"), "application/pdf")},
)
log("10. Upload token invalido", r.status_code == 401, f"{r.status_code}")

# Upload múltiplos seguidos
for i in range(5):
    r = requests.post(
        f"{BASE}/cpf/documentos/upload",
        headers=h,
        files={"file": (f"doc_{i}.pdf", io.BytesIO(b"conteudo"), "application/pdf")},
    )
log("11. Upload multiplos seguidos (5x)", r.status_code == 200, f"ultimo: {r.status_code}")

# Confirmar sem upload prévio
r = requests.post(
    f"{BASE}/cpf/documentos/confirmar",
    headers=h,
    json={
        "tipo_rendimento": "salario",
        "valor": 5000.0,
        "ano_referencia": 2026,
        "mes_referencia": 1,
    },
)
log("12. Confirmar sem upload previo", r.status_code == 200, f"{r.status_code} {r.json()}")

# Confirmar com campos mínimos
r = requests.post(
    f"{BASE}/cpf/documentos/confirmar",
    headers=h,
    json={"tipo_rendimento": "outro"},
)
log("13. Confirmar campos minimos", r.status_code == 200, f"{r.status_code} {r.json()}")

# Confirmar valor negativo
r = requests.post(
    f"{BASE}/cpf/documentos/confirmar",
    headers=h,
    json={"tipo_rendimento": "salario", "valor": -999.0},
)
log("14. Confirmar valor negativo", r.status_code in (200, 422), f"{r.status_code} {r.json()}")

# Confirmar mês inválido
r = requests.post(
    f"{BASE}/cpf/documentos/confirmar",
    headers=h,
    json={"tipo_rendimento": "salario", "valor": 1000.0, "mes_referencia": 13},
)
log("15. Confirmar mes invalido (13)", r.status_code in (200, 422), f"{r.status_code} {r.json()}")

# Confirmar ano inválido
r = requests.post(
    f"{BASE}/cpf/documentos/confirmar",
    headers=h,
    json={"tipo_rendimento": "salario", "valor": 1000.0, "ano_referencia": 1800},
)
log("16. Confirmar ano invalido (1800)", r.status_code in (200, 422), f"{r.status_code} {r.json()}")


# ── CONCORRÊNCIA ───────────────────────────────────────────────────────
print("\n=== CONCORRENCIA ===")


def confirmar_concorrente(email, resultado_lista, idx):
    t = login(email, "senha1234")
    r = requests.post(
        f"{BASE}/cpf/documentos/confirmar",
        headers=headers(t),
        json={
            "tipo_rendimento": "salario",
            "valor": float(idx * 1000),
            "ano_referencia": 2026,
            "mes_referencia": idx % 12 + 1,
        },
    )
    resultado_lista.append((idx, r.status_code, r.json()))


# Dois utilizadores CPF diferentes em simultâneo
res17 = []
t1 = threading.Thread(
    target=confirmar_concorrente, args=("stress_cpf@teste.com", res17, 1)
)
t2 = threading.Thread(
    target=confirmar_concorrente, args=("teste_cpf@teste.com", res17, 2)
)
t1.start()
t2.start()
t1.join()
t2.join()
ok17 = all(r[1] == 200 for r in res17)
log("17. Concorrencia dois utilizadores", ok17, str(res17))

# Mesmo utilizador duas vezes em simultâneo
res18 = []
t3 = threading.Thread(
    target=confirmar_concorrente, args=("stress_cpf@teste.com", res18, 3)
)
t4 = threading.Thread(
    target=confirmar_concorrente, args=("stress_cpf@teste.com", res18, 4)
)
t3.start()
t4.start()
t3.join()
t4.join()
ok18 = all(r[1] == 200 for r in res18)
log("18. Concorrencia mesmo utilizador", ok18, str(res18))

# ── RESUMO ─────────────────────────────────────────────────────────────
print("\n=== RESUMO ===")
falhas = [(t, d) for t, s, d in resultados if s == "FALHOU"]
print(
    f"Total: {len(resultados)} | OK: {len(resultados) - len(falhas)} | FALHOU: {len(falhas)}"
)
if falhas:
    print("\nFalhas:")
    for t, d in falhas:
        print(f"  - {t}: {d}")
