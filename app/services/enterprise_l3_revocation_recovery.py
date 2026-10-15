"""M006-C11: fresh signed revocation gate and read-only C1 recovery triage.

All authorities are injected by an explicitly authorised host. No external
status service, key vault, collector, timer, retry, ledger mutation or production
integration is installed. A signed status proves key possession and freshness,
NOT independent custody or atomic revocation during an already-running call.
"""
from __future__ import annotations

import hmac
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr, UUID4, model_validator

from app.services.enterprise_l3_attested_snapshot_reader import EnterpriseSecuritySnapshotAttestation
from app.services.enterprise_l3_event_router import EnterpriseL3RouteReceipt
from app.services.enterprise_l3_source_authorization_gate import (
    EnterpriseSecuritySourceGrant,
    run_authorized_security_hour,
)


class EnterpriseSecurityAuthorityStatus(BaseModel):
    """Short-lived, independently signed current admission decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0"]
    issuer_id: Literal["enterprise_security_revocation_authority_v1"]
    source_id: UUID4
    rotation_epoch: StrictInt = Field(ge=1)
    grant_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    disposition: Literal["active", "suspended", "revoked"]
    issued_at_utc: AwareDatetime
    valid_until_utc: AwareDatetime
    mac_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_lease(self) -> Self:
        if self.issued_at_utc.utcoffset() != timedelta(0) or self.valid_until_utc.utcoffset() != timedelta(0):
            raise ValueError("ENTERPRISE_C11_STATUS_TIME_NOT_UTC")
        duration = self.valid_until_utc - self.issued_at_utc
        if not timedelta(0) < duration <= timedelta(minutes=5):
            raise ValueError("ENTERPRISE_C11_STATUS_LEASE_INVALID")
        return self


def security_authority_status_signing_bytes(status: EnterpriseSecurityAuthorityStatus) -> bytes:
    if type(status) is not EnterpriseSecurityAuthorityStatus:
        raise TypeError("ENTERPRISE_C11_STATUS_NOT_TYPED")
    try:
        checked = EnterpriseSecurityAuthorityStatus.model_validate(status.model_dump(mode="python"))
    except Exception:
        raise PermissionError("ENTERPRISE_C11_STATUS_INVALID") from None
    return json.dumps(
        checked.model_dump(mode="json", exclude={"mac_sha256"}),
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def enterprise_grant_digest(grant: EnterpriseSecuritySourceGrant) -> str:
    """Bind the complete signed C10 grant, including its governance MAC."""
    if type(grant) is not EnterpriseSecuritySourceGrant:
        raise PermissionError("ENTERPRISE_C11_GRANT_NOT_TYPED")
    try:
        checked = EnterpriseSecuritySourceGrant.model_validate(grant.model_dump(mode="python"))
    except Exception:
        raise PermissionError("ENTERPRISE_C11_GRANT_INVALID") from None
    raw = json.dumps(checked.model_dump(mode="json"), ensure_ascii=True, sort_keys=True,
                     separators=(",", ":")).encode("ascii")
    return sha256(raw).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _valid_secret(secret: bytes) -> bool:
    return type(secret) is bytes and len(secret) >= 32


async def run_revocation_gated_security_hour(
    *,
    status: EnterpriseSecurityAuthorityStatus,
    trusted_status_key: bytes,
    grant: EnterpriseSecuritySourceGrant,
    attestation: EnterpriseSecuritySnapshotAttestation,
    isolated_dir: str | Path,
    slot_utc: datetime,
    ledger_path: str | Path,
    trusted_governance_key: bytes,
    trusted_attestor_key: bytes,
    producer_signing_key: bytes,
    expected_rotation_epoch: int,
    enable_security_shadow: bool = False,
) -> EnterpriseL3RouteReceipt:
    """Require a fresh independent ACTIVE decision before C10 and before replay.

    This is a single-shot gate. The host MUST provide a newly checked status
    for each invocation and enforce current revocations at its own boundary.
    """
    if type(enable_security_shadow) is not bool or not enable_security_shadow:
        raise PermissionError("ENTERPRISE_C11_NOT_AUTHORIZED")
    keys = (trusted_status_key, trusted_governance_key, trusted_attestor_key, producer_signing_key)
    if any(not _valid_secret(key) for key in keys):
        raise PermissionError("ENTERPRISE_C11_KEYS_REQUIRED")
    if len({sha256(key).digest() for key in keys}) != 4:
        raise PermissionError("ENTERPRISE_C11_KEYS_NOT_SEPARATED")
    if type(status) is not EnterpriseSecurityAuthorityStatus:
        raise PermissionError("ENTERPRISE_C11_STATUS_NOT_TYPED")
    try:
        checked = EnterpriseSecurityAuthorityStatus.model_validate(status.model_dump(mode="python"))
    except Exception:
        raise PermissionError("ENTERPRISE_C11_STATUS_INVALID") from None
    if type(expected_rotation_epoch) is not int or expected_rotation_epoch < 1:
        raise PermissionError("ENTERPRISE_C11_EPOCH_INVALID")
    grant_digest = enterprise_grant_digest(grant)
    if (checked.source_id != grant.source_id
            or checked.rotation_epoch != expected_rotation_epoch
            or checked.rotation_epoch != grant.rotation_epoch
            or not hmac.compare_digest(checked.grant_sha256, grant_digest)):
        raise PermissionError("ENTERPRISE_C11_STATUS_SCOPE_MISMATCH")
    expected_mac = hmac.new(trusted_status_key, security_authority_status_signing_bytes(checked), sha256).hexdigest()
    if not hmac.compare_digest(expected_mac, checked.mac_sha256):
        raise PermissionError("ENTERPRISE_C11_STATUS_SIGNATURE_INVALID")
    now = _now_utc()
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise PermissionError("ENTERPRISE_C11_CLOCK_UNTRUSTED")
    if not checked.issued_at_utc <= now < checked.valid_until_utc:
        raise PermissionError("ENTERPRISE_C11_STATUS_NOT_CURRENT")
    if checked.disposition != "active":
        raise PermissionError("ENTERPRISE_C11_SOURCE_" + checked.disposition.upper())
    # All prior C10/C9/C8/C7/C6/C5 gates remain authoritative.
    return await run_authorized_security_hour(
        grant=grant, attestation=attestation, isolated_dir=isolated_dir,
        slot_utc=slot_utc, ledger_path=ledger_path,
        trusted_governance_key=trusted_governance_key,
        trusted_attestor_key=trusted_attestor_key,
        producer_signing_key=producer_signing_key,
        expected_rotation_epoch=expected_rotation_epoch,
        enable_security_shadow=True,
    )


class EnterpriseSecurityRecoveryObservation(BaseModel):
    """Evidence only; this object never authorizes resetting or rerunning."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: UUID4
    state: Literal["not_seen", "claimed", "failed", "completed"]
    manual_review_required: bool
    automatic_retry_allowed: Literal[False] = False


def inspect_security_delivery_state(*, ledger_path: str | Path, event_id: UUID) -> EnterpriseSecurityRecoveryObservation:
    """Read only the existing C1 ledger state; do NOT alter failed/claimed rows.

    Missing, mutable, or unknown databases fail closed rather than implying
    permission to retry. Event IDs are caller-supplied, so this cannot prove
    an event belongs to the security route; it is local triage only.
    """
    if type(event_id) is not UUID or event_id.version != 4:
        raise ValueError("ENTERPRISE_C11_RECOVERY_EVENT_ID_INVALID")
    if not isinstance(ledger_path, (str, Path)):
        raise TypeError("ENTERPRISE_C11_RECOVERY_LEDGER_PATH_INVALID")
    path = Path(ledger_path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise PermissionError("ENTERPRISE_C11_RECOVERY_LEDGER_UNAVAILABLE")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2.0)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA trusted_schema=OFF")
            cols = {row[1] for row in conn.execute("PRAGMA main.table_info('enterprise_l3_event_delivery')")}
            if cols != {"event_id", "event_hash", "state", "receipt_json"}:
                raise PermissionError("ENTERPRISE_C11_RECOVERY_SCHEMA_UNKNOWN")
            records = conn.execute(
                "SELECT state FROM main.enterprise_l3_event_delivery WHERE event_id=? LIMIT 2",
                (str(event_id),),
            ).fetchall()
            if len(records) > 1:
                raise PermissionError("ENTERPRISE_C11_RECOVERY_LEDGER_CONFLICT")
            state = records[0][0] if records else "not_seen"
            if state not in ("not_seen", "claimed", "failed", "completed"):
                raise PermissionError("ENTERPRISE_C11_RECOVERY_STATE_UNKNOWN")
            return EnterpriseSecurityRecoveryObservation(
                event_id=event_id,
                state=state,
                manual_review_required=state in ("claimed", "failed"),
                automatic_retry_allowed=False,
            )
    except sqlite3.Error:
        raise PermissionError("ENTERPRISE_C11_RECOVERY_LEDGER_UNREADABLE") from None
