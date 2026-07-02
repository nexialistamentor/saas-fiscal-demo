"""
B13-OPS-13A — Testes de bloqueio de tempo normativo nos endpoints HTTP.

Prova que os endpoints fiscais MEI bloqueiam com 422 estruturado
quando ano_referencia/data_referencia está ausente, e calculam
normalmente quando presente.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual


@pytest.fixture
def client_auth():
    """Cliente autenticado com mock de auth e paywall liberado."""
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "b13ops13a@test.local"
    mock_user.consulta_paga = True
    app.dependency_overrides[get_usuario_atual] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _payload_bloqueio_valido(detail: dict) -> None:
    assert detail.get("bloqueado") is True
    assert detail.get("tipo_bloqueio") == "TEMPO_NORMATIVO_AUSENTE"
    assert detail.get("estado_l3") == "bloqueado"


# ---------------------------------------------------------------------------
# 1 e 2 — /imposto/calcular (MEI)
# ---------------------------------------------------------------------------

def test_imposto_calcular_mei_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_imposto_calcular_mei_com_ano_referencia_calcula(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
            "ano_referencia": 2026,
        },
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# 3 — /relatorio/mei_tax
# ---------------------------------------------------------------------------

def test_relatorio_mei_tax_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/relatorio/mei_tax",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


# ---------------------------------------------------------------------------
# 4 — /relatorio/imposto-pdf
# ---------------------------------------------------------------------------

def test_relatorio_imposto_pdf_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/relatorio/imposto-pdf",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


# ---------------------------------------------------------------------------
# 5 — assistente_service fluxo MEI sem ano
# ---------------------------------------------------------------------------

def test_assistente_mei_sem_ano_pede_ano_referencia():
    from app.services.assistente_service import _resposta_assistente_mei

    resultado = _resposta_assistente_mei("quanto eu pago de MEI com faturamento de 5000")

    assert resultado.get("bloqueado") is True
    assert resultado.get("tipo_bloqueio") == "TEMPO_NORMATIVO_AUSENTE"
    assert resultado.get("estado_l3") == "bloqueado"
    assert "ano" in resultado.get("resposta", "").lower()


def test_simples_nacional_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I"},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_simples_nacional_com_ano_referencia_calcula(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I", "ano_referencia": 2026},
    )
    assert res.status_code == 200
    assert res.json()["_ano_referencia"] == 2026


def test_calcular_imposto_simples_nacional_sem_ano_bloqueia():
    from app.services.imposto_service import calcular_imposto_simples_nacional
    from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError
    import pytest as _pytest

    with _pytest.raises(TempoNormativoAusenteError):
        calcular_imposto_simples_nacional(rbt12=360000.0, anexo="I")


def test_calcular_imposto_simples_nacional_com_ano_retorna_metadados():
    from app.services.imposto_service import calcular_imposto_simples_nacional

    resultado = calcular_imposto_simples_nacional(rbt12=360000.0, anexo="I", ano_referencia=2026)
    assert resultado["_ano_referencia"] == 2026
    assert resultado["_estado_temporal"] == "resolvido"
