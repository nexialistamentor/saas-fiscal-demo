"""O1 — testes de contrato para POST /perguntar."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual


def _client_mock(consulta_paga=False, empresas=None):
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "assistente-contract@test.local"
    mock_user.empresas = empresas or []
    mock_user.consulta_paga = consulta_paga
    app.dependency_overrides[get_usuario_atual] = lambda: mock_user
    return TestClient(app)


@pytest.fixture
def client_sem_empresa():
    c = _client_mock(empresas=[])
    with c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_com_empresa():
    empresa = MagicMock()
    empresa.id = 1
    c = _client_mock(empresas=[empresa])
    with c:
        yield c
    app.dependency_overrides.clear()


def test_perguntar_mei_sem_ano_bloqueia_estruturado(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto pago de MEI com faturamento de 5000 por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["bloqueado"] is True
    assert body["tipo_bloqueio"] == "TEMPO_NORMATIVO_AUSENTE"
    assert body["estado_l3"] == "bloqueado"


def test_perguntar_mei_com_ano_calcula(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto pago de MEI em 2026 com faturamento de 5000 por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is not True
    assert body["analysis_type"] == "mei_tax"


def test_perguntar_empresa_sem_empresa_vinculada_pede_vinculo(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto minha empresa paga no simples nacional"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "empresa" in body["resposta"].lower() or "login" in body["resposta"].lower()


def test_perguntar_empresa_simples_com_ano_calcula(client_com_empresa):
    res = client_com_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto minha empresa paga no simples nacional em 2026, faturamos 50 mil por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is not True
    assert body["analysis_type"] == "simples_nacional"


def test_perguntar_cpf_sem_ano_bloqueia_estruturado(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto pago de imposto autonomo com faturamento de 5000 por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["bloqueado"] is True
    assert body["tipo_bloqueio"] == "TEMPO_NORMATIVO_AUSENTE"
    assert body["estado_l3"] == "bloqueado"
