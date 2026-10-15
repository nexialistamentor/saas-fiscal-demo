"""M006-C12: one-shot Enterprise L3 host-driven hourly orchestration.

The host explicitly supplies a credential/source authority port. No source,
secret vault, runner, timer, collector, endpoint or background loop is created.
C11 remains the sole admission authority; C5/C1 guard duplicate executions.
No production activation and no access to shared request_logs/MEI.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.enterprise_l3_attested_snapshot_reader import (
    EnterpriseSecuritySnapshotAttestation,
)
from app.services.enterprise_l3_event_router import EnterpriseL3RouteReceipt
from app.services.enterprise_l3_revocation_recovery import (
    EnterpriseSecurityAuthorityStatus,
    run_revocation_gated_security_hour,
)
from app.services.enterprise_l3_source_authorization_gate import EnterpriseSecuritySourceGrant


@dataclass(frozen=True, slots=True, repr=False)
class EnterpriseSecurityHostAuthorities:
    """Ephemeral authority bundle provided by a separately trusted host.

    Secrets are NOT acquired or serialized here. The host owns vault access,
    rotation and ACLs; Python in-memory retention is not secure key storage.
    """

    status: EnterpriseSecurityAuthorityStatus
    grant: EnterpriseSecuritySourceGrant
    attestation: EnterpriseSecuritySnapshotAttestation
    isolated_dir: Path
    ledger_path: Path
    trusted_status_key: bytes = field(repr=False)
    trusted_governance_key: bytes = field(repr=False)
    trusted_attestor_key: bytes = field(repr=False)
    producer_signing_key: bytes = field(repr=False)
    expected_rotation_epoch: int


class EnterpriseSecurityHostAuthorityPort(ABC):
    """Host-implemented port. Inheritance is not proof of source isolation."""

    @abstractmethod
    async def authorities_for_hour(self, *, slot_utc: datetime) -> EnterpriseSecurityHostAuthorities:
        """Fetch the latest status/grant/attestation and four distinct keys."""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _valid_tick_clock(now: datetime) -> datetime:
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise PermissionError("ENTERPRISE_C12_CLOCK_NOT_TRUSTED")
    closed_end = now.replace(minute=0, second=0, microsecond=0)
    if now > closed_end + timedelta(minutes=15):
        raise PermissionError("ENTERPRISE_C12_TICK_OUTSIDE_FRESH_WINDOW")
    return closed_end - timedelta(hours=1)


def _check_host_bundle(bundle: EnterpriseSecurityHostAuthorities, slot: datetime) -> None:
    if type(bundle) is not EnterpriseSecurityHostAuthorities:
        raise PermissionError("ENTERPRISE_C12_HOST_BUNDLE_INVALID")
    if (type(bundle.status) is not EnterpriseSecurityAuthorityStatus
            or type(bundle.grant) is not EnterpriseSecuritySourceGrant
            or type(bundle.attestation) is not EnterpriseSecuritySnapshotAttestation):
        raise PermissionError("ENTERPRISE_C12_HOST_AUTHORITY_NOT_TYPED")
    if (bundle.grant.source_id != bundle.attestation.source_id
            or bundle.grant.source_id != bundle.status.source_id
            or bundle.attestation.slot_utc != slot):
        raise PermissionError("ENTERPRISE_C12_SOURCE_OR_SLOT_MISMATCH")
    if (type(bundle.expected_rotation_epoch) is not int
            or bundle.expected_rotation_epoch < 1
            or bundle.grant.rotation_epoch != bundle.expected_rotation_epoch
            or bundle.status.rotation_epoch != bundle.expected_rotation_epoch):
        raise PermissionError("ENTERPRISE_C12_ROTATION_EPOCH_MISMATCH")
    if (not isinstance(bundle.isolated_dir, Path)
            or not isinstance(bundle.ledger_path, Path)
            or not bundle.isolated_dir.is_absolute()
            or not bundle.ledger_path.is_absolute()):
        raise PermissionError("ENTERPRISE_C12_HOST_PATH_INVALID")
    # Never let the C1 write-ahead ledger point at a source snapshot or any
    # file inside its separately attested, read-only snapshot directory.
    try:
        snapshot_dir = bundle.isolated_dir.resolve(strict=True)
        ledger_target = bundle.ledger_path.resolve(strict=False)
        repo_root = Path(__file__).resolve().parents[2]
        if (not snapshot_dir.is_dir()
                or not bundle.ledger_path.parent.is_dir()
                or ledger_target.is_relative_to(snapshot_dir)
                or ledger_target.is_relative_to(repo_root)):
            raise PermissionError("ENTERPRISE_C12_LEDGER_NOT_ISOLATED")
    except PermissionError:
        raise
    except (OSError, ValueError):
        raise PermissionError("ENTERPRISE_C12_HOST_PATH_INVALID") from None
    keys = (
        bundle.trusted_status_key, bundle.trusted_governance_key,
        bundle.trusted_attestor_key, bundle.producer_signing_key,
    )
    if any(type(key) is not bytes or len(key) < 32 for key in keys):
        raise PermissionError("ENTERPRISE_C12_KEYS_NOT_AVAILABLE")
    if len(set(keys)) != 4:
        raise PermissionError("ENTERPRISE_C12_KEYS_NOT_SEPARATED")


async def run_one_governed_security_tick(
    *,
    host: EnterpriseSecurityHostAuthorityPort,
    enable_security_shadow: bool = False,
) -> EnterpriseL3RouteReceipt:
    """Run the just-closed UTC hour exactly once through C11.

    Does not start a periodic job, persist host credentials, auto-retry, or
    translate an authorization failure into a successful skipped execution.
    The external host must arrange scheduling and fresh authority acquisition.
    """
    if type(enable_security_shadow) is not bool or not enable_security_shadow:
        raise PermissionError("ENTERPRISE_C12_TICK_NOT_AUTHORIZED")
    if not isinstance(host, EnterpriseSecurityHostAuthorityPort):
        raise PermissionError("ENTERPRISE_C12_HOST_NOT_AUTHORIZED")

    slot = _valid_tick_clock(_now_utc())
    bundle = await host.authorities_for_hour(slot_utc=slot)
    _check_host_bundle(bundle, slot)

    # A slow or compromised host cannot reuse the previous hour as if fresh.
    if _valid_tick_clock(_now_utc()) != slot:
        raise PermissionError("ENTERPRISE_C12_TICK_STALE_AFTER_AUTHORITY_FETCH")

    # All HMAC, source/ACL binding, freshness, revocation and replay rules
    # continue to be checked by C11 -> C10 -> C9 -> C8 -> C7 -> C6 -> C5/C1.
    return await run_revocation_gated_security_hour(
        status=bundle.status,
        trusted_status_key=bundle.trusted_status_key,
        grant=bundle.grant,
        attestation=bundle.attestation,
        isolated_dir=bundle.isolated_dir,
        slot_utc=slot,
        ledger_path=bundle.ledger_path,
        trusted_governance_key=bundle.trusted_governance_key,
        trusted_attestor_key=bundle.trusted_attestor_key,
        producer_signing_key=bundle.producer_signing_key,
        expected_rotation_epoch=bundle.expected_rotation_epoch,
        enable_security_shadow=True,
    )
