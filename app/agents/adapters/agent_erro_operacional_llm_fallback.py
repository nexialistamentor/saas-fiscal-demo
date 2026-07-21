"""
app/agents/adapters/agent_erro_operacional_llm_fallback.py — ADR-015 B14.3G.

Adapter soberano assíncrono do canário de pré-execução do fallback LLM
sobre eventos operacionais.

Executa apenas em modo sombra ou dry_run. O modo activo produz bloqueio
auditável. Recalcula deterministicamente a elegibilidade através do motor
B14.3G, avalia a política orçamental declarada na missão e termina sempre
antes de qualquer chamada real a LLM.

Não importa o agente legado. Não importa nem chama LLMRouter, BudgetGuard,
providers de LLM, serviços, ORM, BD, HTTP, filesystem, scheduler, registry
ou executor. Não persiste, não publica, não automatiza e não possui caminho
de sucesso em B14.3G v1.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from app.agents.contracts.agent_erro_operacional import (
    OperationalGlobalEventSnapshot,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.agent_erro_operacional_llm_fallback import (
    AGENT_VERSION_INCOMPATIBLE,
    AGENT_VERSION_INCOMPATIBLE_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED,
    AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR,
    AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE,
    AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE_MESSAGE,
    AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED,
    AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED_MESSAGE,
    EXECUTION_MODE_NOT_AUTHORIZED,
    EXECUTION_MODE_NOT_AUTHORIZED_MESSAGE,
    PERMITE_CHAMADA_REAL_V1,
    AgentErroOperacionalLLMFallbackPreExecutionError,
    AgentErroOperacionalLLMFallbackResultSafetyError,
    AgentErroOperacionalLLMFallbackResultValidationError,
    OperationalLLMFallbackContext,
    OperationalLLMFallbackLegacyDriftError,
)
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.sanitization import (
    assert_context_sanitized,
    assert_result_sanitized,
)
from app.agents.contracts.shared import AgentAlert, BudgetPolicy
from app.agents.contracts.validation import (
    validate_result_against_mission,
)


_TARGET_AGENT = "agent_erro_operacional"
_MISSION_TYPE = "diagnosticar_evento_operacional_llm_fallback"
_CONTEXT_SCHEMA = "agent_erro_operacional_llm_fallback.context"
_CONTEXT_VERSION = "1.0"
_OUTPUT_SCHEMA = "agent_erro_operacional_llm_fallback.result"
_OUTPUT_VERSION = "1.0"
_AGENT_VERSION = "1.0"

_CONTEXT_ADAPTER = TypeAdapter(OperationalLLMFallbackContext)


def _e_datetime_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _validar_fronteira(
    mission: AgentMission,
) -> None:
    """Valida a missão contra a fronteira soberana B14.3G."""
    if mission.target_agent != _TARGET_AGENT:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_TARGET_MISMATCH"
        ) from None

    if mission.mission_type != _MISSION_TYPE:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_TYPE_UNSUPPORTED"
        ) from None

    if mission.context_schema != _CONTEXT_SCHEMA:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "CONTEXT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.context_version != _CONTEXT_VERSION:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "CONTEXT_VERSION_UNSUPPORTED"
        ) from None

    if mission.output_schema != _OUTPUT_SCHEMA:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "OUTPUT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.output_version != _OUTPUT_VERSION:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "OUTPUT_VERSION_UNSUPPORTED"
        ) from None

    if mission.scope not in {"global", "tenant"}:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_SCOPE_UNSUPPORTED"
        ) from None

    if mission.scope == "global":
        if mission.tenant_id is not None:
            raise AgentErroOperacionalLLMFallbackPreExecutionError(
                "MISSION_TENANT_UNSUPPORTED"
            ) from None
    else:
        tenant_id = mission.tenant_id

        if tenant_id is None:
            raise AgentErroOperacionalLLMFallbackPreExecutionError(
                "MISSION_TENANT_REQUIRED"
            ) from None

        if type(tenant_id) is not int or tenant_id <= 0:
            raise AgentErroOperacionalLLMFallbackPreExecutionError(
                "MISSION_TENANT_UNSUPPORTED"
            ) from None

    actor_id = mission.actor_id

    if type(actor_id) is not int or actor_id <= 0:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_ACTOR_UNSUPPORTED"
        ) from None

    if (
        mission.entity_type is not None
        or mission.entity_id is not None
    ):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    if mission.requested_by != "user":
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_REQUESTED_BY_UNSUPPORTED"
        ) from None

    if mission.authority_level != "leitura":
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_AUTHORITY_UNSUPPORTED"
        ) from None

    source_event_id = mission.source_event_id

    if (
        not isinstance(source_event_id, UUID)
        or source_event_id.version != 4
        or mission.source_request_id is not None
        or mission.schedule_slot is not None
    ):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_ORIGIN_UNSUPPORTED"
        ) from None

    if not isinstance(mission.budget_policy, BudgetPolicy):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_BUDGET_UNSUPPORTED"
        ) from None

    if mission.sources:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_SOURCES_UNSUPPORTED"
        ) from None

    if any(
        value is not None
        for value in (
            mission.parent_mission_id,
            mission.deadline,
            mission.idempotency_reference_at,
            mission.ratification_id,
            mission.authorized_by,
            mission.authorization_role,
        )
    ):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_ENVELOPE_UNSUPPORTED"
        ) from None

    if mission.priority != "alta":
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_PRIORITY_UNSUPPORTED"
        ) from None

    if mission.reference_at is None:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_REFERENCE_AT_REQUIRED"
        ) from None

    if (
        not _e_datetime_utc(mission.created_at)
        or not _e_datetime_utc(mission.reference_at)
    ):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "MISSION_TEMPORALITY_UNSUPPORTED"
        ) from None


def _versao_incompativel(
    mission: AgentMission,
) -> bool:
    required = mission.agent_version_required

    return (
        required is not None
        and required != _AGENT_VERSION
    )


def _validar_contexto(
    mission: AgentMission,
) -> OperationalLLMFallbackContext:
    """
    Valida, sanitiza e cruza o snapshot recebido com a missão.

    A entrada bruta não pode escapar para mensagens públicas.
    """
    raw_context = mission.context

    if not isinstance(raw_context, dict):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID"
        ) from None

    try:
        context_model = _CONTEXT_ADAPTER.validate_python(
            raw_context
        )
        context_dump = context_model.model_dump(
            mode="python"
        )
        assert_context_sanitized(context_dump)
    except Exception:
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID"
        ) from None

    if type(context_model) not in (
        OperationalGlobalEventSnapshot,
        OperationalTenantEventSnapshot,
    ):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID"
        ) from None

    if (
        mission.source_event_id != context_model.event_id
        or mission.reference_at != context_model.occurred_at
        or mission.scope != context_model.scope
        or mission.tenant_id != context_model.tenant_id
        or mission.created_at < context_model.occurred_at
    ):
        raise AgentErroOperacionalLLMFallbackPreExecutionError(
            "AG_OPERATIONAL_LLM_FALLBACK_CONTEXT_INVALID"
        ) from None

    return context_model


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
    """Constrói o AgentExecutionResult soberano da B14.3G v1."""
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
    """Valida o resultado e aplica a sanitização soberana."""
    try:
        validate_result_against_mission(
            mission,
            result,
        )
    except Exception:
        raise AgentErroOperacionalLLMFallbackResultValidationError() from None

    try:
        assert_result_sanitized(
            result.model_dump(mode="json")
        )
    except Exception:
        raise AgentErroOperacionalLLMFallbackResultSafetyError() from None

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
    error_code: str,
    error_message: str,
) -> AgentExecutionResult:
    """Constrói um resultado público e opaco de erro operacional."""
    result = _construir_resultado(
        mission=mission,
        status="erro",
        started_at=started_at,
        duration_ms=_calcular_duration_ms(tick_start),
        payload={},
        alerts=[],
        error_code=error_code,
        error_message=error_message,
    )

    return _finalizar(mission, result)


async def execute_agent_erro_operacional_llm_fallback_mission(
    mission: AgentMission,
) -> AgentExecutionResult:
    """
    Executa o canário B14.3G em sombra ou dry_run.

    Recalcula a elegibilidade apenas pelas sentinelas determinísticas.
    O modo activo não analisa o contexto nem importa o motor. Nenhum
    caminho desta versão chama LLM, router, provider ou BudgetGuard.
    """
    _validar_fronteira(mission)

    started_at = datetime.now(timezone.utc)
    tick_start = time.perf_counter_ns()

    if _versao_incompativel(mission):
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code=AGENT_VERSION_INCOMPATIBLE,
            message=AGENT_VERSION_INCOMPATIBLE_MESSAGE,
        )

    if mission.execution_mode == "activo":
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code=EXECUTION_MODE_NOT_AUTHORIZED,
            message=EXECUTION_MODE_NOT_AUTHORIZED_MESSAGE,
        )

    context_model = _validar_contexto(mission)

    try:
        from app.agents.engines.agent_erro_operacional_llm_fallback import (
            executar_agent_erro_operacional_llm_fallback_engine,
        )

        eligible = executar_agent_erro_operacional_llm_fallback_engine(
            context_model
        )
    except OperationalLLMFallbackLegacyDriftError as exc:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            error_code=exc.code,
            error_message=exc.public_message,
        )
    except Exception:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            error_code=AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR,
            error_message=(
                AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE
            ),
        )

    if not eligible:
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code=AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE,
            message=AG_OPERATIONAL_LLM_FALLBACK_NOT_ELIGIBLE_MESSAGE,
        )

    if not mission.budget_policy.allow_llm:
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code=AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED,
            message=(
                AG_OPERATIONAL_LLM_FALLBACK_BUDGET_NOT_AUTHORIZED_MESSAGE
            ),
        )

    if PERMITE_CHAMADA_REAL_V1 is False:
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code=AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED,
            message=(
                AG_OPERATIONAL_LLM_FALLBACK_REAL_CALL_NOT_ENABLED_MESSAGE
            ),
        )

    return _construir_erro(
        mission=mission,
        started_at=started_at,
        tick_start=tick_start,
        error_code=AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR,
        error_message=AG_OPERATIONAL_LLM_FALLBACK_EXECUTION_ERROR_MESSAGE,
    )
