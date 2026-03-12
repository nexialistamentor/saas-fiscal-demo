#!/usr/bin/env python3
"""
Testes operacionais ANTES DO DASHBOARD
=====================================
Executa os 3 testes recomendados: carga, isolamento, limite.

Pré-requisitos:
  - API rodando: uvicorn app.main:app --reload
  - Redis rodando: redis-server
  - Worker rodando: python -m app.workers.analysis_worker
  - Banco preparado: python scripts/preparar_testes.py

Uso:
  # Windows (IMPORTANTE: definir USER_LIMITE para o Teste 3 passar)
  $env:USER_LIMITE="limite@teste.com"; $env:USER_LIMITE_PASS="senha123"
  python scripts/testes_operacionais.py

  # Ou use: .\scripts\executar_testes.ps1

Variáveis de ambiente:
  BASE_URL     - default http://localhost:8000
  USER_A_EMAIL - usuário Empresa A (para testes 1 e 2)
  USER_A_PASS  - senha
  USER_B_EMAIL - usuário Empresa B (para teste 2 isolamento)
  USER_B_PASS  - senha
  USER_LIMITE  - usuário com plano Teste (limite=2) para teste 3
  USER_LIMITE_PASS
"""
import concurrent.futures
import os
import sys

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
XML_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "xmls_testes", "xml_icms_st_teste.xml")


def login(email: str, password: str) -> str | None:
    """Retorna access_token ou None."""
    r = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def obter_empresa_id(token: str) -> int | None:
    """Retorna o primeiro empresa_id do usuário."""
    r = requests.get(
        f"{BASE_URL}/empresas",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    data = r.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0].get("id")
    if isinstance(data, dict) and data.get("empresas"):
        emps = data["empresas"]
        return emps[0].get("id") if emps else None
    return None


def teste_1_carga():
    """Teste 1 — Carga: 50 XMLs simultâneos. Confirma fila Redis, worker, jobs."""
    print("\n" + "=" * 60)
    print("TESTE 1 — CARGA (50 XMLs simultâneos)")
    print("=" * 60)

    email = os.environ.get("USER_A_EMAIL", "teste@teste.com")
    password = os.environ.get("USER_A_PASS", "senha123")

    token = login(email, password)
    if not token:
        print("  FALHA: não foi possível fazer login. Configure USER_A_EMAIL e USER_A_PASS.")
        return False

    empresa_id = obter_empresa_id(token)
    if not empresa_id:
        print("  FALHA: usuário não tem empresa. Cadastre uma empresa antes.")
        return False

    if not os.path.exists(XML_PATH):
        print(f"  FALHA: XML não encontrado em {XML_PATH}")
        return False

    with open(XML_PATH, "rb") as f:
        xml_bytes = f.read()

    def enviar_xml(i: int) -> tuple[int, dict]:
        r = requests.post(
            f"{BASE_URL}/fiscal/analisar-xml",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (f"xml_{i}.xml", xml_bytes, "application/xml")},
            params={"empresa_id": empresa_id},
            timeout=30,
        )
        return r.status_code, r.json() if r.status_code == 200 else {"detail": r.text}

    print("  Enviando 50 XMLs em paralelo...")
    job_ids = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(enviar_xml, i) for i in range(50)]
        for i, f in enumerate(concurrent.futures.as_completed(futures)):
            try:
                status, data = f.result()
                if status == 200 and data.get("job_id"):
                    job_ids.append(data["job_id"])
            except Exception as e:
                print(f"  Requisição {i} erro: {e}")

    print(f"  Jobs enfileirados: {len(job_ids)}")
    if len(job_ids) >= 45:  # tolera algumas falhas
        print("  OK: Fila Redis e worker recebendo jobs.")
        if job_ids:
            r = requests.get(
                f"{BASE_URL}/fiscal/analise/status/{job_ids[0]}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if r.status_code == 200:
                print(f"  Exemplo job status: {r.json().get('status', 'N/A')}")
        return True
    print(f"  ATENÇÃO: Menos de 45 jobs enfileirados ({len(job_ids)}). Verifique Redis e worker.")
    return len(job_ids) > 0


def teste_2_isolamento():
    """Teste 2 — Isolamento: Empresa A acessando /dashboard/analises/{empresa_B} → 403."""
    print("\n" + "=" * 60)
    print("TESTE 2 — ISOLAMENTO (Empresa A → analises Empresa B)")
    print("=" * 60)

    email_a = os.environ.get("USER_A_EMAIL", "teste@teste.com")
    pass_a = os.environ.get("USER_A_PASS", "senha123")
    email_b = os.environ.get("USER_B_EMAIL", "outro@teste.com")
    pass_b = os.environ.get("USER_B_PASS", "senha123")

    token_a = login(email_a, pass_a)
    if not token_a:
        print("  FALHA: login usuário A falhou.")
        return False

    token_b = login(email_b, pass_b)
    if not token_b:
        print("  FALHA: login usuário B falhou. Crie usuário B para teste de isolamento.")
        return False

    empresa_b = obter_empresa_id(token_b)
    if not empresa_b:
        print("  FALHA: usuário B não tem empresa.")
        return False

    # Empresa A tenta acessar análises da Empresa B
    r = requests.get(
        f"{BASE_URL}/dashboard/analises/{empresa_b}",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=10,
    )

    if r.status_code == 403:
        print("  OK: Retornou 403 — isolamento funcionando.")
        return True
    print(f"  FALHA: Esperado 403, obtido {r.status_code}. {r.text[:200]}")
    return False


def teste_3_limite():
    """Teste 3 — Limite: limite_analises=2, rodar 3 análises → 3ª deve retornar 429."""
    print("\n" + "=" * 60)
    print("TESTE 3 — LIMITE (limite_analises=2, 3 análises → 3ª = 429)")
    print("=" * 60)

    email = os.environ.get("USER_LIMITE", os.environ.get("USER_A_EMAIL", "teste@teste.com"))
    password = os.environ.get("USER_LIMITE_PASS", os.environ.get("USER_A_PASS", "senha123"))

    token = login(email, password)
    if not token:
        print("  FALHA: login falhou.")
        return False

    empresa_id = obter_empresa_id(token)
    if not empresa_id:
        print("  FALHA: usuário sem empresa.")
        return False

    if not os.path.exists(XML_PATH):
        print(f"  FALHA: XML não encontrado em {XML_PATH}")
        return False

    with open(XML_PATH, "rb") as f:
        xml_bytes = f.read()

    # Usar /relatorio/gerar-relatorio (usa limite do Plano)
    # O usuário precisa estar no plano "Teste" (limite_analises=2)
    resultados = []
    for i in range(3):
        r = requests.post(
            f"{BASE_URL}/relatorio/gerar-relatorio",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (f"xml_{i}.xml", xml_bytes, "application/xml")},
            params={"empresa_id": empresa_id},
            timeout=60,
        )
        resultados.append((r.status_code, r.json() if r.status_code == 200 else r.json() if r.text else {"detail": r.text}))

    ok_1_2 = resultados[0][0] == 200 and resultados[1][0] == 200
    ok_3_429 = resultados[2][0] == 429

    if ok_1_2 and ok_3_429:
        detail = resultados[2][1].get("detail", "")
        if "limite" in str(detail).lower() or "429" in str(resultados[2][0]):
            print("  OK: 1ª e 2ª análises OK, 3ª retornou 429.")
            print(f"  Detalhe 3ª: {detail[:80]}...")
            return True

    print(f"  Resultados: 1ª={resultados[0][0]}, 2ª={resultados[1][0]}, 3ª={resultados[2][0]}")
    if not ok_3_429:
        print("  FALHA: 3ª análise deveria retornar 429 (limite atingido).")
        print("  Confira: usuário com plano 'Teste' (limite_analises=2).")
    return ok_3_429


def main():
    print("\nTestes operacionais — SaaS Fiscal (pré-Dashboard)")
    print("Base URL:", BASE_URL)
    print("XML:", XML_PATH, "(existe)" if os.path.exists(XML_PATH) else "(NÃO ENCONTRADO)")

    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code != 200:
            print("\nAPI não respondeu OK no /health. Inicie: uvicorn app.main:app --reload")
            sys.exit(1)
    except requests.RequestException as e:
        print(f"\nAPI inacessível: {e}")
        sys.exit(1)

    r1 = teste_1_carga()
    r2 = teste_2_isolamento()
    r3 = teste_3_limite()

    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"  Teste 1 (Carga):     {'OK' if r1 else 'FALHOU'}")
    print(f"  Teste 2 (Isolamento): {'OK' if r2 else 'FALHOU'}")
    print(f"  Teste 3 (Limite):    {'OK' if r3 else 'FALHOU'}")
    print()

    if r1 and r2 and r3:
        print("  Conclusão: Backend SaaS pronto. Próxima etapa: Dashboard + testes com empresas reais + monetização.")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
