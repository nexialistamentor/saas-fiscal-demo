from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual
from app.services import assistente_service


@pytest.fixture
def client_sem_empresa():
    usuario = MagicMock(spec=User)
    usuario.id = 1
    usuario.email = "faturamento-ausente@test.local"
    usuario.empresas = []
    usuario.consulta_paga = False

    app.dependency_overrides[get_usuario_atual] = lambda: usuario

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_mei_sem_faturamento_bloqueia_sem_chamar_motor(monkeypatch):
    def fail_engine(*_args, **_kwargs):
        raise AssertionError(
            "Motor nao deve ser chamado sem faturamento"
        )

    monkeypatch.setattr(
        assistente_service,
        "executar_analise",
        fail_engine,
    )

    resultado = assistente_service._resposta_assistente_mei(
        "quanto pago de MEI em 2026"
    )

    assert resultado["bloqueado"] is True
    assert resultado["tipo_bloqueio"] == "FATURAMENTO_AUSENTE"
    assert resultado["estado_l3"] == "bloqueado"
    assert resultado["analysis_type"] == "mei_tax"
    assert resultado["requires_payment"] is False
    assert "faturamento" in resultado["resposta"].lower()


def test_mei_faturamento_zero_nao_presume_5000(monkeypatch):
    chamada = {}

    def fake_engine(analysis_type, dados):
        chamada["analysis_type"] = analysis_type
        chamada["dados"] = dados
        return {
            "tributos": {"das": 0},
            "alertas": [],
        }

    monkeypatch.setattr(
        assistente_service,
        "executar_analise",
        fake_engine,
    )

    resultado = assistente_service._resposta_assistente_mei(
        "quanto pago de MEI em 2026 com faturamento de 0 por mes"
    )

    assert chamada["analysis_type"] == "mei_tax"
    assert chamada["dados"]["faturamento"] == 0
    assert resultado.get("bloqueado") is not True
    assert "R$ 0,00" in resultado["resposta"]
    assert "R$ 5.000,00" not in resultado["resposta"]


def test_endpoint_mei_sem_faturamento_bloqueia_estruturado(
    client_sem_empresa,
):
    resposta = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "quanto pago de MEI em 2026"},
    )

    assert resposta.status_code == 200
    body = resposta.json()
    assert body["bloqueado"] is True
    assert body["tipo_bloqueio"] == "FATURAMENTO_AUSENTE"
    assert body["estado_l3"] == "bloqueado"
    assert body["analysis_type"] == "mei_tax"
    assert body["requires_payment"] is False
    assert "faturamento" in body["resposta"].lower()
    assert "5.000,00" not in body["resposta"]
