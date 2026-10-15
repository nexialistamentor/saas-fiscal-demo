"""M006-C8 RED: enrolled, external, read-only hourly aggregate source."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

SLOT = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)
END = SLOT + timedelta(hours=1)
ISSUED = END + timedelta(minutes=5)
KEY = b"test-only-key-for-security-chain-end-to-end-5678"


def _source(tmp_path: Path, *, source_id=None, row=True) -> tuple[Path, object]:
    root = tmp_path / "separate_enterprise_telemetry"
    root.mkdir()
    identity = source_id or uuid4()
    with sqlite3.connect(root / "enterprise_security_aggregates.sqlite3") as conn:
        conn.execute("CREATE TABLE enterprise_security_manifest (source_id TEXT, source_scope TEXT, source_name TEXT, schema_version TEXT, complete INTEGER)")
        conn.execute("CREATE TABLE enterprise_security_hourly (slot_utc TEXT, window_end_utc TEXT, collected_at_utc TEXT, complete INTEGER, max_distinct_accounts_per_ip INTEGER, max_requests_per_user INTEGER, requests_without_user_agent INTEGER)")
        conn.execute("INSERT INTO enterprise_security_manifest VALUES (?,?,?,?,?)", (str(identity), "enterprise_only", "enterprise_request_logs_isolated_v1", "1.0", 1))
        if row:
            conn.execute("INSERT INTO enterprise_security_hourly VALUES (?,?,?,?,?,?,?)", ("2026-10-15T14:00:00Z", "2026-10-15T15:00:00Z", "2026-10-15T15:02:00Z", 1, 4, 101, 21))
    return root, identity


def _mutate(root, sql, params=()):
    with sqlite3.connect(root / "enterprise_security_aggregates.sqlite3") as conn:
        conn.execute(sql, params)


def _reader(root, uid):
    from app.services.enterprise_l3_isolated_sqlite_reader import EnterpriseL3IsolatedSqliteReader
    return EnterpriseL3IsolatedSqliteReader(isolated_dir=root, expected_source_id=uid)


@pytest.mark.asyncio
async def test_c8_reader_produces_only_closed_aggregates_without_mutation(tmp_path):
    root, uid = _source(tmp_path)
    db = root / "enterprise_security_aggregates.sqlite3"
    before = db.read_bytes()
    report = await _reader(root, uid).read_hour(slot_utc=SLOT)
    assert db.read_bytes() == before
    assert report.source_scope == "enterprise_only"
    assert report.window_start_utc == SLOT
    assert report.window_end_utc == END
    assert report.metrics.max_distinct_accounts_per_ip == 4
    assert report.metrics.max_requests_per_user == 101
    assert report.metrics.requests_without_user_agent == 21
    serialized = report.model_dump_json()
    assert "user_id" not in serialized and "ip_address" not in serialized


@pytest.mark.asyncio
async def test_c8_full_C8_C7_C6_C5_chain_and_replay(tmp_path, monkeypatch):
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    from app.services import enterprise_l3_signed_security_trigger as c6
    root, uid = _source(tmp_path)
    reader = _reader(root, uid)
    window = await produce_signed_security_window(
        reader=reader, slot_utc=SLOT, produced_at_utc=ISSUED,
        signing_key=KEY, enable_security_shadow=True,
    )
    monkeypatch.setattr(c6, "_now_utc", lambda: ISSUED)
    ledger = tmp_path / "delivery.sqlite3"
    first = await c6.run_signed_security_window(window=window, trusted_key=KEY, ledger_path=ledger, enable_security_shadow=True)
    again = await c6.run_signed_security_window(window=window, trusted_key=KEY, ledger_path=ledger, enable_security_shadow=True)
    assert first.event_id == again.event_id
    assert first.result.execution_id == again.result.execution_id
    assert first.result.mode == "sombra"
    assert first.result.actions_executed == []
    assert first.result.llm_used is False
    assert KEY not in ledger.read_bytes()


@pytest.mark.asyncio
async def test_c8_unenrolled_source_identity_denied(tmp_path):
    root, uid = _source(tmp_path)
    with pytest.raises(PermissionError, match="NOT_ENROLLED"):
        await _reader(root, uuid4()).read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("source_scope", "mixed"), ("source_name", "untrusted"),
    ("schema_version", "2.0"), ("complete", 0),
])
async def test_c8_manifest_metadata_mismatch_denied(tmp_path, field, value):
    root, uid = _source(tmp_path)
    _mutate(root, f"UPDATE enterprise_security_manifest SET {field}=?", (value,))
    with pytest.raises(PermissionError, match="NOT_ENROLLED"):
        await _reader(root, uid).read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    "CREATE TABLE request_logs (ip TEXT, user_id INTEGER)",
    "CREATE VIEW raw_events AS SELECT * FROM enterprise_security_hourly",
    "ALTER TABLE enterprise_security_hourly ADD COLUMN ip TEXT",
    "CREATE TABLE unrelated (id INTEGER)",
])
async def test_c8_extra_raw_or_cross_source_schema_denied(tmp_path, sql):
    root, uid = _source(tmp_path)
    _mutate(root, sql)
    with pytest.raises(PermissionError, match="SCHEMA_UNSAFE|COLUMNS_UNSAFE"):
        await _reader(root, uid).read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c8_missing_or_duplicate_hours_denied(tmp_path):
    root, uid = _source(tmp_path, row=False)
    with pytest.raises(PermissionError, match="WINDOW_MISSING_OR_DUPLICATED"):
        await _reader(root, uid).read_hour(slot_utc=SLOT)
    _mutate(root, "INSERT INTO enterprise_security_hourly VALUES (?,?,?,?,?,?,?)", ("2026-10-15T14:00:00Z", "2026-10-15T15:00:00Z", "2026-10-15T15:02:00Z", 1, 4, 101, 21))
    _mutate(root, "INSERT INTO enterprise_security_hourly VALUES (?,?,?,?,?,?,?)", ("2026-10-15T14:00:00Z", "2026-10-15T15:00:00Z", "2026-10-15T15:02:00Z", 1, 4, 101, 21))
    with pytest.raises(PermissionError, match="WINDOW_MISSING_OR_DUPLICATED"):
        await _reader(root, uid).read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("complete", 0), ("max_requests_per_user", -1),
    ("max_distinct_accounts_per_ip", "fake"),
    ("window_end_utc", "2026-10-15T16:00:00Z"),
    ("collected_at_utc", "2026-10-15T15:20:00Z"),
])
async def test_c8_corrupt_window_denied(tmp_path, field, value):
    root, uid = _source(tmp_path)
    _mutate(root, f"UPDATE enterprise_security_hourly SET {field}=?", (value,))
    with pytest.raises(PermissionError, match="NOT_COMPLETE|METRICS_INVALID|AGGREGATE_INVALID"):
        await _reader(root, uid).read_hour(slot_utc=SLOT)


@pytest.mark.asyncio
async def test_c8_invalid_hour_rejected_before_read(tmp_path):
    root, uid = _source(tmp_path)
    reader = _reader(root, uid)
    for bad in (SLOT.replace(tzinfo=None), SLOT+timedelta(minutes=1), SLOT.astimezone(timezone(timedelta(hours=-3))), None):
        with pytest.raises(ValueError, match="SLOT_NOT_UTC_HOUR"):
            await reader.read_hour(slot_utc=bad)


def test_c8_requires_enrolled_external_regular_file(tmp_path):
    from app.services.enterprise_l3_isolated_sqlite_reader import EnterpriseL3IsolatedSqliteReader
    root, uid = _source(tmp_path)
    with pytest.raises(ValueError, match="ENROLLED_SOURCE_REQUIRED"):
        EnterpriseL3IsolatedSqliteReader(isolated_dir=root, expected_source_id="source")
    with pytest.raises(ValueError, match="ISOLATED_DIR_REQUIRED"):
        EnterpriseL3IsolatedSqliteReader(isolated_dir=Path("relative"), expected_source_id=uid)
    other = tmp_path / "empty"
    other.mkdir()
    with pytest.raises(PermissionError, match="SOURCE_FILE_REQUIRED"):
        EnterpriseL3IsolatedSqliteReader(isolated_dir=other, expected_source_id=uid)
    otherfile = tmp_path / "other.sqlite3"
    otherfile.write_bytes(b"wrong")
    link = other / "enterprise_security_aggregates.sqlite3"
    try:
        link.symlink_to(otherfile)
    except OSError as exc:
        # Restricted Windows accounts cannot create symbolic links (1314).
        # Test the exact fail-closed predicate without granting privileges.
        if getattr(exc, "winerror", None) != 1314:
            raise
        link.write_bytes(b"wrong")
        from unittest.mock import patch
        with patch.object(
            Path, "is_symlink", autospec=True,
            side_effect=lambda candidate: candidate == link,
        ) as checked:
            with pytest.raises(PermissionError, match="SOURCE_FILE_REQUIRED"):
                EnterpriseL3IsolatedSqliteReader(isolated_dir=other, expected_source_id=uid)
            checked.assert_called_once_with(link)
    else:
        with pytest.raises(PermissionError, match="SOURCE_FILE_REQUIRED"):
            EnterpriseL3IsolatedSqliteReader(isolated_dir=other, expected_source_id=uid)


def test_c8_has_no_source_writes_or_legacy_imports():
    import inspect
    import app.services.enterprise_l3_isolated_sqlite_reader as m
    source = inspect.getsource(m)
    for forbidden in ("conn.execute(\"CREATE", "conn.execute(\"INSERT", "conn.execute(\"UPDATE", "conn.execute(\"DELETE", "SessionLocal", "app.models", "from sqlalchemy", "app.agents.agent_scheduler", "run_all(", "os.getenv", "while True:"):
        assert forbidden not in source
    assert "?mode=ro" in source
    assert "PRAGMA query_only=ON" in source
