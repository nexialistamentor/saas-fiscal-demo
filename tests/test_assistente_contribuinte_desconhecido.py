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
    usuario.email = "contribuinte-desconhecido@test.local"
    usuario.empresas = []
    usuario.consulta_paga = False

    app.dependency_overrides[get_usuario_atual] = lambda: usuario

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_faturamento_sem_tipo_nao_e_assumido_como_mei(monkeypatch):
    def fail_mei(*_args, **_kwargs):
        raise AssertionError(
            "Fluxo MEI nao deve ser chamado sem tipo de contribuinte"
        )

    monkeypatch.setattr(
        assistente_service,
        "_resposta_assistente_mei",
        fail_mei,
    )

    resultado = assistente_service.responder_pergunta(
        "faturamos 5000 por mes em 2026"
    )

    assert resultado["analysis_type"] is None
    assert resultado["requires_payment"] is False
    assert "tipo de contribuinte" in resultado["resposta"].lower()


def test_endpoint_faturamento_sem_tipo_pede_contribuinte(
    client_sem_empresa,
):
    resposta = client_sem_empresa.post(
        "/perguntar",
        json={
            "pergunta": "faturamos 5000 por mes em 2026"
        },
    )

    assert resposta.status_code == 200
    body = resposta.json()
    assert body["analysis_type"] is None
    assert body["requires_payment"] is False
    assert body.get("bloqueado") is not True
    assert "tipo de contribuinte" in body["resposta"].lower()
    assert "mei" not in str(body.get("analysis_type", "")).lower()
