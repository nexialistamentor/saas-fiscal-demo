"""ADR-020: immutable coverage contract, ledger and checkpoints.

Revision ID: 0023_adr020_coverage
Revises: 0022_adr020_policy
Create Date: 2026-08-01

PostgreSQL-only. These records preserve evidence and grant no operational
or fiscal authority.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0023_adr020_coverage"
down_revision: str = "0022_adr020_policy"
branch_labels = None
depends_on = None

_APPEND_ONLY_TABLES = (
    "coverage_contracts",
    "coverage_ledger_entries",
    "coverage_checkpoint_records",
)


def _require_postgresql() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0023_adr020_coverage is PostgreSQL-only by ratified "
            f"ADR-020. Detected dialect: {bind.dialect.name}"
        )


def _jsonb(name: str) -> sa.Column:
    return sa.Column(
        name, postgresql.JSONB(astext_type=sa.Text()), nullable=False
    )


def _append_only(table_name: str) -> None:
    op.execute(f"""
        CREATE TRIGGER trg_{table_name}_append_only_mutation
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION adr020_reject_append_only_mutation();
    """)
    op.execute(f"""
        CREATE TRIGGER trg_{table_name}_append_only_truncate
        BEFORE TRUNCATE ON {table_name}
        FOR EACH STATEMENT EXECUTE FUNCTION adr020_reject_append_only_mutation();
    """)


def upgrade() -> None:
    _require_postgresql()

    op.create_table(
        "coverage_contracts",
        sa.Column("coverage_contract_record_id", sa.String(64), primary_key=True),
        sa.Column("coverage_contract_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("contract_state", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        _jsonb("expected_calendar"),
        _jsonb("publication_schedule"),
        _jsonb("delay_windows"),
        _jsonb("mandatory_sections"),
        _jsonb("expected_files_partitions"),
        _jsonb("pagination"),
        _jsonb("cursors"),
        _jsonb("empty_response_semantics"),
        _jsonb("proven_absence_rules"),
        _jsonb("authorized_redirects"),
        _jsonb("media_types"),
        sa.Column("adapter_id", sa.String(64), nullable=False),
        _jsonb("compatible_adapter_versions"),
        _jsonb("technical_limits"),
        _jsonb("retry_policy"),
        _jsonb("continuity_policy_reference"),
        _jsonb("evidence"),
        _jsonb("audit"),
        _jsonb("ratification"),
        _jsonb("revocation"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("coverage_contract_id", "contract_version", name="uq_coverage_contracts_identity"),
        sa.UniqueConstraint("coverage_contract_id", "contract_version", "contract_hash", name="uq_coverage_contracts_exact_subject"),
        sa.UniqueConstraint("contract_hash", name="uq_coverage_contracts_contract_hash"),
        sa.UniqueConstraint("record_hash", name="uq_coverage_contracts_record_hash"),
        sa.CheckConstraint("contract_version > 0", name="ck_coverage_contracts_version_positive"),
        sa.CheckConstraint("contract_state IN ('proposta', 'auditada', 'ratificada', 'revogada')", name="ck_coverage_contracts_state_valid"),
        sa.CheckConstraint("contract_hash ~ '^[0-9a-f]{64}$' AND record_hash ~ '^[0-9a-f]{64}$'", name="ck_coverage_contracts_hashes_sha256"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_coverage_contracts_validity_order"),
        sa.CheckConstraint("length(trim(coverage_contract_id)) > 0 AND length(trim(source_id)) > 0 AND length(trim(timezone)) > 0 AND length(trim(adapter_id)) > 0", name="ck_coverage_contracts_identity_not_empty"),
    )

    op.create_table(
        "coverage_ledger_entries",
        sa.Column("coverage_ledger_entry_id", sa.String(64), primary_key=True),
        sa.Column("coverage_contract_id", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit_type", sa.String(16), nullable=False),
        sa.Column("unit_id", sa.String(255), nullable=False),
        sa.Column("unit_order", sa.Integer(), nullable=False),
        sa.Column("observation_outcome", sa.String(32), nullable=False),
        sa.Column("processing_outcome", sa.String(32), nullable=False),
        sa.Column("coverage_outcome", sa.String(16), nullable=False),
        sa.Column("response_kind", sa.String(16), nullable=False),
        sa.Column("cycle_fully_evaluated", sa.Boolean(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        _jsonb("evidence"),
        _jsonb("provenance"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["coverage_contract_id", "contract_version", "contract_hash"], ["coverage_contracts.coverage_contract_id", "coverage_contracts.contract_version", "coverage_contracts.contract_hash"], name="fk_coverage_ledger_entries_exact_contract", ondelete="RESTRICT"),
        sa.UniqueConstraint("coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", "unit_order", name="uq_coverage_ledger_entries_unit_order"),
        sa.UniqueConstraint("coverage_ledger_entry_id", "coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", name="uq_coverage_ledger_entries_exact_checkpoint_target"),
        sa.UniqueConstraint("record_hash", name="uq_coverage_ledger_entries_record_hash"),
        sa.CheckConstraint("contract_version > 0 AND unit_order > 0 AND fencing_token > 0", name="ck_coverage_ledger_entries_positive_order_fence"),
        sa.CheckConstraint("window_end > window_start", name="ck_coverage_ledger_entries_window_order"),
        sa.CheckConstraint("unit_type IN ('publication', 'section', 'page', 'file', 'partition', 'period')", name="ck_coverage_ledger_entries_unit_type_valid"),
        sa.CheckConstraint("observation_outcome IN ('observed', 'not_observed', 'source_unavailable')", name="ck_coverage_ledger_entries_observation_valid"),
        sa.CheckConstraint("processing_outcome IN ('pending', 'succeeded', 'failed', 'proven_absence')", name="ck_coverage_ledger_entries_processing_valid"),
        sa.CheckConstraint("coverage_outcome IN ('covered', 'gap', 'not_covered')", name="ck_coverage_ledger_entries_coverage_valid"),
        sa.CheckConstraint("response_kind IN ('non_empty', 'empty', 'not_applicable')", name="ck_coverage_ledger_entries_response_kind_valid"),
        sa.CheckConstraint("coverage_outcome <> 'covered' OR processing_outcome IN ('succeeded', 'proven_absence')", name="ck_coverage_ledger_entries_failure_not_covered"),
        sa.CheckConstraint("response_kind <> 'empty' OR coverage_outcome <> 'covered' OR cycle_fully_evaluated", name="ck_coverage_ledger_entries_empty_requires_full_cycle"),
        sa.CheckConstraint("contract_hash ~ '^[0-9a-f]{64}$' AND record_hash ~ '^[0-9a-f]{64}$'", name="ck_coverage_ledger_entries_hashes_sha256"),
    )

    op.create_table(
        "coverage_checkpoint_records",
        sa.Column("coverage_checkpoint_record_id", sa.String(64), primary_key=True),
        sa.Column("coverage_contract_id", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkpoint_sequence", sa.Integer(), nullable=False),
        sa.Column("observed_through", sa.Integer(), nullable=True),
        sa.Column("completed_through", sa.Integer(), nullable=True),
        sa.Column("covered_through", sa.Integer(), nullable=True),
        sa.Column("pending_gap_from", sa.Integer(), nullable=True),
        sa.Column("cycle_fully_evaluated", sa.Boolean(), nullable=False),
        sa.Column("last_ledger_entry_id", sa.String(64), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        _jsonb("evidence"),
        _jsonb("provenance"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["coverage_contract_id", "contract_version", "contract_hash"], ["coverage_contracts.coverage_contract_id", "coverage_contracts.contract_version", "coverage_contracts.contract_hash"], name="fk_coverage_checkpoint_records_exact_contract", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["last_ledger_entry_id", "coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end"], ["coverage_ledger_entries.coverage_ledger_entry_id", "coverage_ledger_entries.coverage_contract_id", "coverage_ledger_entries.contract_version", "coverage_ledger_entries.contract_hash", "coverage_ledger_entries.window_start", "coverage_ledger_entries.window_end"], name="fk_coverage_checkpoint_records_exact_last_entry", ondelete="RESTRICT"),
        sa.UniqueConstraint("coverage_contract_id", "contract_version", "contract_hash", "window_start", "window_end", "checkpoint_sequence", name="uq_coverage_checkpoint_records_sequence"),
        sa.UniqueConstraint("record_hash", name="uq_coverage_checkpoint_records_record_hash"),
        sa.CheckConstraint("contract_version > 0 AND checkpoint_sequence > 0 AND fencing_token > 0", name="ck_coverage_checkpoint_records_positive_sequence_fence"),
        sa.CheckConstraint("window_end > window_start", name="ck_coverage_checkpoint_records_window_order"),
        sa.CheckConstraint("observed_through IS NULL OR observed_through > 0", name="ck_coverage_checkpoint_records_observed_positive"),
        sa.CheckConstraint("completed_through IS NULL OR completed_through > 0", name="ck_coverage_checkpoint_records_completed_positive"),
        sa.CheckConstraint("covered_through IS NULL OR covered_through > 0", name="ck_coverage_checkpoint_records_covered_positive"),
        sa.CheckConstraint("pending_gap_from IS NULL OR pending_gap_from > 0", name="ck_coverage_checkpoint_records_gap_positive"),
        sa.CheckConstraint("completed_through IS NULL OR observed_through IS NOT NULL AND completed_through <= observed_through", name="ck_coverage_checkpoint_records_completed_within_observed"),
        sa.CheckConstraint("covered_through IS NULL OR completed_through IS NOT NULL AND covered_through <= completed_through", name="ck_coverage_checkpoint_records_covered_within_completed"),
        sa.CheckConstraint("pending_gap_from IS NULL OR pending_gap_from = COALESCE(covered_through, 0) + 1", name="ck_coverage_checkpoint_records_first_gap"),
        sa.CheckConstraint("pending_gap_from IS NOT NULL OR cycle_fully_evaluated", name="ck_coverage_checkpoint_records_no_gap_requires_full_cycle"),
        sa.CheckConstraint("contract_hash ~ '^[0-9a-f]{64}$' AND record_hash ~ '^[0-9a-f]{64}$'", name="ck_coverage_checkpoint_records_hashes_sha256"),
    )

    op.execute("""
        CREATE FUNCTION adr020_validate_coverage_ledger_entry() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.coverage_outcome = 'covered'
               AND NEW.processing_outcome NOT IN ('succeeded', 'proven_absence') THEN
                RAISE EXCEPTION 'ADR-020 failure cannot be promoted to coverage';
            END IF;
            IF NEW.response_kind = 'empty' AND NEW.coverage_outcome = 'covered'
               AND NOT NEW.cycle_fully_evaluated THEN
                RAISE EXCEPTION 'ADR-020 empty response does not close coverage without integral cycle';
            END IF;
            RETURN NEW;
        END; $$;
    """)
    op.execute("""
        CREATE FUNCTION adr020_validate_coverage_checkpoint() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE last_entry coverage_ledger_entries%ROWTYPE;
        BEGIN
            SELECT * INTO STRICT last_entry FROM coverage_ledger_entries
             WHERE coverage_ledger_entry_id = NEW.last_ledger_entry_id;
            IF (last_entry.coverage_contract_id, last_entry.contract_version,
                last_entry.contract_hash, last_entry.window_start, last_entry.window_end)
               IS DISTINCT FROM
                (NEW.coverage_contract_id, NEW.contract_version,
                 NEW.contract_hash, NEW.window_start, NEW.window_end) THEN
                RAISE EXCEPTION 'ADR-020 implicit contract or window switch forbidden';
            END IF;
            IF NEW.fencing_token < last_entry.fencing_token THEN
                RAISE EXCEPTION 'ADR-020 stale checkpoint fencing token';
            END IF;
            RETURN NEW;
        EXCEPTION WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'ADR-020 exact last coverage ledger entry not found';
        END; $$;
    """)
    op.execute("CREATE TRIGGER trg_coverage_ledger_entries_validate_insert BEFORE INSERT ON coverage_ledger_entries FOR EACH ROW EXECUTE FUNCTION adr020_validate_coverage_ledger_entry();")
    op.execute("CREATE TRIGGER trg_coverage_checkpoint_records_validate_insert BEFORE INSERT ON coverage_checkpoint_records FOR EACH ROW EXECUTE FUNCTION adr020_validate_coverage_checkpoint();")
    for table_name in _APPEND_ONLY_TABLES:
        _append_only(table_name)


def downgrade() -> None:
    raise RuntimeError(
        "Migration 0023_adr020_coverage is irreversible by ratified ADR-020 "
        "append-only requirements"
    )
