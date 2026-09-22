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
    usuario.email = "limite-mei-contract@test.local"
    usuario.empresas = []
    usuario.consulta_paga = False

    app.dependency_overrides[get_usuario_atual] = lambda: usuario
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_perguntar_limite_mei_responde_normativo_sem_faturamento_motor_ou_llm(
    client_sem_empresa,
    monkeypatch,
):
    def chamada_proibida(*_args, **_kwargs):
        raise AssertionError("limite do MEI nao deve chamar motor mei_tax nem LLM")

    monkeypatch.setattr(assistente_service, "executar_analise", chamada_proibida)
    monkeypatch.setattr(llm_router, "completar", chamada_proibida)

    pergunta = "Qual é o limite do MEI?"
    assert assistente_service.identificar_intencao(pergunta) == "limite_mensal_mei"

    resposta = client_sem_empresa.post(
        "/perguntar",
        json={"pergunta": pergunta},
    )

    assert resposta.status_code == 200
    body = resposta.json()
    texto = body["resposta"].lower()

    pedidos_de_faturamento = (
        "informe seu faturamento",
        "informe o faturamento",
        "qual é o seu faturamento",
        "qual e o seu faturamento",
    )
    assert not any(pedido in texto for pedido in pedidos_de_faturamento)
    assert "limite" in texto
    assert "r$" in texto
    assert any(caractere.isdigit() for caractere in texto)
    assert body["requires_payment"] is False
