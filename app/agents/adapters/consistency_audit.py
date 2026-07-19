"""app/agents/adapters/consistency_audit.py — ADR-012 B14.3D.

Adapter soberano assíncrono para ConsistencyAuditAgent.
Executa apenas em modo sombra ou dry_run. O modo activo produz
bloqueio auditável.

Não chama o agente legado. Não persiste. Não acede a BD, ORM,
Session, HTTP, filesystem, LLM ou scheduler.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.agents.contracts.consistency_audit import (
    ConsistencyAuditContext,
    ConsistencyAuditPreExecutionError,
    ConsistencyAuditResultSafetyError,
    ConsistencyAuditResultValidationError,
)
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.sanitization import assert_result_sanitized
from app.agents.contracts.shared import AgentAlert, BudgetPolicy
from app.agents.contracts.validation import validate_result_against_mission
from app.agents.engines.consistency_audit import (
    construir_payload_consistency_audit,
    validate_consistency_audit_payload_against_context,
)


_TARGET_AGENT = "consistency_audit_agent"
_MISSION_TYPE = "auditar_consistencia_fiscal"
_CONTEXT_SCHEMA = "consistency_audit.context"
_CONTEXT_VERSION = "1.0"
_OUTPUT_SCHEMA = "consistency_audit.result"
_OUTPUT_VERSION = "1.0"
_AGENT_VERSION = "1.0"

_EXECUTION_ERROR_MESSAGE = (
    "Não foi possível concluir a auditoria de consistência fiscal."
)


# ---------------------------------------------------------------------------
# Fronteira soberana
# ---------------------------------------------------------------------------


def _validar_fronteira(
    mission: AgentMission,
) -> tuple[int, int, int]:
    """Valida a missão contra o contrato soberano B14.3D.

    Returns:
        (tenant_id, actor_id, documento_id)

    Raises:
        ConsistencyAuditPreExecutionError: Perante qualquer violação
            do contrato de fronteira.
    """
    if mission.target_agent != _TARGET_AGENT:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_TARGET_MISMATCH"
        ) from None

    if mission.mission_type != _MISSION_TYPE:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_TYPE_UNSUPPORTED"
        ) from None

    if mission.context_schema != _CONTEXT_SCHEMA:
        raise ConsistencyAuditPreExecutionError(
            "CONTEXT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.context_version != _CONTEXT_VERSION:
        raise ConsistencyAuditPreExecutionError(
            "CONTEXT_VERSION_UNSUPPORTED"
        ) from None

    if mission.output_schema != _OUTPUT_SCHEMA:
        raise ConsistencyAuditPreExecutionError(
            "OUTPUT_SCHEMA_UNSUPPORTED"
        ) from None

    if mission.output_version != _OUTPUT_VERSION:
        raise ConsistencyAuditPreExecutionError(
            "OUTPUT_VERSION_UNSUPPORTED"
        ) from None

    if mission.scope != "documento":
        raise ConsistencyAuditPreExecutionError(
            "MISSION_SCOPE_UNSUPPORTED"
        ) from None

    tenant_id = mission.tenant_id

    if tenant_id is None:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_TENANT_REQUIRED"
        ) from None

    if type(tenant_id) is not int or tenant_id <= 0:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_TENANT_UNSUPPORTED"
        ) from None

    actor_id = mission.actor_id

    if type(actor_id) is not int or actor_id <= 0:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_ACTOR_UNSUPPORTED"
        ) from None

    # B14.3D: actor_id e tenant_id representam identidades distintas;
    # a autorização pertence a fronteira própria. Não exigimos igualdade.

    if mission.entity_type != "documento_fiscal":
        raise ConsistencyAuditPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    documento_id = mission.entity_id

    if type(documento_id) is not int or documento_id <= 0:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    if mission.requested_by not in {"user", "system"}:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_REQUESTED_BY_UNSUPPORTED"
        ) from None

    if mission.authority_level != "leitura":
        raise ConsistencyAuditPreExecutionError(
            "MISSION_AUTHORITY_UNSUPPORTED"
        ) from None

    source_request_id = mission.source_request_id

    if (
        not isinstance(source_request_id, str)
        or not source_request_id.strip()
        or mission.source_event_id is not None
        or mission.schedule_slot is not None
    ):
        raise ConsistencyAuditPreExecutionError(
            "MISSION_ORIGIN_UNSUPPORTED"
        ) from None

    if mission.budget_policy != BudgetPolicy():
        raise ConsistencyAuditPreExecutionError(
            "MISSION_BUDGET_UNSUPPORTED"
        ) from None

    if mission.sources:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_SOURCES_UNSUPPORTED"
        ) from None

    return tenant_id, actor_id, documento_id


def _validar_contexto(
    mission: AgentMission,
    *,
    documento_id: int,
) -> ConsistencyAuditContext:
    """Valida e constrói o contexto L3 a partir da missão.

    Args:
        mission: Missão soberana validada.
        documento_id: ID do documento fiscal esperado.

    Returns:
        ConsistencyAuditContext: Contexto tipado e validado.

    Raises:
        ConsistencyAuditPreExecutionError: Se o contexto for inválido
            ou divergir do documento_id da missão.
    """
    raw_context = mission.context

    if not isinstance(raw_context, dict):
        raise ConsistencyAuditPreExecutionError(
            "AG_CONSISTENCY_AUDIT_CONTEXT_INVALID"
        ) from None

    try:
        context_model = ConsistencyAuditContext.model_validate(
            raw_context
        )
    except Exception:
        raise ConsistencyAuditPreExecutionError(
            "AG_CONSISTENCY_AUDIT_CONTEXT_INVALID"
        ) from None

    # Invariante: entity_id == context.documento_id (ADR-012 §6.2)
    if context_model.documento_id != documento_id:
        raise ConsistencyAuditPreExecutionError(
            "MISSION_ENTITY_UNSUPPORTED"
        ) from None

    # Invariante: empresa_id > 0, documento_id > 0 (já validado pelo contrato)
    # Invariante: pelo menos um par aplicável (já validado pelo model_validator)

    return context_model


# ---------------------------------------------------------------------------
# Resultado soberano
# ---------------------------------------------------------------------------


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
    """Finaliza o resultado com validação independente e sanitização."""
    try:
        validate_result_against_mission(mission, result)
    except Exception:
        raise ConsistencyAuditResultValidationError() from None

    try:
        assert_result_sanitized(
            result.model_dump(mode="json")
        )
    except Exception:
        raise ConsistencyAuditResultSafetyError() from None

    return result


def _construir_bloqueio(
    *,
    mission: AgentMission,
    started_at: datetime,
    tick_start: int,
    code: str,
    message: str,
) -> AgentExecutionResult:
    """Constrói resultado bloqueado com alerta público."""
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
    """Constrói resultado de erro de execução."""
    result = _construir_resultado(
        mission=mission,
        status="erro",
        started_at=started_at,
        duration_ms=_calcular_duration_ms(tick_start),
        payload={},
        alerts=[],
        error_code="AG_CONSISTENCY_AUDIT_EXECUTION_ERROR",
        error_message=_EXECUTION_ERROR_MESSAGE,
    )

    return _finalizar(mission, result)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------


async def execute_consistency_audit_mission(
    mission: AgentMission,
) -> AgentExecutionResult:
    """Executa a auditoria de consistência L3 em sombra ou dry_run.

    O ConsistencyAuditAgent legado nunca é chamado.
    """
    _, _, documento_id = _validar_fronteira(mission)
    context_model = _validar_contexto(
        mission,
        documento_id=documento_id,
    )

    started_at = datetime.now(timezone.utc)
    tick_start = time.perf_counter_ns()

    # Ordem canónica: versão antes do modo
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
        payload_model = construir_payload_consistency_audit(
            context_model
        )

        validate_consistency_audit_payload_against_context(
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
