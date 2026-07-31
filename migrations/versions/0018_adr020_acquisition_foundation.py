"""ADR-020 v0.3 R2: acquisition foundation, implementation correction R3.

Revision ID: 0018_adr020_acq_foundation
Revises: 0017_alertas_resolucao
Create Date: 2026-07-31

Creates exactly four append-only persistence tables:
- ArtifactReference
- AcquisitionExecution
- NormativeArtifact
- ArtifactVerificationRecord

The tables store immutable event/projection records. The migration is
PostgreSQL-only and irreversible by design. It does not authorize acquisition,
activation, calculation, replay, worker execution, deploy, or production.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0018_adr020_acq_foundation"
down_revision: str = "0017_alertas_resolucao"
branch_labels = None
depends_on = None


_APPEND_ONLY_TABLES = (
    "artifact_references",
    "acquisition_executions",
    "normative_artifacts",
    "artifact_verification_records",
)


def _require_postgresql() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0018_adr020_acq_foundation is PostgreSQL-only "
            "by ratified ADR-020 v0.3 R2. "
            f"Detected dialect: {bind.dialect.name}"
        )


def _create_append_only_guards(table_name: str) -> None:
    mutation_trigger = f"trg_{table_name}_append_only_mutation"
    truncate_trigger = f"trg_{table_name}_append_only_truncate"
    op.execute(
        f"""
        CREATE TRIGGER {mutation_trigger}
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION adr020_reject_append_only_mutation();
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {truncate_trigger}
        BEFORE TRUNCATE ON {table_name}
        FOR EACH STATEMENT
        EXECUTE FUNCTION adr020_reject_append_only_mutation();
        """
    )


def upgrade() -> None:
    _require_postgresql()

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "artifact_references",
        sa.Column(
            "artifact_reference_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column("artifact_reference_id", sa.String(64), nullable=False),
        sa.Column("reference_event", sa.String(32), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "previous_artifact_reference_record_id",
            sa.String(64),
            nullable=True,
        ),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("exact_locator", sa.Text(), nullable=False),
        sa.Column("official_identifier", sa.String(255), nullable=True),
        sa.Column("expected_media_type", sa.String(255), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "artifact_reference_id",
            "event_sequence",
            name="uq_artifact_references_identity_sequence",
        ),
        sa.UniqueConstraint(
            "artifact_reference_record_id",
            "artifact_reference_id",
            name="uq_artifact_references_record_identity",
        ),
        sa.ForeignKeyConstraint(
            [
                "previous_artifact_reference_record_id",
                "artifact_reference_id",
            ],
            [
                "artifact_references.artifact_reference_record_id",
                "artifact_references.artifact_reference_id",
            ],
            name="fk_artifact_references_previous_same_identity",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_artifact_references_record_hash",
        ),
        sa.CheckConstraint(
            "reference_event IN "
            "('identificada', 'agendada', 'resolvida', 'nao_resolvida')",
            name="ck_artifact_references_event_valid",
        ),
        sa.CheckConstraint(
            "event_sequence > 0",
            name="ck_artifact_references_sequence_positive",
        ),
        sa.CheckConstraint(
            "(event_sequence = 1 "
            "AND reference_event = 'identificada' "
            "AND previous_artifact_reference_record_id IS NULL) "
            "OR (event_sequence > 1 "
            "AND previous_artifact_reference_record_id IS NOT NULL)",
            name="ck_artifact_references_initial_or_predecessor",
        ),
        sa.CheckConstraint(
            "previous_artifact_reference_record_id IS NULL "
            "OR previous_artifact_reference_record_id "
            "<> artifact_reference_record_id",
            name="ck_artifact_references_no_self_reference",
        ),
        sa.CheckConstraint(
            "length(trim(source_id)) > 0",
            name="ck_artifact_references_source_id_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(exact_locator)) > 0",
            name="ck_artifact_references_locator_not_empty",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_artifact_references_record_hash_sha256",
        ),
    )
    op.create_index(
        "ix_artifact_references_artifact_reference_id",
        "artifact_references",
        ["artifact_reference_id"],
    )
    op.create_index(
        "ix_artifact_references_reference_event",
        "artifact_references",
        ["reference_event"],
    )
    op.create_index(
        "ix_artifact_references_source_id",
        "artifact_references",
        ["source_id"],
    )
    op.create_index(
        "ix_artifact_references_official_identifier",
        "artifact_references",
        ["official_identifier"],
    )
    op.create_index(
        "ix_artifact_references_occurred_at",
        "artifact_references",
        ["occurred_at"],
    )

    op.create_table(
        "acquisition_executions",
        sa.Column(
            "acquisition_execution_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column("acquisition_execution_id", sa.String(64), nullable=False),
        sa.Column("artifact_reference_record_id", sa.String(64), nullable=False),
        sa.Column("artifact_reference_id", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("execution_event", sa.String(32), nullable=False),
        sa.Column("projected_state", sa.String(32), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "previous_acquisition_execution_record_id",
            sa.String(64),
            nullable=True,
        ),
        sa.Column("actor_or_worker", sa.String(255), nullable=False),
        sa.Column("adapter_version", sa.String(128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "structured_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "structured_error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_reference_record_id", "artifact_reference_id"],
            [
                "artifact_references.artifact_reference_record_id",
                "artifact_references.artifact_reference_id",
            ],
            name="fk_acquisition_executions_exact_reference",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "acquisition_execution_id",
            "event_sequence",
            name="uq_acquisition_executions_identity_sequence",
        ),
        sa.UniqueConstraint(
            "artifact_reference_id",
            "attempt_number",
            "event_sequence",
            name="uq_acquisition_executions_reference_attempt_sequence",
        ),
        sa.UniqueConstraint(
            "acquisition_execution_record_id",
            "acquisition_execution_id",
            "artifact_reference_id",
            "attempt_number",
            name="uq_acquisition_executions_record_attempt",
        ),
        sa.UniqueConstraint(
            "acquisition_execution_record_id",
            "acquisition_execution_id",
            "artifact_reference_id",
            "attempt_number",
            "execution_event",
            "projected_state",
            name="uq_acquisition_executions_exact_projection",
        ),
        sa.ForeignKeyConstraint(
            [
                "previous_acquisition_execution_record_id",
                "acquisition_execution_id",
                "artifact_reference_id",
                "attempt_number",
            ],
            [
                "acquisition_executions.acquisition_execution_record_id",
                "acquisition_executions.acquisition_execution_id",
                "acquisition_executions.artifact_reference_id",
                "acquisition_executions.attempt_number",
            ],
            name="fk_acquisition_executions_previous_same_attempt",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_acquisition_executions_record_hash",
        ),
        sa.CheckConstraint(
            "execution_event IN "
            "('criacao', 'inicio', 'conclusao', 'conclusao_parcial', "
            "'indisponibilidade', 'falha', 'interrupcao', 'cancelamento')",
            name="ck_acquisition_executions_event_valid",
        ),
        sa.CheckConstraint(
            "projected_state IN "
            "('planeada', 'em_execucao', 'concluida', 'concluida_parcial', "
            "'indisponivel', 'falhada', 'interrompida', 'cancelada')",
            name="ck_acquisition_executions_state_valid",
        ),
        sa.CheckConstraint(
            "(execution_event = 'criacao' AND projected_state = 'planeada') "
            "OR (execution_event = 'inicio' AND projected_state = 'em_execucao') "
            "OR (execution_event = 'conclusao' AND projected_state = 'concluida') "
            "OR (execution_event = 'conclusao_parcial' "
            "AND projected_state = 'concluida_parcial') "
            "OR (execution_event = 'indisponibilidade' "
            "AND projected_state = 'indisponivel') "
            "OR (execution_event = 'falha' AND projected_state = 'falhada') "
            "OR (execution_event = 'interrupcao' "
            "AND projected_state = 'interrompida') "
            "OR (execution_event = 'cancelamento' "
            "AND projected_state = 'cancelada')",
            name="ck_acquisition_executions_event_state_pair",
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_acquisition_executions_attempt_positive",
        ),
        sa.CheckConstraint(
            "event_sequence > 0",
            name="ck_acquisition_executions_sequence_positive",
        ),
        sa.CheckConstraint(
            "(event_sequence = 1 "
            "AND execution_event = 'criacao' "
            "AND projected_state = 'planeada' "
            "AND previous_acquisition_execution_record_id IS NULL) "
            "OR (event_sequence > 1 "
            "AND previous_acquisition_execution_record_id IS NOT NULL)",
            name="ck_acquisition_executions_initial_or_predecessor",
        ),
        sa.CheckConstraint(
            "previous_acquisition_execution_record_id IS NULL "
            "OR previous_acquisition_execution_record_id "
            "<> acquisition_execution_record_id",
            name="ck_acquisition_executions_no_self_reference",
        ),
        sa.CheckConstraint(
            "length(trim(actor_or_worker)) > 0",
            name="ck_acquisition_executions_actor_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(adapter_version)) > 0",
            name="ck_acquisition_executions_adapter_not_empty",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL "
            "OR finished_at >= started_at",
            name="ck_acquisition_executions_time_order",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_acquisition_executions_record_hash_sha256",
        ),
    )
    op.create_index(
        "ix_acquisition_executions_acquisition_execution_id",
        "acquisition_executions",
        ["acquisition_execution_id"],
    )
    op.create_index(
        "ix_acquisition_executions_artifact_reference_id",
        "acquisition_executions",
        ["artifact_reference_id"],
    )
    op.create_index(
        "ix_acquisition_executions_execution_event",
        "acquisition_executions",
        ["execution_event"],
    )
    op.create_index(
        "ix_acquisition_executions_projected_state",
        "acquisition_executions",
        ["projected_state"],
    )
    op.create_index(
        "ix_acquisition_executions_occurred_at",
        "acquisition_executions",
        ["occurred_at"],
    )
    op.create_index(
        "uq_acquisition_executions_reference_attempt_initial",
        "acquisition_executions",
        ["artifact_reference_id", "attempt_number"],
        unique=True,
        postgresql_where=sa.text("event_sequence = 1"),
    )

    op.create_table(
        "normative_artifacts",
        sa.Column("normative_artifact_id", sa.String(64), primary_key=True),
        sa.Column(
            "acquisition_execution_record_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column("acquisition_execution_id", sa.String(64), nullable=False),
        sa.Column("artifact_reference_id", sa.String(64), nullable=False),
        sa.Column("acquisition_attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "acquisition_event",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'conclusao'"),
        ),
        sa.Column(
            "acquisition_state",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'concluida'"),
        ),
        sa.Column("immutable_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("immutable_location", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("media_type", sa.String(255), nullable=False),
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "acquisition_execution_record_id",
                "acquisition_execution_id",
                "artifact_reference_id",
                "acquisition_attempt_number",
                "acquisition_event",
                "acquisition_state",
            ],
            [
                "acquisition_executions.acquisition_execution_record_id",
                "acquisition_executions.acquisition_execution_id",
                "acquisition_executions.artifact_reference_id",
                "acquisition_executions.attempt_number",
                "acquisition_executions.execution_event",
                "acquisition_executions.projected_state",
            ],
            name="fk_normative_artifacts_completed_execution",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "normative_artifact_id",
            "artifact_hash",
            name="uq_normative_artifacts_identity_hash",
        ),
        sa.UniqueConstraint(
            "acquisition_execution_record_id",
            name="uq_normative_artifacts_single_per_acquisition_completion",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_normative_artifacts_record_hash",
        ),
        sa.CheckConstraint(
            "acquisition_event = 'conclusao' "
            "AND acquisition_state = 'concluida'",
            name="ck_normative_artifacts_completed_acquisition",
        ),
        sa.CheckConstraint(
            "(immutable_bytes IS NOT NULL AND immutable_location IS NULL) "
            "OR (immutable_bytes IS NULL AND immutable_location IS NOT NULL)",
            name="ck_normative_artifacts_exactly_one_storage",
        ),
        sa.CheckConstraint(
            "immutable_location IS NULL "
            "OR immutable_location ~ "
            "'^cas\\+sha256://[0-9a-f]{64}/[1-9][0-9]*$'",
            name="ck_normative_artifacts_canonical_cas_location",
        ),
        sa.CheckConstraint(
            "byte_size > 0",
            name="ck_normative_artifacts_byte_size_positive",
        ),
        sa.CheckConstraint(
            "length(trim(media_type)) > 0",
            name="ck_normative_artifacts_media_type_not_empty",
        ),
        sa.CheckConstraint(
            "artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_normative_artifacts_artifact_hash_sha256",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_normative_artifacts_record_hash_sha256",
        ),
    )
    op.create_index(
        "ix_normative_artifacts_acquisition_execution_id",
        "normative_artifacts",
        ["acquisition_execution_id"],
    )
    op.create_index(
        "ix_normative_artifacts_artifact_reference_id",
        "normative_artifacts",
        ["artifact_reference_id"],
    )
    op.create_index(
        "ix_normative_artifacts_artifact_hash",
        "normative_artifacts",
        ["artifact_hash"],
    )

    op.create_table(
        "artifact_verification_records",
        sa.Column(
            "artifact_verification_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column("normative_artifact_id", sa.String(64), nullable=False),
        sa.Column("verified_artifact_hash", sa.String(64), nullable=False),
        sa.Column("verification_type", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("verifier", sa.String(255), nullable=False),
        sa.Column("verifier_version", sa.String(128), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(64), nullable=True),
        sa.Column("previous_verification_record_id", sa.String(64), nullable=True),
        sa.Column(
            "authenticity_verification_record_id",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "authenticity_predecessor_type",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "authenticity_predecessor_outcome",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "integrity_verification_record_id",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "integrity_predecessor_type",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "integrity_predecessor_outcome",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["normative_artifact_id", "verified_artifact_hash"],
            [
                "normative_artifacts.normative_artifact_id",
                "normative_artifacts.artifact_hash",
            ],
            name="fk_artifact_verifications_artifact_hash",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "artifact_verification_record_id",
            "normative_artifact_id",
            "verified_artifact_hash",
            name="uq_artifact_verifications_identity_artifact",
        ),
        sa.UniqueConstraint(
            "artifact_verification_record_id",
            "normative_artifact_id",
            "verified_artifact_hash",
            "verification_type",
            "outcome",
            name="uq_artifact_verifications_exact_result",
        ),
        sa.ForeignKeyConstraint(
            [
                "previous_verification_record_id",
                "normative_artifact_id",
                "verified_artifact_hash",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
            ],
            name="fk_artifact_verifications_previous_same_artifact",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "authenticity_verification_record_id",
                "normative_artifact_id",
                "verified_artifact_hash",
                "authenticity_predecessor_type",
                "authenticity_predecessor_outcome",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
                "artifact_verification_records.verification_type",
                "artifact_verification_records.outcome",
            ],
            name="fk_artifact_verifications_authenticity_favorable",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "integrity_verification_record_id",
                "normative_artifact_id",
                "verified_artifact_hash",
                "integrity_predecessor_type",
                "integrity_predecessor_outcome",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
                "artifact_verification_records.verification_type",
                "artifact_verification_records.outcome",
            ],
            name="fk_artifact_verifications_integrity_favorable",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_artifact_verifications_record_hash",
        ),
        sa.CheckConstraint(
            "verification_type IN ('authenticity', 'integrity', 'preservation')",
            name="ck_artifact_verifications_type_valid",
        ),
        sa.CheckConstraint(
            "outcome IN "
            "('conclusivo_favoravel', 'conclusivo_desfavoravel', 'inconclusivo')",
            name="ck_artifact_verifications_outcome_valid",
        ),
        sa.CheckConstraint(
            "(verification_type = 'authenticity' "
            "AND authenticity_verification_record_id IS NULL "
            "AND integrity_verification_record_id IS NULL) "
            "OR (verification_type = 'integrity' "
            "AND authenticity_verification_record_id IS NOT NULL "
            "AND integrity_verification_record_id IS NULL "
            "AND previous_verification_record_id "
            "= authenticity_verification_record_id) "
            "OR (verification_type = 'preservation' "
            "AND authenticity_verification_record_id IS NOT NULL "
            "AND integrity_verification_record_id IS NOT NULL "
            "AND previous_verification_record_id "
            "= integrity_verification_record_id)",
            name="ck_artifact_verifications_cumulative_predecessors",
        ),
        sa.CheckConstraint(
            "(authenticity_verification_record_id IS NULL "
            "AND authenticity_predecessor_type IS NULL "
            "AND authenticity_predecessor_outcome IS NULL) "
            "OR (authenticity_verification_record_id IS NOT NULL "
            "AND authenticity_predecessor_type = 'authenticity' "
            "AND authenticity_predecessor_outcome = 'conclusivo_favoravel')",
            name="ck_artifact_verifications_authenticity_constants",
        ),
        sa.CheckConstraint(
            "(integrity_verification_record_id IS NULL "
            "AND integrity_predecessor_type IS NULL "
            "AND integrity_predecessor_outcome IS NULL) "
            "OR (integrity_verification_record_id IS NOT NULL "
            "AND integrity_predecessor_type = 'integrity' "
            "AND integrity_predecessor_outcome = 'conclusivo_favoravel')",
            name="ck_artifact_verifications_integrity_constants",
        ),
        sa.CheckConstraint(
            "previous_verification_record_id IS NULL "
            "OR previous_verification_record_id "
            "<> artifact_verification_record_id",
            name="ck_artifact_verifications_no_self_reference",
        ),
        sa.CheckConstraint(
            "length(trim(verifier)) > 0",
            name="ck_artifact_verifications_verifier_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(verifier_version)) > 0",
            name="ck_artifact_verifications_verifier_version_not_empty",
        ),
        sa.CheckConstraint(
            "verified_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_artifact_verifications_artifact_hash_sha256",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_artifact_verifications_record_hash_sha256",
        ),
    )
    op.create_index(
        "ix_artifact_verification_records_normative_artifact_id",
        "artifact_verification_records",
        ["normative_artifact_id"],
    )
    op.create_index(
        "ix_artifact_verification_records_verification_type",
        "artifact_verification_records",
        ["verification_type"],
    )
    op.create_index(
        "ix_artifact_verification_records_outcome",
        "artifact_verification_records",
        ["outcome"],
    )
    op.create_index(
        "ix_artifact_verification_records_timestamp",
        "artifact_verification_records",
        ["timestamp"],
    )

    op.execute(
        """
        CREATE FUNCTION adr020_reject_append_only_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'ADR-020 append-only table % does not allow %',
                TG_TABLE_NAME,
                TG_OP
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_artifact_reference_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            previous_row artifact_references%ROWTYPE;
        BEGIN
            IF NEW.discovered_at > NEW.occurred_at THEN
                RAISE EXCEPTION
                    'ADR-020 ArtifactReference discovered_at cannot follow occurred_at';
            END IF;

            IF NEW.event_sequence = 1 THEN
                IF NEW.reference_event <> 'identificada'
                   OR NEW.previous_artifact_reference_record_id IS NOT NULL THEN
                    RAISE EXCEPTION 'ADR-020 invalid initial ArtifactReference event';
                END IF;
                RETURN NEW;
            END IF;

            SELECT * INTO STRICT previous_row
            FROM artifact_references
            WHERE artifact_reference_record_id =
                  NEW.previous_artifact_reference_record_id
              AND artifact_reference_id = NEW.artifact_reference_id;

            IF NEW.event_sequence <> previous_row.event_sequence + 1 THEN
                RAISE EXCEPTION 'ADR-020 non-contiguous ArtifactReference sequence';
            END IF;

            IF NEW.occurred_at < previous_row.occurred_at THEN
                RAISE EXCEPTION 'ADR-020 ArtifactReference chronology regressed';
            END IF;

            IF NEW.source_id IS DISTINCT FROM previous_row.source_id
               OR NEW.exact_locator IS DISTINCT FROM previous_row.exact_locator
               OR NEW.official_identifier IS DISTINCT FROM previous_row.official_identifier
               OR NEW.expected_media_type IS DISTINCT FROM previous_row.expected_media_type
               OR NEW.discovered_at IS DISTINCT FROM previous_row.discovered_at THEN
                RAISE EXCEPTION 'ADR-020 ArtifactReference identity changed across events';
            END IF;

            IF NOT (
                (previous_row.reference_event = 'identificada'
                 AND NEW.reference_event IN ('agendada', 'resolvida', 'nao_resolvida'))
                OR
                (previous_row.reference_event = 'agendada'
                 AND NEW.reference_event IN ('resolvida', 'nao_resolvida'))
            ) THEN
                RAISE EXCEPTION 'ADR-020 forbidden ArtifactReference transition % -> %',
                    previous_row.reference_event,
                    NEW.reference_event;
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION 'ADR-020 ArtifactReference predecessor not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_acquisition_execution_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            previous_row acquisition_executions%ROWTYPE;
            reference_event_value text;
        BEGIN
            SELECT reference_event INTO STRICT reference_event_value
            FROM artifact_references
            WHERE artifact_reference_record_id = NEW.artifact_reference_record_id
              AND artifact_reference_id = NEW.artifact_reference_id;

            IF reference_event_value = 'nao_resolvida' THEN
                RAISE EXCEPTION 'ADR-020 unresolved reference cannot start acquisition';
            END IF;

            IF NEW.event_sequence = 1 THEN
                IF NEW.execution_event <> 'criacao'
                   OR NEW.projected_state <> 'planeada'
                   OR NEW.previous_acquisition_execution_record_id IS NOT NULL
                   OR NEW.started_at IS NOT NULL
                   OR NEW.finished_at IS NOT NULL THEN
                    RAISE EXCEPTION 'ADR-020 invalid initial AcquisitionExecution event';
                END IF;
                RETURN NEW;
            END IF;

            SELECT * INTO STRICT previous_row
            FROM acquisition_executions
            WHERE acquisition_execution_record_id =
                  NEW.previous_acquisition_execution_record_id
              AND acquisition_execution_id = NEW.acquisition_execution_id
              AND artifact_reference_id = NEW.artifact_reference_id
              AND attempt_number = NEW.attempt_number;

            IF NEW.event_sequence <> previous_row.event_sequence + 1 THEN
                RAISE EXCEPTION 'ADR-020 non-contiguous acquisition sequence';
            END IF;

            IF NEW.occurred_at < previous_row.occurred_at THEN
                RAISE EXCEPTION 'ADR-020 acquisition chronology regressed';
            END IF;

            IF NEW.artifact_reference_record_id IS DISTINCT FROM
               previous_row.artifact_reference_record_id
               OR NEW.actor_or_worker IS DISTINCT FROM previous_row.actor_or_worker
               OR NEW.adapter_version IS DISTINCT FROM previous_row.adapter_version
               OR (previous_row.started_at IS NOT NULL
                   AND NEW.started_at IS DISTINCT FROM previous_row.started_at) THEN
                RAISE EXCEPTION 'ADR-020 acquisition identity changed across events';
            END IF;

            IF NOT (
                (previous_row.projected_state = 'planeada'
                 AND NEW.projected_state IN ('em_execucao', 'cancelada'))
                OR
                (previous_row.projected_state = 'em_execucao'
                 AND NEW.projected_state IN (
                     'concluida',
                     'concluida_parcial',
                     'indisponivel',
                     'falhada',
                     'interrompida',
                     'cancelada'
                 ))
            ) THEN
                RAISE EXCEPTION 'ADR-020 forbidden acquisition transition % -> %',
                    previous_row.projected_state,
                    NEW.projected_state;
            END IF;

            IF NEW.projected_state = 'em_execucao'
               AND (NEW.started_at IS NULL OR NEW.finished_at IS NOT NULL) THEN
                RAISE EXCEPTION 'ADR-020 em_execucao requires started_at only';
            END IF;

            IF NEW.started_at IS NOT NULL
               AND NEW.started_at > NEW.occurred_at THEN
                RAISE EXCEPTION 'ADR-020 started_at cannot follow occurred_at';
            END IF;

            IF NEW.finished_at IS NOT NULL
               AND (NEW.started_at IS NULL
                    OR NEW.finished_at < NEW.started_at
                    OR NEW.finished_at > NEW.occurred_at) THEN
                RAISE EXCEPTION 'ADR-020 acquisition timestamps are not causal';
            END IF;

            IF previous_row.projected_state = 'planeada'
               AND NEW.projected_state = 'cancelada'
               AND NEW.started_at IS NOT NULL THEN
                RAISE EXCEPTION 'ADR-020 pre-start cancellation cannot invent started_at';
            END IF;

            IF NEW.projected_state = 'concluida' THEN
                IF NEW.started_at IS NULL OR NEW.finished_at IS NULL THEN
                    RAISE EXCEPTION 'ADR-020 concluded acquisition requires timestamps';
                END IF;
                IF NEW.structured_result IS NULL
                   OR NOT (NEW.structured_result @> '{"bytes_received": true}'::jsonb)
                   OR COALESCE(NEW.structured_result->>'byte_size', '') !~ '^[1-9][0-9]*$'
                   OR COALESCE(NEW.structured_result->>'artifact_hash', '')
                      !~ '^[0-9a-f]{64}$' THEN
                    RAISE EXCEPTION 'ADR-020 concluded acquisition lacks exact byte proof';
                END IF;
            ELSIF NEW.projected_state IN (
                'concluida_parcial',
                'indisponivel',
                'falhada',
                'interrompida',
                'cancelada'
            ) AND NEW.finished_at IS NULL THEN
                RAISE EXCEPTION 'ADR-020 terminal acquisition requires finished_at';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION 'ADR-020 acquisition predecessor/reference not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_normative_artifact()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            execution_result jsonb;
            execution_finished_at timestamptz;
            expected_location text;
        BEGIN
            SELECT structured_result, finished_at
            INTO STRICT execution_result, execution_finished_at
            FROM acquisition_executions
            WHERE acquisition_execution_record_id =
                  NEW.acquisition_execution_record_id
              AND acquisition_execution_id = NEW.acquisition_execution_id
              AND artifact_reference_id = NEW.artifact_reference_id
              AND attempt_number = NEW.acquisition_attempt_number
              AND execution_event = 'conclusao'
              AND projected_state = 'concluida';

            IF execution_result IS NULL
               OR execution_finished_at IS NULL
               OR NOT (execution_result @> '{"bytes_received": true}'::jsonb)
               OR COALESCE(execution_result->>'byte_size', '') !~ '^[1-9][0-9]*$'
               OR (execution_result->>'byte_size')::bigint <> NEW.byte_size
               OR lower(COALESCE(execution_result->>'artifact_hash', ''))
                  <> NEW.artifact_hash THEN
                RAISE EXCEPTION 'ADR-020 artifact diverges from concluded acquisition proof';
            END IF;

            IF NEW.acquired_at < execution_finished_at THEN
                RAISE EXCEPTION
                    'ADR-020 artifact acquired_at precedes acquisition completion';
            END IF;

            IF NEW.immutable_bytes IS NOT NULL THEN
                IF octet_length(NEW.immutable_bytes) <> NEW.byte_size THEN
                    RAISE EXCEPTION 'ADR-020 byte_size mismatch';
                END IF;
                IF encode(digest(NEW.immutable_bytes, 'sha256'), 'hex')
                   <> NEW.artifact_hash THEN
                    RAISE EXCEPTION 'ADR-020 artifact_hash mismatch';
                END IF;
            ELSE
                expected_location :=
                    'cas+sha256://' || NEW.artifact_hash || '/' || NEW.byte_size::text;
                IF NEW.immutable_location IS DISTINCT FROM expected_location THEN
                    RAISE EXCEPTION
                        'ADR-020 immutable_location is not canonical content address';
                END IF;
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION 'ADR-020 exact concluded acquisition not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_verification_order()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            artifact_acquired_at timestamptz;
            authenticity_row artifact_verification_records%ROWTYPE;
            integrity_row artifact_verification_records%ROWTYPE;
            previous_row artifact_verification_records%ROWTYPE;
        BEGIN
            SELECT acquired_at INTO STRICT artifact_acquired_at
            FROM normative_artifacts
            WHERE normative_artifact_id = NEW.normative_artifact_id
              AND artifact_hash = NEW.verified_artifact_hash;

            IF NEW.timestamp < artifact_acquired_at THEN
                RAISE EXCEPTION
                    'ADR-020 verification timestamp precedes artifact acquisition';
            END IF;

            IF NEW.previous_verification_record_id IS NOT NULL THEN
                SELECT * INTO STRICT previous_row
                FROM artifact_verification_records
                WHERE artifact_verification_record_id =
                      NEW.previous_verification_record_id
                  AND normative_artifact_id = NEW.normative_artifact_id
                  AND verified_artifact_hash = NEW.verified_artifact_hash;
                IF previous_row.timestamp > NEW.timestamp THEN
                    RAISE EXCEPTION 'ADR-020 verification predecessor is later';
                END IF;
            END IF;

            IF NEW.verification_type = 'authenticity' THEN
                IF NEW.previous_verification_record_id IS NOT NULL
                   AND previous_row.verification_type <> 'authenticity' THEN
                    RAISE EXCEPTION
                        'ADR-020 authenticity chain must follow authenticity';
                END IF;
                RETURN NEW;
            END IF;

            SELECT * INTO STRICT authenticity_row
            FROM artifact_verification_records
            WHERE artifact_verification_record_id =
                  NEW.authenticity_verification_record_id
              AND normative_artifact_id = NEW.normative_artifact_id
              AND verified_artifact_hash = NEW.verified_artifact_hash
              AND verification_type = 'authenticity'
              AND outcome = 'conclusivo_favoravel';

            IF authenticity_row.timestamp > NEW.timestamp THEN
                RAISE EXCEPTION 'ADR-020 authenticity predecessor is later';
            END IF;

            IF NEW.verification_type = 'integrity' THEN
                RETURN NEW;
            END IF;

            SELECT * INTO STRICT integrity_row
            FROM artifact_verification_records
            WHERE artifact_verification_record_id =
                  NEW.integrity_verification_record_id
              AND normative_artifact_id = NEW.normative_artifact_id
              AND verified_artifact_hash = NEW.verified_artifact_hash
              AND verification_type = 'integrity'
              AND outcome = 'conclusivo_favoravel';

            IF integrity_row.timestamp > NEW.timestamp
               OR integrity_row.authenticity_verification_record_id
                  IS DISTINCT FROM NEW.authenticity_verification_record_id THEN
                RAISE EXCEPTION
                    'ADR-020 preservation predecessors are not cumulative';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION 'ADR-020 artifact or favorable verification predecessor not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_artifact_references_validate_event
        BEFORE INSERT ON artifact_references
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_artifact_reference_event();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_acquisition_executions_validate_event
        BEFORE INSERT ON acquisition_executions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_acquisition_execution_event();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_normative_artifacts_validate_content
        BEFORE INSERT ON normative_artifacts
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_normative_artifact();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_artifact_verifications_validate_order
        BEFORE INSERT ON artifact_verification_records
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_verification_order();
        """
    )

    for table_name in _APPEND_ONLY_TABLES:
        _create_append_only_guards(table_name)


def downgrade() -> None:
    _require_postgresql()
    raise RuntimeError(
        "ADR-020 migration 0018 is irreversible: append-only normative history "
        "cannot be dropped, truncated, rewritten, or downgraded destructively"
    )
