"""M006-C9: independent snapshot attestation gate over C8 isolated reader.

Candidate LOCAL/shadow integration only. The host independently supplies the
expected source UUID and a trusted attestor key; the attestation is separate
from the SQLite file. HMAC proves key possession and binds snapshot bytes;
it cannot prove how the source collected those counters or the host's ACLs.

No writer, collector, timer, source credential lookup, raw logs or legacy agent.
"""
from __future__ import annotations

import hmac
import json
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictStr, UUID4, model_validator

from app.services.enterprise_l3_isolated_sqlite_reader import EnterpriseL3IsolatedSqliteReader
from app.services.enterprise_l3_security_aggregate_producer import (
    EnterpriseSecurityAggregateReader,
    EnterpriseSecurityAggregateReport,
)


_SNAPSHOT_FILENAME = "enterprise_security_aggregates.sqlite3"
_MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


class EnterpriseSecuritySnapshotAttestation(BaseModel):
    """Out-of-band attestation signed by a separately authorised source owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0"]
    issuer_id: Literal["enterprise_security_source_authority_v1"]
    source_id: UUID4
    slot_utc: AwareDatetime
    attested_at_utc: AwareDatetime
    snapshot_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    mac_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_hour(self) -> Self:
        if (
            self.slot_utc.utcoffset() != timedelta(0)
            or self.attested_at_utc.utcoffset() != timedelta(0)
            or any((self.slot_utc.minute, self.slot_utc.second, self.slot_utc.microsecond))
        ):
            raise ValueError("ENTERPRISE_C9_TIME_NOT_UTC_HOUR")
        end = self.slot_utc + timedelta(hours=1)
        if not end <= self.attested_at_utc <= end + timedelta(minutes=15):
            raise ValueError("ENTERPRISE_C9_ATTESTATION_TIME_INVALID")
        return self


def snapshot_attestation_signing_bytes(attestation: EnterpriseSecuritySnapshotAttestation) -> bytes:
    if type(attestation) is not EnterpriseSecuritySnapshotAttestation:
        raise TypeError("ENTERPRISE_C9_ATTESTATION_NOT_TYPED")
    try:
        verified = EnterpriseSecuritySnapshotAttestation.model_validate(
            attestation.model_dump(mode="python")
        )
    except Exception:
        raise PermissionError("ENTERPRISE_C9_ATTESTATION_INVALID") from None
    return json.dumps(
        verified.model_dump(mode="json", exclude={"mac_sha256"}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


class EnterpriseL3AttestedSnapshotReader(EnterpriseSecurityAggregateReader):
    """C7 reader port guarded by separately supplied HMAC and file digest.

    Rejects changed or live SQLite sidecar files; the host must ensure that
    snapshots are immutable and inaccessible to untrusted writers.
    """

    def __init__(
        self,
        *,
        isolated_dir: str | Path,
        expected_source_id: UUID,
        attestation: EnterpriseSecuritySnapshotAttestation,
        trusted_attestor_key: bytes,
        enable_security_shadow: bool = False,
    ) -> None:
        if type(enable_security_shadow) is not bool or not enable_security_shadow:
            raise PermissionError("ENTERPRISE_C9_NOT_AUTHORIZED")
        if type(trusted_attestor_key) is not bytes or len(trusted_attestor_key) < 32:
            raise PermissionError("ENTERPRISE_C9_TRUSTED_KEY_REQUIRED")
        if type(attestation) is not EnterpriseSecuritySnapshotAttestation:
            raise TypeError("ENTERPRISE_C9_ATTESTATION_NOT_TYPED")
        try:
            validated = EnterpriseSecuritySnapshotAttestation.model_validate(
                attestation.model_dump(mode="python")
            )
        except Exception:
            raise PermissionError("ENTERPRISE_C9_ATTESTATION_INVALID") from None
        if type(expected_source_id) is not UUID or expected_source_id.version != 4:
            raise PermissionError("ENTERPRISE_C9_SOURCE_NOT_ENROLLED")
        if validated.source_id != expected_source_id:
            raise PermissionError("ENTERPRISE_C9_SOURCE_NOT_ENROLLED")
        expected_mac = hmac.new(
            trusted_attestor_key, snapshot_attestation_signing_bytes(validated), sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_mac, validated.mac_sha256):
            raise PermissionError("ENTERPRISE_C9_ATTESTATION_SIGNATURE_INVALID")

        # C8 independently enforces external directory, expected source UUID,
        # read-only query and fixed schema. Do not bypass its checks.
        self._reader = EnterpriseL3IsolatedSqliteReader(
            isolated_dir=isolated_dir, expected_source_id=expected_source_id,
        )
        self._snapshot_path = self._reader._path
        self._attestation = validated

    def _digest_snapshot(self) -> str:
        target = self._snapshot_path
        if target.is_symlink() or not target.is_file() or target.resolve(strict=True).parent != target.parent:
            raise PermissionError("ENTERPRISE_C9_SOURCE_PATH_UNSAFE")
        # An active WAL/journal can change the logical SQLite view without
        # changing the main file bytes. Treat such snapshots as untrusted.
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(target) + suffix).exists() or Path(str(target) + suffix).is_symlink():
                raise PermissionError("ENTERPRISE_C9_LIVE_SQLITE_NOT_ALLOWED")
        try:
            if target.stat().st_size > _MAX_SNAPSHOT_BYTES:
                raise PermissionError("ENTERPRISE_C9_SNAPSHOT_TOO_LARGE")
            with target.open("rb") as stream:
                data = stream.read(_MAX_SNAPSHOT_BYTES + 1)
            if len(data) > _MAX_SNAPSHOT_BYTES:
                raise PermissionError("ENTERPRISE_C9_SNAPSHOT_TOO_LARGE")
            if target.is_symlink() or target.resolve(strict=True).parent != target.parent:
                raise PermissionError("ENTERPRISE_C9_SOURCE_PATH_UNSAFE")
            return sha256(data).hexdigest()
        except OSError:
            raise PermissionError("ENTERPRISE_C9_SNAPSHOT_UNREADABLE") from None

    async def read_hour(self, *, slot_utc: datetime) -> EnterpriseSecurityAggregateReport:
        if type(slot_utc) is not datetime or slot_utc != self._attestation.slot_utc:
            raise PermissionError("ENTERPRISE_C9_SLOT_NOT_ATTESTED")
        expected = self._attestation.snapshot_sha256
        if not hmac.compare_digest(self._digest_snapshot(), expected):
            raise PermissionError("ENTERPRISE_C9_SNAPSHOT_DIGEST_CONFLICT")
        report = await self._reader.read_hour(slot_utc=slot_utc)
        if not hmac.compare_digest(self._digest_snapshot(), expected):
            raise PermissionError("ENTERPRISE_C9_SNAPSHOT_CHANGED_DURING_READ")
        if report.collected_at_utc > self._attestation.attested_at_utc:
            raise PermissionError("ENTERPRISE_C9_ATTESTATION_BEFORE_COLLECTION")
        return report
