"""M006-C10 — local shadow admission of independently approved Enterprise sources.

An EXTERNAL host must issue and authenticate a short-lived governance grant,
provision three distinct secrets, attest an immutable external snapshot, supply
a current rotation epoch and invoke this entrypoint explicitly. This module
neither provisions keys nor verifies external custody or independent operators.
No auto-start, collector, endpoint, legacy scheduler, DB-source writes or MEI.
The only durable mutation downstream is C1's existing execution ledger.
"""
from __future__ import annotations

import hmac
import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr, UUID4, model_validator

from app.services.enterprise_l3_attested_snapshot_reader import (
    EnterpriseL3AttestedSnapshotReader,
    EnterpriseSecuritySnapshotAttestation,
)
from app.services.enterprise_l3_event_router import EnterpriseL3RouteReceipt
from app.services.enterprise_l3_security_aggregate_producer import produce_signed_security_window
from app.services.enterprise_l3_signed_security_trigger import run_signed_security_window


class EnterpriseSecuritySourceGrant(BaseModel):
    """Externally signed scope/key pins. This object is NOT proof of host ACLs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0"]
    issuer_id: Literal["enterprise_security_governance_v1"]
    source_id: UUID4
    source_scope: Literal["enterprise_only"]
    execution_mode: Literal["sombra"]
    rotation_epoch: StrictInt = Field(ge=1)
    valid_from_utc: AwareDatetime
    valid_until_utc: AwareDatetime
    snapshot_directory: StrictStr = Field(min_length=1, max_length=4096)
    attestor_key_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    producer_key_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    mac_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def valid_grant(self) -> Self:
        if any(dt.utcoffset() != timedelta(0) for dt in (
            self.valid_from_utc, self.valid_until_utc,
        )):
            raise ValueError("ENTERPRISE_C10_GRANT_TIME_NOT_UTC")
        duration = self.valid_until_utc - self.valid_from_utc
        if duration <= timedelta(0) or duration > timedelta(hours=24):
            raise ValueError("ENTERPRISE_C10_GRANT_DURATION_INVALID")
        if self.attestor_key_sha256 == self.producer_key_sha256:
            raise ValueError("ENTERPRISE_C10_GRANT_KEYS_NOT_SEPARATED")
        if not Path(self.snapshot_directory).is_absolute():
            raise ValueError("ENTERPRISE_C10_GRANT_DIRECTORY_NOT_ABSOLUTE")
        return self


def enterprise_source_grant_signing_bytes(grant: EnterpriseSecuritySourceGrant) -> bytes:
    if type(grant) is not EnterpriseSecuritySourceGrant:
        raise TypeError("ENTERPRISE_C10_GRANT_NOT_TYPED")
    try:
        verified = EnterpriseSecuritySourceGrant.model_validate(grant.model_dump(mode="python"))
    except Exception:
        raise PermissionError("ENTERPRISE_C10_GRANT_INVALID") from None
    return json.dumps(
        verified.model_dump(mode="json", exclude={"mac_sha256"}),
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _valid_secret(secret: bytes) -> bool:
    return type(secret) is bytes and len(secret) >= 32


async def run_authorized_security_hour(
    *,
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
    """Execute exactly one short-lived approved shadow window via C9→C7→C6→C5.

    The host must supply the actual key material and trusted current epoch. No
    keys, raw telemetry or grant are persisted. On C1 failure no retry occurs.
    """
    if type(enable_security_shadow) is not bool or not enable_security_shadow:
        raise PermissionError("ENTERPRISE_C10_NOT_AUTHORIZED")
    if any(not _valid_secret(k) for k in (
        trusted_governance_key, trusted_attestor_key, producer_signing_key,
    )):
        raise PermissionError("ENTERPRISE_C10_TRUSTED_KEYS_REQUIRED")
    if type(expected_rotation_epoch) is not int or expected_rotation_epoch < 1:
        raise PermissionError("ENTERPRISE_C10_ROTATION_EPOCH_REQUIRED")
    if type(grant) is not EnterpriseSecuritySourceGrant:
        raise PermissionError("ENTERPRISE_C10_GRANT_NOT_TYPED")
    try:
        valid = EnterpriseSecuritySourceGrant.model_validate(grant.model_dump(mode="python"))
    except Exception:
        raise PermissionError("ENTERPRISE_C10_GRANT_INVALID") from None
    if valid.rotation_epoch != expected_rotation_epoch:
        raise PermissionError("ENTERPRISE_C10_ROTATION_EPOCH_MISMATCH")

    gov_hash = sha256(trusted_governance_key).hexdigest()
    att_hash = sha256(trusted_attestor_key).hexdigest()
    producer_hash = sha256(producer_signing_key).hexdigest()
    if len({gov_hash, att_hash, producer_hash}) != 3:
        raise PermissionError("ENTERPRISE_C10_KEYS_NOT_SEPARATED")
    if (
        not hmac.compare_digest(valid.attestor_key_sha256, att_hash)
        or not hmac.compare_digest(valid.producer_key_sha256, producer_hash)
    ):
        raise PermissionError("ENTERPRISE_C10_KEY_PIN_MISMATCH")
    mac = hmac.new(
        trusted_governance_key, enterprise_source_grant_signing_bytes(valid), sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, valid.mac_sha256):
        raise PermissionError("ENTERPRISE_C10_GOVERNANCE_SIGNATURE_INVALID")
    if type(attestation) is not EnterpriseSecuritySnapshotAttestation:
        raise PermissionError("ENTERPRISE_C10_ATTESTATION_NOT_TYPED")
    try:
        validated_attestation = EnterpriseSecuritySnapshotAttestation.model_validate(
            attestation.model_dump(mode="python")
        )
    except Exception:
        raise PermissionError("ENTERPRISE_C10_ATTESTATION_INVALID") from None
    if type(slot_utc) is not datetime or slot_utc.tzinfo is None or slot_utc.utcoffset() != timedelta(0):
        raise PermissionError("ENTERPRISE_C10_SLOT_INVALID")
    if validated_attestation.source_id != valid.source_id or validated_attestation.slot_utc != slot_utc:
        raise PermissionError("ENTERPRISE_C10_SOURCE_OR_SLOT_MISMATCH")

    now = _now_utc()
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise PermissionError("ENTERPRISE_C10_CLOCK_NOT_TRUSTED")
    window_end = slot_utc + timedelta(hours=1)
    if not (
        valid.valid_from_utc <= window_end <= now < valid.valid_until_utc
        and window_end <= now <= window_end + timedelta(minutes=15)
    ):
        raise PermissionError("ENTERPRISE_C10_GRANT_NOT_CURRENT")
    if not isinstance(isolated_dir, (str, Path)):
        raise PermissionError("ENTERPRISE_C10_DIRECTORY_INVALID")
    bound = Path(valid.snapshot_directory)
    supplied = Path(isolated_dir)
    if (not supplied.is_absolute() or not supplied.is_dir()
            or supplied.is_symlink() or bound.is_symlink()
            or supplied.resolve(strict=True) != bound.resolve(strict=True)):
        raise PermissionError("ENTERPRISE_C10_DIRECTORY_NOT_AUTHORIZED")

    reader = EnterpriseL3AttestedSnapshotReader(
        isolated_dir=supplied,
        expected_source_id=valid.source_id,
        attestation=validated_attestation,
        trusted_attestor_key=trusted_attestor_key,
        enable_security_shadow=True,
    )
    window = await produce_signed_security_window(
        reader=reader,
        slot_utc=slot_utc,
        produced_at_utc=now,
        signing_key=producer_signing_key,
        enable_security_shadow=True,
    )
    return await run_signed_security_window(
        window=window,
        trusted_key=producer_signing_key,
        ledger_path=ledger_path,
        enable_security_shadow=True,
    )
