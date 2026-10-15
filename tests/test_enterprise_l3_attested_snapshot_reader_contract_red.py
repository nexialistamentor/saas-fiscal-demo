"""M006-C9 RED: independent key+digest enrollment on an immutable C8 snapshot."""
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
ISSUED = END + timedelta(minutes=5)
KEY = b"test-only-independent-attestor-key-012345678901234567"
C7_KEY = b"test-only-c7-signature-key-012345678901234567890"


def _source(tmp_path: Path):
    directory = tmp_path / "external_enterprise_hourly"
    directory.mkdir()
    identity = uuid4()
    file = directory / "enterprise_security_aggregates.sqlite3"
    with sqlite3.connect(file) as conn:
        conn.execute("CREATE TABLE enterprise_security_manifest (source_id TEXT, source_scope TEXT, source_name TEXT, schema_version TEXT, complete INTEGER)")
        conn.execute("CREATE TABLE enterprise_security_hourly (slot_utc TEXT, window_end_utc TEXT, collected_at_utc TEXT, complete INTEGER, max_distinct_accounts_per_ip INTEGER, max_requests_per_user INTEGER, requests_without_user_agent INTEGER)")
        conn.execute("INSERT INTO enterprise_security_manifest VALUES (?,?,?,?,?)", (str(identity), "enterprise_only", "enterprise_request_logs_isolated_v1", "1.0", 1))
        conn.execute("INSERT INTO enterprise_security_hourly VALUES (?,?,?,?,?,?,?)", ("2026-10-15T14:00:00Z", "2026-10-15T15:00:00Z", "2026-10-15T15:02:00Z", 1, 4, 101, 21))
    return directory, identity, file


def _attest(file, uid, *, key=KEY, **updates):
    from app.services.enterprise_l3_attested_snapshot_reader import (
        EnterpriseSecuritySnapshotAttestation, snapshot_attestation_signing_bytes,
    )
    attrs = dict(
        version="1.0",
        issuer_id="enterprise_security_source_authority_v1",
        source_id=uid,
        slot_utc=SLOT,
        attested_at_utc=ISSUED,
        snapshot_sha256=sha256(file.read_bytes()).hexdigest(),
        mac_sha256="0" * 64,
    )
    attrs.update(updates)
    unsigned = EnterpriseSecuritySnapshotAttestation(**attrs)
    return unsigned.model_copy(update={
        "mac_sha256": hmac.new(key, snapshot_attestation_signing_bytes(unsigned), sha256).hexdigest()
    })


def _reader(root, uid, attest, *, key=KEY, enabled=True):
    from app.services.enterprise_l3_attested_snapshot_reader import EnterpriseL3AttestedSnapshotReader
    return EnterpriseL3AttestedSnapshotReader(
        isolated_dir=root, expected_source_id=uid, attestation=attest,
        trusted_attestor_key=key, enable_security_shadow=enabled,
    )


@pytest.mark.asyncio
async def test_c9_attested_external_snapshot_reaches_c7_c6_c5(tmp_path, monkeypatch):
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    from app.services import enterprise_l3_signed_security_trigger as c6
    root, uid, file = _source(tmp_path)
    before = file.read_bytes()
    reader = _reader(root, uid, _attest(file, uid))
    report = await reader.read_hour(slot_utc=SLOT)
    assert report.source_scope == "enterprise_only"
    assert report.metrics.max_requests_per_user == 101
    signed = await produce_signed_security_window(
        reader=reader, slot_utc=SLOT, produced_at_utc=ISSUED,
        signing_key=C7_KEY, enable_security_shadow=True,
    )
    monkeypatch.setattr(c6, "_now_utc", lambda: ISSUED)
    ledger = tmp_path / "c9_ledger.sqlite3"
    first = await c6.run_signed_security_window(
        window=signed, trusted_key=C7_KEY, ledger_path=ledger, enable_security_shadow=True,
    )
    second = await c6.run_signed_security_window(
        window=signed, trusted_key=C7_KEY, ledger_path=ledger, enable_security_shadow=True,
    )
    assert first.result.execution_id == second.result.execution_id
    assert first.result.mode == "sombra"
    assert not first.result.actions_executed and not first.result.llm_used
    assert before == file.read_bytes()
    assert KEY not in file.read_bytes() and KEY not in ledger.read_bytes()
    assert C7_KEY not in ledger.read_bytes()


@pytest.mark.asyncio
async def test_c9_identical_data_wrong_identity_denied(tmp_path):
    root, uid, file = _source(tmp_path)
    with pytest.raises(PermissionError, match="SOURCE_NOT_ENROLLED"):
        _reader(root, uuid4(), _attest(file, uid))


@pytest.mark.asyncio
async def test_c9_wrong_key_and_attestation_tamper_denied(tmp_path):
    root, uid, file = _source(tmp_path)
    att = _attest(file, uid)
    with pytest.raises(PermissionError, match="SIGNATURE_INVALID"):
        _reader(root, uid, att, key=b"independent-key-other-012345678901234567890")
    changed = att.model_copy(update={"snapshot_sha256": "a" * 64})
    with pytest.raises(PermissionError, match="SIGNATURE_INVALID"):
        _reader(root, uid, changed)


@pytest.mark.asyncio
async def test_c9_mutated_file_rejected_after_valid_attestation(tmp_path):
    root, uid, file = _source(tmp_path)
    reader = _reader(root, uid, _attest(file, uid))
    with sqlite3.connect(file) as conn:
        conn.execute("UPDATE enterprise_security_hourly SET max_requests_per_user=999")
    with pytest.raises(PermissionError, match="SNAPSHOT_DIGEST_CONFLICT"):
        await reader.read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c9_replaced_file_same_manifest_rejected(tmp_path):
    root, uid, file = _source(tmp_path)
    reader = _reader(root, uid, _attest(file, uid))
    file.write_bytes(file.read_bytes() + b"changed")
    with pytest.raises(PermissionError, match="SNAPSHOT_DIGEST_CONFLICT"):
        await reader.read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c9_reject_live_journal_and_wal(tmp_path):
    root, uid, file = _source(tmp_path)
    reader = _reader(root, uid, _attest(file, uid))
    for ext in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(file) + ext)
        sidecar.write_bytes(b"unsafe")
        with pytest.raises(PermissionError, match="LIVE_SQLITE_NOT_ALLOWED"):
            await reader.read_hour(slot_utc=SLOT)
        sidecar.unlink()


@pytest.mark.asyncio
async def test_c9_digest_change_during_read_rejected(tmp_path, monkeypatch):
    root, uid, file = _source(tmp_path)
    reader = _reader(root, uid, _attest(file, uid))
    original = reader._reader.read_hour
    async def alter(*, slot_utc):
        result = await original(slot_utc=slot_utc)
        file.write_bytes(file.read_bytes() + b"changed")
        return result
    monkeypatch.setattr(reader._reader, "read_hour", alter)
    with pytest.raises(PermissionError, match="SNAPSHOT_CHANGED_DURING_READ"):
        await reader.read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c9_reject_wrong_requested_slot_before_read(tmp_path, monkeypatch):
    root, uid, file = _source(tmp_path)
    reader = _reader(root, uid, _attest(file, uid))
    forbidden = AsyncMock(side_effect=AssertionError("READ_FORBIDDEN"))
    monkeypatch.setattr(reader._reader, "read_hour", forbidden)
    with pytest.raises(PermissionError, match="SLOT_NOT_ATTESTED"):
        await reader.read_hour(slot_utc=SLOT + timedelta(hours=1))
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_c9_reject_attestation_before_data_collected(tmp_path):
    root, uid, file = _source(tmp_path)
    # Attestation at 15:00, but source collection occurs 15:02.
    reader = _reader(root, uid, _attest(file, uid, attested_at_utc=END))
    with pytest.raises(PermissionError, match="ATTESTATION_BEFORE_COLLECTION"):
        await reader.read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c9_fail_closed_by_default_and_bad_key_without_db(tmp_path):
    root, uid, file = _source(tmp_path)
    att = _attest(file, uid)
    for bad in (False, None, "true", 1):
        with pytest.raises(PermissionError, match="NOT_AUTHORIZED"):
            _reader(root, uid, att, enabled=bad)
    for bad in (None, "secret", b"short", bytearray(KEY)):
        with pytest.raises(PermissionError, match="TRUSTED_KEY_REQUIRED"):
            _reader(root, uid, att, key=bad)


@pytest.mark.parametrize("overrides", [
    {"slot_utc": SLOT + timedelta(minutes=1)},
    {"slot_utc": SLOT.replace(tzinfo=None)},
    {"attested_at_utc": END - timedelta(seconds=1)},
    {"attested_at_utc": END + timedelta(minutes=16)},
    {"issuer_id": "self_reported"},
    {"source_id": "untrusted"},
    {"snapshot_sha256": "123"},
    {"mac_sha256": "0"},
])
def test_c9_invalid_attestation_fields_rejected(overrides, tmp_path):
    from app.services.enterprise_l3_attested_snapshot_reader import EnterpriseSecuritySnapshotAttestation
    _, uid, file = _source(tmp_path)
    attrs = _attest(file, uid).model_dump(mode="python")
    attrs.update(overrides)
    with pytest.raises(Exception):
        EnterpriseSecuritySnapshotAttestation.model_validate(attrs)


def test_c9_no_source_credentials_writes_scheduler_or_legacy():
    import inspect
    import app.services.enterprise_l3_attested_snapshot_reader as module
    source = inspect.getsource(module)
    for forbidden in (
        "SessionLocal", "app.models", "from sqlalchemy", "run_all(",
        "os.getenv(", "os.environ", "asyncio.sleep(", "while True:",
        "app.agents.agent_scheduler", "INSERT INTO", "UPDATE enterprise_",
        "DELETE FROM", "CREATE TABLE", "httpx.", "requests.",
    ):
        assert forbidden not in source
