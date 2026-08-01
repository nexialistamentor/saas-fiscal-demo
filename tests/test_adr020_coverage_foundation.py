"""Commit 6 contract: immutable ADR-020 coverage foundation."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import re

import pytest
import sqlalchemy as sa
from sqlalchemy import event

import app.models as models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0023_adr020_coverage_foundation.py"


def _columns(model):
    return set(model.__table__.columns.keys())


def _checks(model):
    return " ".join(
        str(item.sqltext) for item in model.__table__.constraints
        if isinstance(item, sa.CheckConstraint)
    ).lower()


def _foreign_keys(model):
    return {
        item.name for item in model.__table__.constraints
        if isinstance(item, sa.ForeignKeyConstraint)
    }


def _source():
    return MIGRATION.read_text(encoding="utf-8")


def test_exact_models_and_tables_exist():
    assert models.CoverageContract.__tablename__ == "coverage_contracts"
    assert models.CoverageLedgerEntry.__tablename__ == "coverage_ledger_entries"
    assert models.CoverageCheckpointRecord.__tablename__ == "coverage_checkpoint_records"


def test_contract_is_physical_versioned_content_addressed_and_non_authoritative():
    fields = _columns(models.CoverageContract)
    required = {
        "coverage_contract_record_id", "coverage_contract_id", "source_id",
        "contract_version", "contract_hash", "contract_state",
        "effective_from", "effective_to", "timezone", "expected_calendar",
        "publication_schedule", "delay_windows", "mandatory_sections",
        "expected_files_partitions", "pagination", "cursors",
        "empty_response_semantics", "proven_absence_rules",
        "authorized_redirects", "media_types", "adapter_id",
        "compatible_adapter_versions", "technical_limits", "retry_policy",
        "continuity_policy_reference", "evidence", "audit", "ratification",
        "revocation", "created_at", "record_hash",
    }
    assert required == fields
    assert not issubclass(models.CoverageContract, models.PolicyVersion)
    assert {"active", "authority", "authorization", "operational_authority"}.isdisjoint(fields)
    uniques = {
        item.name for item in models.CoverageContract.__table__.constraints
        if isinstance(item, sa.UniqueConstraint)
    }
    assert {"uq_coverage_contracts_identity", "uq_coverage_contracts_exact_subject", "uq_coverage_contracts_contract_hash", "uq_coverage_contracts_record_hash"} <= uniques


def test_ledger_preserves_each_exact_unit_order_window_contract_and_fence():
    fields = _columns(models.CoverageLedgerEntry)
    assert {"coverage_ledger_entry_id", "coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", "unit_type", "unit_id", "unit_order", "observation_outcome", "processing_outcome", "coverage_outcome", "fencing_token", "evidence", "provenance", "record_hash"} <= fields
    assert "fk_coverage_ledger_entries_exact_contract" in _foreign_keys(models.CoverageLedgerEntry)
    unique_names = {
        item.name for item in models.CoverageLedgerEntry.__table__.constraints
        if isinstance(item, sa.UniqueConstraint)
    }
    assert "uq_coverage_ledger_entries_unit_order" in unique_names
    checks = _checks(models.CoverageLedgerEntry)
    for value in ("publication", "section", "page", "file", "partition", "period", "succeeded", "failed", "proven_absence", "gap", "covered"):
        assert value in checks


def test_checkpoints_are_independent_snapshots_with_exact_links():
    fields = _columns(models.CoverageCheckpointRecord)
    assert {"observed_through", "completed_through", "covered_through", "pending_gap_from", "last_ledger_entry_id", "checkpoint_sequence", "fencing_token"} <= fields
    assert {"fk_coverage_checkpoint_records_exact_contract", "fk_coverage_checkpoint_records_exact_last_entry"} <= _foreign_keys(models.CoverageCheckpointRecord)
    assert "state" not in fields and "current" not in fields


def _ledger(**overrides):
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    values = dict(
        coverage_ledger_entry_id="entry", coverage_contract_id="contract",
        contract_version=1, contract_hash="a" * 64, window_start=start,
        window_end=start + timedelta(days=1), unit_type="page", unit_id="page-1",
        unit_order=1, observation_outcome="observed",
        processing_outcome="succeeded", coverage_outcome="covered",
        response_kind="non_empty", cycle_fully_evaluated=False, fencing_token=1,
        evidence={"exact": True}, provenance={"exact": True}, record_hash="b" * 64,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _checkpoint(**overrides):
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    values = dict(
        coverage_checkpoint_record_id="checkpoint", coverage_contract_id="contract",
        contract_version=1, contract_hash="a" * 64, window_start=start,
        window_end=start + timedelta(days=1), checkpoint_sequence=1,
        observed_through=3, completed_through=2, covered_through=1,
        pending_gap_from=2, cycle_fully_evaluated=False,
        last_ledger_entry_id="entry", fencing_token=1,
        evidence={"exact": True}, provenance={"exact": True}, record_hash="b" * 64,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_failure_is_preserved_but_never_promoted_to_coverage():
    with pytest.raises(ValueError, match="cannot be promoted"):
        models._adr020_validate_coverage_ledger_insert(
            None, None, _ledger(processing_outcome="failed")
        )
    models._adr020_validate_coverage_ledger_insert(
        None, None, _ledger(processing_outcome="failed", coverage_outcome="not_covered")
    )


def test_empty_response_does_not_close_coverage_without_integral_cycle():
    with pytest.raises(ValueError, match="integral completed cycle"):
        models._adr020_validate_coverage_ledger_insert(
            None, None, _ledger(response_kind="empty")
        )
    models._adr020_validate_coverage_ledger_insert(
        None, None, _ledger(response_kind="empty", cycle_fully_evaluated=True)
    )


def test_coverage_is_contiguous_and_first_gap_is_explicit():
    models._adr020_validate_coverage_checkpoint_insert(None, None, _checkpoint())
    with pytest.raises(ValueError, match="first contiguous gap"):
        models._adr020_validate_coverage_checkpoint_insert(
            None, None, _checkpoint(pending_gap_from=3)
        )
    with pytest.raises(ValueError, match="exceeds completed"):
        models._adr020_validate_coverage_checkpoint_insert(
            None, None, _checkpoint(covered_through=3, pending_gap_from=4)
        )


def test_no_gap_requires_the_same_window_to_be_fully_evaluated():
    with pytest.raises(ValueError, match="integral evaluated cycle"):
        models._adr020_validate_coverage_checkpoint_insert(
            None, None, _checkpoint(pending_gap_from=None)
        )
    models._adr020_validate_coverage_checkpoint_insert(
        None, None, _checkpoint(pending_gap_from=None, cycle_fully_evaluated=True)
    )


def test_all_three_models_are_append_only():
    guard = models._adr020_reject_append_only_mutation
    for model in (models.CoverageContract, models.CoverageLedgerEntry, models.CoverageCheckpointRecord):
        assert event.contains(model, "before_update", guard)
        assert event.contains(model, "before_delete", guard)


def test_migration_lineage_postgresql_jsonb_constraints_and_guards():
    source = _source()
    lowered = source.lower()
    assert 'revision: str = "0023_adr020_coverage"' in source
    assert 'down_revision: str = "0022_adr020_policy"' in source
    assert re.findall(r'op\.create_table\(\s*["\']([^"\']+)', source) == [
        "coverage_contracts", "coverage_ledger_entries", "coverage_checkpoint_records"
    ]
    for fragment in ("postgresql-only", "jsonb", "exact_contract", "exact_last_entry", "unit_order", "fencing_token", "failure cannot be promoted", "implicit contract or window switch forbidden", "before update or delete", "before truncate"):
        assert fragment in lowered
    assert "irreversible" in lowered and "raise runtimeerror" in lowered
    assert "op.drop_table" not in lowered


def test_later_commit_entities_are_absent():
    source = (_source() + Path(models.__file__).read_text(encoding="utf-8")).lower()
    for entity in (
        "CalculationBundle",
        "CalculationExecutionRecord",
        "CalculationResultRecord",
        "ReplayExecutionRecord",
        "ReplayVerificationRecord",
    ):
        assert not hasattr(models, entity)
        assert not re.search(rf"class\s+{entity}\b", source, re.IGNORECASE)
