#!/usr/bin/env python3
"""
Executa os passos do fluxo Swagger em ordem:

1. Criar usuário (POST /auth/register)
2. Fazer login (POST /auth/login)
3. Usar token para autorizar
4. Testar endpoint protegido (POST /upload-xml)

Execute:
  python scripts/testar_api_swagger.py

Pré-requisito: API rodando (uvicorn app.main:app --reload --port 8000)
Se for primeira vez, execute antes: python scripts/preparar_testes.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
EMAIL = "teste@empresa.com"
PASSWORD = "senha123"
XML_TESTE = os.path.join(os.path.dirname(__file__), "..", "app", "xmls_testes", "xml_icms_st_teste.xml")


def main():
    print("=" * 50)
    print("Teste do fluxo API (ordem Swagger)")
    print("=" * 50)

    # 1. Criar usuário
    print("\n1. POST /auth/register")
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10,
    )
    if r.status_code == 200:
        print("   OK - Usuário criado:", r.json().get("email", EMAIL))
    elif r.status_code == 400 and "já cadastrado" in r.text:
        print("   OK - Usuário já existe, continuando...")
    else:
        print(f"   ERRO {r.status_code}: {r.text}")
        if "Plano Basico não existe" in r.text:
            print("\n   Execute primeiro: python scripts/preparar_testes.py")
        sys.exit(1)

    # 2. Login
    print("\n2. POST /auth/login")
    r = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"   ERRO {r.status_code}: {r.text}")
        sys.exit(1)
    data = r.json()
    token = data.get("access_token")
    if not token:
        print("   ERRO: access_token não retornado")
        sys.exit(1)
    print("   OK - Token obtido")

    # 3. Autorizar (uso implícito no próximo passo)
    print("\n3. Autorizar API (token será usado no upload)")

    # 4. POST /upload-xml
    print("\n4. POST /upload-xml (endpoint protegido)")
    if not os.path.exists(XML_TESTE):
        print(f"   ERRO: XML de teste não encontrado: {XML_TESTE}")
        sys.exit(1)
    with open(XML_TESTE, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/upload-xml",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("xml_teste.xml", f, "application/xml")},
            timeout=30,
        )
    if r.status_code == 200:
        doc_id = r.json().get("documento_id", "?")
        print(f"   OK - Documento criado: id={doc_id}")
    else:
        print(f"   ERRO {r.status_code}: {r.text}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Todos os passos executados com sucesso!")
    print("=" * 50)


if __name__ == "__main__":
    main()
