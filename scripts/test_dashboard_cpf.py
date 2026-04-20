"""
Testes do dashboard CPF — valida cards principais via POST /cpf/dashboard.

Executar: python scripts/test_dashboard_cpf.py
"""

import sys
import requests
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

API = "http://127.0.0.1:8000"


def obter_token(email, senha):
    r = requests.post(f"{API}/auth/login", data={"username": email, "password": senha})
    assert r.status_code == 200, f"Login falhou: {r.text}"
    return r.json()["access_token"]


def dashboard_cpf(token, faturamento, despesas=0.0):
    r = requests.post(
        f"{API}/cpf/dashboard",
        json={"faturamento_mensal": faturamento, "despesas": despesas},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"dashboard falhou: {r.status_code} {r.text}"
    return r.json()


def test_cpf_card_impacto_financeiro():
    """Card Impacto Financeiro Anual — CPF com faturamento tributável."""
    token = obter_token("teste@fiscal.com", "senha123")
    json = dashboard_cpf(token, faturamento=5000)
    assert "imposto_anual" in json, "Resposta deve ter imposto_anual"
    assert json["imposto_anual"] >= 0
    print(f"[OK] imposto_anual CPF: R$ {json['imposto_anual']}")


def test_cpf_card_isencao():
    """Card Impacto Financeiro — CPF sem imposto (base = faturamento − despesas = 0)."""
    token = obter_token("teste@fiscal.com", "senha123")
    json = dashboard_cpf(token, faturamento=2000, despesas=2000)
    assert json["imposto_anual"] == 0 and json["imposto_mensal"] == 0, (
        "Base zero deve resultar em imposto zero (motor CPF simplificado 6%)"
    )
    print(f"[OK] base zero CPF: imposto_anual={json['imposto_anual']}")


if __name__ == "__main__":
    test_cpf_card_impacto_financeiro()
    test_cpf_card_isencao()
    print("\n[OK] Dashboard CPF — todos os testes passaram.")
