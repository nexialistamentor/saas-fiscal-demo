"""M006-C12 RED: one trusted host-driven tick, no loop/source/secret store."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

UTC = timezone.utc
NOW = datetime(2026, 10, 15, 15, 5, tzinfo=UTC)
SLOT = datetime(2026, 10, 15, 14, tzinfo=UTC)
KEYS = tuple((f"c12-test-only-role-{i}-".encode() * 4) for i in range(4))


def _typed_bundle(tmp_path):
    import app.services.enterprise_l3_governed_tick as c12
    from app.services.enterprise_l3_revocation_recovery import EnterpriseSecurityAuthorityStatus
    from app.services.enterprise_l3_source_authorization_gate import EnterpriseSecuritySourceGrant
    from app.services.enterprise_l3_attested_snapshot_reader import EnterpriseSecuritySnapshotAttestation
    source = uuid4()
    epoch = 7
    source_dir = tmp_path / "isolated_source"
    source_dir.mkdir(exist_ok=True)
    return c12.EnterpriseSecurityHostAuthorities(
        status=EnterpriseSecurityAuthorityStatus.model_construct(source_id=source, rotation_epoch=epoch),
        grant=EnterpriseSecuritySourceGrant.model_construct(source_id=source, rotation_epoch=epoch),
        attestation=EnterpriseSecuritySnapshotAttestation.model_construct(source_id=source, slot_utc=SLOT),
        isolated_dir=source_dir,
        ledger_path=tmp_path / 'execution.sqlite3',
        trusted_status_key=KEYS[0],
        trusted_governance_key=KEYS[1],
        trusted_attestor_key=KEYS[2],
        producer_signing_key=KEYS[3],
        expected_rotation_epoch=epoch,
    )


def _host(bundle):
    from app.services.enterprise_l3_governed_tick import EnterpriseSecurityHostAuthorityPort

    class Host(EnterpriseSecurityHostAuthorityPort):
        async def authorities_for_hour(self, *, slot_utc):
            raise AssertionError('substituted with mock')

    instance = Host()
    instance.authorities_for_hour = AsyncMock(return_value=bundle)
    return instance


@pytest.mark.asyncio
async def test_c12_selects_latest_closed_hour_and_routes_only_through_c11(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    bundle = _typed_bundle(tmp_path)
    host = _host(bundle)
    receipt = object()
    call = AsyncMock(return_value=receipt)
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', call)
    result = await c12.run_one_governed_security_tick(host=host, enable_security_shadow=True)
    assert result is receipt
    host.authorities_for_hour.assert_awaited_once_with(slot_utc=SLOT)
    call.assert_awaited_once_with(
        status=bundle.status, trusted_status_key=KEYS[0],
        grant=bundle.grant, attestation=bundle.attestation,
        isolated_dir=bundle.isolated_dir, slot_utc=SLOT, ledger_path=tmp_path / 'execution.sqlite3',
        trusted_governance_key=KEYS[1], trusted_attestor_key=KEYS[2],
        producer_signing_key=KEYS[3], expected_rotation_epoch=7,
        enable_security_shadow=True,
    )
    assert not (tmp_path / 'execution.sqlite3').exists()
    assert 'test-only-role' not in repr(bundle)


@pytest.mark.asyncio
async def test_c12_default_deny_without_fetch_or_dispatch(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    host = _host(_typed_bundle(tmp_path))
    dispatched = AsyncMock()
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', dispatched)
    for flag in (False, None, 'true', 1):
        with pytest.raises(PermissionError, match='TICK_NOT_AUTHORIZED'):
            await c12.run_one_governed_security_tick(host=host, enable_security_shadow=flag)
    host.authorities_for_hour.assert_not_awaited()
    dispatched.assert_not_awaited()


@pytest.mark.asyncio
async def test_c12_rejects_arbitrary_host(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    for host in (None, AsyncMock(), object()):
        with pytest.raises(PermissionError, match='HOST_NOT_AUTHORIZED'):
            await c12.run_one_governed_security_tick(host=host, enable_security_shadow=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('now,code', [
    (NOW.replace(tzinfo=None), 'CLOCK_NOT_TRUSTED'),
    (NOW.astimezone(timezone(timedelta(hours=-3))), 'CLOCK_NOT_TRUSTED'),
    (NOW + timedelta(minutes=11), 'TICK_OUTSIDE_FRESH_WINDOW'),
    (NOW + timedelta(hours=2, minutes=11), 'TICK_OUTSIDE_FRESH_WINDOW'),
    (None, 'CLOCK_NOT_TRUSTED'),
])
async def test_c12_invalid_clock_never_fetches(tmp_path, monkeypatch, now, code):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: now)
    host = _host(_typed_bundle(tmp_path))
    with pytest.raises(PermissionError, match=code):
        await c12.run_one_governed_security_tick(host=host, enable_security_shadow=True)
    host.authorities_for_hour.assert_not_awaited()


@pytest.mark.asyncio
async def test_c12_host_bundle_must_be_typed(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    for fake in (None, {}, object()):
        with pytest.raises(PermissionError, match='HOST_BUNDLE_INVALID'):
            await c12.run_one_governed_security_tick(host=_host(fake), enable_security_shadow=True)


@pytest.mark.asyncio
async def test_c12_status_source_id_epoch_slot_bound_before_dispatch(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    bundled = _typed_bundle(tmp_path)
    dispatched = AsyncMock(side_effect=AssertionError('UNAUTHORIZED_C11'))
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', dispatched)
    for fake, code in (
        (replace(bundled, expected_rotation_epoch=8), 'ROTATION_EPOCH_MISMATCH'),
        (replace(bundled, status=bundled.status.model_copy(update={'source_id':uuid4()})), 'SOURCE_OR_SLOT_MISMATCH'),
        (replace(bundled, attestation=bundled.attestation.model_copy(update={'slot_utc':SLOT-timedelta(hours=1)})), 'SOURCE_OR_SLOT_MISMATCH'),
    ):
        with pytest.raises(PermissionError, match=code):
            await c12.run_one_governed_security_tick(host=_host(fake), enable_security_shadow=True)
    dispatched.assert_not_awaited()


@pytest.mark.asyncio
async def test_c12_key_custody_and_paths_fail_closed_before_dispatch(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    bundled = _typed_bundle(tmp_path)
    dispatched = AsyncMock(side_effect=AssertionError('UNAUTHORIZED_C11'))
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', dispatched)
    for fake, code in (
        (replace(bundled, ledger_path=bundled.isolated_dir / "enterprise_security_aggregates.sqlite3"), "LEDGER_NOT_ISOLATED"),
        (replace(bundled, producer_signing_key=b'short'), 'KEYS_NOT_AVAILABLE'),
        (replace(bundled, producer_signing_key=KEYS[0]), 'KEYS_NOT_SEPARATED'),
        (replace(bundled, trusted_governance_key='plain string'), 'KEYS_NOT_AVAILABLE'),
        (replace(bundled, isolated_dir=Path('relative')), 'HOST_PATH_INVALID'),
        (replace(bundled, ledger_path=Path('relative')), 'HOST_PATH_INVALID'),
    ):
        with pytest.raises(PermissionError, match=code):
            await c12.run_one_governed_security_tick(host=_host(fake), enable_security_shadow=True)
    dispatched.assert_not_awaited()


@pytest.mark.asyncio
async def test_c12_expired_during_provider_fetch_aborts_before_c11(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    clocks = iter((NOW, NOW + timedelta(minutes=11)))
    monkeypatch.setattr(c12, '_now_utc', lambda: next(clocks))
    dispatched = AsyncMock(side_effect=AssertionError('UNAUTHORIZED_C11'))
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', dispatched)
    with pytest.raises(PermissionError, match='TICK_OUTSIDE_FRESH_WINDOW'):
        await c12.run_one_governed_security_tick(host=_host(_typed_bundle(tmp_path)), enable_security_shadow=True)
    dispatched.assert_not_awaited()


@pytest.mark.asyncio
async def test_c12_provider_error_propagates_and_does_not_retry(tmp_path, monkeypatch):
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    host = _host(_typed_bundle(tmp_path))
    host.authorities_for_hour = AsyncMock(side_effect=RuntimeError('SOURCE_UNAVAILABLE'))
    dispatch = AsyncMock(side_effect=AssertionError('UNAUTHORIZED_C11'))
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', dispatch)
    with pytest.raises(RuntimeError, match='SOURCE_UNAVAILABLE'):
        await c12.run_one_governed_security_tick(host=host, enable_security_shadow=True)
    host.authorities_for_hour.assert_awaited_once()
    dispatch.assert_not_awaited()


def test_c12_no_legacy_db_logger_raw_logs_scheduler_or_background_loop():
    import inspect
    import app.services.enterprise_l3_governed_tick as c12
    source = inspect.getsource(c12)
    for forbidden in (
        'SessionLocal', 'app.models', 'from sqlalchemy',
        'os.environ', 'os.getenv', 'asyncio.sleep(', 'while True:',
        'app.agents.agent_scheduler', 'run_all(', 'CREATE TABLE', 'INSERT INTO',
        'pickle', 'httpx', 'requests.',
    ):
        assert forbidden not in source
    # Only the negative declaration in the module docstring mentions shared logs.
    assert source.count('request_logs') == 1
