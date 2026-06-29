"""
B13-OPS-05 — Replay controlado dos bugs B13.

Prova numa única bateria:
- Eventos conhecidos → sentinela local → P0 → zero tokens
- Evento desconhecido → BudgetGuard → bloqueado → P2 seguro → zero DeepSeek real

Evidência operacional L3: bugs deixam de depender do Miguel como sensor manual.
"""
import pytest
from unittest.mock import patch

from app.schemas.evento_operacional import EventoOperacional
from app.schemas.llm_schema import AgentOutputSchema
from app.agents.agent_erro_operacional import AgentErroOperacional

agent = AgentErroOperacional()

# ---------------------------------------------------------------------------
# Fixtures — eventos reais B13
# ---------------------------------------------------------------------------

REPLAY_EVENTOS_CONHECIDOS = [
    (
        "B13-P0-01 — CNAE SaaS → 5811 errado",
        EventoOperacional(
            tipo="cnae_errado",
            origem="formalizacao_router",
            mensagem="CNAE retornou 5811 livros para actividade software SaaS",
            endpoint="/formalizacao/recomendar-cnae",
            status_http=200,
        ),
    ),
    (
        "B13-P0-02 — MEI 500k sem inelegibilidade",
        EventoOperacional(
            tipo="mei_inelegivel_sem_alerta",
            origem="formalizacao_router",
            mensagem="MEI com faturamento 500000 sem bloqueio de inelegibilidade",
            endpoint="/formalizacao/simular-empresa",
            status_http=200,
        ),
    ),
    (
        "B13-P0-03 — faturamento zero → 422 técnico",
        EventoOperacional(
            tipo="validacao_tecnica",
            origem="formalizacao_router",
            mensagem="faturamento zero retornou 422 técnico",
            endpoint="/formalizacao/simular-empresa",
            status_http=422,
        ),
    ),
    (
        "B13-P0-06 — gate de termos/race condition",
        EventoOperacional(
            tipo="race_condition_frontend",
            origem="validarSessao",
            mensagem="Termos de Uso não aceites",
            endpoint="/empresas/",
            status_http=403,
        ),
    ),
    (
        "B13-P0-07 — CTA login não preserva email",
        EventoOperacional(
            tipo="cta_login_contexto_perdido",
            origem="App.jsx",
            mensagem="CTA login não preserva email do registo",
        ),
    ),
    (
        "Vercel — VITE_API_URL vazia",
        EventoOperacional(
            tipo="env_vazia",
            origem="vercel_deploy",
            mensagem="VITE_API_URL vazia no ambiente Vercel — bundle aponta para string vazia",
        ),
    ),
]

EVENTO_DESCONHECIDO = EventoOperacional(
    tipo="erro_desconhecido",
    origem="servico_x",
    mensagem="timeout inesperado em operação interna",
)


# ---------------------------------------------------------------------------
# Replay — eventos conhecidos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("nome,evento", REPLAY_EVENTOS_CONHECIDOS)
async def test_replay_evento_conhecido_p0_sem_tokens(nome, evento):
    """
    Cada evento B13 conhecido deve:
    - ser classificado como P0 por sentinela local
    - não chamar BudgetGuard
    - não chamar LLMRouter
    - output validar contra AgentOutputSchema
    """
    with patch("app.agents.agent_erro_operacional.budget_verificar") as mock_bg, \
         patch("app.services.llm_router.completar") as mock_llm:

        resultado = await agent.run(evento)

        mock_bg.assert_not_called(), f"[{nome}] BudgetGuard foi chamado — evento devia ser reconhecido por sentinela"
        mock_llm.assert_not_called(), f"[{nome}] LLMRouter foi chamado — evento devia ser reconhecido por sentinela"

    assert resultado.classificacao == "P0", f"[{nome}] esperado P0, obtido {resultado.classificacao}"
    assert isinstance(resultado, AgentOutputSchema), f"[{nome}] output não valida contra AgentOutputSchema"
    assert isinstance(resultado.ficheiros_provaveis, list)
    assert isinstance(resultado.evidencias, list)


# ---------------------------------------------------------------------------
# Replay — evento desconhecido
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_replay_evento_desconhecido_budget_bloqueia_sem_deepseek(monkeypatch):
    """
    Evento desconhecido em fallback:
    - passa pelo BudgetGuard
    - LLM_ALLOW_REAL_CALLS=false bloqueia
    - resultado P2 seguro
    - LLMRouter real não é chamado
    """
    from app.schemas.llm_usage_schema import BudgetCheckResult

    monkeypatch.setenv("LLM_ALLOW_REAL_CALLS", "false")

    mock_budget = BudgetCheckResult(
        permitido=False,
        motivo="LLM_ALLOW_REAL_CALLS=false — travão absoluto activo",
    )

    with patch("app.agents.agent_erro_operacional.budget_verificar", return_value=mock_budget) as mock_bg, \
         patch("app.services.llm_router.completar") as mock_llm:

        resultado = await agent.run(EVENTO_DESCONHECIDO, modo_llm="fallback")

        mock_bg.assert_called_once()
        mock_llm.assert_not_called()

    assert resultado.classificacao == "P2"
    assert "orçamento" in resultado.causa_provavel
    assert isinstance(resultado, AgentOutputSchema)
