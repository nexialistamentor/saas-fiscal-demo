"""M006-C10 RED: authentic short-lived governance and distinct key custody."""
from __future__ import annotations

import asyncio
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
GOV = b"c10-governance-only-test-key-1234567890123456"
ATT = b"c10-attestor-only-test-key-123456789012345678"
PROD = b"c10-producer-only-test-key-1234567890123456"
EPOCH = 7


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
    att = unsigned.model_copy(update={
        "mac_sha256": hmac.new(ATT, snapshot_attestation_signing_bytes(unsigned), sha256).hexdigest(),
    })
    return root, uid, att, file


def _grant(root, uid, **updates):
    from app.services.enterprise_l3_source_authorization_gate import (
        EnterpriseSecuritySourceGrant, enterprise_source_grant_signing_bytes,
    )
    attrs = dict(
        version="1.0", issuer_id="enterprise_security_governance_v1",
        source_id=uid, source_scope="enterprise_only", execution_mode="sombra",
        rotation_epoch=EPOCH, valid_from_utc=END - timedelta(minutes=1),
        valid_until_utc=END + timedelta(hours=1), snapshot_directory=str(root),
        attestor_key_sha256=sha256(ATT).hexdigest(),
        producer_key_sha256=sha256(PROD).hexdigest(), mac_sha256="0"*64,
    )
    attrs.update(updates)
    unsigned = EnterpriseSecuritySourceGrant(**attrs)
    return unsigned.model_copy(update={
        "mac_sha256": hmac.new(GOV, enterprise_source_grant_signing_bytes(unsigned), sha256).hexdigest(),
    })


def _call(root, grant, att, tmp_path, **updates):
    from app.services.enterprise_l3_source_authorization_gate import run_authorized_security_hour
    values = dict(
        grant=grant, attestation=att, isolated_dir=root, slot_utc=SLOT,
        ledger_path=tmp_path / "delivery.sqlite3", trusted_governance_key=GOV,
        trusted_attestor_key=ATT, producer_signing_key=PROD,
        expected_rotation_epoch=EPOCH, enable_security_shadow=True,
    )
    values.update(updates)
    return run_authorized_security_hour(**values)


def _clock(monkeypatch):
    import app.services.enterprise_l3_source_authorization_gate as c10
    import app.services.enterprise_l3_signed_security_trigger as c6
    monkeypatch.setattr(c10, "_now_utc", lambda: NOW)
    monkeypatch.setattr(c6, "_now_utc", lambda: NOW)


@pytest.mark.asyncio
async def test_c10_authorized_chain_reuses_c1_once_with_distinct_keys(tmp_path, monkeypatch):
    import app.services.enterprise_l3_source_authorization_gate as c10
    import app.services.enterprise_l3_shadow_scheduler as c5
    from app.agents.security_audit_agent import security_audit_agent
    _clock(monkeypatch)
    root, uid, att, db = _source(tmp_path)
    grant = _grant(root, uid)
    baseline = db.read_bytes()
    legacy = AsyncMock(side_effect=AssertionError("LEGACY_NOT_ALLOWED"))
    monkeypatch.setattr(security_audit_agent, "run", legacy)
    first = await _call(root, grant, att, tmp_path)
    forbidden = AsyncMock(side_effect=AssertionError("DUPLICATE_AGENT_EXECUTION"))
    monkeypatch.setattr(c5, "route_enterprise_l3_event", forbidden)
    second = await _call(root, grant, att, tmp_path)
    assert first.mission_id == second.mission_id
    assert first.result.execution_id == second.result.execution_id
    assert first.result.agent_id == "security_audit_agent"
    assert first.result.payload["total_alerts"] == 3
    assert first.result.mode == "sombra" and first.result.requires_human_review
    assert first.result.actions_executed == [] and first.result.actions_proposed == []
    assert first.result.llm_used is False and first.result.provider is None
    assert db.read_bytes() == baseline
    ledger = (tmp_path / "delivery.sqlite3").read_bytes()
    assert not any(k in ledger for k in (GOV,ATT,PROD))
    legacy.assert_not_awaited()
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_c10_default_denied_before_source_or_ledger(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    grant = _grant(root, uid)
    for v in (False, None, 1, "true"):
        with pytest.raises(PermissionError, match="C10_NOT_AUTHORIZED"):
            await _call(root, grant, att, tmp_path, enable_security_shadow=v)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("keyname,key", [
    ("trusted_governance_key", b"short"),
    ("trusted_attestor_key", None),
    ("producer_signing_key", "plaintext"),
    ("producer_signing_key", bytearray(PROD)),
])
async def test_c10_bad_key_material_denied(tmp_path, monkeypatch, keyname, key):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    with pytest.raises(PermissionError, match="TRUSTED_KEYS_REQUIRED"):
        await _call(root, _grant(root, uid), att, tmp_path, **{keyname:key})
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c10_governance_signature_is_independent_of_attestor(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    grant = _grant(root, uid)
    altered = grant.model_copy(update={"snapshot_directory": str(tmp_path / "elsewhere")})
    with pytest.raises(PermissionError, match="GOVERNANCE_SIGNATURE_INVALID"):
        await _call(root, altered, att, tmp_path)
    with pytest.raises(PermissionError, match="GOVERNANCE_SIGNATURE_INVALID"):
        await _call(root, grant, att, tmp_path, trusted_governance_key=b"another-governance-key-0123456789012345")
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["trusted_attestor_key", "producer_signing_key"])
async def test_c10_revoked_or_mismatched_key_pins_denied(tmp_path, monkeypatch, role):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    with pytest.raises(PermissionError, match="KEY_PIN_MISMATCH"):
        await _call(root, _grant(root, uid), att, tmp_path,
                    **{role: b"new-key-of-same-role-012345678901234567890"})


@pytest.mark.asyncio
async def test_c10_key_roles_must_be_distinct(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    with pytest.raises(PermissionError, match="KEYS_NOT_SEPARATED"):
        await _call(root, _grant(root, uid), att, tmp_path, producer_signing_key=ATT)
    with pytest.raises(PermissionError, match="KEYS_NOT_SEPARATED"):
        await _call(root, _grant(root, uid), att, tmp_path, trusted_governance_key=ATT)


@pytest.mark.asyncio
async def test_c10_rotation_epoch_required_and_exact(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    for epoch, code in ((0, "ROTATION_EPOCH_REQUIRED"), (True,"ROTATION_EPOCH_REQUIRED"), (6,"ROTATION_EPOCH_MISMATCH"), (8,"ROTATION_EPOCH_MISMATCH")):
        with pytest.raises(PermissionError, match=code):
            await _call(root, _grant(root, uid), att, tmp_path, expected_rotation_epoch=epoch)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c10_expired_grant_denied_and_no_source_read(tmp_path, monkeypatch):
    import app.services.enterprise_l3_source_authorization_gate as c10
    root, uid, att, _ = _source(tmp_path)
    grant = _grant(root, uid)
    monkeypatch.setattr(c10, "_now_utc", lambda: NOW + timedelta(hours=2))
    with pytest.raises(PermissionError, match="GRANT_NOT_CURRENT"):
        await _call(root, grant, att, tmp_path)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c10_source_id_and_slot_must_match(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    other = _grant(root, uuid4())
    with pytest.raises(PermissionError, match="SOURCE_OR_SLOT_MISMATCH"):
        await _call(root, other, att, tmp_path)
    with pytest.raises(PermissionError, match="SOURCE_OR_SLOT_MISMATCH"):
        await _call(root, _grant(root, uid), att, tmp_path, slot_utc=SLOT + timedelta(hours=1))
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.asyncio
async def test_c10_directory_pinned_to_governance_grant(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(PermissionError, match="DIRECTORY_NOT_AUTHORIZED"):
        await _call(root, _grant(root, uid), att, tmp_path, isolated_dir=other)


@pytest.mark.asyncio
async def test_c10_attestation_wrong_key_is_denied_before_ledger(tmp_path, monkeypatch):
    _clock(monkeypatch)
    root, uid, att, _ = _source(tmp_path)
    fake_att = att.model_copy(update={"snapshot_sha256": "0"*64})
    with pytest.raises(PermissionError, match="C9_ATTESTATION_SIGNATURE_INVALID"):
        await _call(root, _grant(root, uid), fake_att, tmp_path)
    assert not (tmp_path / "delivery.sqlite3").exists()


@pytest.mark.parametrize("attrs", [
    {"source_scope":"mixed"}, {"execution_mode":"ativo"},
    {"rotation_epoch":0}, {"valid_until_utc": END-timedelta(hours=2)},
    {"valid_until_utc": END+timedelta(days=2)},
    {"snapshot_directory":"relative"},
    {"attestor_key_sha256":"0"*64,"producer_key_sha256":"0"*64},
])
def test_c10_invalid_grant_rejected(tmp_path, attrs):
    from app.services.enterprise_l3_source_authorization_gate import EnterpriseSecuritySourceGrant
    root, uid, _, _ = _source(tmp_path)
    data = _grant(root, uid).model_dump(mode="python")
    data.update(attrs)
    with pytest.raises(Exception):
        EnterpriseSecuritySourceGrant.model_validate(data)


def test_c10_no_key_storage_source_writer_autostart_or_legacy():
    import inspect
    import app.services.enterprise_l3_source_authorization_gate as c10
    s = inspect.getsource(c10)
    for forbidden in ("SessionLocal", "app.models", "from sqlalchemy", "os.getenv(", "os.environ",
                      "CREATE TABLE", "INSERT INTO", "UPDATE enterprise_", "asyncio.sleep(",
                      "while True:", "app.agents.agent_scheduler", "run_all(", "httpx."):
        assert forbidden not in s
