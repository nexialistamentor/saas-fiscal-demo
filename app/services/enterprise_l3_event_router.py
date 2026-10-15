"""M006-C4 — encaminhamento tipado e explicito de eventos Enterprise L3.

Recebe apenas snapshots ja produzidos por componentes internos confiaveis.
Nao e endpoint, autenticador de origem, scheduler, monitor, listener ou job.
Usa o ledger C1 para eventos operacionais. Seguranca nao tem dedup duravel.
Nao chama run_all, agentes legados, ORM, DB, HTTP ou LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, UUID4, model_validator

from app.agents.agent_executor import AgentExecutor
from app.agents.contracts.agent_erro_operacional import (
    OperationalGlobalEventSnapshot,
    OperationalTenantEventSnapshot,
)
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.security_audit import SecurityAuditContext
from app.agents.mission_factory import create_agent_mission
from app.services.enterprise_l3_delivery import EnterpriseL3Delivery


class EnterpriseSecurityAggregateEvent(BaseModel):
    """Indicadores agregados, recebidos de uma fonte interna futura."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID4
    occurred_at: AwareDatetime
    kind: Literal["security_aggregate"]
    origem: Literal["enterprise_runtime"]
    scope: Literal["global"]
    metrics: SecurityAuditContext

    @model_validator(mode="after")
    def require_utc(self) -> Self:
        if self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("ENTERPRISE_SECURITY_EVENT_TIME_NOT_UTC")
        return self


@dataclass(frozen=True, slots=True)
class EnterpriseL3RouteReceipt:
    event_id: UUID
    target_agent: str
    mission_id: UUID
    idempotency_key: str
    result: AgentExecutionResult


def _check_read_only_result(result: AgentExecutionResult) -> None:
    if (
        result.mode != "sombra"
        or result.actions_proposed
        or result.actions_executed
        or result.llm_used
        or result.provider is not None
    ):
        raise PermissionError("ENTERPRISE_ROUTE_EFFECT_NOT_ALLOWED")


async def route_enterprise_l3_event(
    event: (
        OperationalGlobalEventSnapshot
        | OperationalTenantEventSnapshot
        | EnterpriseSecurityAggregateEvent
    ),
    *,
    enable_security_shadow: bool = False,
    delivery: EnterpriseL3Delivery | None = None,
) -> EnterpriseL3RouteReceipt:
    """Encaminha por contrato tipado; nunca por strings arbitrarias.

    Eventos operacionais exigem o ledger C1 explicitamente, evitando
    contornar a deduplicacao duravel numa segunda rota.
    O opt-in de seguranca e local a esta chamada, nunca ambiental.
    """

    if type(enable_security_shadow) is not bool:
        raise TypeError("ENTERPRISE_ROUTE_SECURITY_OPTIN_INVALID")

    if type(event) in (OperationalGlobalEventSnapshot, OperationalTenantEventSnapshot):
        if type(delivery) is not EnterpriseL3Delivery:
            raise PermissionError("ENTERPRISE_ROUTE_DELIVERY_REQUIRED")
        receipt = await delivery.deliver(event)
        _check_read_only_result(receipt.result)
        return EnterpriseL3RouteReceipt(
            event_id=receipt.event_id,
            target_agent="agent_erro_operacional",
            mission_id=receipt.mission_id,
            idempotency_key=receipt.idempotency_key,
            result=receipt.result,
        )

    if type(event) is not EnterpriseSecurityAggregateEvent:
        raise TypeError("ENTERPRISE_ROUTE_EVENT_NOT_TYPED")
    if delivery is not None:
        raise PermissionError("ENTERPRISE_ROUTE_SECURITY_DELIVERY_UNSUPPORTED")

    # model_copy(update=...) nao revalida Pydantic; impedir envelopes forjados.
    try:
        validated = EnterpriseSecurityAggregateEvent.model_validate(
            event.model_dump(mode="python")
        )
    except Exception:
        raise PermissionError("ENTERPRISE_ROUTE_SECURITY_EVENT_INVALID") from None

    if not enable_security_shadow:
        raise PermissionError("ENTERPRISE_ROUTE_SECURITY_NOT_AUTHORIZED")

    mission = create_agent_mission(
        mission_type="auditar_seguranca_agregada",
        target_agent="security_audit_agent",
        context=validated.metrics.model_dump(mode="python"),
        context_schema="security_audit.context",
        output_schema="security_audit.result",
        scope="global",
        requested_by="system",
        authority_level="leitura",
        execution_mode="sombra",
        source_event_id=validated.event_id,
        agent_version_required="1.0",
        created_at=validated.occurred_at,
        reference_at=validated.occurred_at,
        priority="alta",
    )
    result = await AgentExecutor(enable_security_shadow=True).execute_mission(mission)
    _check_read_only_result(result)
    if (
        result.agent_id != "security_audit_agent"
        or result.payload.get("publication_allowed") is not False
        or result.payload.get("security_action_allowed") is not False
        or not result.requires_human_review
    ):
        raise PermissionError("ENTERPRISE_ROUTE_SECURITY_RESULT_INVALID")

    return EnterpriseL3RouteReceipt(
        event_id=validated.event_id,
        target_agent="security_audit_agent",
        mission_id=mission.mission_id,
        idempotency_key=mission.idempotency_key,
        result=result,
    )
