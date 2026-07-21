"""
app/agents/adapters/agent_erro_operacional.py — ADR-014 B14.3F.

Adapter soberano assíncrono para AgentErroOperacional L3.
Executa apenas em modo sombra ou dry_run. O modo activo produz
bloqueio auditável.

Não chama o agente legado. Não persiste. Não acede a BD, ORM,
Session, HTTP, filesystem, LLM, scheduler, registry ou executor.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from app.agents.contracts.agent_erro_operacional import (
    AgentErroDiagnosisPreExecutionError,
    AgentErroDiagnosisResultSafetyError,
    AgentErroDiagnosisResultValidationError,
    OperationalEventSnapshot,
    OperationalGlobalEventSnapshot,
    OperationalLegacyDriftError,
    OperationalTenantEventSnapshot,
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
_MISSION_TYPE = "diagnosticar_evento_operacional"
_CONTEXT_SCHEMA = "agent_erro_operacional.context"
_CONTEXT_VERSION = "1.0"
_OUTPUT_SCHEMA = "agent_erro_operacional.result"
_OUTPUT_VERSION = "1.0"
_AGENT_VERSION = "1.0"

_EXECUTION_ERROR_CODE = (
    "AG_OPERATIONAL_DIAGNOSIS_EXECUTION_ERROR"
)
_EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir o diagnóstico do evento operacional."
)
_LEGACY_DRIFT_CODE = (
    "AG_OPERATIONAL_DIAGNOSIS_LEGACY_DRIFT"
)
_LEGACY_DRIFT_MESSAGE = (
    "O motor de diagnóstico detectou uma divergência "
    "no legado protegido."
)

_CONTEXT_ADAPTER = TypeAdapter(OperationalEventSnapshot)


def _e_datetime_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _validar_fronteira(
    mission: AgentMission,
) -> None:
    """Valida a missão contra a fronteira soberana B14.3F."""
    if mission.target_agent != _TARGET_AGENT:
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_TARGET_MISMATCH"
        ) from None

    if mission.mission_type != _MISSION_TYPE:
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_TYPE_UNSUPPORTED"
        ) from None

    if mission.context_schema != _CONTEXT_SCHEMA:
        raise AgentErroDiagnosisPreExecutionError(
            "CONTEXT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.context_version != _CONTEXT_VERSION:
        raise AgentErroDiagnosisPreExecutionError(
            "CONTEXT_VERSION_UNSUPPORTED"
        ) from None

    if mission.output_schema != _OUTPUT_SCHEMA:
        raise AgentErroDiagnosisPreExecutionError(
            "OUTPUT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.output_version != _OUTPUT_VERSION:
        raise AgentErroDiagnosisPreExecutionError(
            "OUTPUT_VERSION_UNSUPPORTED"
        ) from None

    if mission.scope not in {"global", "tenant"}:
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_SCOPE_UNSUPPORTED"
        ) from None

    if mission.scope == "global":
        if mission.tenant_id is not None:
            raise AgentErroDiagnosisPreExecutionError(
                "MISSION_TENANT_UNSUPPORTED"
            ) from None
    else:
        tenant_id = mission.tenant_id

        if tenant_id is None:
            raise AgentErroDiagnosisPreExecutionError(
                "MISSION_TENANT_REQUIRED"
            ) from None

        if type(tenant_id) is not int or tenant_id <= 0:
            raise AgentErroDiagnosisPreExecutionError(
                "MISSION_TENANT_UNSUPPORTED"
            ) from None

    if mission.actor_id is not None:
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_ACTOR_UNSUPPORTED"
        ) from None

    if (
        mission.entity_type is not None
        or mission.entity_id is not None
    ):
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    if mission.requested_by != "system":
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_REQUESTED_BY_UNSUPPORTED"
        ) from None

    if mission.authority_level != "leitura":
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_AUTHORITY_UNSUPPORTED"
        ) from None

    source_event_id = mission.source_event_id

    if (
        not isinstance(source_event_id, UUID)
        or source_event_id.version != 4
        or mission.source_request_id is not None
        or mission.schedule_slot is not None
    ):
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_ORIGIN_UNSUPPORTED"
        ) from None

    if mission.budget_policy != BudgetPolicy():
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_BUDGET_UNSUPPORTED"
        ) from None

    if mission.sources:
        raise AgentErroDiagnosisPreExecutionError(
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
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_ENVELOPE_UNSUPPORTED"
        ) from None

    if mission.priority != "alta":
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_PRIORITY_UNSUPPORTED"
        ) from None

    if mission.reference_at is None:
        raise AgentErroDiagnosisPreExecutionError(
            "MISSION_REFERENCE_AT_REQUIRED"
        ) from None

    if (
        not _e_datetime_utc(mission.created_at)
        or not _e_datetime_utc(mission.reference_at)
    ):
        raise AgentErroDiagnosisPreExecutionError(
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
) -> OperationalEventSnapshot:
    """
    Valida, sanitiza e cruza o snapshot recebido com a missão.

    A entrada bruta não pode escapar para mensagens públicas.
    """
    raw_context = mission.context

    if not isinstance(raw_context, dict):
        raise AgentErroDiagnosisPreExecutionError(
            "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID"
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
        raise AgentErroDiagnosisPreExecutionError(
            "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID"
        ) from None

    if type(context_model) not in (
        OperationalGlobalEventSnapshot,
        OperationalTenantEventSnapshot,
    ):
        raise AgentErroDiagnosisPreExecutionError(
            "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID"
        ) from None

    if (
        mission.source_event_id != context_model.event_id
        or mission.reference_at != context_model.occurred_at
        or mission.scope != context_model.scope
        or mission.tenant_id != context_model.tenant_id
        or mission.created_at < context_model.occurred_at
    ):
        raise AgentErroDiagnosisPreExecutionError(
            "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID"
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
    requires_human_review: bool = True,
) -> AgentExecutionResult:
    """Constrói o AgentExecutionResult soberano."""
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
        requires_human_review=requires_human_review,
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
        raise AgentErroDiagnosisResultValidationError() from None

    try:
        assert_result_sanitized(
            result.model_dump(mode="json")
        )
    except Exception:
        raise AgentErroDiagnosisResultSafetyError() from None

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
    """Constrói um resultado público de erro operacional."""
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


async def execute_agent_erro_operacional_mission(
    mission: AgentMission,
) -> AgentExecutionResult:
    """
    Executa o diagnóstico operacional L3 em sombra ou dry_run.

    O modo activo não analisa o contexto nem chama o motor.
    O agente legado nunca é chamado directamente.
    """
    _validar_fronteira(mission)

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

    context_model = _validar_contexto(mission)

    try:
        from app.agents.engines.agent_erro_operacional import (
            executar_agent_erro_operacional_engine,
        )

        payload_model = executar_agent_erro_operacional_engine(
            context_model
        )
        payload_dict = payload_model.model_dump(
            mode="python"
        )
    except OperationalLegacyDriftError:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            error_code=_LEGACY_DRIFT_CODE,
            error_message=_LEGACY_DRIFT_MESSAGE,
        )
    except Exception:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            error_code=_EXECUTION_ERROR_CODE,
            error_message=_EXECUTION_ERROR_MESSAGE,
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
        requires_human_review=(
            payload_model.requires_human_review
        ),
    )

    return _finalizar(mission, result)
