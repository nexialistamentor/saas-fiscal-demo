"""M006-C2: candidato L3 de auditoria de seguranca, apenas em sombra.

Nao acessa request_logs, ORM, DB, HTTP, filesystem, LLM ou agente legado.
Nao integra a allowlist central sem ratificacao contratual independente.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter_ns
from uuid import uuid4

from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.security_audit import SecurityAuditContext
from app.agents.contracts.sanitization import assert_result_sanitized
from app.agents.contracts.shared import AgentAlert, BudgetPolicy
from app.agents.contracts.validation import validate_result_against_mission
from app.agents.engines.security_audit import avaliar_indicadores


_MESSAGES = {
    "MULTI_ACCOUNT_PATTERN": ("critico", "Concentracao elevada de contas por origem agregada."),
    "USER_REQUEST_VOLUME": ("alto", "Volume de pedidos por utilizador acima do limiar."),
    "MISSING_USER_AGENT_VOLUME": ("medio", "Volume elevado de pedidos sem identificacao de cliente."),
}


def _check_mission(mission: AgentMission) -> None:
    if (
        type(mission) is not AgentMission
        or mission.target_agent != "security_audit_agent"
        or mission.mission_type != "auditar_seguranca_agregada"
        or mission.context_schema != "security_audit.context"
        or mission.output_schema != "security_audit.result"
        or mission.context_version != "1.0"
        or mission.output_version != "1.0"
        or mission.agent_version_required != "1.0"
        or mission.scope != "global"
        or mission.tenant_id is not None
        or mission.actor_id is not None
        or mission.entity_type is not None
        or mission.entity_id is not None
        or mission.requested_by != "system"
        or mission.authority_level != "leitura"
        or mission.execution_mode not in {"sombra", "dry_run"}
        or mission.source_event_id is None
        or mission.source_request_id is not None
        or mission.schedule_slot is not None
        or mission.budget_policy != BudgetPolicy()
        or bool(mission.sources)
        or mission.ratification_id is not None
        or mission.authorized_by is not None
        or mission.authorization_role is not None
    ):
        raise PermissionError("SECURITY_L3_BOUNDARY_DENIED")


async def execute_security_audit_mission(
    mission: AgentMission,
) -> AgentExecutionResult:
    """Avalia metricas ja agregadas: sem consultas e sem acoes."""
    _check_mission(mission)
    try:
        ctx = SecurityAuditContext.model_validate(mission.context)
    except Exception:
        raise PermissionError("SECURITY_L3_CONTEXT_INVALID") from None

    started = datetime.now(timezone.utc)
    tick = perf_counter_ns()
    codes = avaliar_indicadores(ctx)
    duration_ms = max(0, (perf_counter_ns() - tick) // 1_000_000)
    alerts = [
        AgentAlert(code=code, severity=_MESSAGES[code][0], message=_MESSAGES[code][1])
        for code in codes
    ]
    result = AgentExecutionResult(
        execution_id=uuid4(),
        attempt=1,
        agent_id="security_audit_agent",
        agent_version="1.0",
        mission_type=mission.mission_type,
        mission_id=mission.mission_id,
        correlation_id=mission.correlation_id,
        status="sucesso",
        scope="global",
        tenant_id=None,
        started_at=started,
        finished_at=started + timedelta(milliseconds=duration_ms),
        duration_ms=duration_ms,
        mode=mission.execution_mode,
        alerts=alerts,
        evidence=[],
        actions_proposed=[],
        actions_executed=[],
        requires_human_review=True,
        payload_schema=mission.output_schema,
        payload_version=mission.output_version,
        payload={
            "alert_codes": codes,
            "total_alerts": len(codes),
            "window_minutes": ctx.window_minutes,
            "publication_allowed": False,
            "security_action_allowed": False,
        },
        llm_used=False,
        retryable=False,
    )
    validate_result_against_mission(mission, result)
    assert_result_sanitized(result.model_dump(mode="json"))
    return result
