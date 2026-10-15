"""M006-C5: agendamento L3 por tick EXPLICITO, sem loop nem autostart.

Apenas a rota security_aggregate/global/60 min em sombra. Encaminha pelo
router C4 e usa o MESMO ledger transacional C1 para impedir replay e
concorrencia; nao cria outra tabela, base de inteligencia ou autoridade.

O produtor de metricas e o disparador de ticks ainda nao existem aqui.
O caminho e estritamente local/read-only, sem legado/LLM/HTTP/ORM.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from app.agents.contracts.canonical import (
    build_context_hash,
    build_mission_idempotency_key,
)
from app.agents.contracts.sanitization import assert_result_sanitized
from app.agents.contracts.security_audit import SecurityAuditContext
from app.services.enterprise_l3_delivery import EnterpriseL3Delivery
from app.services.enterprise_l3_event_dispatch import EnterpriseL3DispatchReceipt
from app.services.enterprise_l3_event_router import (
    EnterpriseL3RouteReceipt,
    EnterpriseSecurityAggregateEvent,
    route_enterprise_l3_event,
)


def _security_hour_event(
    slot_utc: datetime,
    metrics: SecurityAuditContext,
) -> EnterpriseSecurityAggregateEvent:
    if not isinstance(slot_utc, datetime) or slot_utc.tzinfo is None:
        raise ValueError("ENTERPRISE_SECURITY_SLOT_UTC_REQUIRED")
    if slot_utc.utcoffset() != timedelta(0):
        raise ValueError("ENTERPRISE_SECURITY_SLOT_UTC_REQUIRED")
    if (slot_utc.minute, slot_utc.second, slot_utc.microsecond) != (0, 0, 0):
        raise ValueError("ENTERPRISE_SECURITY_SLOT_HOUR_BOUNDARY_REQUIRED")
    if type(metrics) is not SecurityAuditContext:
        raise TypeError("ENTERPRISE_SECURITY_AGGREGATE_NOT_TYPED")
    try:
        validated_metrics = SecurityAuditContext.model_validate(
            metrics.model_dump(mode="python")
        )
    except Exception:
        raise ValueError("ENTERPRISE_SECURITY_AGGREGATE_INVALID") from None

    # A identidade e da janela (NAO dos valores das metricas): valores
    # divergentes na mesma janela produzem CONFLITO, nunca outra execucao.
    name = f"solveris.enterprise.security_aggregate.hour.v1|{slot_utc.isoformat()}"
    event_id = UUID(bytes=sha256(name.encode("ascii")).digest()[:16], version=4)
    return EnterpriseSecurityAggregateEvent(
        event_id=event_id,
        occurred_at=slot_utc,
        kind="security_aggregate",
        origem="enterprise_runtime",
        scope="global",
        metrics=validated_metrics,
    )


def _verified_receipt(
    receipt: EnterpriseL3RouteReceipt,
    event: EnterpriseSecurityAggregateEvent,
) -> EnterpriseL3RouteReceipt:
    if not isinstance(receipt, EnterpriseL3RouteReceipt):
        raise PermissionError("ENTERPRISE_SECURITY_RECEIPT_INVALID")
    result = receipt.result
    expected_key = build_mission_idempotency_key(
        mission_type="auditar_seguranca_agregada",
        target_agent="security_audit_agent",
        scope="global",
        tenant_id=None,
        entity_type=None,
        entity_id=None,
        source_event_id=event.event_id,
        schedule_slot=None,
        source_request_id=None,
        idempotency_reference_at=None,
        contract_version="1.0",
    )
    if (
        receipt.event_id != event.event_id
        or receipt.target_agent != "security_audit_agent"
        or receipt.idempotency_key != expected_key
        or receipt.mission_id != result.mission_id
        or result.agent_id != "security_audit_agent"
        or result.mission_type != "auditar_seguranca_agregada"
        or result.scope != "global"
        or result.tenant_id is not None
        or result.mode != "sombra"
        or result.status != "sucesso"
        or result.payload_schema != "security_audit.result"
        or result.payload_version != "1.0"
        or result.agent_version != "1.0"
        or result.actions_proposed
        or result.actions_executed
        or result.llm_used
        or result.provider is not None
        or result.tokens_used is not None
        or result.cost_actual is not None
        or result.cost_estimated is not None
        or not result.requires_human_review
        or result.payload.get("publication_allowed") is not False
        or result.payload.get("security_action_allowed") is not False
        or result.payload.get("window_minutes") != 60
    ):
        raise PermissionError("ENTERPRISE_SECURITY_RECEIPT_INVALID")
    try:
        assert_result_sanitized(result.model_dump(mode="json"))
    except Exception:
        raise PermissionError("ENTERPRISE_SECURITY_RECEIPT_UNSAFE") from None
    return receipt


class EnterpriseL3ShadowScheduler:
    """Uma entrada de tick autorizada, SEM temporizador ou ciclo autonomo."""

    def __init__(self, ledger_path: str | Path) -> None:
        self._delivery = EnterpriseL3Delivery(ledger_path)

    async def run_security_hour(
        self,
        *,
        slot_utc: datetime,
        metrics: SecurityAuditContext,
        enable_security_shadow: bool = False,
    ) -> EnterpriseL3RouteReceipt:
        # A fronteira opt-in antecede a abertura/criacao do ledger.
        if type(enable_security_shadow) is not bool or not enable_security_shadow:
            raise PermissionError("ENTERPRISE_SECURITY_SCHEDULE_NOT_AUTHORIZED")
        event = _security_hour_event(slot_utc, metrics)
        fingerprint = build_context_hash(event.model_dump(mode="python"))

        # Reusa deliberadamente as transicoes atomicas C1. Nao ha segunda
        # implementacao SQLite. Estas APIs internas permanecem congeladas
        # pelo contrato C1 e pelo contrato C5.
        saved = self._delivery._claim_or_replay(event.event_id, fingerprint)
        if saved is not None:
            replay = EnterpriseL3RouteReceipt(
                event_id=saved.event_id,
                target_agent="security_audit_agent",
                mission_id=saved.mission_id,
                idempotency_key=saved.idempotency_key,
                result=saved.result,
            )
            return _verified_receipt(replay, event)

        try:
            receipt = await route_enterprise_l3_event(
                event, enable_security_shadow=True,
            )
            receipt = _verified_receipt(receipt, event)
            self._delivery._transition(
                event.event_id,
                fingerprint,
                "completed",
                EnterpriseL3DispatchReceipt(
                    event_id=receipt.event_id,
                    mission_id=receipt.mission_id,
                    idempotency_key=receipt.idempotency_key,
                    result=receipt.result,
                ),
            )
            return receipt
        except BaseException:
            # Sem retries automaticos: claim preso ou falha exige revisao.
            self._delivery._transition(event.event_id, fingerprint, "failed")
            raise
