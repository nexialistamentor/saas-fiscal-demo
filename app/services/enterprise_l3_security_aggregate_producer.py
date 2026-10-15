"""M006-C7: signed Enterprise security aggregates from an injected reader.

No reader implementation, database, raw request log, environment secret,
filesystem secret, timer, HTTP, LLM or legacy scheduler is installed here.
A separately authorised host must supply an ENTERPRISE-ISOLATED reader and
secret. Source isolation is an external prerequisite, not proved by HMAC.
"""
from __future__ import annotations

import hmac
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.agents.contracts.security_audit import SecurityAuditContext
from app.services.enterprise_l3_signed_security_trigger import (
    EnterpriseSignedSecurityWindow,
    security_window_signing_bytes,
)


class EnterpriseSecurityAggregateReport(BaseModel):
    """Closed, complete, Enterprise-only aggregate; no raw identifiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: Literal["enterprise_request_logs_isolated_v1"]
    source_scope: Literal["enterprise_only"]
    complete: Literal[True]
    window_start_utc: AwareDatetime
    window_end_utc: AwareDatetime
    collected_at_utc: AwareDatetime
    metrics: SecurityAuditContext

    @model_validator(mode="after")
    def verify_window(self) -> Self:
        for value in (
            self.window_start_utc,
            self.window_end_utc,
            self.collected_at_utc,
        ):
            if value.utcoffset() != timedelta(0):
                raise ValueError("ENTERPRISE_SECURITY_SOURCE_TIME_NOT_UTC")
        start = self.window_start_utc
        if (start.minute, start.second, start.microsecond) != (0, 0, 0):
            raise ValueError("ENTERPRISE_SECURITY_SOURCE_HOUR_INVALID")
        if self.window_end_utc != start + timedelta(hours=1):
            raise ValueError("ENTERPRISE_SECURITY_SOURCE_WINDOW_INVALID")
        if not (
            self.window_end_utc <= self.collected_at_utc
            <= self.window_end_utc + timedelta(minutes=15)
        ):
            raise ValueError("ENTERPRISE_SECURITY_SOURCE_COLLECTION_INVALID")
        return self


class EnterpriseSecurityAggregateReader(ABC):
    """Read-only integration port; host owns source isolation/authorization.

    A subclass is NOT proof that its implementation uses an isolated source.
    No implementation or source connection is provided by this package.
    """

    @abstractmethod
    async def read_hour(self, *, slot_utc: datetime) -> EnterpriseSecurityAggregateReport:
        """Return only the finalized summary for this exact UTC hour."""


async def produce_signed_security_window(
    *,
    reader: EnterpriseSecurityAggregateReader,
    slot_utc: datetime,
    produced_at_utc: datetime,
    signing_key: bytes,
    enable_security_shadow: bool = False,
) -> EnterpriseSignedSecurityWindow:
    """Sign a validated summary; never acquire source data or secrets itself.

    This is a candidate production boundary, not a deployed data collector.
    HMAC authenticates the key holder, not the correctness of the counters.
    """
    if type(enable_security_shadow) is not bool or not enable_security_shadow:
        raise PermissionError("ENTERPRISE_SECURITY_PRODUCER_NOT_AUTHORIZED")
    if type(signing_key) is not bytes or len(signing_key) < 32:
        raise PermissionError("ENTERPRISE_SECURITY_SIGNING_KEY_REQUIRED")
    if not isinstance(reader, EnterpriseSecurityAggregateReader):
        raise TypeError("ENTERPRISE_SECURITY_READER_NOT_AUTHORIZED")
    if (
        not isinstance(slot_utc, datetime)
        or slot_utc.tzinfo is None
        or slot_utc.utcoffset() != timedelta(0)
        or (slot_utc.minute, slot_utc.second, slot_utc.microsecond) != (0, 0, 0)
    ):
        raise ValueError("ENTERPRISE_SECURITY_PRODUCER_SLOT_INVALID")
    if (
        not isinstance(produced_at_utc, datetime)
        or produced_at_utc.tzinfo is None
        or produced_at_utc.utcoffset() != timedelta(0)
    ):
        raise ValueError("ENTERPRISE_SECURITY_PRODUCER_TIME_INVALID")
    window_end = slot_utc + timedelta(hours=1)
    if not (
        window_end <= produced_at_utc <= window_end + timedelta(minutes=15)
    ):
        raise PermissionError("ENTERPRISE_SECURITY_PRODUCER_WINDOW_NOT_FRESH")

    # Reader may be arbitrary host code: validate all data again, including
    # any frozen Pydantic objects modified through model_copy(update=...).
    response = await reader.read_hour(slot_utc=slot_utc)
    if type(response) is not EnterpriseSecurityAggregateReport:
        raise PermissionError("ENTERPRISE_SECURITY_SOURCE_REPORT_INVALID")
    try:
        report = EnterpriseSecurityAggregateReport.model_validate(
            response.model_dump(mode="python")
        )
    except Exception:
        raise PermissionError("ENTERPRISE_SECURITY_SOURCE_REPORT_INVALID") from None
    if (
        report.window_start_utc != slot_utc
        or report.window_end_utc != window_end
        or report.collected_at_utc > produced_at_utc
    ):
        raise PermissionError("ENTERPRISE_SECURITY_SOURCE_WINDOW_MISMATCH")

    unsigned = EnterpriseSignedSecurityWindow(
        schema_version="1.0",
        producer_id="enterprise_security_aggregator_v1",
        slot_utc=slot_utc,
        produced_at_utc=produced_at_utc,
        metrics=report.metrics,
        mac_sha256="0" * 64,
    )
    digest = hmac.new(signing_key, security_window_signing_bytes(unsigned), sha256).hexdigest()
    return EnterpriseSignedSecurityWindow.model_validate({
        **unsigned.model_dump(mode="python"),
        "mac_sha256": digest,
    })
