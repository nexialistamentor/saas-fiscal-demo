"""M006-C0: dispatcher L3 Enterprise para evento operacional tipado.

Sem scheduler, persistencia, BD, HTTP, LLM ou efeitos de dominio.
A identidade idempotente nao equivale a deduplicacao duravel.
"""

from dataclasses import dataclass
from uuid import UUID

from app.agents.agent_executor import AgentExecutor
from app.agents.contracts.agent_erro_operacional import (
    OperationalGlobalEventSnapshot,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.mission_factory import create_agent_mission


@dataclass(frozen=True, slots=True)
class EnterpriseL3DispatchReceipt:
    event_id: UUID
    mission_id: UUID
    idempotency_key: str
    result: AgentExecutionResult


async def dispatch_operational_event(
    event: OperationalGlobalEventSnapshot | OperationalTenantEventSnapshot,
) -> EnterpriseL3DispatchReceipt:
    """Executa somente diagnostico L3 Enterprise em modo sombra."""

    if type(event) not in (
        OperationalGlobalEventSnapshot,
        OperationalTenantEventSnapshot,
    ):
        raise TypeError("ENTERPRISE_EVENT_NOT_TYPED")

    validated = type(event).model_validate(
        event.model_dump(mode="python")
    )

    if validated.origem != "enterprise_runtime":
        raise PermissionError("ENTERPRISE_EVENT_ORIGIN_NOT_ALLOWED")

    if validated.tipo != "schema_drift":
        raise PermissionError("ENTERPRISE_EVENT_TYPE_NOT_ALLOWED")

    mission = create_agent_mission(
        mission_type="diagnosticar_evento_operacional",
        target_agent="agent_erro_operacional",
        context=validated.model_dump(mode="python"),
        context_schema="agent_erro_operacional.context",
        output_schema="agent_erro_operacional.result",
        scope=validated.scope,
        tenant_id=validated.tenant_id,
        requested_by="system",
        authority_level="leitura",
        execution_mode="sombra",
        source_event_id=validated.event_id,
        created_at=validated.occurred_at,
        reference_at=validated.occurred_at,
        agent_version_required="1.0",
        priority="alta",
    )

    result = await AgentExecutor().execute_mission(mission)

    if result.actions_executed or result.llm_used:
        raise PermissionError("ENTERPRISE_L3_EFFECT_NOT_ALLOWED")

    return EnterpriseL3DispatchReceipt(
        event_id=validated.event_id,
        mission_id=mission.mission_id,
        idempotency_key=mission.idempotency_key,
        result=result,
    )
