"""M006-C7: source-isolation port and ephemeral HMAC signing; no source access."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.agents.contracts.security_audit import SecurityAuditContext

SLOT = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)
END = SLOT + timedelta(hours=1)
ISSUED = END + timedelta(minutes=5)
KEY = b"local-test-only-security-key-not-for-production-12345"


def _metrics():
    return SecurityAuditContext(
        source_kind="enterprise_aggregated_request_logs",
        window_minutes=60,
        max_distinct_accounts_per_ip=4,
        max_requests_per_user=101,
        requests_without_user_agent=21,
    )


def _report(**updates):
    from app.services.enterprise_l3_security_aggregate_producer import EnterpriseSecurityAggregateReport
    data = dict(
        source_name="enterprise_request_logs_isolated_v1",
        source_scope="enterprise_only",
        complete=True,
        window_start_utc=SLOT,
        window_end_utc=END,
        collected_at_utc=END + timedelta(minutes=2),
        metrics=_metrics(),
    )
    data.update(updates)
    return EnterpriseSecurityAggregateReport(**data)


def _reader(report=None):
    from app.services.enterprise_l3_security_aggregate_producer import EnterpriseSecurityAggregateReader

    class SyntheticReader(EnterpriseSecurityAggregateReader):
        def __init__(self, result):
            self.read_hour = AsyncMock(return_value=result)

        async def read_hour(self, *, slot_utc):
            raise AssertionError("unexpected invocation")

    return SyntheticReader(report if report is not None else _report())


@pytest.mark.asyncio
async def test_c7_signer_envelope_passes_c6_and_replays_c5(tmp_path, monkeypatch):
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    from app.services import enterprise_l3_signed_security_trigger as c6
    from app.agents.security_audit_agent import security_audit_agent

    legacy = AsyncMock(side_effect=AssertionError("LEGACY_AGENT_NOT_AUTHORIZED"))
    monkeypatch.setattr(security_audit_agent, "run", legacy)
    monkeypatch.setattr(c6, "_now_utc", lambda: ISSUED)
    reader = _reader()
    window = await produce_signed_security_window(
        reader=reader, slot_utc=SLOT, produced_at_utc=ISSUED,
        signing_key=KEY, enable_security_shadow=True,
    )
    reader.read_hour.assert_awaited_once_with(slot_utc=SLOT)
    ledger = tmp_path / "shared.sqlite3"
    first = await c6.run_signed_security_window(
        window=window, trusted_key=KEY, ledger_path=ledger,
        enable_security_shadow=True,
    )
    replay = await c6.run_signed_security_window(
        window=window, trusted_key=KEY, ledger_path=ledger,
        enable_security_shadow=True,
    )
    assert first.result.execution_id == replay.result.execution_id
    assert first.result.payload["total_alerts"] == 3
    assert first.result.mode == "sombra"
    assert first.result.actions_proposed == first.result.actions_executed == []
    assert first.result.llm_used is False
    legacy.assert_not_awaited()
    assert KEY not in ledger.read_bytes()
    assert b"user_id" not in ledger.read_bytes()
    assert b"192.168." not in window.model_dump_json().encode()
    assert KEY not in window.model_dump_json().encode()


@pytest.mark.asyncio
async def test_c7_optin_and_key_gates_precede_reader_invocation():
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    reader = _reader()
    for allowed in (False, None, 1, "true"):
        with pytest.raises(PermissionError, match="PRODUCER_NOT_AUTHORIZED"):
            await produce_signed_security_window(
                reader=reader, slot_utc=SLOT, produced_at_utc=ISSUED,
                signing_key=KEY, enable_security_shadow=allowed,
            )
    for key in (None, "secret", b"short", bytearray(KEY)):
        with pytest.raises(PermissionError, match="SIGNING_KEY_REQUIRED"):
            await produce_signed_security_window(
                reader=reader, slot_utc=SLOT, produced_at_utc=ISSUED,
                signing_key=key, enable_security_shadow=True,
            )
    reader.read_hour.assert_not_awaited()


@pytest.mark.asyncio
async def test_c7_only_explicit_reader_subclass_is_admitted():
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    for candidate in (None, object(), AsyncMock()):
        with pytest.raises(TypeError, match="READER_NOT_AUTHORIZED"):
            await produce_signed_security_window(
                reader=candidate, slot_utc=SLOT, produced_at_utc=ISSUED,
                signing_key=KEY, enable_security_shadow=True,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"complete": False},
    {"source_name": "request_logs"},
    {"source_scope": "mixed"},
    {"window_end_utc": END + timedelta(seconds=1)},
    {"window_start_utc": SLOT + timedelta(hours=1)},
    {"collected_at_utc": SLOT},
    {"collected_at_utc": END + timedelta(minutes=16)},
])
async def test_c7_invalid_source_payload_blocked_before_signing(bad):
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    forged = _report().model_copy(update=bad)
    with pytest.raises(PermissionError, match="SOURCE_REPORT_INVALID"):
        await produce_signed_security_window(
            reader=_reader(forged), slot_utc=SLOT, produced_at_utc=ISSUED,
            signing_key=KEY, enable_security_shadow=True,
        )


@pytest.mark.asyncio
async def test_c7_wrong_slot_or_collection_after_signature_is_denied():
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    for report in (
        _report().model_copy(update={"window_start_utc": SLOT - timedelta(hours=1), "window_end_utc": SLOT, "collected_at_utc": SLOT + timedelta(minutes=2)}),
        _report(collected_at_utc=END + timedelta(minutes=10)),
    ):
        with pytest.raises(PermissionError, match="SOURCE_WINDOW_MISMATCH"):
            await produce_signed_security_window(
                reader=_reader(report), slot_utc=SLOT, produced_at_utc=ISSUED,
                signing_key=KEY, enable_security_shadow=True,
            )


@pytest.mark.asyncio
async def test_c7_bad_slot_or_issue_time_blocks_before_reader():
    from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
    reader = _reader()
    for value in (None, SLOT.replace(tzinfo=None), SLOT + timedelta(minutes=1), SLOT.astimezone(timezone(timedelta(hours=-3)))):
        with pytest.raises(ValueError, match="PRODUCER_SLOT_INVALID"):
            await produce_signed_security_window(
                reader=reader, slot_utc=value, produced_at_utc=ISSUED,
                signing_key=KEY, enable_security_shadow=True,
            )
    for value in (None, ISSUED.replace(tzinfo=None), ISSUED.astimezone(timezone(timedelta(hours=-3)))):
        with pytest.raises(ValueError, match="PRODUCER_TIME_INVALID"):
            await produce_signed_security_window(
                reader=reader, slot_utc=SLOT, produced_at_utc=value,
                signing_key=KEY, enable_security_shadow=True,
            )
    for value in (END - timedelta(seconds=1), END + timedelta(minutes=16)):
        with pytest.raises(PermissionError, match="PRODUCER_WINDOW_NOT_FRESH"):
            await produce_signed_security_window(
                reader=reader, slot_utc=SLOT, produced_at_utc=value,
                signing_key=KEY, enable_security_shadow=True,
            )
    reader.read_hour.assert_not_awaited()


def test_c7_envelope_report_extra_fields_fail_closed():
    from app.services.enterprise_l3_security_aggregate_producer import EnterpriseSecurityAggregateReport
    base = _report().model_dump(mode="python")
    for key, value in (("ip", "192.168.1.1"), ("user_id", 22), ("raw_events", [])):
        with pytest.raises(Exception):
            EnterpriseSecurityAggregateReport.model_validate({**base, key: value})
    with pytest.raises(Exception):
        EnterpriseSecurityAggregateReport.model_validate({**base, "metrics": {"ip": "192.168.1.1"}})


def test_c7_no_db_secret_lookup_scheduler_autostart_or_legacy_access():
    import inspect
    import app.services.enterprise_l3_security_aggregate_producer as mod
    s = inspect.getsource(mod)
    for forbidden in (
        "SessionLocal", "app.models", '"request_logs"', "from sqlalchemy",
        "os.environ", "os.getenv", "open(", "while True:", "asyncio.sleep(",
        "app.agents.agent_scheduler", "run_all(", "httpx", "requests.",
    ):
        # The module is intentionally free of source/secret acquisition.
        assert forbidden not in s.replace("source request logs", "source logs")
