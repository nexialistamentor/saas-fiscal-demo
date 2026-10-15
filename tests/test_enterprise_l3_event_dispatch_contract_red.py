"""M006-C0 RED — Integracao operacional L3 Enterprise."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.agents.contracts.agent_erro_operacional import (
    OperationalGlobalEventSnapshot,
)


def _evento():
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
async def test_m006_evento_chega_ao_executor_l3():
    from app.services.enterprise_l3_event_dispatch import (
        dispatch_operational_event,
    )

    event = _evento()
    receipt = await dispatch_operational_event(event)
    result = receipt.result

    assert receipt.event_id == event.event_id
    assert receipt.mission_id == result.mission_id
    assert len(receipt.idempotency_key) == 64

    assert result.agent_id == "agent_erro_operacional"
    assert result.status == "sucesso"
    assert result.mode == "sombra"
    assert result.payload["diagnostico_codigo"] == (
        "SCHEMA_DRIFT_UNDEFINED_COLUMN"
    )
    assert result.payload["automation_allowed"] is False
    assert result.payload["publication_allowed"] is False
    assert result.actions_executed == []
    assert result.llm_used is False


@pytest.mark.asyncio
async def test_m006_rejeita_evento_nao_tipado():
    from app.services.enterprise_l3_event_dispatch import (
        dispatch_operational_event,
    )

    with pytest.raises(TypeError, match="ENTERPRISE_EVENT_NOT_TYPED"):
        await dispatch_operational_event({
            "tipo": "schema_drift",
            "origem": "desconhecida",
        })


@pytest.mark.asyncio
async def test_m006_mesmo_evento_preserva_idempotencia():
    from app.services.enterprise_l3_event_dispatch import (
        dispatch_operational_event,
    )

    event = _evento()
    first = await dispatch_operational_event(event)
    second = await dispatch_operational_event(event)

    assert first.idempotency_key == second.idempotency_key
    assert first.result.status == "sucesso"
    assert second.result.status == "sucesso"
    assert first.result.actions_executed == []
    assert second.result.actions_executed == []
