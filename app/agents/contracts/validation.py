"""
app/agents/contracts/validation.py — ADR-008 B14.0/B14.1.

Validação cruzada pura entre AgentMission e AgentExecutionResult.
Este módulo não executa missões, não persiste resultados e não activa
AgentExecutor, scheduler, agentes existentes ou providers LLM.

Lacunas normativas deliberadamente não implementadas:
- contagem de chamadas para BudgetPolicy.max_calls;
- comparação de AgentMission.agent_version_required.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission


def _exigir_igualdade(
    *,
    campo: str,
    valor_resultado: Any,
    valor_missao: Any,
) -> None:
    if valor_resultado != valor_missao:
        raise ValueError(
            "Resultado incompatível com a missão: "
            f"{campo} divergente"
        )


def _validar_correspondencia_basica(
    mission: AgentMission,
    result: AgentExecutionResult,
) -> None:
    comparacoes = (
        (
            "agent_id",
            result.agent_id,
            mission.target_agent,
        ),
        (
            "mission_id",
            result.mission_id,
            mission.mission_id,
        ),
        (
            "mission_type",
            result.mission_type,
            mission.mission_type,
        ),
        (
            "correlation_id",
            result.correlation_id,
            mission.correlation_id,
        ),
        (
            "scope",
            result.scope,
            mission.scope,
        ),
        (
            "tenant_id",
            result.tenant_id,
            mission.tenant_id,
        ),
        (
            "mode",
            result.mode,
            mission.execution_mode,
        ),
        (
            "payload_schema",
            result.payload_schema,
            mission.output_schema,
        ),
        (
            "payload_version",
            result.payload_version,
            mission.output_version,
        ),
    )

    for campo, valor_resultado, valor_missao in comparacoes:
        _exigir_igualdade(
            campo=campo,
            valor_resultado=valor_resultado,
            valor_missao=valor_missao,
        )


def _validar_budget_llm(
    mission: AgentMission,
    result: AgentExecutionResult,
) -> None:
    if not result.llm_used:
        return

    policy = mission.budget_policy

    if not policy.allow_llm:
        raise ValueError(
            "Resultado incompatível com a missão: "
            "llm_used=True mas BudgetPolicy.allow_llm=False"
        )

    if result.provider not in policy.allowed_providers:
        raise ValueError(
            "Resultado incompatível com a missão: "
            "provider não autorizado em BudgetPolicy"
        )

    if (
        result.tokens_used is not None
        and result.tokens_used > policy.max_output_tokens
    ):
        raise ValueError(
            "Resultado incompatível com a missão: "
            "tokens_used excede BudgetPolicy.max_output_tokens"
        )

    _validar_custo_maximo(
        campo="cost_estimated",
        custo=result.cost_estimated,
        max_cost=policy.max_cost,
    )
    _validar_custo_maximo(
        campo="cost_actual",
        custo=result.cost_actual,
        max_cost=policy.max_cost,
    )


def _validar_custo_maximo(
    *,
    campo: str,
    custo: Decimal | None,
    max_cost: Decimal,
) -> None:
    if custo is not None and custo > max_cost:
        raise ValueError(
            "Resultado incompatível com a missão: "
            f"{campo} excede BudgetPolicy.max_cost"
        )


def _validar_autoridade_das_accoes(
    mission: AgentMission,
    result: AgentExecutionResult,
) -> None:
    if not result.actions_executed:
        return

    if mission.execution_mode != "activo":
        raise ValueError(
            "Resultado incompatível com a missão: "
            "actions_executed exige execution_mode='activo'"
        )

    if mission.authority_level not in {
        "execucao",
        "elevada",
    }:
        raise ValueError(
            "Resultado incompatível com a missão: "
            "actions_executed exige authority_level "
            "'execucao' ou 'elevada'"
        )

    for action in result.actions_executed:
        if action.status != "executada":
            raise ValueError(
                "Resultado incompatível com a missão: "
                "actions_executed aceita apenas status='executada'"
            )


def validate_result_against_mission(
    mission: AgentMission,
    result: AgentExecutionResult,
) -> None:
    """
    Valida a correspondência missão × resultado sem efeitos secundários.

    O futuro AgentExecutor deverá chamar esta função antes de persistir o
    resultado. Esta função não implementa contador de chamadas nem comparação
    de versão mínima do agente por ausência de regra normativa suficiente.
    """
    if not isinstance(mission, AgentMission):
        raise TypeError("mission deve ser AgentMission")
    if not isinstance(result, AgentExecutionResult):
        raise TypeError(
            "result deve ser AgentExecutionResult"
        )

    _validar_correspondencia_basica(mission, result)
    _validar_budget_llm(mission, result)
    _validar_autoridade_das_accoes(mission, result)
