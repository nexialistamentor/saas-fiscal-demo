"""M006-C13: host-bound, single-shot Enterprise L3 authority/secret adapter.

Wires separately injected public-authority feed and key-custody ports into
C12's abstract host interface. Re-reads revocation after credential acquisition
and refuses stale leases/clock drift. Does NOT implement a real source,
external trust root, credential vault, collector, scheduler, MEI or deployment.
ABC/provider instances are not proof of separate operators or source isolation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from app.services.enterprise_l3_attested_snapshot_reader import EnterpriseSecuritySnapshotAttestation
from app.services.enterprise_l3_governed_tick import (
    EnterpriseSecurityHostAuthorities, EnterpriseSecurityHostAuthorityPort,
)
from app.services.enterprise_l3_revocation_recovery import EnterpriseSecurityAuthorityStatus
from app.services.enterprise_l3_source_authorization_gate import EnterpriseSecuritySourceGrant


@dataclass(frozen=True, slots=True)
class EnterpriseSecurityHostEnrollment:
    """Host-pinned source identity and paths, not evidence of their ownership."""
    source_id: UUID
    rotation_epoch: int
    isolated_dir: Path
    ledger_path: Path


@dataclass(frozen=True, slots=True)
class EnterpriseSecurityPublicAuthorities:
    grant: EnterpriseSecuritySourceGrant
    attestation: EnterpriseSecuritySnapshotAttestation
    status: EnterpriseSecurityAuthorityStatus


@dataclass(frozen=True, slots=True, repr=False)
class EnterpriseSecurityKeyLease:
    """Ephemeral host-supplied key material; not a key store or memory scrub."""
    source_id: UUID
    rotation_epoch: int
    slot_utc: datetime
    valid_from_utc: datetime
    valid_until_utc: datetime
    trusted_status_key: bytes = field(repr=False)
    trusted_governance_key: bytes = field(repr=False)
    trusted_attestor_key: bytes = field(repr=False)
    producer_signing_key: bytes = field(repr=False)


class EnterpriseSecurityPublicAuthorityFeed(ABC):
    """Separately configured external governance/attestation/status provider."""
    @abstractmethod
    async def authorities_for_hour(
        self, *, slot_utc: datetime, source_id: UUID, rotation_epoch: int
    ) -> EnterpriseSecurityPublicAuthorities:
        raise NotImplementedError

    @abstractmethod
    async def latest_status(
        self, *, slot_utc: datetime, source_id: UUID, rotation_epoch: int
    ) -> EnterpriseSecurityAuthorityStatus:
        """Refetch status after obtaining keys; must bypass host-side caches."""
        raise NotImplementedError


class EnterpriseSecurityKeyCustodyPort(ABC):
    """Host-owned key provider, not implemented in this package."""
    @abstractmethod
    async def acquire_lease(
        self, *, slot_utc: datetime, source_id: UUID, rotation_epoch: int
    ) -> EnterpriseSecurityKeyLease:
        raise NotImplementedError


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fresh_now(slot_utc: datetime) -> datetime:
    now = _now_utc()
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise PermissionError("ENTERPRISE_C13_CLOCK_NOT_TRUSTED")
    end = slot_utc + timedelta(hours=1)
    if not (end <= now <= end + timedelta(minutes=15)):
        raise PermissionError("ENTERPRISE_C13_WINDOW_NOT_FRESH")
    return now


def _check_status(
    status: EnterpriseSecurityAuthorityStatus,
    enrollment: EnterpriseSecurityHostEnrollment,
    grant: EnterpriseSecuritySourceGrant,
    now: datetime,
) -> None:
    if type(status) is not EnterpriseSecurityAuthorityStatus:
        raise PermissionError("ENTERPRISE_C13_STATUS_NOT_TYPED")
    if (status.source_id != enrollment.source_id
            or status.rotation_epoch != enrollment.rotation_epoch):
        raise PermissionError("ENTERPRISE_C13_STATUS_SCOPE_MISMATCH")
    if status.disposition != "active":
        raise PermissionError("ENTERPRISE_C13_STATUS_NOT_ACTIVE")
    if not (status.issued_at_utc <= now < status.valid_until_utc):
        raise PermissionError("ENTERPRISE_C13_STATUS_NOT_CURRENT")
    # C11 subsequently validates this status' MAC and its grant SHA256.
    if type(status.grant_sha256) is not str or len(status.grant_sha256) != 64:
        raise PermissionError("ENTERPRISE_C13_STATUS_GRANT_UNBOUND")


class EnterpriseL3ProvisionedHost(EnterpriseSecurityHostAuthorityPort):
    """Explicit C12 host adapter; no job, secrets registry or implicit opt-in."""
    def __init__(
        self, *, enrollment: EnterpriseSecurityHostEnrollment,
        authority_feed: EnterpriseSecurityPublicAuthorityFeed,
        key_custody: EnterpriseSecurityKeyCustodyPort,
        enable_security_shadow: bool = False,
    ) -> None:
        if type(enable_security_shadow) is not bool or not enable_security_shadow:
            raise PermissionError("ENTERPRISE_C13_HOST_NOT_AUTHORIZED")
        if type(enrollment) is not EnterpriseSecurityHostEnrollment:
            raise PermissionError("ENTERPRISE_C13_ENROLLMENT_INVALID")
        if (type(enrollment.source_id) is not UUID or enrollment.source_id.version != 4
                or type(enrollment.rotation_epoch) is not int or enrollment.rotation_epoch < 1):
            raise PermissionError("ENTERPRISE_C13_ENROLLMENT_INVALID")
        if (not isinstance(enrollment.isolated_dir, Path)
                or not isinstance(enrollment.ledger_path, Path)
                or not enrollment.isolated_dir.is_absolute()
                or not enrollment.ledger_path.is_absolute()):
            raise PermissionError("ENTERPRISE_C13_PATH_NOT_ABSOLUTE")
        if (not isinstance(authority_feed, EnterpriseSecurityPublicAuthorityFeed)
                or not isinstance(key_custody, EnterpriseSecurityKeyCustodyPort)):
            raise PermissionError("ENTERPRISE_C13_PROVIDER_NOT_AUTHORIZED")
        self._enrollment = enrollment
        self._feed = authority_feed
        self._custody = key_custody

    async def authorities_for_hour(self, *, slot_utc: datetime) -> EnterpriseSecurityHostAuthorities:
        enrollment = self._enrollment
        if (type(slot_utc) is not datetime or slot_utc.tzinfo is None
                or slot_utc.utcoffset() != timedelta(0)
                or any((slot_utc.minute, slot_utc.second, slot_utc.microsecond))):
            raise PermissionError("ENTERPRISE_C13_SLOT_NOT_UTC_HOUR")
        now = _fresh_now(slot_utc)
        scope = dict(
            slot_utc=slot_utc, source_id=enrollment.source_id,
            rotation_epoch=enrollment.rotation_epoch,
        )
        public = await self._feed.authorities_for_hour(**scope)
        if type(public) is not EnterpriseSecurityPublicAuthorities:
            raise PermissionError("ENTERPRISE_C13_PUBLIC_ENVELOPE_INVALID")
        if (type(public.grant) is not EnterpriseSecuritySourceGrant
                or type(public.attestation) is not EnterpriseSecuritySnapshotAttestation):
            raise PermissionError("ENTERPRISE_C13_PUBLIC_AUTHORITY_NOT_TYPED")
        grant, attestation = public.grant, public.attestation
        if (grant.source_id != enrollment.source_id
                or attestation.source_id != enrollment.source_id
                or attestation.slot_utc != slot_utc
                or grant.rotation_epoch != enrollment.rotation_epoch):
            raise PermissionError("ENTERPRISE_C13_PUBLIC_SCOPE_MISMATCH")
        if (grant.source_scope != "enterprise_only" or grant.execution_mode != "sombra"
                or Path(grant.snapshot_directory) != enrollment.isolated_dir):
            raise PermissionError("ENTERPRISE_C13_PUBLIC_ENROLLMENT_MISMATCH")
        _check_status(public.status, enrollment, grant, now)
        lease = await self._custody.acquire_lease(**scope)
        if type(lease) is not EnterpriseSecurityKeyLease:
            raise PermissionError("ENTERPRISE_C13_KEY_LEASE_INVALID")
        now = _fresh_now(slot_utc)
        if (lease.source_id != enrollment.source_id
                or type(lease.rotation_epoch) is not int
                or lease.rotation_epoch != enrollment.rotation_epoch
                or lease.slot_utc != slot_utc):
            raise PermissionError("ENTERPRISE_C13_LEASE_SCOPE_MISMATCH")
        if any(type(t) is not datetime or t.tzinfo is None or t.utcoffset() != timedelta(0)
               for t in (lease.valid_from_utc, lease.valid_until_utc)):
            raise PermissionError("ENTERPRISE_C13_LEASE_TIME_INVALID")
        if not (timedelta(0) < lease.valid_until_utc - lease.valid_from_utc <= timedelta(minutes=5)
                and lease.valid_from_utc <= now < lease.valid_until_utc):
            raise PermissionError("ENTERPRISE_C13_LEASE_EXPIRED")
        keys = (
            lease.trusted_status_key, lease.trusted_governance_key,
            lease.trusted_attestor_key, lease.producer_signing_key,
        )
        if any(type(key) is not bytes or len(key) < 32 for key in keys):
            raise PermissionError("ENTERPRISE_C13_LEASE_KEYS_INVALID")
        if len(set(keys)) != 4:
            raise PermissionError("ENTERPRISE_C13_LEASE_KEYS_NOT_SEPARATED")
        # Second fetch must come AFTER custody; a revoked or rolled status
        # never reaches C12, even if the initial envelope said 'active'.
        current = await self._feed.latest_status(**scope)
        now = _fresh_now(slot_utc)
        if not (lease.valid_from_utc <= now < lease.valid_until_utc):
            raise PermissionError("ENTERPRISE_C13_LEASE_EXPIRED")
        _check_status(current, enrollment, grant, now)
        if current.grant_sha256 != public.status.grant_sha256:
            raise PermissionError("ENTERPRISE_C13_GRANT_CHANGED_AFTER_FETCH")
        if current.issued_at_utc < public.status.issued_at_utc:
            raise PermissionError("ENTERPRISE_C13_STATUS_REGRESSED")
        # C12/C11 repeat structural, MAC, time, path and revocation checks.
        return EnterpriseSecurityHostAuthorities(
            status=current, grant=grant, attestation=attestation,
            isolated_dir=enrollment.isolated_dir, ledger_path=enrollment.ledger_path,
            trusted_status_key=keys[0], trusted_governance_key=keys[1],
            trusted_attestor_key=keys[2], producer_signing_key=keys[3],
            expected_rotation_epoch=enrollment.rotation_epoch,
        )
