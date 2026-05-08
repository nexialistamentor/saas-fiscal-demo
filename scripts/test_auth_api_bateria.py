"""
Bateria rápida de smoke tests contra a API (auth + /empresas/).
Usar antes de commit: `python scripts/test_auth_api_bateria.py`
BASE via env AUTH_API_TEST_BASE (default: produção Railway).
"""
from __future__ import annotations

import json
import os
import sys

import httpx

BASE = os.environ.get(
    "AUTH_API_TEST_BASE", "https://saas-fiscal-demo-production.up.railway.app"
).rstrip("/")

EMAIL = os.environ.get("AUTH_API_TEST_EMAIL", "teste_bateria@saas.com")
PASSWORD = os.environ.get("AUTH_API_TEST_PASSWORD", "Teste123!")


def main() -> None:
    failures = []

    print("=== TESTE 1: Registo ===")
    r = httpx.post(
        f"{BASE}/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "tipo_usuario": "empresa",
        },
        timeout=30.0,
    )
    print(f"Status: {r.status_code}")
    registro_ok = r.status_code in (200, 201) or (
        r.status_code == 400 and "cadastrado" in (r.text or "").lower()
    )
    if not registro_ok:
        failures.append(f"Registo inesperado: {r.status_code} {r.text[:200]}")

    print("=== TESTE 2: Login ===")
    r = httpx.post(
        f"{BASE}/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    print(f"Status: {r.status_code}")
    token = ""
    if r.status_code == 200:
        try:
            token = r.json().get("access_token", "") or ""
        except json.JSONDecodeError:
            pass
    print(f"Token: {token[:30]}..." if token else "SEM TOKEN")
    if r.status_code != 200 or not token:
        failures.append(f"Login falhou: status={r.status_code}")

    print("=== TESTE 2b: Aceitar termos (desbloqueia rotas fiscais) ===")
    r = httpx.post(
        f"{BASE}/auth/accept-terms",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        failures.append(f"accept-terms esperado 200, veio {r.status_code}")

    print("=== TESTE 3: Empresas autenticado ===")
    r = httpx.get(
        f"{BASE}/empresas/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        failures.append(f"/empresas/ autenticado esperado 200, veio {r.status_code}")

    print("=== TESTE 4: Token inválido ===")
    r = httpx.get(
        f"{BASE}/empresas/",
        headers={"Authorization": "Bearer invalido"},
        timeout=30.0,
    )
    print(f"Status: {r.status_code} (esperado 401)")
    if r.status_code != 401:
        failures.append(f"Token inválido esperado 401, veio {r.status_code}")

    print("=== TESTE 5: Sem token ===")
    r = httpx.get(f"{BASE}/empresas/", timeout=30.0)
    print(f"Status: {r.status_code} (esperado 401)")
    if r.status_code != 401:
        failures.append(f"Sem token esperado 401, veio {r.status_code}")

    if failures:
        print("\n--- RESUMO: FALHAS ---")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\n--- Todos os testes passaram ---")


if __name__ == "__main__":
    main()
