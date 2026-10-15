"""M006-C11 RED: signed short-lived source status and immutable failure triage."""
from __future__ import annotations

import hmac
import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

SLOT = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)
END = SLOT + timedelta(hours=1)
NOW = END + timedelta(minutes=5)
GOV = b"c11-governance-test-key-separate-1234567890"
ATT = b"c11-attestor-test-key-separate-123456789012"
PROD = b"c11-producer-test-key-separate-123456789012"
STATUS_KEY = b"c11-revocation-only-test-key-12345678901234"
EPOCH = 12


def _source(tmp_path):
    from app.services.enterprise_l3_attested_snapshot_reader import (
        EnterpriseSecuritySnapshotAttestation, snapshot_attestation_signing_bytes,
    )
    root = tmp_path / "external_enterprise"
    root.mkdir()
    uid = uuid4()
    file = root / "enterprise_security_aggregates.sqlite3"
    with sqlite3.connect(file) as conn:
        conn.execute("CREATE TABLE enterprise_security_manifest (source_id TEXT, source_scope TEXT, source_name TEXT, schema_version TEXT, complete INTEGER)")
        conn.execute("CREATE TABLE enterprise_security_hourly (slot_utc TEXT, window_end_utc TEXT, collected_at_utc TEXT, complete INTEGER, max_distinct_accounts_per_ip INTEGER, max_requests_per_user INTEGER, requests_without_user_agent INTEGER)")
        conn.execute("INSERT INTO enterprise_security_manifest VALUES (?,?,?,?,?)", (str(uid), "enterprise_only", "enterprise_request_logs_isolated_v1", "1.0", 1))
        conn.execute("INSERT INTO enterprise_security_hourly VALUES (?,?,?,?,?,?,?)", ("2026-10-15T14:00:00Z", "2026-10-15T15:00:00Z", "2026-10-15T15:02:00Z", 1, 4, 101, 21))
    unsigned = EnterpriseSecuritySnapshotAttestation(
        version="1.0", issuer_id="enterprise_security_source_authority_v1",
        source_id=uid, slot_utc=SLOT, attested_at_utc=NOW,
        snapshot_sha256=sha256(file.read_bytes()).hexdigest(), mac_sha256="0"*64,
    )
    attestation = unsigned.model_copy(update={
        "mac_sha256": hmac.new(ATT, snapshot_attestation_signing_bytes(unsigned), sha256).hexdigest(),
    })
    return root, uid, attestation


def _grant(root, uid):
    from app.services.enterprise_l3_source_authorization_gate import (
        EnterpriseSecuritySourceGrant, enterprise_source_grant_signing_bytes,
    )
    unsigned = EnterpriseSecuritySourceGrant(
        version="1.0", issuer_id="enterprise_security_governance_v1",
        source_id=uid, source_scope="enterprise_only", execution_mode="sombra",
        rotation_epoch=EPOCH, valid_from_utc=END - timedelta(minutes=1),
        valid_until_utc=END + timedelta(hours=1), snapshot_directory=str(root),
        attestor_key_sha256=sha256(ATT).hexdigest(),
        producer_key_sha256=sha256(PROD).hexdigest(), mac_sha256="0"*64,
    )
    return unsigned.model_copy(update={
        "mac_sha256": hmac.new(GOV, enterprise_source_grant_signing_bytes(unsigned), sha256).hexdigest(),
    })


def _status(grant, *, disposition="active", source_id=None, epoch=EPOCH,
            issued=NOW-timedelta(seconds=30), until=NOW+timedelta(minutes=1), key=STATUS_KEY):
    from app.services.enterprise_l3_revocation_recovery import (
        EnterpriseSecurityAuthorityStatus, enterprise_grant_digest,
        security_authority_status_signing_bytes,
    )
    unsigned = EnterpriseSecurityAuthorityStatus(
        version="1.0", issuer_id="enterprise_security_revocation_authority_v1",
        source_id=source_id or grant.source_id, rotation_epoch=epoch,
        grant_sha256=enterprise_grant_digest(grant), disposition=disposition,
        issued_at_utc=issued, valid_until_utc=until, mac_sha256="0"*64,
    )
    return unsigned.model_copy(update={
        "mac_sha256": hmac.new(key, security_authority_status_signing_bytes(unsigned), sha256).hexdigest(),
    })


def _clock(monkeypatch):
    import app.services.enterprise_l3_revocation_recovery as c11
    import app.services.enterprise_l3_source_authorization_gate as c10
    import app.services.enterprise_l3_signed_security_trigger as c6
    monkeypatch.setattr(c11, "_now_utc", lambda: NOW)
    monkeypatch.setattr(c10, "_now_utc", lambda: NOW)
    monkeypatch.setattr(c6, "_now_utc", lambda: NOW)


def _call(root, att, approved_grant, state, tmp_path, **kwargs):
    from app.services.enterprise_l3_revocation_recovery import run_revocation_gated_security_hour
    args = dict(
        status=state, trusted_status_key=STATUS_KEY, grant=approved_grant, attestation=att,
        isolated_dir=root, slot_utc=SLOT, ledger_path=tmp_path / "delivery.sqlite3",
        trusted_governance_key=GOV, trusted_attestor_key=ATT,
        producer_signing_key=PROD, expected_rotation_epoch=EPOCH,
        enable_security_shadow=True,
    )
    args.update(kwargs)
    return run_revocation_gated_security_hour(**args)


@pytest.mark.asyncio
async def test_c11_active_runs_c10_once_and_replays_with_same_receipt(tmp_path, monkeypatch):
    import app.services.enterprise_l3_revocation_recovery as c11
    import app.services.enterprise_l3_shadow_scheduler as c5
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    status = _status(grant)
    first = await _call(root, att, grant, status, tmp_path)
    forbidden = AsyncMock(side_effect=AssertionError("REPLAY_DISPATCH_FORBIDDEN"))
    monkeypatch.setattr(c5, "route_enterprise_l3_event", forbidden)
    second = await _call(root, att, grant, status, tmp_path)
    assert first.mission_id == second.mission_id
    assert first.result.execution_id == second.result.execution_id
    assert first.result.status == "sucesso" and first.result.mode == "sombra"
    assert first.result.actions_executed == [] and first.result.llm_used is False
    assert first.result.requires_human_review is True
    forbidden.assert_not_awaited()
    saved = (tmp_path / "delivery.sqlite3").read_bytes()
    for secret in (STATUS_KEY, GOV, ATT, PROD):
        assert secret not in saved


@pytest.mark.asyncio
@pytest.mark.parametrize("disposition,code", [
    ("revoked", "SOURCE_REVOKED"), ("suspended", "SOURCE_SUSPENDED"),
])
async def test_c11_revocation_and_suspension_prevent_any_c10_call(tmp_path, monkeypatch, disposition, code):
    import app.services.enterprise_l3_revocation_recovery as c11
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    forbidden = AsyncMock(side_effect=AssertionError("C10_MUST_NOT_EXECUTE"))
    monkeypatch.setattr(c11, "run_authorized_security_hour", forbidden)
    with pytest.raises(PermissionError, match=code):
        await _call(root, att, grant, _status(grant, disposition=disposition), tmp_path)
    forbidden.assert_not_awaited()
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c11_active_replay_blocked_after_revocation(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    first = await _call(root, att, grant, _status(grant), tmp_path)
    with pytest.raises(PermissionError, match="SOURCE_REVOKED"):
        await _call(root, att, grant, _status(grant, disposition="revoked"), tmp_path)
    from app.services.enterprise_l3_revocation_recovery import inspect_security_delivery_state
    observation = inspect_security_delivery_state(ledger_path=tmp_path / "delivery.sqlite3", event_id=first.event_id)
    assert observation.state == "completed" and not observation.automatic_retry_allowed


@pytest.mark.asyncio
async def test_c11_invalid_or_reused_secret_rejected_before_c10(tmp_path, monkeypatch):
    import app.services.enterprise_l3_revocation_recovery as c11
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    state = _status(grant)
    forbidden = AsyncMock(side_effect=AssertionError("C10_MUST_NOT_EXECUTE"))
    monkeypatch.setattr(c11, "run_authorized_security_hour", forbidden)
    for kwargs, code in (
        ({"trusted_status_key": b"short"}, "KEYS_REQUIRED"),
        ({"trusted_status_key": GOV}, "KEYS_NOT_SEPARATED"),
        ({"trusted_status_key": b"c11-other-long-revocation-key-1234567890"}, "STATUS_SIGNATURE_INVALID"),
    ):
        with pytest.raises(PermissionError, match=code):
            await _call(root, att, grant, state, tmp_path, **kwargs)
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_c11_status_tampering_cannot_enable_revoked(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    fake = _status(grant, disposition="revoked").model_copy(update={"disposition":"active"})
    with pytest.raises(PermissionError, match="STATUS_SIGNATURE_INVALID"):
        await _call(root, att, grant, fake, tmp_path)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c11_status_source_epoch_and_grant_hash_pinned(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    cases = (
        _status(grant, source_id=uuid4()),
        _status(grant, epoch=EPOCH+1),
        _status(grant).model_copy(update={"grant_sha256":"0"*64}),
    )
    for state in cases:
        with pytest.raises(PermissionError, match="STATUS_SCOPE_MISMATCH"):
            await _call(root, att, grant, state, tmp_path)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c11_old_or_future_lease_fails_closed(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    for state in (
        _status(grant, issued=NOW-timedelta(minutes=2), until=NOW),
        _status(grant, issued=NOW+timedelta(seconds=1), until=NOW+timedelta(minutes=2)),
    ):
        with pytest.raises(PermissionError, match="STATUS_NOT_CURRENT"):
            await _call(root, att, grant, state, tmp_path)


@pytest.mark.asyncio
async def test_c11_optin_fail_closed_without_status_or_ledger(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    for flag in (False, None, 1, "true"):
        with pytest.raises(PermissionError, match="C11_NOT_AUTHORIZED"):
            await _call(root, att, grant, _status(grant), tmp_path, enable_security_shadow=flag)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c11_untyped_grant_fails_closed_before_c10(tmp_path, monkeypatch):
    import app.services.enterprise_l3_revocation_recovery as c11
    _clock(monkeypatch)
    root, uid, att = _source(tmp_path)
    grant = _grant(root, uid)
    forbidden = AsyncMock(side_effect=AssertionError("UNAUTHORIZED_EXECUTION"))
    monkeypatch.setattr(c11, "run_authorized_security_hour", forbidden)
    with pytest.raises(PermissionError, match="GRANT_NOT_TYPED"):
        await _call(root, att, grant, _status(grant), tmp_path, grant={"source_id":str(uid)})
    forbidden.assert_not_awaited()


def test_c11_invalid_status_contract_rejected(tmp_path):
    from app.services.enterprise_l3_revocation_recovery import EnterpriseSecurityAuthorityStatus
    root, uid, _ = _source(tmp_path)
    state = _status(_grant(root,uid))
    for delta in (
        {"issued_at_utc": NOW.replace(tzinfo=None)},
        {"valid_until_utc": NOW + timedelta(minutes=6)},
        {"valid_until_utc": NOW - timedelta(minutes=1)},
        {"disposition":"auto_retry"},
        {"issuer_id":"self_reported"},
        {"extra":"raw_data"},
    ):
        with pytest.raises(Exception):
            EnterpriseSecurityAuthorityStatus.model_validate({**state.model_dump(mode="python"), **delta})


def test_c11_recovery_read_only_states_without_payload(tmp_path):
    from app.services.enterprise_l3_revocation_recovery import inspect_security_delivery_state
    ledger = tmp_path / "local_delivery.sqlite3"
    keys = {state:uuid4() for state in ("claimed", "failed", "completed")}
    with sqlite3.connect(ledger) as db:
        db.execute("CREATE TABLE enterprise_l3_event_delivery (event_id TEXT PRIMARY KEY NOT NULL, event_hash TEXT NOT NULL, state TEXT NOT NULL, receipt_json TEXT)")
        for state, uid in keys.items():
            db.execute("INSERT INTO enterprise_l3_event_delivery VALUES (?,?,?,?)", (str(uid), "a"*64, state, '"no raw data"' if state == 'completed' else None))
    before = ledger.read_bytes()
    for state, uid in keys.items():
        observed = inspect_security_delivery_state(ledger_path=ledger, event_id=uid)
        assert observed.state == state
        assert observed.manual_review_required == (state in ("claimed", "failed"))
        assert observed.automatic_retry_allowed is False
        assert "receipt_json" not in observed.model_dump_json()
    unseen = inspect_security_delivery_state(ledger_path=ledger, event_id=uuid4())
    assert unseen.state == "not_seen" and unseen.automatic_retry_allowed is False
    assert ledger.read_bytes() == before


def test_c11_recovery_unknown_or_missing_ledger_blocks(tmp_path):
    from app.services.enterprise_l3_revocation_recovery import inspect_security_delivery_state
    missing = tmp_path / "not_here.sqlite3"
    with pytest.raises(PermissionError, match="LEDGER_UNAVAILABLE"):
        inspect_security_delivery_state(ledger_path=missing, event_id=uuid4())
    assert not missing.exists()
    with sqlite3.connect(tmp_path / "unrelated.sqlite3") as db:
        db.execute("CREATE TABLE other (raw TEXT)")
    with pytest.raises(PermissionError, match="SCHEMA_UNKNOWN"):
        inspect_security_delivery_state(ledger_path=tmp_path / "unrelated.sqlite3", event_id=uuid4())
    with pytest.raises(ValueError, match="EVENT_ID_INVALID"):
        inspect_security_delivery_state(ledger_path=missing, event_id="not uuid")


def test_c11_recovery_never_allows_state_reset_or_retry(tmp_path):
    from app.services.enterprise_l3_revocation_recovery import EnterpriseSecurityRecoveryObservation
    with pytest.raises(Exception):
        EnterpriseSecurityRecoveryObservation(event_id=uuid4(), state="failed", manual_review_required=True, automatic_retry_allowed=True)
    with pytest.raises(Exception):
        EnterpriseSecurityRecoveryObservation(event_id=uuid4(), state="rearmed", manual_review_required=False, automatic_retry_allowed=False)


def test_c11_no_automatic_job_credentials_ledger_writes_or_legacy():
    import inspect
    import app.services.enterprise_l3_revocation_recovery as module
    s = inspect.getsource(module)
    for forbidden in (
        "SessionLocal", "app.models", "from sqlalchemy", "os.getenv(", "os.environ",
        "INSERT INTO", "UPDATE enterprise_", "DELETE FROM", "CREATE TABLE",
        "app.agents.agent_scheduler", "run_all(", "asyncio.sleep(", "while True:",
    ):
        assert forbidden not in s
