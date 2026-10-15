"""M006-C4 RED — o evento tipado seleciona o agente, sem scheduler legado."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agents.contracts.agent_erro_operacional import OperationalGlobalEventSnapshot
from app.agents.contracts.security_audit import SecurityAuditContext


def _security():
    from app.services.enterprise_l3_event_router import EnterpriseSecurityAggregateEvent

    return EnterpriseSecurityAggregateEvent(
        event_id=uuid4(),
        occurred_at=datetime.now(timezone.utc),
        kind="security_aggregate",
        origem="enterprise_runtime",
        scope="global",
        metrics=SecurityAuditContext(
            source_kind="enterprise_aggregated_request_logs",
            window_minutes=60,
            max_distinct_accounts_per_ip=4,
            max_requests_per_user=101,
            requests_without_user_agent=21,
        ),
    )


def _operational():
    return OperationalGlobalEventSnapshot(
        event_id=uuid4(),
        occurred_at=datetime.now(timezone.utc),
        scope="global",
        tenant_id=None,
        tipo="schema_drift",
        origem="enterprise_runtime",
        mensagem="Falha de esquema detectada.",
        contexto_indicadores=("UNDEFINED_COLUMN",),
    )


@pytest.mark.asyncio
async def test_c4_seguranca_selecionada_sem_chamada_ao_legado(monkeypatch):
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event
    from app.agents.security_audit_agent import security_audit_agent

    legacy = AsyncMock(side_effect=AssertionError("LEGACY_SECURITY_EXECUTED"))
    monkeypatch.setattr(security_audit_agent, "run", legacy)

    event = _security()
    receipt = await route_enterprise_l3_event(event, enable_security_shadow=True)
    assert receipt.event_id == event.event_id
    assert receipt.target_agent == "security_audit_agent"
    assert receipt.mission_id == receipt.result.mission_id
    assert len(receipt.idempotency_key) == 64
    assert receipt.result.status == "sucesso"
    assert receipt.result.mode == "sombra"
    assert receipt.result.payload["alert_codes"] == [
        "MULTI_ACCOUNT_PATTERN", "USER_REQUEST_VOLUME", "MISSING_USER_AGENT_VOLUME"
    ]
    assert receipt.result.payload["security_action_allowed"] is False
    assert receipt.result.payload["publication_allowed"] is False
    assert receipt.result.requires_human_review is True
    assert receipt.result.actions_proposed == []
    assert receipt.result.actions_executed == []
    assert receipt.result.llm_used is False
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_c4_seguranca_falha_fechada_sem_optin(monkeypatch):
    import app.services.enterprise_l3_event_router as module

    factory = AsyncMock(side_effect=AssertionError("MUST_NOT_EXECUTE"))
    monkeypatch.setattr(module, "AgentExecutor", factory)
    with pytest.raises(PermissionError, match="ENTERPRISE_ROUTE_SECURITY_NOT_AUTHORIZED"):
        await module.route_enterprise_l3_event(_security())
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_c4_evento_operacional_usa_ledger_c1_e_agente_de_erro(tmp_path):
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event
    from app.services.enterprise_l3_delivery import EnterpriseL3Delivery

    event = _operational()
    delivery = EnterpriseL3Delivery(tmp_path / "c4_events.sqlite3")
    receipt = await route_enterprise_l3_event(event, delivery=delivery)
    replay = await route_enterprise_l3_event(event, delivery=delivery)
    assert replay.mission_id == receipt.mission_id
    assert replay.result.execution_id == receipt.result.execution_id
    assert receipt.event_id == event.event_id
    assert receipt.target_agent == "agent_erro_operacional"
    assert receipt.result.agent_id == "agent_erro_operacional"
    assert receipt.result.payload["diagnostico_codigo"] == "SCHEMA_DRIFT_UNDEFINED_COLUMN"
    assert receipt.result.mode == "sombra"
    assert receipt.result.actions_executed == []
    assert receipt.result.llm_used is False


@pytest.mark.asyncio
async def test_c4_rejeita_evento_nao_tipado_e_optin_invalido():
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event

    with pytest.raises(TypeError, match="ENTERPRISE_ROUTE_EVENT_NOT_TYPED"):
        await route_enterprise_l3_event({"tipo": "security_aggregate"})
    with pytest.raises(TypeError, match="ENTERPRISE_ROUTE_SECURITY_OPTIN_INVALID"):
        await route_enterprise_l3_event(_security(), enable_security_shadow="true")


@pytest.mark.asyncio
async def test_c4_rejeita_payload_de_seguranca_adulterado():
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event

    altered = _security().model_copy(update={"kind": "unratified_kind"})
    with pytest.raises(PermissionError, match="ENTERPRISE_ROUTE_SECURITY_EVENT_INVALID"):
        await route_enterprise_l3_event(altered, enable_security_shadow=True)


@pytest.mark.asyncio
async def test_c4_evento_operacional_nao_pode_desviar_para_segurança():
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event

    altered = _operational().model_copy(update={"tipo": "security_aggregate"})
    from app.services.enterprise_l3_delivery import EnterpriseL3Delivery
    # O tipo e validado pelo ledger mesmo com opt-in de seguranca.
    # Aqui nao existe permissao de criar uma rota alternativa.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as temp:
        delivery = EnterpriseL3Delivery(Path(temp) / "c4.sqlite3")
        with pytest.raises(PermissionError, match="ENTERPRISE_EVENT_TYPE_NOT_ALLOWED"):
            await route_enterprise_l3_event(
                altered, enable_security_shadow=True, delivery=delivery
            )


@pytest.mark.asyncio
async def test_c4_mesmo_evento_seguranca_preserva_chave_nao_dedup():
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event

    event = _security()
    first = await route_enterprise_l3_event(event, enable_security_shadow=True)
    second = await route_enterprise_l3_event(event, enable_security_shadow=True)
    assert first.idempotency_key == second.idempotency_key
    assert first.mission_id != second.mission_id
    # C4 nao promete persistencia/deduplicacao. C1 e exclusivo de schema_drift.


@pytest.mark.asyncio
async def test_c4_evento_operacional_exige_ledger_expresso():
    from app.services.enterprise_l3_event_router import route_enterprise_l3_event
    with pytest.raises(PermissionError, match="ENTERPRISE_ROUTE_DELIVERY_REQUIRED"):
        await route_enterprise_l3_event(_operational())
