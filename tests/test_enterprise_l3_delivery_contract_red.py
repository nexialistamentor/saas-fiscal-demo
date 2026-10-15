"""M006-C1 — contrato RED: idempotência operacional sem criar memória fiscal paralela."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.agents.contracts.agent_erro_operacional import (
    OperationalGlobalEventSnapshot,
)


def _event():
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
async def test_c1_replay_duravel_preserva_execucao_sem_dados_brutos(tmp_path):
    import app.services.enterprise_l3_delivery as module

    path = tmp_path / "enterprise_l3.sqlite3"
    event = _event()
    first = await module.EnterpriseL3Delivery(path).deliver(event)

    async def should_not_dispatch(_event):
        raise AssertionError("REPLAY_MUST_NOT_EXECUTE_AGENT")

    original = module.dispatch_operational_event
    module.dispatch_operational_event = should_not_dispatch
    try:
        second = await module.EnterpriseL3Delivery(path).deliver(event)
    finally:
        module.dispatch_operational_event = original

    assert first.event_id == second.event_id == event.event_id
    assert first.mission_id == second.mission_id
    assert first.result.execution_id == second.result.execution_id
    assert first.idempotency_key == second.idempotency_key
    assert first.result.status == second.result.status == "sucesso"
    assert path.is_file()
    assert b"Falha de esquema detectada." not in path.read_bytes()


@pytest.mark.asyncio
async def test_c1_concorrencia_impede_segunda_execucao(tmp_path, monkeypatch):
    import app.services.enterprise_l3_delivery as module

    path = tmp_path / "enterprise_l3.sqlite3"
    event = _event()
    real_dispatch = module.dispatch_operational_event
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def controlled_dispatch(snapshot):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return await real_dispatch(snapshot)

    monkeypatch.setattr(module, "dispatch_operational_event", controlled_dispatch)
    task = asyncio.create_task(module.EnterpriseL3Delivery(path).deliver(event))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        with pytest.raises(RuntimeError, match="ENTERPRISE_EVENT_IN_PROGRESS"):
            await module.EnterpriseL3Delivery(path).deliver(event)
    finally:
        release.set()
        await task

    assert calls == 1


@pytest.mark.asyncio
async def test_c1_mesmo_id_payload_diferente_bloqueado(tmp_path):
    from app.services.enterprise_l3_delivery import EnterpriseL3Delivery

    delivery = EnterpriseL3Delivery(tmp_path / "enterprise_l3.sqlite3")
    event = _event()
    await delivery.deliver(event)

    altered = event.model_copy(update={"mensagem": "Outro evento operacional."})
    with pytest.raises(ValueError, match="ENTERPRISE_EVENT_PAYLOAD_CONFLICT"):
        await delivery.deliver(altered)


@pytest.mark.asyncio
async def test_c1_falha_nao_produz_retry_automatico(tmp_path, monkeypatch):
    import app.services.enterprise_l3_delivery as module

    path = tmp_path / "enterprise_l3.sqlite3"
    event = _event()

    async def failing_dispatch(_):
        raise RuntimeError("SIMULATED_EXECUTION_FAILURE")

    monkeypatch.setattr(module, "dispatch_operational_event", failing_dispatch)
    with pytest.raises(RuntimeError, match="SIMULATED_EXECUTION_FAILURE"):
        await module.EnterpriseL3Delivery(path).deliver(event)

    with pytest.raises(RuntimeError, match="ENTERPRISE_EVENT_RECOVERY_REQUIRED"):
        await module.EnterpriseL3Delivery(path).deliver(event)


@pytest.mark.asyncio
async def test_c1_rejeita_origem_ou_tipo_nao_autorizados_sem_escrever(tmp_path):
    from app.services.enterprise_l3_delivery import EnterpriseL3Delivery

    path = tmp_path / "enterprise_l3.sqlite3"
    event = _event()
    for alteration in (
        {"origem": "origem_estranha"},
        {"tipo": "evento_sem_autorizacao"},
    ):
        altered = event.model_copy(update=alteration)
        with pytest.raises(PermissionError, match="ENTERPRISE_EVENT_.*_NOT_ALLOWED"):
            await EnterpriseL3Delivery(path).deliver(altered)
    assert not path.exists()
