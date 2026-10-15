"""M006-C13 RED: independent host feed and time-limited custody before C12."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

SLOT = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)
NOW = SLOT + timedelta(hours=1, minutes=5)
KEYS = tuple((f"unit-only-c13-key-role-{i}-".encode() * 3) for i in range(4))


def _fixtures(tmp_path):
    import app.services.enterprise_l3_provisioned_host as c13
    from app.services.enterprise_l3_revocation_recovery import EnterpriseSecurityAuthorityStatus
    from app.services.enterprise_l3_source_authorization_gate import EnterpriseSecuritySourceGrant
    from app.services.enterprise_l3_attested_snapshot_reader import EnterpriseSecuritySnapshotAttestation
    uid = uuid4()
    source_dir = tmp_path / 'external_source'
    source_dir.mkdir(exist_ok=True)
    enrollment = c13.EnterpriseSecurityHostEnrollment(
        source_id=uid, rotation_epoch=4,
        isolated_dir=source_dir, ledger_path=tmp_path / 'c1.sqlite3',
    )
    grant = EnterpriseSecuritySourceGrant.model_construct(
        source_id=uid, rotation_epoch=4, source_scope='enterprise_only',
        execution_mode='sombra', snapshot_directory=str(source_dir),
    )
    status = EnterpriseSecurityAuthorityStatus.model_construct(
        source_id=uid, rotation_epoch=4,
        grant_sha256='a' * 64, disposition='active',
        issued_at_utc=NOW - timedelta(seconds=20),
        valid_until_utc=NOW + timedelta(minutes=2),
    )
    attestation = EnterpriseSecuritySnapshotAttestation.model_construct(
        source_id=uid, slot_utc=SLOT,
    )
    public = c13.EnterpriseSecurityPublicAuthorities(
        grant=grant, attestation=attestation, status=status,
    )
    lease = c13.EnterpriseSecurityKeyLease(
        source_id=uid, rotation_epoch=4, slot_utc=SLOT,
        valid_from_utc=NOW-timedelta(minutes=1),
        valid_until_utc=NOW+timedelta(minutes=1),
        trusted_status_key=KEYS[0], trusted_governance_key=KEYS[1],
        trusted_attestor_key=KEYS[2], producer_signing_key=KEYS[3],
    )

    class Feed(c13.EnterpriseSecurityPublicAuthorityFeed):
        async def authorities_for_hour(self, **kwargs):
            raise AssertionError('mocked')
        async def latest_status(self, **kwargs):
            raise AssertionError('mocked')

    class Custody(c13.EnterpriseSecurityKeyCustodyPort):
        async def acquire_lease(self, **kwargs):
            raise AssertionError('mocked')

    feed, custody = Feed(), Custody()
    feed.authorities_for_hour = AsyncMock(return_value=public)
    feed.latest_status = AsyncMock(return_value=status)
    custody.acquire_lease = AsyncMock(return_value=lease)
    return enrollment, public, lease, feed, custody


def _setup(tmp_path, monkeypatch):
    import app.services.enterprise_l3_provisioned_host as c13
    import app.services.enterprise_l3_governed_tick as c12
    monkeypatch.setattr(c13, '_now_utc', lambda: NOW)
    monkeypatch.setattr(c12, '_now_utc', lambda: NOW)
    enrollment, public, lease, feed, custody = _fixtures(tmp_path)
    host = c13.EnterpriseL3ProvisionedHost(
        enrollment=enrollment, authority_feed=feed, key_custody=custody,
        enable_security_shadow=True,
    )
    return c13, c12, host, enrollment, public, lease, feed, custody


@pytest.mark.asyncio
async def test_c13_host_selects_independent_ports_and_calls_c12_once(tmp_path, monkeypatch):
    c13, c12, host, enrolled, public, lease, feed, custody = _setup(tmp_path, monkeypatch)
    result = object()
    c11 = AsyncMock(return_value=result)
    monkeypatch.setattr(c12, 'run_revocation_gated_security_hour', c11)
    received = await c12.run_one_governed_security_tick(
        host=host, enable_security_shadow=True,
    )
    assert received is result
    expected = dict(slot_utc=SLOT, source_id=enrolled.source_id, rotation_epoch=4)
    feed.authorities_for_hour.assert_awaited_once_with(**expected)
    custody.acquire_lease.assert_awaited_once_with(**expected)
    feed.latest_status.assert_awaited_once_with(**expected)
    assert c11.await_count == 1
    args = c11.await_args.kwargs
    assert args['enable_security_shadow'] is True
    assert args['status'] is public.status
    assert args['trusted_status_key'] == KEYS[0]
    assert args['producer_signing_key'] == KEYS[3]
    assert args['ledger_path'] == enrolled.ledger_path
    assert not enrolled.ledger_path.exists()
    assert 'unit-only-c13-key' not in repr(lease)
    assert not hasattr(host, 'signing_key')


@pytest.mark.asyncio
async def test_c13_constructor_rejects_default_and_unapproved_ports(tmp_path, monkeypatch):
    c13, _, _, enrolled, _, _, feed, custody = _setup(tmp_path, monkeypatch)
    for flag in (None, False, 1, 'true'):
        with pytest.raises(PermissionError, match='HOST_NOT_AUTHORIZED'):
            c13.EnterpriseL3ProvisionedHost(
                enrollment=enrolled, authority_feed=feed, key_custody=custody,
                enable_security_shadow=flag,
            )
    for kwargs in ({'authority_feed': object()}, {'key_custody': AsyncMock()}):
        with pytest.raises(PermissionError, match='PROVIDER_NOT_AUTHORIZED'):
            c13.EnterpriseL3ProvisionedHost(**(dict(
                enrollment=enrolled, authority_feed=feed, key_custody=custody,
                enable_security_shadow=True,
            ) | kwargs))
    feed.authorities_for_hour.assert_not_awaited()
    custody.acquire_lease.assert_not_awaited()


@pytest.mark.asyncio
async def test_c13_rejects_invalid_enrollment(tmp_path, monkeypatch):
    c13, _, _, enrolled, _, _, feed, custody = _setup(tmp_path, monkeypatch)
    for enrollment, code in (
        (replace(enrolled, rotation_epoch=True), 'ENROLLMENT_INVALID'),
        (replace(enrolled, source_id='not-uuid'), 'ENROLLMENT_INVALID'),
        (replace(enrolled, isolated_dir=tmp_path.relative_to(tmp_path)), 'PATH_NOT_ABSOLUTE'),
        (replace(enrolled, ledger_path=tmp_path.relative_to(tmp_path)), 'PATH_NOT_ABSOLUTE'),
    ):
        with pytest.raises(PermissionError, match=code):
            c13.EnterpriseL3ProvisionedHost(
                enrollment=enrollment, authority_feed=feed, key_custody=custody,
                enable_security_shadow=True,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize('slot', [
    SLOT.replace(tzinfo=None), SLOT+timedelta(minutes=1),
    SLOT.astimezone(timezone(timedelta(hours=-3))), None,
])
async def test_c13_bad_slot_prevents_any_acquisition(tmp_path, monkeypatch, slot):
    _, _, host, _, _, _, feed, custody = _setup(tmp_path, monkeypatch)
    with pytest.raises(PermissionError, match='SLOT_NOT_UTC_HOUR'):
        await host.authorities_for_hour(slot_utc=slot)
    feed.authorities_for_hour.assert_not_awaited()
    custody.acquire_lease.assert_not_awaited()


@pytest.mark.asyncio
async def test_c13_rejects_untrusted_clock_before_acquisition(tmp_path, monkeypatch):
    c13, _, host, _, _, _, feed, custody = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(c13, '_now_utc', lambda: NOW + timedelta(minutes=11))
    with pytest.raises(PermissionError, match='WINDOW_NOT_FRESH'):
        await host.authorities_for_hour(slot_utc=SLOT)
    feed.authorities_for_hour.assert_not_awaited()
    custody.acquire_lease.assert_not_awaited()


@pytest.mark.asyncio
async def test_c13_public_scope_or_enrollment_mismatch_blocks_secrets(tmp_path, monkeypatch):
    c13, _, host, enrolled, public, _, feed, custody = _setup(tmp_path, monkeypatch)
    cases = (
        (replace(public, grant=public.grant.model_copy(update={'source_id':uuid4()})), 'PUBLIC_SCOPE_MISMATCH'),
        (replace(public, attestation=public.attestation.model_copy(update={'slot_utc':SLOT-timedelta(hours=1)})), 'PUBLIC_SCOPE_MISMATCH'),
        (replace(public, grant=public.grant.model_copy(update={'snapshot_directory':str(enrolled.ledger_path)})), 'PUBLIC_ENROLLMENT_MISMATCH'),
        (replace(public, grant=public.grant.model_copy(update={'source_scope':'mixed'})), 'PUBLIC_ENROLLMENT_MISMATCH'),
    )
    for envelope, code in cases:
        feed.authorities_for_hour.return_value = envelope
        with pytest.raises(PermissionError, match=code):
            await host.authorities_for_hour(slot_utc=SLOT)
    custody.acquire_lease.assert_not_awaited()


@pytest.mark.asyncio
async def test_c13_revoked_during_secret_acquisition_blocks_c12(tmp_path, monkeypatch):
    c13, _, host, _, public, _, feed, custody = _setup(tmp_path, monkeypatch)
    feed.latest_status.return_value = public.status.model_copy(update={'disposition':'revoked'})
    with pytest.raises(PermissionError, match='STATUS_NOT_ACTIVE'):
        await host.authorities_for_hour(slot_utc=SLOT)
    custody.acquire_lease.assert_awaited_once()
    feed.latest_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_c13_old_status_after_key_acquisition_blocks(tmp_path, monkeypatch):
    _, _, host, _, public, _, feed, _ = _setup(tmp_path, monkeypatch)
    feed.latest_status.return_value = public.status.model_copy(
        update={'issued_at_utc': public.status.issued_at_utc-timedelta(seconds=5)})
    with pytest.raises(PermissionError, match='STATUS_REGRESSED'):
        await host.authorities_for_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c13_status_changed_grant_hash_blocks(tmp_path, monkeypatch):
    _, _, host, _, public, _, feed, _ = _setup(tmp_path, monkeypatch)
    feed.latest_status.return_value = public.status.model_copy(update={'grant_sha256':'b'*64})
    with pytest.raises(PermissionError, match='GRANT_CHANGED_AFTER_FETCH'):
        await host.authorities_for_hour(slot_utc=SLOT)


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation,code', [
    ({'source_id':uuid4()}, 'LEASE_SCOPE_MISMATCH'),
    ({'rotation_epoch':5}, 'LEASE_SCOPE_MISMATCH'),
    ({'valid_until_utc':NOW-timedelta(seconds=1)}, 'LEASE_EXPIRED'),
    ({'valid_from_utc':NOW+timedelta(seconds=1)}, 'LEASE_EXPIRED'),
    ({'valid_until_utc':NOW+timedelta(minutes=10)}, 'LEASE_EXPIRED'),
    ({'trusted_attestor_key':b'short'}, 'LEASE_KEYS_INVALID'),
    ({'producer_signing_key':KEYS[0]}, 'LEASE_KEYS_NOT_SEPARATED'),
])
async def test_c13_invalid_key_lease_blocks_second_status_fetch(tmp_path, monkeypatch, mutation, code):
    c13, _, host, _, _, lease, feed, custody = _setup(tmp_path, monkeypatch)
    custody.acquire_lease.return_value = replace(lease, **mutation)
    with pytest.raises(PermissionError, match=code):
        await host.authorities_for_hour(slot_utc=SLOT)
    feed.latest_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_c13_lease_expired_during_last_status_fetch_blocks(tmp_path, monkeypatch):
    c13, _, host, _, _, _, feed, _ = _setup(tmp_path, monkeypatch)
    clock = iter((NOW, NOW, NOW+timedelta(minutes=2)))
    monkeypatch.setattr(c13, '_now_utc', lambda: next(clock))
    with pytest.raises(PermissionError, match='LEASE_EXPIRED'):
        await host.authorities_for_hour(slot_utc=SLOT)
    feed.latest_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_c13_failing_public_feed_or_custody_is_never_retried(tmp_path, monkeypatch):
    _, _, host, _, public, _, feed, custody = _setup(tmp_path, monkeypatch)
    feed.authorities_for_hour.side_effect = RuntimeError('EXTERNAL_AUTH_UNAVAILABLE')
    with pytest.raises(RuntimeError, match='EXTERNAL_AUTH_UNAVAILABLE'):
        await host.authorities_for_hour(slot_utc=SLOT)
    feed.authorities_for_hour.assert_awaited_once()
    custody.acquire_lease.assert_not_awaited()
    feed.authorities_for_hour.side_effect = None
    custody.acquire_lease.side_effect = RuntimeError('EXTERNAL_VAULT_UNAVAILABLE')
    with pytest.raises(RuntimeError, match='EXTERNAL_VAULT_UNAVAILABLE'):
        await host.authorities_for_hour(slot_utc=SLOT)
    custody.acquire_lease.assert_awaited_once()
    feed.latest_status.assert_not_awaited()


def test_c13_never_implements_vault_source_scheduler_or_legacy():
    import inspect
    import app.services.enterprise_l3_provisioned_host as c13
    source = inspect.getsource(c13)
    for forbidden in (
        'SessionLocal', 'from sqlalchemy', 'app.models', 'os.getenv', 'os.environ',
        'while True:', 'asyncio.sleep(', 'run_all(', 'app.agents.agent_scheduler',
        'httpx.', 'requests.', 'CREATE TABLE', 'INSERT INTO', 'UPDATE enterprise_',
    ):
        assert forbidden not in source


@pytest.mark.asyncio
async def test_c13_initial_revoked_prevents_key_acquisition(tmp_path, monkeypatch):
    _, _, host, _, public, _, feed, custody = _setup(tmp_path, monkeypatch)
    feed.authorities_for_hour.return_value = replace(
        public, status=public.status.model_copy(update={'disposition':'revoked'}))
    with pytest.raises(PermissionError, match='STATUS_NOT_ACTIVE'):
        await host.authorities_for_hour(slot_utc=SLOT)
    custody.acquire_lease.assert_not_awaited()
    feed.latest_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_c13_tampered_latest_status_type_fails_closed(tmp_path, monkeypatch):
    _, _, host, _, _, _, feed, custody = _setup(tmp_path, monkeypatch)
    feed.latest_status.return_value = {'disposition':'active'}
    with pytest.raises(PermissionError, match='STATUS_NOT_TYPED'):
        await host.authorities_for_hour(slot_utc=SLOT)
    custody.acquire_lease.assert_awaited_once()
