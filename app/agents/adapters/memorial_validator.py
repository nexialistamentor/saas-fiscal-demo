"""
app/agents/adapters/memorial_validator.py - ADR-013 B14.3E.

Adapter soberano assincrono para MemorialValidatorAgent.
Executa apenas em modo sombra ou dry_run. O modo activo produz
bloqueio auditavel.

Nao chama o agente legado. Nao persiste. Nao acede a BD, ORM,
Session, HTTP, filesystem, LLM, scheduler, registry ou executor.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.memorial_validator import (
    MemorialValidatorContext,
    MemorialValidatorPreExecutionError,
    MemorialValidatorResultSafetyError,
    MemorialValidatorResultValidationError,
)
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.sanitization import assert_result_sanitized
from app.agents.contracts.shared import AgentAlert, BudgetPolicy
from app.agents.contracts.validation import (
    validate_result_against_mission,
)
from app.agents.engines.memorial_validator import (
    construir_payload_memorial,
    validate_memorial_validator_payload_against_context,
)


_TARGET_AGENT = "memorial_validator_agent"
_MISSION_TYPE = "validar_memorial_fiscal"
_CONTEXT_SCHEMA = "memorial_validator.context"
_CONTEXT_VERSION = "1.0"
_OUTPUT_SCHEMA = "memorial_validator.result"
_OUTPUT_VERSION = "1.0"
_AGENT_VERSION = "1.0"

_EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir a validação do memorial fiscal."
)


def _validar_fronteira(
    mission: AgentMission,
) -> tuple[int, int, int]:
    """
    Valida a missao contra a fronteira soberana B14.3E.

    Returns:
        tenant_id, actor_id e relatorio_id.
    """
    if mission.target_agent != _TARGET_AGENT:
        raise MemorialValidatorPreExecutionError(
            "MISSION_TARGET_MISMATCH"
        ) from None

    if mission.mission_type != _MISSION_TYPE:
        raise MemorialValidatorPreExecutionError(
            "MISSION_TYPE_UNSUPPORTED"
        ) from None

    if mission.context_schema != _CONTEXT_SCHEMA:
        raise MemorialValidatorPreExecutionError(
            "CONTEXT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.context_version != _CONTEXT_VERSION:
        raise MemorialValidatorPreExecutionError(
            "CONTEXT_VERSION_UNSUPPORTED"
        ) from None

    if mission.output_schema != _OUTPUT_SCHEMA:
        raise MemorialValidatorPreExecutionError(
            "OUTPUT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.output_version != _OUTPUT_VERSION:
        raise MemorialValidatorPreExecutionError(
            "OUTPUT_VERSION_UNSUPPORTED"
        ) from None

    if mission.scope != "documento":
        raise MemorialValidatorPreExecutionError(
            "MISSION_SCOPE_UNSUPPORTED"
        ) from None

    tenant_id = mission.tenant_id

    if tenant_id is None:
        raise MemorialValidatorPreExecutionError(
            "MISSION_TENANT_REQUIRED"
        ) from None

    if type(tenant_id) is not int or tenant_id <= 0:
        raise MemorialValidatorPreExecutionError(
            "MISSION_TENANT_UNSUPPORTED"
        ) from None

    actor_id = mission.actor_id

    if type(actor_id) is not int or actor_id <= 0:
        raise MemorialValidatorPreExecutionError(
            "MISSION_ACTOR_UNSUPPORTED"
        ) from None

    if mission.entity_type != "relatorio_analise":
        raise MemorialValidatorPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    relatorio_id = mission.entity_id

    if type(relatorio_id) is not int or relatorio_id <= 0:
        raise MemorialValidatorPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    if mission.requested_by not in {"user", "system"}:
        raise MemorialValidatorPreExecutionError(
            "MISSION_REQUESTED_BY_UNSUPPORTED"
        ) from None

    if mission.authority_level != "leitura":
        raise MemorialValidatorPreExecutionError(
            "MISSION_AUTHORITY_UNSUPPORTED"
        ) from None

    source_request_id = mission.source_request_id

    if (
        not isinstance(source_request_id, str)
        or not source_request_id.strip()
        or mission.source_event_id is not None
        or mission.schedule_slot is not None
    ):
        raise MemorialValidatorPreExecutionError(
            "MISSION_ORIGIN_UNSUPPORTED"
        ) from None

    if mission.budget_policy != BudgetPolicy():
        raise MemorialValidatorPreExecutionError(
            "MISSION_BUDGET_UNSUPPORTED"
        ) from None

    if mission.sources:
        raise MemorialValidatorPreExecutionError(
            "MISSION_SOURCES_UNSUPPORTED"
        ) from None

    return tenant_id, actor_id, relatorio_id

def _validar_contexto(
    mission: AgentMission,
    *,
    relatorio_id: int,
) -> MemorialValidatorContext:
    """
    Valida o snapshot minimo do memorial recebido na missao.

    A entrada bruta nao pode escapar para mensagens publicas.
    """
    raw_context = mission.context

    if not isinstance(raw_context, dict):
        raise MemorialValidatorPreExecutionError(
            "AG_MEMORIAL_VALIDATOR_CONTEXT_INVALID"
        ) from None

    try:
        context_model = MemorialValidatorContext.model_validate(
            raw_context
        )
    except Exception:
        raise MemorialValidatorPreExecutionError(
            "AG_MEMORIAL_VALIDATOR_CONTEXT_INVALID"
        ) from None

    if context_model.relatorio_id != relatorio_id:
        raise MemorialValidatorPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    return context_model


def _versao_incompativel(
    mission: AgentMission,
) -> bool:
    required = mission.agent_version_required

    return (
        required is not None
        and required != _AGENT_VERSION
    )


def _calcular_duration_ms(
    tick_start: int,
) -> int:
    tick_end = time.perf_counter_ns()

    return max(
        0,
        (tick_end - tick_start) // 1_000_000,
    )


def _construir_resultado(
    *,
    mission: AgentMission,
    status: str,
    started_at: datetime,
    duration_ms: int,
    payload: dict,
    alerts: list[AgentAlert],
    error_code: str | None,
    error_message: str | None,
) -> AgentExecutionResult:
    """Constroi o AgentExecutionResult soberano."""
    finished_at = started_at + timedelta(
        milliseconds=duration_ms
    )

    return AgentExecutionResult(
        execution_id=uuid4(),
        attempt=1,
        agent_id=_TARGET_AGENT,
        agent_version=_AGENT_VERSION,
        mission_type=mission.mission_type,
        mission_id=mission.mission_id,
        correlation_id=mission.correlation_id,
        status=status,
        scope=mission.scope,
        tenant_id=mission.tenant_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        mode=mission.execution_mode,
        alerts=alerts,
        evidence=[],
        actions_proposed=[],
        actions_executed=[],
        requires_human_review=True,
        payload_schema=mission.output_schema,
        payload_version=mission.output_version,
        payload=payload,
        llm_used=False,
        provider=None,
        tokens_used=None,
        cost_estimated=None,
        cost_actual=None,
        currency=None,
        retryable=False,
        error_code=error_code,
        error_message=error_message,
    )

def _finalizar(
    mission: AgentMission,
    result: AgentExecutionResult,
) -> AgentExecutionResult:
    """
    Valida o resultado contra a missão e aplica a sanitização soberana.
    """
    try:
        validate_result_against_mission(
            mission,
            result,
        )
    except Exception:
        raise MemorialValidatorResultValidationError() from None

    try:
        assert_result_sanitized(
            result.model_dump(mode="json")
        )
    except Exception:
        raise MemorialValidatorResultSafetyError() from None

    return result


def _construir_bloqueio(
    *,
    mission: AgentMission,
    started_at: datetime,
    tick_start: int,
    code: str,
    message: str,
) -> AgentExecutionResult:
    """Constrói um bloqueio auditável com payload vazio."""
    result = _construir_resultado(
        mission=mission,
        status="bloqueado",
        started_at=started_at,
        duration_ms=_calcular_duration_ms(tick_start),
        payload={},
        alerts=[
            AgentAlert(
                code=code,
                severity="alto",
                message=message,
                evidence_refs=[],
            )
        ],
        error_code=None,
        error_message=None,
    )

    return _finalizar(mission, result)


def _construir_erro(
    *,
    mission: AgentMission,
    started_at: datetime,
    tick_start: int,
) -> AgentExecutionResult:
    """Constrói o resultado público de erro operacional."""
    result = _construir_resultado(
        mission=mission,
        status="erro",
        started_at=started_at,
        duration_ms=_calcular_duration_ms(tick_start),
        payload={},
        alerts=[],
        error_code="AG_MEMORIAL_VALIDATOR_EXECUTION_ERROR",
        error_message=_EXECUTION_ERROR_MESSAGE,
    )

    return _finalizar(mission, result)

async def execute_memorial_validator_mission(
    mission: AgentMission,
) -> AgentExecutionResult:
    """
    Executa a validacao L3 do memorial em sombra ou dry_run.

    O modo activo nao analisa o contexto nem chama o motor.
    O agente legado nunca e chamado.
    """
    _, _, relatorio_id = _validar_fronteira(mission)

    started_at = datetime.now(timezone.utc)
    tick_start = time.perf_counter_ns()

    if _versao_incompativel(mission):
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code="AGENT_VERSION_INCOMPATIBLE",
            message="Versão do agente incompatível com a missão.",
        )

    if mission.execution_mode == "activo":
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code="EXECUTION_MODE_NOT_AUTHORIZED",
            message="Modo activo não autorizado neste canário.",
        )

    context_model = _validar_contexto(
        mission,
        relatorio_id=relatorio_id,
    )

    try:
        payload_model = construir_payload_memorial(
            context_model
        )

        validate_memorial_validator_payload_against_context(
            context=context_model,
            payload=payload_model,
        )

        payload_dict = payload_model.model_dump(
            mode="python"
        )
    except Exception:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
        )

    result = _construir_resultado(
        mission=mission,
        status="sucesso",
        started_at=started_at,
        duration_ms=_calcular_duration_ms(tick_start),
        payload=payload_dict,
        alerts=[],
        error_code=None,
        error_message=None,
    )

    return _finalizar(mission, result)