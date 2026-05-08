"""
Fluxo E2E contra a API (Railway ou local): registo com empresa, termos, LGPD,
listagem de empresas e várias perguntas ao Assistente Fiscal (abertura, encerramento, fiscal).

BASE: env AUTH_API_TEST_BASE (default produção Railway).
Email único por execução para evitar colisão de registo.

Uso: python scripts/test_api_fluxo_completo.py
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE = os.environ.get(
    "AUTH_API_TEST_BASE", "https://saas-fiscal-demo-production.up.railway.app"
).rstrip("/")

TIMEOUT = 60.0


def _cnpj_teste_unico() -> str:
    """14 dígitos (sem validação de DV neste endpoint)."""
    nucleo = random.randint(10**11, 10**12 - 1)
    return f"{nucleo:014d}"


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _print_assistente(label: str, r: httpx.Response) -> None:
    at = "N/A"
    schema = "N/A"
    preview = False
    try:
        j = r.json()
        at = j.get("analysis_type", "N/A")
        schema = j.get("schema_type", "N/A")
        preview = bool(j.get("preview"))
    except json.JSONDecodeError:
        j = {}
    snip = ""
    if isinstance(j.get("resposta"), str):
        snip = j["resposta"][:120].replace("\n", " ")
        if len(j["resposta"]) > 120:
            snip += "…"
    print(
        f"{label}: {r.status_code} | analysis_type={at} | schema_type={schema} | preview={preview}"
    )
    if snip:
        print(f"    resposta (trecho): {snip}")


def main() -> None:
    email = os.environ.get(
        "AUTH_API_TEST_EMAIL",
        f"fluxo_completo_{int(time.time())}_{random.randint(1000, 9999)}@saas.com",
    )
    password = os.environ.get("AUTH_API_TEST_PASSWORD", "Teste123!")
    cnpj = os.environ.get("AUTH_API_TEST_CNPJ") or _cnpj_teste_unico()

    failures: list[str] = []

    print(f"BASE={BASE}\nEMAIL={email}\nCNPJ={cnpj}\n")

    # 1. Registo com empresa (nome + documento — é assim que a API cria a empresa)
    print("=== 1. Registo (tipo empresa + CNPJ) ===")
    r = httpx.post(
        f"{BASE}/auth/register",
        json={
            "email": email,
            "password": password,
            "tipo_usuario": "empresa",
            "nome": "Empresa Fluxo Completo SA",
            "documento": cnpj,
        },
        timeout=TIMEOUT,
    )
    print(f"Status: {r.status_code}")
    empresa_id_registo = None
    if r.status_code in (200, 201):
        try:
            empresa_id_registo = r.json().get("empresa_id")
        except json.JSONDecodeError:
            pass
    elif r.status_code == 400 and "cadastrado" in (r.text or "").lower():
        print("(email já existia — continuar com login)")
    else:
        failures.append(f"Registo: {r.status_code} {r.text[:300]}")
    print(f"empresa_id no registo: {empresa_id_registo}")

    # 2. Login
    print("\n=== 2. Login ===")
    r = httpx.post(
        f"{BASE}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
    )
    token = ""
    if r.status_code == 200:
        try:
            token = r.json().get("access_token", "") or ""
        except json.JSONDecodeError:
            pass
    print(f"Status: {r.status_code} | Token: {'OK' if token else 'FALHOU'}")
    if not token:
        failures.append("Login sem token")
        print("\n--- Abortado (sem token) ---")
        for f in failures:
            print(f"  FALHA: {f}")
        sys.exit(1)

    h = _hdr(token)

    # 3. Termos + LGPD
    print("\n=== 3. Aceitar termos ===")
    r = httpx.post(f"{BASE}/auth/accept-terms", headers=h, timeout=TIMEOUT)
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        failures.append(f"accept-terms {r.status_code}")

    print("\n=== 4. Consentimento LGPD ===")
    r = httpx.post(f"{BASE}/auth/consent", headers=h, timeout=TIMEOUT)
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        failures.append(f"consent {r.status_code}")

    # 5. Empresas (GET — POST /empresas/ não existe na API atual)
    print("\n=== 5. GET /empresas/ ===")
    r = httpx.get(f"{BASE}/empresas/", headers=h, timeout=TIMEOUT)
    print(f"Status: {r.status_code}")
    empresas = []
    if r.status_code == 200:
        try:
            empresas = r.json()
        except json.JSONDecodeError:
            pass
    print(f"Quantidade: {len(empresas) if isinstance(empresas, list) else 'N/A'}")
    if isinstance(empresas, list) and empresas:
        e0 = empresas[0]
        print(f"Primeira empresa: id={e0.get('id')} cnpj={e0.get('cnpj')} regime={e0.get('regime_tributario')}")

    # 6. Auth auxiliar
    print("\n=== 6. GET /auth/has-consented ===")
    r = httpx.get(f"{BASE}/auth/has-consented", headers=h, timeout=TIMEOUT)
    print(f"Status: {r.status_code} | {r.text[:200]}")

    print("\n=== 7. GET /auth/my-data (trecho) ===")
    r = httpx.get(f"{BASE}/auth/my-data", headers=h, timeout=TIMEOUT)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        try:
            md = r.json()
            print(f"Keys: {list(md.keys())}")
        except json.JSONDecodeError:
            print(r.text[:300])

    # 8. Assistente — várias intenções
    print("\n=== 8. Assistente Fiscal (/perguntar) ===")
    perguntas = [
        ("Abertura MEI", "como abro um MEI?"),
        ("Abertura empresa (ME/EPP)", "quero abrir empresa ltda pelo redesim"),
        ("Encerramento genérico", "quero fechar minha empresa"),
        # Evitar "portal do empreendedor" na mesma frase — está em PALAVRAS_ABERTURA e ganha prioridade.
        ("Encerramento MEI + baixa", "como dar baixa no mei e cancelar o cnpj microempreendedor"),
        ("Limite MEI", "qual o limite de faturamento do mei por ano?"),
        ("Simples com valor", "quanto minha empresa paga no simples nacional se faturamos 30 mil por mes"),
        ("Recuperação (motor)", "quanto posso recuperar de pis e cofins com icms na base faturando 100 mil por mes"),
        ("Planejamento regimes", "lucro presumido ou lucro real é melhor para mim com 200 mil por mes"),
    ]
    for label, pergunta in perguntas:
        r = httpx.post(
            f"{BASE}/perguntar",
            json={"pergunta": pergunta},
            headers=h,
            timeout=TIMEOUT,
        )
        _print_assistente(label, r)
        if r.status_code != 200:
            failures.append(f"/perguntar [{label}] {r.status_code}")

    print("\n=== 9. Health ===")
    r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
    print(f"Status: {r.status_code} | {r.text}")

    print("\n--- Concluído ---")
    if failures:
        print("FALHAS:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
