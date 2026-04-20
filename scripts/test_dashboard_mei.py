"""
Testes do dashboard MEI — valida cards principais via POST /imposto/calcular.

Executar: python scripts/test_dashboard_mei.py
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


def calcular_mei(token, faturamento, despesas=0):
    r = requests.post(
        f"{API}/imposto/calcular",
        json={"tipo_usuario": "mei", "faturamento_mensal": faturamento, "despesas": despesas},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"calcular falhou: {r.status_code} {r.text}"
    return r.json()


def test_mei_card_impacto_financeiro():
    """Card Impacto Financeiro Anual — MEI com faturamento normal."""
    token = obter_token("teste@fiscal.com", "senha123")
    json = calcular_mei(token, faturamento=5000)
    assert json["tipo"] == "mei"
    assert json["imposto_mensal"] > 0, "DAS mensal deve ser positivo"
    # API devolve imposto_anual = das * 12; comparar com arredondamento (float).
    assert round(json["imposto_anual"], 2) == round(json["imposto_mensal"] * 12, 2)
    print(f"[OK] impacto_financeiro_anual: R$ {json['imposto_anual']}")


def test_mei_card_alertas():
    """Card Percepções — MEI próximo do limite anual (R$ 81.000)."""
    token = obter_token("teste@fiscal.com", "senha123")
    json = calcular_mei(token, faturamento=6800)
    assert isinstance(json["alertas"], list)
    assert len(json["alertas"]) > 0, "Deve gerar alerta próximo do limite"
    print(f"[OK] alertas gerados: {len(json['alertas'])} — {json['alertas']}")


if __name__ == "__main__":
    test_mei_card_impacto_financeiro()
    test_mei_card_alertas()
    print("\n[OK] Dashboard MEI — todos os testes passaram.")
