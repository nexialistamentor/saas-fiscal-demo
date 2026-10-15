"""M006-C6 RED: only a signed, fresh, closed 60-min aggregate enters C5."""
from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import AsyncMock

import pytest

from app.agents.contracts.security_audit import SecurityAuditContext


_SLOT = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
_NOW = _SLOT + timedelta(hours=1, minutes=5)
_KEY = b"test-only-local-contract-key-1234567890-xyz"


def _signed(*, slot=_SLOT, produced=None, metrics=None, key=_KEY):
    from app.services import enterprise_l3_signed_security_trigger as mod
    if produced is None:
        produced = slot + timedelta(hours=1, minutes=2)
    if metrics is None:
        metrics = SecurityAuditContext(
            source_kind="enterprise_aggregated_request_logs",
            window_minutes=60,
            max_distinct_accounts_per_ip=4,
            max_requests_per_user=101,
            requests_without_user_agent=21,
        )
    unsigned = mod.EnterpriseSignedSecurityWindow(
        schema_version="1.0",
        producer_id="enterprise_security_aggregator_v1",
        slot_utc=slot,
        produced_at_utc=produced,
        metrics=metrics,
        mac_sha256="0" * 64,
    )
    digest = hmac.new(key, mod.security_window_signing_bytes(unsigned), sha256).hexdigest()
    return unsigned.model_copy(update={"mac_sha256": digest})


@pytest.mark.asyncio
async def test_c6_signed_window_runs_c5_once_and_replays(tmp_path, monkeypatch):
    from app.services import enterprise_l3_signed_security_trigger as mod
    import app.services.enterprise_l3_shadow_scheduler as c5
    monkeypatch.setattr(mod, "_now_utc", lambda: _NOW)
    from app.agents.security_audit_agent import security_audit_agent
    legacy = AsyncMock(side_effect=AssertionError("LEGACY_NOT_AUTHORIZED"))
    monkeypatch.setattr(security_audit_agent, "run", legacy)

    ledger = tmp_path / "shared_ledger.sqlite3"
    window = _signed()
    first = await mod.run_signed_security_window(
        window=window, trusted_key=_KEY, ledger_path=ledger,
        enable_security_shadow=True,
    )
    legacy.assert_not_awaited()
    blocked = AsyncMock(side_effect=AssertionError("REPLAY_MUST_NOT_CALL_AGENT"))
    monkeypatch.setattr(c5, "route_enterprise_l3_event", blocked)
    replay = await mod.run_signed_security_window(
        window=window, trusted_key=_KEY, ledger_path=ledger,
        enable_security_shadow=True,
    )
    assert first.event_id == replay.event_id
    assert first.mission_id == replay.mission_id
    assert first.result.execution_id == replay.result.execution_id
    assert first.result.status == "sucesso"
    assert first.result.mode == "sombra"
    assert first.result.payload["total_alerts"] == 3
    assert first.result.requires_human_review is True
    assert not first.result.actions_executed
    assert first.result.llm_used is False
    blocked.assert_not_awaited()
    assert ledger.exists()
    assert b"test-only-local-contract-key" not in ledger.read_bytes()
    assert b"enterprise_security_aggregator_v1" not in ledger.read_bytes()


@pytest.mark.asyncio
async def test_c6_default_closed_and_invalid_key_before_ledger(tmp_path, monkeypatch):
    from app.services import enterprise_l3_signed_security_trigger as mod
    monkeypatch.setattr(mod, "_now_utc", lambda: _NOW)
    ledger = tmp_path / "no.sqlite3"
    window = _signed()
    with pytest.raises(PermissionError, match="NOT_AUTHORIZED"):
        await mod.run_signed_security_window(window=window, trusted_key=_KEY, ledger_path=ledger)
    for key in (None, "insecure", b"too-short"):
        with pytest.raises(PermissionError, match="TRUSTED_KEY_REQUIRED"):
            await mod.run_signed_security_window(
                window=window, trusted_key=key, ledger_path=ledger,
                enable_security_shadow=True,
            )
    assert not ledger.exists()


@pytest.mark.asyncio
async def test_c6_tampered_metrics_and_wrong_key_fail_before_ledger(tmp_path, monkeypatch):
    from app.services import enterprise_l3_signed_security_trigger as mod
    monkeypatch.setattr(mod, "_now_utc", lambda: _NOW)
    ledger = tmp_path / "no.sqlite3"
    window = _signed()
    tampered = window.model_copy(update={"metrics": window.metrics.model_copy(
        update={"max_requests_per_user": 999}
    )})
    for payload, key in ((tampered, _KEY), (window, b"alternative-key-123456789012345678901234")):
        with pytest.raises(PermissionError, match="ATTESTATION_INVALID"):
            await mod.run_signed_security_window(
                window=payload, trusted_key=key, ledger_path=ledger,
                enable_security_shadow=True,
            )
    assert not ledger.exists()


@pytest.mark.asyncio
async def test_c6_expired_and_future_window_fail_before_ledger(tmp_path, monkeypatch):
    from app.services import enterprise_l3_signed_security_trigger as mod
    monkeypatch.setattr(mod, "_now_utc", lambda: _NOW)
    ledger = tmp_path / "no.sqlite3"
    cases = [
        _signed(slot=_SLOT - timedelta(hours=1)),
        _signed(slot=_SLOT + timedelta(hours=1)),
        _signed(produced=_NOW + timedelta(minutes=1)),
    ]
    for window in cases:
        with pytest.raises(PermissionError, match="ATTESTATION_STALE"):
            await mod.run_signed_security_window(
                window=window, trusted_key=_KEY, ledger_path=ledger,
                enable_security_shadow=True,
            )
    assert not ledger.exists()


@pytest.mark.asyncio
async def test_c6_signed_different_metrics_same_slot_conflict(tmp_path, monkeypatch):
    from app.services import enterprise_l3_signed_security_trigger as mod
    monkeypatch.setattr(mod, "_now_utc", lambda: _NOW)
    ledger = tmp_path / "shared.sqlite3"
    await mod.run_signed_security_window(
        window=_signed(), trusted_key=_KEY, ledger_path=ledger,
        enable_security_shadow=True,
    )
    changed = SecurityAuditContext(
        source_kind="enterprise_aggregated_request_logs",
        window_minutes=60,
        max_distinct_accounts_per_ip=4,
        max_requests_per_user=102,
        requests_without_user_agent=21,
    )
    with pytest.raises(ValueError, match="ENTERPRISE_EVENT_PAYLOAD_CONFLICT"):
        await mod.run_signed_security_window(
            window=_signed(metrics=changed), trusted_key=_KEY, ledger_path=ledger,
            enable_security_shadow=True,
        )


def test_c6_contract_fails_closed_for_untrusted_fields():
    from app.services import enterprise_l3_signed_security_trigger as mod
    window = _signed()
    with pytest.raises(Exception):
        mod.EnterpriseSignedSecurityWindow.model_validate({
            **window.model_dump(mode="python"), "ip": "192.168.1.1",
        })
    with pytest.raises(Exception):
        mod.EnterpriseSignedSecurityWindow.model_validate({
            **window.model_dump(mode="python"), "producer_id": "untrusted",
        })
    with pytest.raises(Exception):
        mod.EnterpriseSignedSecurityWindow.model_validate({
            **window.model_dump(mode="python"), "slot_utc": _SLOT + timedelta(minutes=1),
        })
    with pytest.raises(Exception):
        mod.EnterpriseSignedSecurityWindow.model_validate({
            **window.model_dump(mode="python"), "produced_at_utc": _SLOT,
        })


def test_c6_has_no_autostart_source_db_or_legacy_scheduler():
    import inspect
    from app.services import enterprise_l3_signed_security_trigger as mod
    src = inspect.getsource(mod)
    for forbidden in (
        "app.agents.agent_scheduler", "SessionLocal", "while True:",
        "asyncio.sleep(", "os.getenv(", "requests.", "httpx.",
        "run_all(", "get_agent(",
    ):
        assert forbidden not in src
