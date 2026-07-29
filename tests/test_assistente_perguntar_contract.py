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


def test_perguntar_sem_auth_retorna_401():
    """Sem override de auth, /perguntar deve rejeitar com 401."""
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.post(
            "/perguntar",
            json={"pergunta": "quanto pago de MEI em 2026 com faturamento de 5000 por mes"},
        )
    assert res.status_code == 401


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
    assert body["requires_payment"] is False


def test_perguntar_mei_com_ano_calcula(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto pago de MEI em 2026 com faturamento de 5000 por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is not True
    assert body["analysis_type"] == "mei_tax"
    assert body["requires_payment"] is False
    assert "DAS" in body["resposta"] or "MEI" in body["resposta"]


def test_perguntar_empresa_sem_empresa_vinculada_pede_vinculo(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto minha empresa paga no simples nacional"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "empresa" in body["resposta"].lower() or "login" in body["resposta"].lower()


def test_perguntar_empresa_simples_com_ano_sem_anexo_bloqueia(client_com_empresa):
    res = client_com_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto minha empresa paga no simples nacional em 2026, faturamos 50 mil por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is True
    assert body["tipo_bloqueio"] == "ANEXO_SIMPLES_NAO_DETERMINADO"
    assert body["estado_l3"] == "bloqueado"
    assert body["analysis_type"] == "simples_nacional"
    assert body["requires_payment"] is False


def test_perguntar_empresa_simples_nao_infere_anexo_por_atividade(client_com_empresa):
    res = client_com_empresa.post(
        "/perguntar",
        json={
            "pergunta": (
                "faturamos 50 mil por mes; quanto uma empresa de servico de "
                "consultoria paga no simples nacional no ano de referencia 2026"
            )
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is True
    assert body["tipo_bloqueio"] == "ANEXO_SIMPLES_NAO_DETERMINADO"
    assert body["estado_l3"] == "bloqueado"
    assert body["analysis_type"] == "simples_nacional"
    assert body["requires_payment"] is False

def test_perguntar_empresa_simples_com_anexo_explicito_calcula(client_com_empresa):
    res = client_com_empresa.post(
        "/perguntar",
        json={
            "pergunta": (
                "quanto minha empresa paga no simples nacional, faturamos 50 mil por mes, "
                "Anexo III, ano de referencia 2026"
            )
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is not True
    assert body["analysis_type"] == "simples_nacional"
    assert body["requires_payment"] is False
    assert "Anexo III" in body["resposta"]


def test_perguntar_empresa_simples_sem_ano_bloqueia_estruturado(client_com_empresa):
    res = client_com_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto minha empresa paga no simples nacional, faturamos 50 mil por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["bloqueado"] is True
    assert body["tipo_bloqueio"] == "TEMPO_NORMATIVO_AUSENTE"
    assert body["estado_l3"] == "bloqueado"
    assert body["requires_payment"] is False
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
    assert body["requires_payment"] is False


def test_perguntar_cpf_com_ano_calcula(client_sem_empresa):
    res = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto pago de imposto autonomo em 2026 com faturamento de 5000 por mes"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("bloqueado") is not True
    assert body["analysis_type"] == "cpf_tax"
    assert body["requires_payment"] is False
