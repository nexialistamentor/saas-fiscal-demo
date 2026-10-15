"""M006-C8: read-only consumer of separately provisioned Enterprise hourly aggregates.

This is NOT a log collector, data producer, source attestor or periodic job.
The caller explicitly enrolls the expected source UUID and an external
snapshot directory. Only the fixed aggregate schema can be queried.
A matching manifest is not independent evidence of upstream provenance.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from app.agents.contracts.security_audit import SecurityAuditContext
from app.services.enterprise_l3_security_aggregate_producer import (
    EnterpriseSecurityAggregateReader,
    EnterpriseSecurityAggregateReport,
)


_FILENAME = "enterprise_security_aggregates.sqlite3"
_MANIFEST = "enterprise_security_manifest"
_AGGREGATES = "enterprise_security_hourly"
_COLUMNS = {
    _MANIFEST: {
        "source_id", "source_scope", "source_name", "schema_version", "complete",
    },
    _AGGREGATES: {
        "slot_utc", "window_end_utc", "collected_at_utc", "complete",
        "max_distinct_accounts_per_ip", "max_requests_per_user",
        "requests_without_user_agent",
    },
}


def _utc_hour(value: datetime) -> str:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or (value.minute, value.second, value.microsecond) != (0, 0, 0)
    ):
        raise ValueError("ENTERPRISE_C8_SLOT_NOT_UTC_HOUR")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> datetime:
    if type(value) is not str:
        raise PermissionError("ENTERPRISE_C8_SOURCE_TIME_INVALID")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        raise PermissionError("ENTERPRISE_C8_SOURCE_TIME_INVALID") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise PermissionError("ENTERPRISE_C8_SOURCE_TIME_INVALID")
    return parsed.replace(tzinfo=timezone.utc)


class EnterpriseL3IsolatedSqliteReader(EnterpriseSecurityAggregateReader):
    """Read one completed hour from an explicitly enrolled external SQLite file.

    The host must separately attest who controls the directory and producer.
    The component cannot determine who originally wrote the counters.
    """

    def __init__(self, *, isolated_dir: str | Path, expected_source_id: UUID) -> None:
        if not isinstance(isolated_dir, (Path, str)):
            raise TypeError("ENTERPRISE_C8_ISOLATED_DIR_INVALID")
        directory = Path(isolated_dir)
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError("ENTERPRISE_C8_ISOLATED_DIR_REQUIRED")
        if type(expected_source_id) is not UUID or expected_source_id.version != 4:
            raise ValueError("ENTERPRISE_C8_ENROLLED_SOURCE_REQUIRED")
        root = Path(__file__).resolve().parents[2]
        resolved_dir = directory.resolve(strict=True)
        if resolved_dir.is_relative_to(root):
            raise PermissionError("ENTERPRISE_C8_SOURCE_INSIDE_REPOSITORY")
        file_path = resolved_dir / _FILENAME
        if file_path.is_symlink() or not file_path.is_file():
            raise PermissionError("ENTERPRISE_C8_SOURCE_FILE_REQUIRED")
        if file_path.resolve(strict=True).parent != resolved_dir:
            raise PermissionError("ENTERPRISE_C8_SOURCE_PATH_ESCAPES_DIR")
        self._path = file_path
        self._source_id = str(expected_source_id)

    def _open(self) -> sqlite3.Connection:
        if self._path.is_symlink() or not self._path.is_file():
            raise PermissionError("ENTERPRISE_C8_SOURCE_FILE_REQUIRED")
        if self._path.resolve(strict=True).parent != self._path.parent:
            raise PermissionError("ENTERPRISE_C8_SOURCE_PATH_ESCAPES_DIR")
        try:
            conn = sqlite3.connect(self._path.as_uri() + "?mode=ro", uri=True, timeout=2)
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA trusted_schema=OFF")
            return conn
        except sqlite3.Error:
            raise PermissionError("ENTERPRISE_C8_SOURCE_UNREADABLE") from None

    @staticmethod
    def _verify_structure(conn: sqlite3.Connection, enrolled_id: str) -> None:
        databases = conn.execute("PRAGMA database_list").fetchall()
        if len(databases) != 1 or databases[0][1] != "main":
            raise PermissionError("ENTERPRISE_C8_SOURCE_SCOPE_INVALID")
        entries = conn.execute(
            "SELECT type, name, sql FROM main.sqlite_master "
            "WHERE type IN ('table','view','trigger')"
        ).fetchall()
        if (
            len(entries) != len(_COLUMNS)
            or {name for _, name, _ in entries} != set(_COLUMNS)
            or any(kind != "table" or not isinstance(sql, str)
                   or not sql.lstrip().upper().startswith("CREATE TABLE ")
                   for kind, _, sql in entries)
        ):
            raise PermissionError("ENTERPRISE_C8_SOURCE_SCHEMA_UNSAFE")
        for table_name, expected in _COLUMNS.items():
            cols = {row[1] for row in conn.execute(f"PRAGMA main.table_info('{table_name}')")}
            if cols != expected:
                raise PermissionError("ENTERPRISE_C8_SOURCE_COLUMNS_UNSAFE")
        manifests = conn.execute(
            "SELECT source_id, source_scope, source_name, schema_version, complete "
            "FROM main.enterprise_security_manifest LIMIT 2"
        ).fetchall()
        if len(manifests) != 1 or manifests[0] != (
            enrolled_id, "enterprise_only", "enterprise_request_logs_isolated_v1", "1.0", 1,
        ):
            raise PermissionError("ENTERPRISE_C8_SOURCE_NOT_ENROLLED")

    async def read_hour(self, *, slot_utc: datetime) -> EnterpriseSecurityAggregateReport:
        slot_text = _utc_hour(slot_utc)
        conn = self._open()
        try:
            with conn:
                self._verify_structure(conn, self._source_id)
                rows = conn.execute(
                    "SELECT window_end_utc, collected_at_utc, complete, "
                    "max_distinct_accounts_per_ip, max_requests_per_user, "
                    "requests_without_user_agent FROM main.enterprise_security_hourly "
                    "WHERE slot_utc=? LIMIT 2", (slot_text,),
                ).fetchall()
                if len(rows) != 1:
                    raise PermissionError("ENTERPRISE_C8_WINDOW_MISSING_OR_DUPLICATED")
                end, collected, complete, multi, volume, no_agent = rows[0]
                if type(complete) is not int or complete != 1:
                    raise PermissionError("ENTERPRISE_C8_WINDOW_NOT_COMPLETE")
                if any(type(c) is not int for c in (multi, volume, no_agent)):
                    raise PermissionError("ENTERPRISE_C8_METRICS_INVALID")
                try:
                    metrics = SecurityAuditContext(
                        source_kind="enterprise_aggregated_request_logs",
                        window_minutes=60,
                        max_distinct_accounts_per_ip=multi,
                        max_requests_per_user=volume,
                        requests_without_user_agent=no_agent,
                    )
                    return EnterpriseSecurityAggregateReport(
                        source_name="enterprise_request_logs_isolated_v1",
                        source_scope="enterprise_only",
                        complete=True,
                        window_start_utc=slot_utc,
                        window_end_utc=_parse_utc(end),
                        collected_at_utc=_parse_utc(collected),
                        metrics=metrics,
                    )
                except PermissionError:
                    raise
                except (ValueError, TypeError):
                    raise PermissionError("ENTERPRISE_C8_AGGREGATE_INVALID") from None
        except sqlite3.Error:
            raise PermissionError("ENTERPRISE_C8_SOURCE_QUERY_FAILED") from None
        finally:
            conn.close()
