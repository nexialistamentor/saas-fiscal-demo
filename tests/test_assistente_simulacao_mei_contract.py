from unittest.mock import Mock

import pytest

from app.services import assistente_service, llm_router


PERGUNTA = (
    "Faturando R$ 6.000 por mês como MEI prestador de serviços em 2026, "
    "quanto pago?"
)


@pytest.fixture(autouse=True)
def bloquear_llm_e_agentes(monkeypatch):
    falha = Mock(side_effect=AssertionError("LLM ou agente não deve ser chamado"))
    monkeypatch.setattr(llm_router, "completar", falha)
    monkeypatch.setattr(assistente_service.asyncio, "run", falha)


def _resultado_motor(modo="estimativa"):
    resultado = {"tributos": {"das": 81.05}, "alertas": []}
    if modo is not None:
        resultado["modo"] = modo
    return resultado


def test_simulacao_mei_publica_resultado_do_barramento_canonico(monkeypatch):
    executar_analise = Mock(return_value=_resultado_motor())
    monkeypatch.setattr(assistente_service, "executar_analise", executar_analise)

    assert assistente_service.identificar_intencao(PERGUNTA) == "simulacao_mei"

    resposta = assistente_service.responder_pergunta(PERGUNTA)

    executar_analise.assert_called_once_with(
        "mei_tax",
        {
            "faturamento": 6000.0,
            "ano_referencia": 2026,
            "atividade": "servicos",
            "modo": "estimativa",
        },
    )
    assert resposta["analysis_type"] == "mei_tax"
    assert resposta["modo"] == "estimativa"
    assert resposta.get("bloqueado") is not True
    assert "R$ 6.000,00" in resposta["resposta"]


@pytest.mark.parametrize("modo", [None, "decisao_definitiva", "adulterado"])
def test_simulacao_mei_falha_fechado_sem_modo_autorizado(monkeypatch, modo):
    executar_analise = Mock(return_value=_resultado_motor(modo))
    monkeypatch.setattr(assistente_service, "executar_analise", executar_analise)

    resposta = assistente_service.responder_pergunta(PERGUNTA)

    executar_analise.assert_called_once()
    assert resposta["bloqueado"] is True
    assert resposta["tipo_bloqueio"] == "MODO_MEI_NAO_COMPROVADO"
    assert resposta["estado_l3"] == "bloqueado"


def test_simulacao_mei_ano_sem_autoridade_permanece_bloqueado(monkeypatch):
    executar_analise = Mock(
        return_value={
            "analysis_type": "mei_tax",
            "erro": "mei_tax_engine",
            "causa": "AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL",
            "mensagem": "Autoridade normativa indisponível para o ano informado.",
        }
    )
    monkeypatch.setattr(assistente_service, "executar_analise", executar_analise)

    resposta = assistente_service.responder_pergunta(
        "Faturando R$ 6.000 por mês como MEI prestador de serviços em 2025, "
        "quanto pago?"
    )

    executar_analise.assert_called_once_with(
        "mei_tax",
        {
            "faturamento": 6000.0,
            "ano_referencia": 2025,
            "atividade": "servicos",
            "modo": "estimativa",
        },
    )
    assert resposta["bloqueado"] is True
    assert resposta["tipo_bloqueio"] == "AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL"
    assert resposta["estado_l3"] == "bloqueado"
