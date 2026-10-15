"""M006-C5 RED: tick L3 de seguranca usa ledger C1 sem executar legado."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.agents.contracts.security_audit import SecurityAuditContext


_SLOT = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)


def _metrics(**override):
    base = dict(
        source_kind="enterprise_aggregated_request_logs",
        window_minutes=60,
        max_distinct_accounts_per_ip=4,
        max_requests_per_user=101,
        requests_without_user_agent=21,
    )
    base.update(override)
    return SecurityAuditContext(**base)


@pytest.mark.asyncio
async def test_c5_evento_horario_replay_duravel_sem_duplicar_agente(tmp_path, monkeypatch):
    import app.services.enterprise_l3_shadow_scheduler as mod

    path = tmp_path / "enterprise_shared.sqlite3"
    first = await mod.EnterpriseL3ShadowScheduler(path).run_security_hour(
        slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
    )

    forbidden = AsyncMock(side_effect=AssertionError("AGENT_REEXECUTED_ON_REPLAY"))
    monkeypatch.setattr(mod, "route_enterprise_l3_event", forbidden)
    second = await mod.EnterpriseL3ShadowScheduler(path).run_security_hour(
        slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
    )
    assert first.event_id == second.event_id
    assert first.mission_id == second.mission_id
    assert first.result.execution_id == second.result.execution_id
    assert first.idempotency_key == second.idempotency_key
    assert first.result.payload["total_alerts"] == 3
    assert first.result.mode == "sombra"
    assert first.result.actions_proposed == first.result.actions_executed == []
    assert first.result.llm_used is False
    forbidden.assert_not_awaited()
    assert path.is_file()
    assert b"192.168." not in path.read_bytes()
    assert b"user_id" not in path.read_bytes()
    assert b"enterprise_aggregated_request_logs" not in path.read_bytes()


@pytest.mark.asyncio
async def test_c5_mesma_janela_metricas_diferentes_bloqueia_sem_novo_dispatch(tmp_path, monkeypatch):
    import app.services.enterprise_l3_shadow_scheduler as mod

    scheduler = mod.EnterpriseL3ShadowScheduler(tmp_path / "l3.sqlite3")
    await scheduler.run_security_hour(
        slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
    )
    forbidden = AsyncMock(side_effect=AssertionError("SECOND_DISPATCH_FORBIDDEN"))
    monkeypatch.setattr(mod, "route_enterprise_l3_event", forbidden)
    with pytest.raises(ValueError, match="ENTERPRISE_EVENT_PAYLOAD_CONFLICT"):
        await scheduler.run_security_hour(
            slot_utc=_SLOT,
            metrics=_metrics(max_requests_per_user=200),
            enable_security_shadow=True,
        )
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_c5_concorrencia_mesma_janela_apenas_uma_execucao(tmp_path, monkeypatch):
    import app.services.enterprise_l3_shadow_scheduler as mod

    original = mod.route_enterprise_l3_event
    started, release = asyncio.Event(), asyncio.Event()
    attempts = 0

    async def held_route(event, **kwargs):
        nonlocal attempts
        attempts += 1
        started.set()
        await release.wait()
        return await original(event, **kwargs)

    monkeypatch.setattr(mod, "route_enterprise_l3_event", held_route)
    ledger = tmp_path / "l3.sqlite3"
    a = mod.EnterpriseL3ShadowScheduler(ledger)
    b = mod.EnterpriseL3ShadowScheduler(ledger)
    pending = asyncio.create_task(a.run_security_hour(
        slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
    ))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        with pytest.raises(RuntimeError, match="ENTERPRISE_EVENT_IN_PROGRESS"):
            await b.run_security_hour(
                slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
            )
    finally:
        release.set()
        await pending
    assert attempts == 1


@pytest.mark.asyncio
async def test_c5_falha_nao_gera_retry_automatico(tmp_path, monkeypatch):
    import app.services.enterprise_l3_shadow_scheduler as mod

    scheduler = mod.EnterpriseL3ShadowScheduler(tmp_path / "l3.sqlite3")
    forbidden = AsyncMock(side_effect=RuntimeError("SIMULATED_FAILURE"))
    monkeypatch.setattr(mod, "route_enterprise_l3_event", forbidden)
    with pytest.raises(RuntimeError, match="SIMULATED_FAILURE"):
        await scheduler.run_security_hour(
            slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
        )
    with pytest.raises(RuntimeError, match="ENTERPRISE_EVENT_RECOVERY_REQUIRED"):
        await scheduler.run_security_hour(
            slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
        )
    forbidden.assert_awaited_once()


@pytest.mark.asyncio
async def test_c5_sem_optin_sem_criar_ficheiro(tmp_path):
    from app.services.enterprise_l3_shadow_scheduler import EnterpriseL3ShadowScheduler

    ledger = tmp_path / "ledger.sqlite3"
    scheduler = EnterpriseL3ShadowScheduler(ledger)
    for bad in (False, None, "true", 1):
        with pytest.raises(PermissionError, match="NOT_AUTHORIZED"):
            await scheduler.run_security_hour(
                slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=bad,
            )
    assert not ledger.exists()


@pytest.mark.asyncio
async def test_c5_rejeita_janelas_invalidas_sem_criar_ledger(tmp_path):
    from app.services.enterprise_l3_shadow_scheduler import EnterpriseL3ShadowScheduler

    ledger = tmp_path / "ledger.sqlite3"
    scheduler = EnterpriseL3ShadowScheduler(ledger)
    for bad in (
        _SLOT + timedelta(minutes=1),
        _SLOT.replace(tzinfo=None),
        _SLOT.astimezone(timezone(timedelta(hours=-3))),
    ):
        with pytest.raises(ValueError, match="ENTERPRISE_SECURITY_SLOT_"):
            await scheduler.run_security_hour(
                slot_utc=bad, metrics=_metrics(), enable_security_shadow=True,
            )
    with pytest.raises(TypeError, match="ENTERPRISE_SECURITY_AGGREGATE_NOT_TYPED"):
        await scheduler.run_security_hour(
            slot_utc=_SLOT, metrics={"ip": "192.168.1.1"},
            enable_security_shadow=True,
        )
    assert not ledger.exists()


@pytest.mark.asyncio
async def test_c5_usa_adapter_puro_nao_legado(tmp_path, monkeypatch):
    from app.agents.security_audit_agent import security_audit_agent
    from app.services.enterprise_l3_shadow_scheduler import EnterpriseL3ShadowScheduler

    legacy = AsyncMock(side_effect=AssertionError("LEGACY_SECURITY_CALLED"))
    monkeypatch.setattr(security_audit_agent, "run", legacy)
    receipt = await EnterpriseL3ShadowScheduler(tmp_path / "l3.sqlite3").run_security_hour(
        slot_utc=_SLOT, metrics=_metrics(), enable_security_shadow=True,
    )
    assert receipt.target_agent == "security_audit_agent"
    assert receipt.result.requires_human_review is True
    assert receipt.result.payload["publication_allowed"] is False
    assert receipt.result.payload["security_action_allowed"] is False
    legacy.assert_not_awaited()


def test_c5_nao_instala_loop_automatico_ou_scheduler_legado():
    import inspect
    import app.services.enterprise_l3_shadow_scheduler as mod

    source = inspect.getsource(mod)
    assert "app.agents.agent_scheduler" not in source
    assert "asyncio.sleep(" not in source
    assert "SessionLocal" not in source
    assert "run_all(" not in source
    assert "_CREATE" not in source
