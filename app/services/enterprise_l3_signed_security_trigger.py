"""M006-C6: authenticated, closed-window, SINGLE-SHOT security L3 trigger.

Does not run a timer, query source logs, create a source credential, sign data,
start any process, use the legacy scheduler, or configure production. The
trusted HMAC key must be supplied by a separately authorised host; the data
producer and its credential provisioning are outside this module.
"""
from __future__ import annotations

import hmac
import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictStr, model_validator

from app.agents.contracts.security_audit import SecurityAuditContext
from app.services.enterprise_l3_event_router import EnterpriseL3RouteReceipt
from app.services.enterprise_l3_shadow_scheduler import EnterpriseL3ShadowScheduler


class EnterpriseSignedSecurityWindow(BaseModel):
    """Authenticated envelope over aggregate counters, never raw request logs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    producer_id: Literal["enterprise_security_aggregator_v1"]
    slot_utc: AwareDatetime
    produced_at_utc: AwareDatetime
    metrics: SecurityAuditContext
    mac_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        for value in (self.slot_utc, self.produced_at_utc):
            if value.utcoffset() != timedelta(0):
                raise ValueError("ENTERPRISE_SECURITY_TIME_NOT_UTC")
        if (
            self.slot_utc.minute != 0
            or self.slot_utc.second != 0
            or self.slot_utc.microsecond != 0
        ):
            raise ValueError("ENTERPRISE_SECURITY_SLOT_NOT_HOURLY")
        if self.produced_at_utc < self.slot_utc + timedelta(hours=1):
            raise ValueError("ENTERPRISE_SECURITY_WINDOW_NOT_CLOSED")
        return self


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def security_window_signing_bytes(window: EnterpriseSignedSecurityWindow) -> bytes:
    """Canonical public data to be signed by an independent trusted producer."""
    if type(window) is not EnterpriseSignedSecurityWindow:
        raise TypeError("ENTERPRISE_SECURITY_WINDOW_NOT_TYPED")
    try:
        valid = EnterpriseSignedSecurityWindow.model_validate(
            window.model_dump(mode="python")
        )
    except Exception:
        raise PermissionError("ENTERPRISE_SECURITY_WINDOW_INVALID") from None
    return json.dumps(
        valid.model_dump(mode="json", exclude={"mac_sha256"}),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


async def run_signed_security_window(
    *,
    window: EnterpriseSignedSecurityWindow,
    trusted_key: bytes,
    ledger_path: str | Path,
    enable_security_shadow: bool = False,
) -> EnterpriseL3RouteReceipt:
    """Verify one closed UTC hour then delegate to the C5 durable guard.

    There is NO periodic loop: an authorised external orchestrator must call
    this method, supply a trusted key, and decide whether/when to run it.
    """
    if type(enable_security_shadow) is not bool or not enable_security_shadow:
        raise PermissionError("ENTERPRISE_SECURITY_TRIGGER_NOT_AUTHORIZED")
    if type(trusted_key) is not bytes or len(trusted_key) < 32:
        raise PermissionError("ENTERPRISE_SECURITY_TRUSTED_KEY_REQUIRED")

    canonical = security_window_signing_bytes(window)
    expected = hmac.new(trusted_key, canonical, sha256).hexdigest()
    if not hmac.compare_digest(expected, window.mac_sha256):
        raise PermissionError("ENTERPRISE_SECURITY_ATTESTATION_INVALID")

    now = _now_utc()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise PermissionError("ENTERPRISE_SECURITY_CLOCK_NOT_TRUSTED")

    end = window.slot_utc + timedelta(hours=1)
    # Only the most recently CLOSED hour is allowed. Old or future windows
    # cannot be silently replayed as fresh, even with a valid signature.
    if not (end <= window.produced_at_utc <= now <= end + timedelta(minutes=15)):
        raise PermissionError("ENTERPRISE_SECURITY_ATTESTATION_STALE")

    # Preserve C5's single atomic ledger authority. No second storage.
    return await EnterpriseL3ShadowScheduler(ledger_path).run_security_hour(
        slot_utc=window.slot_utc,
        metrics=window.metrics,
        enable_security_shadow=True,
    )
