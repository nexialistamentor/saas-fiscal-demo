"""
app/agents/adapters/ag_encerramento.py — ADR-010 B14.3B.

Adapter soberano assíncrono para AgEncerramentoAgent (MEI).

Executa em modo sombra ou dry_run. Modo activo produz bloqueio auditável.

Não modifica o agente legado. Não persiste. Não activa LLM, HTTP ou scheduler.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agents.contracts.ag_encerramento import (
    AgEncerramentoContext,
    AgEncerramentoPreExecutionError,
    AgEncerramentoResultSafetyError,
    AgEncerramentoResultValidationError,
    EncerramentoAccessDeniedError,
    EncerramentoDataUnavailableError,
    EncerramentoPendenciaReader,
)
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.sanitization import assert_result_sanitized
from app.agents.contracts.shared import AgentAlert, BudgetPolicy
from app.agents.contracts.validation import validate_result_against_mission
from app.agents.engines.ag_encerramento import (
    construir_orientacao_encerramento,
    validate_ag_encerramento_payload_against_snapshot,
)

_TARGET_AGENT = "ag_encerramento"
_MISSION_TYPE = "orientar_encerramento_empresa"
_CONTEXT_SCHEMA = "ag_encerramento.context"
_CONTEXT_VERSION = "1.0"
_OUTPUT_SCHEMA = "ag_encerramento.result"
_OUTPUT_VERSION = "1.0"
_AGENT_VERSION = "1.0"

_ACCESS_DENIED_MESSAGE = (
    "Não foi possível autorizar o acesso à empresa solicitada."
)
_DATA_UNAVAILABLE_MESSAGE = (
    "Não foi possível obter os dados necessários para esta orientação."
)
_EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir a orientação de encerramento."
)


def _validar_fronteira(
    mission: AgentMission,
) -> tuple[int, int, datetime]:
    if mission.target_agent != _TARGET_AGENT:
        raise AgEncerramentoPreExecutionError(
            "MISSION_TARGET_MISMATCH"
        ) from None

    if mission.mission_type != _MISSION_TYPE:
        raise AgEncerramentoPreExecutionError(
            "MISSION_TYPE_UNSUPPORTED"
        ) from None

    if mission.context_schema != _CONTEXT_SCHEMA:
        raise AgEncerramentoPreExecutionError(
            "CONTEXT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.context_version != _CONTEXT_VERSION:
        raise AgEncerramentoPreExecutionError(
            "CONTEXT_VERSION_UNSUPPORTED"
        ) from None

    if mission.output_schema != _OUTPUT_SCHEMA:
        raise AgEncerramentoPreExecutionError(
            "OUTPUT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.output_version != _OUTPUT_VERSION:
        raise AgEncerramentoPreExecutionError(
            "OUTPUT_VERSION_UNSUPPORTED"
        ) from None

    if mission.scope != "tenant":
        raise AgEncerramentoPreExecutionError(
            "MISSION_SCOPE_UNSUPPORTED"
        ) from None

    tenant_id = mission.tenant_id

    if type(tenant_id) is not int or tenant_id <= 0:
        raise AgEncerramentoPreExecutionError(
            "MISSION_TENANT_REQUIRED"
        ) from None

    actor_id = mission.actor_id

    if type(actor_id) is not int or actor_id <= 0:
        raise AgEncerramentoPreExecutionError(
            "MISSION_ACTOR_UNSUPPORTED"
        ) from None

    if actor_id != tenant_id:
        raise AgEncerramentoPreExecutionError(
            "MISSION_ACTOR_TENANT_MISMATCH"
        ) from None

    reference_at = mission.reference_at

    if (
        not isinstance(reference_at, datetime)
        or reference_at.tzinfo is None
        or reference_at.utcoffset() != timedelta(0)
        or reference_at > mission.created_at
    ):
        raise AgEncerramentoPreExecutionError(
            "MISSION_REFERENCE_AT_REQUIRED"
        ) from None

    if (
        mission.requested_by not in {"user", "system"}
        or mission.authority_level != "leitura"
    ):
        raise AgEncerramentoPreExecutionError(
            "MISSION_AUTHORITY_UNSUPPORTED"
        ) from None

    source_request_id = mission.source_request_id

    if (
        not isinstance(source_request_id, str)
        or not source_request_id.strip()
        or mission.source_event_id is not None
        or mission.schedule_slot is not None
    ):
        raise AgEncerramentoPreExecutionError(
            "MISSION_ORIGIN_UNSUPPORTED"
        ) from None

    if mission.budget_policy != BudgetPolicy():
        raise AgEncerramentoPreExecutionError(
            "MISSION_BUDGET_UNSUPPORTED"
        ) from None

    if mission.sources:
        raise AgEncerramentoPreExecutionError(
            "MISSION_SOURCES_UNSUPPORTED"
        ) from None

    return tenant_id, actor_id, reference_at


def _validar_contexto(
    mission: AgentMission,
) -> AgEncerramentoContext:
    raw_context = mission.context

    if not isinstance(raw_context, dict):
        raise AgEncerramentoPreExecutionError(
            "AG_ENCERRAMENTO_CONTEXT_INVALID"
        ) from None

    raw_tipo = raw_context.get("tipo_contribuinte", "mei")

    if (
        raw_tipo is None
        or isinstance(raw_tipo, bool)
        or not isinstance(raw_tipo, str)
        or not raw_tipo.strip()
    ):
        raise AgEncerramentoPreExecutionError(
            "AG_ENCERRAMENTO_CONTEXT_INVALID"
        ) from None

    if raw_tipo.strip().casefold() != "mei":
        raise AgEncerramentoPreExecutionError(
            "AG_ENCERRAMENTO_TIPO_UNSUPPORTED"
        ) from None

    try:
        return AgEncerramentoContext.model_validate(raw_context)
    except Exception:
        raise AgEncerramentoPreExecutionError(
            "AG_ENCERRAMENTO_CONTEXT_INVALID"
        ) from None


def _versao_incompativel(mission: AgentMission) -> bool:
    required = mission.agent_version_required
    return required is not None and required != _AGENT_VERSION


def _calcular_duration_ms(tick_start: int) -> int:
    tick_end = time.perf_counter_ns()
    return max(0, (tick_end - tick_start) // 1_000_000)


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
    try:
        validate_result_against_mission(mission, result)
    except Exception:
        raise AgEncerramentoResultValidationError() from None

    try:
        assert_result_sanitized(
            result.model_dump(mode="json")
        )
    except Exception:
        raise AgEncerramentoResultSafetyError() from None

    return result


def _construir_bloqueio(
    *,
    mission: AgentMission,
    started_at: datetime,
    tick_start: int,
    code: str,
    message: str,
) -> AgentExecutionResult:
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
    code: str,
    message: str,
) -> AgentExecutionResult:
    result = _construir_resultado(
        mission=mission,
        status="erro",
        started_at=started_at,
        duration_ms=_calcular_duration_ms(tick_start),
        payload={},
        alerts=[],
        error_code=code,
        error_message=message,
    )

    return _finalizar(mission, result)


async def execute_ag_encerramento_mission(
    mission: AgentMission,
    reader: EncerramentoPendenciaReader,
) -> AgentExecutionResult:
    """
    Executa a capacidade L3 de encerramento MEI em sombra ou dry_run.

    O AgEncerramentoAgent legado nunca é chamado.
    """
    tenant_id, actor_id, reference_at = _validar_fronteira(
        mission
    )
    context_model = _validar_contexto(mission)

    started_at = datetime.now(timezone.utc)
    tick_start = time.perf_counter_ns()

    # Ordem canónica: versão antes do modo.
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

    try:
        snapshot = reader.obter_snapshot(
            tenant_id=tenant_id,
            actor_id=actor_id,
            empresa_id=context_model.empresa_id,
            reference_at=reference_at,
        )

        if snapshot.empresa_id != context_model.empresa_id:
            raise EncerramentoDataUnavailableError() from None

        if snapshot.reference_at != reference_at:
            raise EncerramentoDataUnavailableError() from None

        payload_model = construir_orientacao_encerramento(
            context=context_model,
            snapshot=snapshot,
        )

        validate_ag_encerramento_payload_against_snapshot(
            context=context_model,
            snapshot=snapshot,
            payload=payload_model,
        )

        payload_dict = payload_model.model_dump(
            mode="python"
        )

    except EncerramentoAccessDeniedError:
        return _construir_bloqueio(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code="AG_ENCERRAMENTO_ACCESS_DENIED",
            message=_ACCESS_DENIED_MESSAGE,
        )

    except EncerramentoDataUnavailableError:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code="AG_ENCERRAMENTO_DATA_UNAVAILABLE",
            message=_DATA_UNAVAILABLE_MESSAGE,
        )

    except Exception:
        return _construir_erro(
            mission=mission,
            started_at=started_at,
            tick_start=tick_start,
            code="AG_ENCERRAMENTO_EXECUTION_ERROR",
            message=_EXECUTION_ERROR_MESSAGE,
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
