from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.shared import AgentAlert
from app.agents.contracts.validation import validate_result_against_mission
from app.agents.normative_watchdog_agent import normative_watchdog_agent
from app.agents.patrol_effect_gate import persist_patrol_alerts


_TARGET_AGENT = "normative_watchdog"
_MISSION_TYPE = "patrulhar_base_normativa"
_CONTEXT_SCHEMA = "normative_watchdog.context"
_OUTPUT_SCHEMA = "normative_watchdog.result"
_AGENT_VERSION = "1.0"


def _validar_missao(mission: AgentMission) -> None:
    if mission.target_agent != _TARGET_AGENT:
        raise ValueError("PATROL_TARGET_MISMATCH")

    if mission.mission_type != _MISSION_TYPE:
        raise ValueError("PATROL_MISSION_TYPE_UNSUPPORTED")

    if mission.context_schema != _CONTEXT_SCHEMA:
        raise ValueError("PATROL_CONTEXT_SCHEMA_UNSUPPORTED")

    if mission.output_schema != _OUTPUT_SCHEMA:
        raise ValueError("PATROL_OUTPUT_SCHEMA_UNSUPPORTED")

    if mission.scope not in {"global", "tenant"}:
        raise ValueError("PATROL_SCOPE_UNSUPPORTED")

    if mission.requested_by != "scheduler":
        raise ValueError("PATROL_REQUESTER_UNSUPPORTED")

    if mission.authority_level != "leitura":
        raise ValueError("PATROL_AUTHORITY_UNSUPPORTED")

    if mission.execution_mode != "activo":
        raise ValueError("PATROL_MODE_UNSUPPORTED")

    if not mission.schedule_slot:
        raise ValueError("PATROL_SCHEDULE_SLOT_REQUIRED")


def _converter_alertas(raw_alerts: list[dict]) -> list[AgentAlert]:
    alerts: list[AgentAlert] = []

    for raw in raw_alerts:
        alerts.append(
            AgentAlert(
                code=raw["tipo"],
                severity=raw["nivel"],
                message=raw["descricao"],
            )
        )

    return alerts


async def execute_patrol_mission(
    mission: AgentMission,
) -> AgentExecutionResult:
    _validar_missao(mission)

    started_at = datetime.now(timezone.utc)

    raw_result = await normative_watchdog_agent.run(
        dict(mission.context)
    )

    alerts = _converter_alertas(
        list(raw_result.get("alertas", []))
    )

    finished_at = datetime.now(timezone.utc)
    duration_ms = max(
        0,
        int((finished_at - started_at).total_seconds() * 1000),
    )

    result = AgentExecutionResult(
        execution_id=uuid4(),
        attempt=1,
        agent_id=_TARGET_AGENT,
        agent_version=_AGENT_VERSION,
        mission_type=mission.mission_type,
        mission_id=mission.mission_id,
        correlation_id=mission.correlation_id,
        status="sucesso",
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
        requires_human_review=False,
        payload_schema=mission.output_schema,
        payload_version=mission.output_version,
        payload={
            "total_alertas": len(alerts),
            "ufs_sem_cobertura": raw_result.get(
                "ufs_sem_cobertura",
                [],
            ),
            "ncms_expirados": raw_result.get(
                "ncms_expirados",
                [],
            ),
        },
        llm_used=False,
    )

    validate_result_against_mission(mission, result)

    if result.alerts:
        persist_patrol_alerts(
            mission=mission,
            result=result,
        )

    return result
