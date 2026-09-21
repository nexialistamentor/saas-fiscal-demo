from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual
from app.services import assistente_service, llm_router


@pytest.fixture
def client_sem_empresa():
    usuario = MagicMock(spec=User)
    usuario.id = 1
    usuario.email = "limite-mei-temporal@test.local"
    usuario.empresas = []
    usuario.consulta_paga = False

    app.dependency_overrides[get_usuario_atual] = lambda: usuario
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_limite_mei_sem_autoridade_temporal_falha_fechado_sem_motor_ou_llm(
    client_sem_empresa,
    monkeypatch,
):
    def chamada_proibida(*_args, **_kwargs):
        raise AssertionError("limite do MEI nao deve chamar motor mei_tax nem LLM")

    monkeypatch.setattr(assistente_service, "executar_analise", chamada_proibida)
    monkeypatch.setattr(llm_router, "completar", chamada_proibida)

    resposta = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": "Qual é o limite do MEI em 2027?"},
    )

    assert resposta.status_code == 200
    body = resposta.json()
    assert body["bloqueado"] is True
    assert body["tipo_bloqueio"] == "AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL"
    assert body["estado_l3"] == "bloqueado"
    assert body["requires_payment"] is False
    assert "2027" in body["resposta"]
