"""Prove generated UI questions stay on existing deterministic MEI paths."""
from unittest.mock import Mock
import pytest
from app.services import assistente_service as service, llm_router

@pytest.mark.parametrize('atividade,label', [('comercio_industria', 'comércio'), ('comercio_industria', 'indústria'), ('servicos', 'serviços')])
@pytest.mark.parametrize('valor,expected', [('6000.25', 6000.25), ('2026', 2026.0)])
def test_guided_das_reuses_canonical_engine_without_agents(monkeypatch, atividade, label, valor, expected):
    sentinel = Mock(side_effect=AssertionError('LLM/agent forbidden'))
    monkeypatch.setattr(llm_router, 'completar', sentinel)
    monkeypatch.setattr(service.asyncio, 'run', sentinel)
    engine = Mock(return_value={'tributos': {'das': 81.05}, 'alertas': [], 'modo': 'estimativa'})
    monkeypatch.setattr(service, 'executar_analise', engine)
    question = f'Como MEI de {label} em 2026, faturando R$ {valor} por mês, quanto pago de DAS?'
    result = service.responder_pergunta(question)
    engine.assert_called_once_with('mei_tax', {'faturamento': expected, 'ano_referencia': 2026, 'atividade': atividade, 'modo': 'estimativa'})
    assert result['requires_payment'] is False
    assert result['modo'] == 'estimativa'
    sentinel.assert_not_called()

def test_guided_limit_routes_without_engine_or_agents(monkeypatch):
    sentinel = Mock(side_effect=AssertionError('unexpected dependency'))
    monkeypatch.setattr(service.asyncio, 'run', sentinel)
    monkeypatch.setattr(llm_router, 'completar', sentinel)
    monkeypatch.setattr(service, 'executar_analise', sentinel)
    response = {'resposta': 'limite normativo', 'analysis_type': 'mei_limit', 'requires_payment': False}
    handler = Mock(return_value=response)
    monkeypatch.setattr(service, '_resposta_limite_mei', handler)
    assert service.responder_pergunta('Qual o limite do MEI em 2026?') == response
    handler.assert_called_once_with('Qual o limite do MEI em 2026?')
    sentinel.assert_not_called()
