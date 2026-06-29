"""
Testes B13-OPS-04 — LLMBudgetGuard.
10 testes obrigatórios aprovados pelo GPT.
"""
import pytest
from app.schemas.llm_usage_schema import BudgetCheckRequest
from app.services.llm_budget_guard import verificar, _reset_contadores


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    """Reset contadores e ambiente antes de cada teste."""
    _reset_contadores()
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "false")
    monkeypatch.setenv("LLM_BUDGET_ENABLED", "true")
    monkeypatch.setenv("LLM_DAILY_MAX_CALLS", "5")
    monkeypatch.setenv("LLM_MONTHLY_MAX_CALLS", "10")
    monkeypatch.setenv("LLM_MAX_INPUT_CHARS", "12000")
    monkeypatch.setenv("LLM_REQUIRE_REASON", "true")


def _req(**kwargs) -> BudgetCheckRequest:
    defaults = dict(tarefa="diagnostico_erro", motivo="teste", input_chars=100)
    defaults.update(kwargs)
    return BudgetCheckRequest(**defaults)


def test_allow_real_calls_false_bloqueia(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "false")
    r = verificar(_req())
    assert not r.permitido
    assert "travão absoluto" in r.motivo


def test_diario_excedido_bloqueia(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    monkeypatch.setenv("LLM_DAILY_MAX_CALLS", "2")
    verificar(_req())
    verificar(_req())
    r = verificar(_req())
    assert not r.permitido
    assert "diário" in r.motivo
    assert r.daily_remaining == 0


def test_mensal_excedido_bloqueia(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    monkeypatch.setenv("LLM_DAILY_MAX_CALLS", "100")
    monkeypatch.setenv("LLM_MONTHLY_MAX_CALLS", "2")
    verificar(_req())
    verificar(_req())
    r = verificar(_req())
    assert not r.permitido
    assert "mensal" in r.motivo
    assert r.monthly_remaining == 0


def test_input_maior_que_limite_bloqueia(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    monkeypatch.setenv("LLM_MAX_INPUT_CHARS", "100")
    r = verificar(_req(input_chars=200))
    assert not r.permitido
    assert "input_chars" in r.motivo


def test_max_output_tokens_acima_do_limite_bloqueia(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1024")
    r = verificar(_req(max_output_tokens=2048))
    assert not r.permitido
    assert "max_output_tokens" in r.motivo


def test_motivo_ausente_bloqueia(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    monkeypatch.setenv("LLM_REQUIRE_REASON", "true")
    r = verificar(_req(motivo=None))
    assert not r.permitido
    assert "motivo" in r.motivo.lower()


def test_tudo_ok_permite(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    r = verificar(_req())
    assert r.permitido
    assert r.daily_remaining is not None
    assert r.monthly_remaining is not None


def test_chamada_permitida_incrementa_contador(monkeypatch):
    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "true")
    monkeypatch.setenv("LLM_DAILY_MAX_CALLS", "5")
    verificar(_req())
    verificar(_req())
    r = verificar(_req())
    assert r.permitido
    assert r.daily_remaining == 2  # 5 - 3


def test_evento_conhecido_nao_chama_budget_guard():
    """B13-P0-06 reconhecido por sentinela — BudgetGuard nunca chamado."""
    from unittest.mock import patch as mock_patch
    from app.schemas.evento_operacional import EventoOperacional
    from app.agents.agent_erro_operacional import AgentErroOperacional
    import asyncio

    agent = AgentErroOperacional()
    evento = EventoOperacional(
        tipo="race_condition_frontend",
        origem="validarSessao",
        mensagem="Termos de Uso não aceites",
        endpoint="/empresas/",
        status_http=403,
    )
    with mock_patch("app.agents.agent_erro_operacional.budget_verificar") as mock_bg:
        resultado = asyncio.get_event_loop().run_until_complete(agent.run(evento))
        mock_bg.assert_not_called()

    assert resultado.classificacao == "P0"


def test_evento_desconhecido_fallback_passa_por_budget(monkeypatch):
    """Evento desconhecido em fallback passa pelo BudgetGuard antes do LLMRouter."""
    from unittest.mock import patch as mock_patch, MagicMock
    from app.schemas.evento_operacional import EventoOperacional
    from app.schemas.llm_usage_schema import BudgetCheckResult
    from app.agents.agent_erro_operacional import AgentErroOperacional
    import asyncio

    agent = AgentErroOperacional()
    evento = EventoOperacional(
        tipo="erro_desconhecido",
        origem="servico_x",
        mensagem="timeout inesperado",
    )
    mock_resultado = BudgetCheckResult(
        permitido=False,
        motivo="LLM_ALLOW_REAL_CALLS=false — travão absoluto activo",
    )
    with mock_patch("app.agents.agent_erro_operacional.budget_verificar", return_value=mock_resultado) as mock_bg:
        resultado = asyncio.get_event_loop().run_until_complete(
            agent.run(evento, modo_llm="fallback")
        )
        mock_bg.assert_called_once()

    assert resultado.classificacao == "P2"
    assert "orçamento" in resultado.causa_provavel
