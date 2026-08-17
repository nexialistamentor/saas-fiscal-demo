"""G1/G2/G3 — testes de contrato HTTP para /imposto/*."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual


@pytest.fixture
def client_auth():
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "imposto-contract@test.local"
    app.dependency_overrides[get_usuario_atual] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _payload_bloqueio_valido(detail: dict) -> None:
    assert detail.get("bloqueado") is True
    assert detail.get("tipo_bloqueio") == "TEMPO_NORMATIVO_AUSENTE"
    assert detail.get("estado_l3") == "bloqueado"


# ---------------------------------------------------------------------------
# G1 — POST /imposto/calcular
# ---------------------------------------------------------------------------

def test_g1_calcular_cpf_com_ano_retorna_200(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={"tipo_usuario": "CPF", "faturamento_mensal": 5000.0, "ano_referencia": 2026},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tipo"] == "cpf"
    assert "imposto_mensal" in body
    assert body["imposto_anual"] == body["imposto_mensal"] * 12
    assert body["_ano_referencia"] == 2026
    assert body["_estado_temporal"] == "resolvido"


def test_g1_calcular_cpf_sem_ano_bloqueia_422(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={"tipo_usuario": "CPF", "faturamento_mensal": 5000.0},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_g1_calcular_mei_com_ano_bloqueia_sem_autoridade_oficial(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
            "atividade": "comercio",
            "ano_referencia": 2026,
        },
    )
    assert res.status_code == 503
    body = res.json()["detail"]
    assert body["bloqueado"] is True
    assert body["tipo_bloqueio"] == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    assert "imposto_mensal" not in body
    assert "imposto_anual" not in body


def test_mei_r001_atividade_ausente_bloqueia_sem_produzir_das(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={"tipo_usuario": "MEI", "faturamento_mensal": 5000.0, "ano_referencia": 2026},
    )

    assert res.status_code == 422
    body = res.json()
    assert body["detail"]["bloqueado"] is True
    assert body["detail"]["tipo_bloqueio"] == "ATIVIDADE_MEI_AUSENTE"
    assert "imposto_mensal" not in body


def test_mei_r001_atividade_vazia_bloqueia_sem_produzir_das(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
            "ano_referencia": 2026,
            "atividade": "",
        },
    )

    assert res.status_code == 422
    body = res.json()
    assert body["detail"]["bloqueado"] is True
    assert body["detail"]["tipo_bloqueio"] == "ATIVIDADE_MEI_AUSENTE"
    assert "imposto_mensal" not in body


def test_mei_r001_atividade_desconhecida_bloqueia_sem_produzir_das(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
            "ano_referencia": 2026,
            "atividade": "atividade_inexistente",
        },
    )

    assert res.status_code == 422
    body = res.json()
    assert body["detail"]["bloqueado"] is True
    assert body["detail"]["tipo_bloqueio"] == "ATIVIDADE_MEI_INVALIDA"
    assert "imposto_mensal" not in body


def test_g1_calcular_mei_sem_ano_bloqueia_422(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={"tipo_usuario": "MEI", "faturamento_mensal": 5000.0},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


# ---------------------------------------------------------------------------
# G2 — POST /imposto/simular-ano
# ---------------------------------------------------------------------------

def test_g2_simular_ano_mei_com_ano_retorna_200(client_auth):
    res = client_auth.post(
        "/imposto/simular-ano",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
            "atividade": "comercio",
            "ano_referencia": 2026,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tipo_usuario"] == "MEI"
    assert body["faturamento_anual"] == 5000.0 * 12
    assert "imposto_anual_estimado" in body
    assert "percentual_limite_mei" in body
    assert "valor_restante_limite" in body
    assert body["_ano_referencia"] == 2026
    assert body["_estado_temporal"] == "resolvido"


def test_g2_simular_ano_mei_sem_ano_bloqueia_422(client_auth):
    res = client_auth.post(
        "/imposto/simular-ano",
        json={"tipo_usuario": "MEI", "faturamento_mensal": 5000.0},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_g2_simular_ano_mei_acima_limite_gera_alerta(client_auth):
    res = client_auth.post(
        "/imposto/simular-ano",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 10000.0,
            "atividade": "comercio",
            "ano_referencia": 2026,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert any("limite do MEI" in a for a in body["alertas"])


# ---------------------------------------------------------------------------
# G3 — POST /imposto/simples-nacional
# ---------------------------------------------------------------------------

def test_g3_simples_nacional_com_ano_referencia_retorna_200(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I", "ano_referencia": 2026},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["_ano_referencia"] == 2026
    assert body["_estado_temporal"] == "resolvido"
    assert "das_mensal" in body
    assert "das_anual" in body


def test_g3_simples_nacional_com_data_referencia_resolve_ano(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I", "data_referencia": "2026-03-15"},
    )
    assert res.status_code == 200
    assert res.json()["_ano_referencia"] == 2026


def test_g3_simples_nacional_sem_tempo_normativo_bloqueia_422(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I"},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])
