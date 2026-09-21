from unittest.mock import Mock

import pytest

from app.services import assistente_service, llm_router


PERGUNTAS_NATURAIS = (
    "Quanto paga o MEI de imposto?",
    "Quanto pago de DAS como MEI prestador de serviços em 2026?",
    "Qual o imposto mensal do MEI?",
)


@pytest.fixture(autouse=True)
def bloquear_llm_e_agentes(monkeypatch):
    chamada_proibida = Mock(
        side_effect=AssertionError("imposto_mei não deve chamar LLM ou agente")
    )
    monkeypatch.setattr(llm_router, "completar", chamada_proibida)
    monkeypatch.setattr(assistente_service.asyncio, "run", chamada_proibida)
    yield
    chamada_proibida.assert_not_called()


@pytest.mark.parametrize("pergunta", PERGUNTAS_NATURAIS)
def test_imposto_mei_reconhece_formulacoes_naturais(pergunta):
    assert assistente_service.identificar_intencao(pergunta) == "imposto_mei"


def test_imposto_mei_com_dados_usa_barramento_canonico_exatamente_uma_vez(
    monkeypatch,
):
    executar_analise = Mock(
        return_value={
            "modo": "estimativa",
            "tributos": {"das": 81.05},
            "alertas": [],
        }
    )
    monkeypatch.setattr(assistente_service, "executar_analise", executar_analise)

    resposta = assistente_service.responder_pergunta(
        "Quanto pago de DAS como MEI prestador de serviços em 2026, "
        "com faturamento mensal de R$ 6.000?"
    )

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
    assert "R$ 81,05" in resposta["resposta"]


@pytest.mark.parametrize("modo", [None, "", "decisao_definitiva", "inválido"])
def test_imposto_mei_bloqueia_resultado_sem_modo_de_estimativa(monkeypatch, modo):
    resultado = {"tributos": {"das": 81.05}, "alertas": []}
    if modo is not None:
        resultado["modo"] = modo
    executar_analise = Mock(return_value=resultado)
    monkeypatch.setattr(assistente_service, "executar_analise", executar_analise)

    resposta = assistente_service.responder_pergunta(
        "Qual o imposto mensal do MEI prestador de serviços em 2026, "
        "com faturamento mensal de R$ 6.000?"
    )

    executar_analise.assert_called_once()
    assert resposta["bloqueado"] is True
    assert resposta["tipo_bloqueio"] == "MODO_MEI_NAO_COMPROVADO"
    assert resposta["estado_l3"] == "bloqueado"


def test_imposto_mei_bloqueia_ano_sem_autoridade(monkeypatch):
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
        "Quanto pago de DAS como MEI prestador de serviços em 2025, "
        "com faturamento mensal de R$ 6.000?"
    )

    executar_analise.assert_called_once()
    assert resposta["bloqueado"] is True
    assert resposta["tipo_bloqueio"] == "AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL"
    assert resposta["estado_l3"] == "bloqueado"


@pytest.mark.parametrize(
    ("pergunta", "bloqueio", "dado_pedido", "dados_nao_pedidos"),
    (
        (
            "Quanto paga o MEI de imposto?",
            "FATURAMENTO_AUSENTE",
            "faturamento",
            ("ano", "atividade"),
        ),
        (
            "Quanto paga o MEI de imposto com faturamento mensal de R$ 6.000?",
            "TEMPO_NORMATIVO_AUSENTE",
            "ano",
            ("atividade", "faturamento"),
        ),
        (
            "Quanto paga o MEI de imposto em 2026 com faturamento mensal de R$ 6.000?",
            "ATIVIDADE_MEI_AUSENTE",
            "atividade",
            ("faturamento",),
        ),
    ),
)
def test_imposto_mei_pede_somente_o_proximo_dado_necessario(
    monkeypatch,
    pergunta,
    bloqueio,
    dado_pedido,
    dados_nao_pedidos,
):
    executar_analise = Mock(
        side_effect=AssertionError("motor não deve ser chamado com dados ausentes")
    )
    monkeypatch.setattr(assistente_service, "executar_analise", executar_analise)

    resposta = assistente_service.responder_pergunta(pergunta)

    executar_analise.assert_not_called()
    assert resposta["bloqueado"] is True
    assert resposta["tipo_bloqueio"] == bloqueio
    assert resposta["estado_l3"] == "bloqueado"
    assert dado_pedido in resposta["resposta"].lower()
    for dado in dados_nao_pedidos:
        assert dado not in resposta["resposta"].lower()
