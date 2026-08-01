"""ADR-020: append-only extraction foundation.

Revision ID: 0019_adr020_extraction
Revises: 0018_adr020_acq_foundation
Create Date: 2026-08-01

Creates exactly two append-only persistence tables:
- ExtractionRun
- ExtractionResult

The migration is PostgreSQL-only and irreversible by design. It establishes
persistence and causal validation only. It does not authorize worker execution,
parsing, activation, calculation, scheduling, deployment, or production use.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0019_adr020_extraction"
down_revision: str = "0018_adr020_acq_foundation"
branch_labels = None
depends_on = None


_APPEND_ONLY_TABLES = (
    "extraction_runs",
    "extraction_results",
)


def _require_postgresql() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0019_adr020_extraction is PostgreSQL-only "
            "by ratified ADR-020. "
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

    op.create_table(
        "extraction_runs",
        sa.Column(
            "extraction_run_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column("extraction_run_id", sa.String(64), nullable=False),
        sa.Column("normative_artifact_id", sa.String(64), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("extractor_id", sa.String(255), nullable=False),
        sa.Column("extractor_version", sa.String(128), nullable=False),
        sa.Column("parameters_hash", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("run_event", sa.String(32), nullable=False),
        sa.Column("projected_state", sa.String(32), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "previous_extraction_run_record_id",
            sa.String(64),
            nullable=True,
        ),
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
            "preservation_verification_record_id",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "preservation_predecessor_type",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "preservation_predecessor_outcome",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
            ["normative_artifact_id", "artifact_hash"],
            [
                "normative_artifacts.normative_artifact_id",
                "normative_artifacts.artifact_hash",
            ],
            name="fk_extraction_runs_exact_artifact",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "extraction_run_id",
            "event_sequence",
            name="uq_extraction_runs_identity_sequence",
        ),
        sa.UniqueConstraint(
            "normative_artifact_id",
            "artifact_hash",
            "extractor_id",
            "extractor_version",
            "parameters_hash",
            "attempt_number",
            "event_sequence",
            name="uq_extraction_runs_exact_attempt_sequence",
        ),
        sa.UniqueConstraint(
            "extraction_run_record_id",
            "extraction_run_id",
            "normative_artifact_id",
            "artifact_hash",
            "attempt_number",
            name="uq_extraction_runs_record_attempt",
        ),
        sa.UniqueConstraint(
            "extraction_run_record_id",
            "extraction_run_id",
            "normative_artifact_id",
            "artifact_hash",
            "extractor_id",
            "extractor_version",
            "parameters_hash",
            "attempt_number",
            "run_event",
            "projected_state",
            name="uq_extraction_runs_exact_projection",
        ),
        sa.ForeignKeyConstraint(
            [
                "previous_extraction_run_record_id",
                "extraction_run_id",
                "normative_artifact_id",
                "artifact_hash",
                "attempt_number",
            ],
            [
                "extraction_runs.extraction_run_record_id",
                "extraction_runs.extraction_run_id",
                "extraction_runs.normative_artifact_id",
                "extraction_runs.artifact_hash",
                "extraction_runs.attempt_number",
            ],
            name="fk_extraction_runs_previous_same_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "authenticity_verification_record_id",
                "normative_artifact_id",
                "artifact_hash",
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
            name="fk_extraction_runs_authenticity_favorable",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "integrity_verification_record_id",
                "normative_artifact_id",
                "artifact_hash",
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
            name="fk_extraction_runs_integrity_favorable",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "preservation_verification_record_id",
                "normative_artifact_id",
                "artifact_hash",
                "preservation_predecessor_type",
                "preservation_predecessor_outcome",
            ],
            [
                "artifact_verification_records.artifact_verification_record_id",
                "artifact_verification_records.normative_artifact_id",
                "artifact_verification_records.verified_artifact_hash",
                "artifact_verification_records.verification_type",
                "artifact_verification_records.outcome",
            ],
            name="fk_extraction_runs_preservation_favorable",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_extraction_runs_record_hash",
        ),
        sa.CheckConstraint(
            "run_event IN "
            "('criacao', 'inicio', 'conclusao', 'falha', 'cancelamento')",
            name="ck_extraction_runs_event_valid",
        ),
        sa.CheckConstraint(
            "projected_state IN "
            "('pendente', 'em_processamento', 'concluida', "
            "'falhada', 'cancelada')",
            name="ck_extraction_runs_state_valid",
        ),
        sa.CheckConstraint(
            "(run_event = 'criacao' AND projected_state = 'pendente') "
            "OR (run_event = 'inicio' "
            "AND projected_state = 'em_processamento') "
            "OR (run_event = 'conclusao' "
            "AND projected_state = 'concluida') "
            "OR (run_event = 'falha' AND projected_state = 'falhada') "
            "OR (run_event = 'cancelamento' "
            "AND projected_state = 'cancelada')",
            name="ck_extraction_runs_event_state_pair",
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_extraction_runs_attempt_positive",
        ),
        sa.CheckConstraint(
            "event_sequence > 0",
            name="ck_extraction_runs_sequence_positive",
        ),
        sa.CheckConstraint(
            "(event_sequence = 1 "
            "AND run_event = 'criacao' "
            "AND projected_state = 'pendente' "
            "AND previous_extraction_run_record_id IS NULL) "
            "OR (event_sequence > 1 "
            "AND previous_extraction_run_record_id IS NOT NULL)",
            name="ck_extraction_runs_initial_or_predecessor",
        ),
        sa.CheckConstraint(
            "previous_extraction_run_record_id IS NULL "
            "OR previous_extraction_run_record_id "
            "<> extraction_run_record_id",
            name="ck_extraction_runs_no_self_reference",
        ),
        sa.CheckConstraint(
            "("
            "authenticity_verification_record_id IS NULL "
            "AND authenticity_predecessor_type IS NULL "
            "AND authenticity_predecessor_outcome IS NULL "
            "AND integrity_verification_record_id IS NULL "
            "AND integrity_predecessor_type IS NULL "
            "AND integrity_predecessor_outcome IS NULL "
            "AND preservation_verification_record_id IS NULL "
            "AND preservation_predecessor_type IS NULL "
            "AND preservation_predecessor_outcome IS NULL"
            ") OR ("
            "authenticity_verification_record_id IS NOT NULL "
            "AND authenticity_predecessor_type = 'authenticity' "
            "AND authenticity_predecessor_outcome "
            "= 'conclusivo_favoravel' "
            "AND integrity_verification_record_id IS NOT NULL "
            "AND integrity_predecessor_type = 'integrity' "
            "AND integrity_predecessor_outcome "
            "= 'conclusivo_favoravel' "
            "AND preservation_verification_record_id IS NOT NULL "
            "AND preservation_predecessor_type = 'preservation' "
            "AND preservation_predecessor_outcome "
            "= 'conclusivo_favoravel'"
            ")",
            name="ck_extraction_runs_favorable_gates",
        ),
        sa.CheckConstraint(
            "length(trim(extractor_id)) > 0",
            name="ck_extraction_runs_extractor_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(extractor_version)) > 0",
            name="ck_extraction_runs_version_not_empty",
        ),
        sa.CheckConstraint(
            "artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_extraction_runs_artifact_hash_sha256",
        ),
        sa.CheckConstraint(
            "parameters_hash ~ '^[0-9a-f]{64}$'",
            name="ck_extraction_runs_parameters_hash_sha256",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_extraction_runs_record_hash_sha256",
        ),
    )

    op.create_index(
        "ix_extraction_runs_extraction_run_id",
        "extraction_runs",
        ["extraction_run_id"],
    )
    op.create_index(
        "ix_extraction_runs_normative_artifact_id",
        "extraction_runs",
        ["normative_artifact_id"],
    )
    op.create_index(
        "ix_extraction_runs_artifact_hash",
        "extraction_runs",
        ["artifact_hash"],
    )
    op.create_index(
        "ix_extraction_runs_projected_state",
        "extraction_runs",
        ["projected_state"],
    )
    op.create_index(
        "ix_extraction_runs_occurred_at",
        "extraction_runs",
        ["occurred_at"],
    )

    op.create_table(
        "extraction_results",
        sa.Column(
            "extraction_result_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "extraction_run_record_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column("extraction_run_id", sa.String(64), nullable=False),
        sa.Column("normative_artifact_id", sa.String(64), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("extractor_id", sa.String(255), nullable=False),
        sa.Column("extractor_version", sa.String(128), nullable=False),
        sa.Column("parameters_hash", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "run_event",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'conclusao'"),
        ),
        sa.Column(
            "run_state",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'concluida'"),
        ),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column(
            "structured_content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "extraction_run_record_id",
                "extraction_run_id",
                "normative_artifact_id",
                "artifact_hash",
                "extractor_id",
                "extractor_version",
                "parameters_hash",
                "attempt_number",
                "run_event",
                "run_state",
            ],
            [
                "extraction_runs.extraction_run_record_id",
                "extraction_runs.extraction_run_id",
                "extraction_runs.normative_artifact_id",
                "extraction_runs.artifact_hash",
                "extraction_runs.extractor_id",
                "extraction_runs.extractor_version",
                "extraction_runs.parameters_hash",
                "extraction_runs.attempt_number",
                "extraction_runs.run_event",
                "extraction_runs.projected_state",
            ],
            name="fk_extraction_results_concluded_run",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "extraction_result_id",
            "record_hash",
            name="uq_extraction_results_identity_hash",
        ),
        sa.UniqueConstraint(
            "extraction_run_record_id",
            name="uq_extraction_results_single_per_run_completion",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_extraction_results_record_hash",
        ),
        sa.CheckConstraint(
            "run_event = 'conclusao' AND run_state = 'concluida'",
            name="ck_extraction_results_concluded_run",
        ),
        sa.CheckConstraint(
            "outcome IN ('conclusivo', 'inconclusivo', 'rejeitado')",
            name="ck_extraction_results_outcome_valid",
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_extraction_results_attempt_positive",
        ),
        sa.CheckConstraint(
            "length(trim(extractor_id)) > 0",
            name="ck_extraction_results_extractor_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(extractor_version)) > 0",
            name="ck_extraction_results_version_not_empty",
        ),
        sa.CheckConstraint(
            "artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_extraction_results_artifact_hash_sha256",
        ),
        sa.CheckConstraint(
            "parameters_hash ~ '^[0-9a-f]{64}$'",
            name="ck_extraction_results_parameters_hash_sha256",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_extraction_results_record_hash_sha256",
        ),
    )

    op.create_index(
        "ix_extraction_results_extraction_run_id",
        "extraction_results",
        ["extraction_run_id"],
    )
    op.create_index(
        "ix_extraction_results_normative_artifact_id",
        "extraction_results",
        ["normative_artifact_id"],
    )
    op.create_index(
        "ix_extraction_results_artifact_hash",
        "extraction_results",
        ["artifact_hash"],
    )
    op.create_index(
        "ix_extraction_results_outcome",
        "extraction_results",
        ["outcome"],
    )
    op.create_index(
        "ix_extraction_results_created_at",
        "extraction_results",
        ["created_at"],
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_extraction_run_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            previous_row extraction_runs%ROWTYPE;
            authenticity_time timestamptz;
            integrity_time timestamptz;
            preservation_time timestamptz;
        BEGIN
            IF NEW.event_sequence = 1 THEN
                IF NEW.run_event <> 'criacao'
                   OR NEW.projected_state <> 'pendente'
                   OR NEW.previous_extraction_run_record_id IS NOT NULL
                   OR NEW.started_at IS NOT NULL
                   OR NEW.finished_at IS NOT NULL THEN
                    RAISE EXCEPTION
                        'ADR-020 invalid initial ExtractionRun event';
                END IF;
                RETURN NEW;
            END IF;

            SELECT * INTO STRICT previous_row
            FROM extraction_runs
            WHERE extraction_run_record_id =
                  NEW.previous_extraction_run_record_id
              AND extraction_run_id = NEW.extraction_run_id
              AND normative_artifact_id = NEW.normative_artifact_id
              AND artifact_hash = NEW.artifact_hash
              AND attempt_number = NEW.attempt_number;

            IF NEW.event_sequence <> previous_row.event_sequence + 1 THEN
                RAISE EXCEPTION
                    'ADR-020 non-contiguous ExtractionRun sequence';
            END IF;

            IF NEW.occurred_at < previous_row.occurred_at THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionRun chronology regressed';
            END IF;

            IF NEW.extractor_id IS DISTINCT FROM previous_row.extractor_id
               OR NEW.extractor_version IS DISTINCT FROM
                  previous_row.extractor_version
               OR NEW.parameters_hash IS DISTINCT FROM
                  previous_row.parameters_hash
               OR (
                    previous_row.started_at IS NOT NULL
                    AND NEW.started_at IS DISTINCT FROM
                        previous_row.started_at
               ) THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionRun identity changed across events';
            END IF;

            IF NOT (
                (
                    previous_row.projected_state = 'pendente'
                    AND NEW.projected_state IN (
                        'em_processamento',
                        'cancelada'
                    )
                )
                OR
                (
                    previous_row.projected_state = 'em_processamento'
                    AND NEW.projected_state IN (
                        'concluida',
                        'falhada',
                        'cancelada'
                    )
                )
            ) THEN
                RAISE EXCEPTION
                    'ADR-020 forbidden ExtractionRun transition % -> %',
                    previous_row.projected_state,
                    NEW.projected_state;
            END IF;

            IF NEW.projected_state IN (
                'em_processamento',
                'concluida',
                'falhada'
            ) THEN
                SELECT timestamp INTO STRICT authenticity_time
                FROM artifact_verification_records
                WHERE artifact_verification_record_id =
                      NEW.authenticity_verification_record_id
                  AND normative_artifact_id =
                      NEW.normative_artifact_id
                  AND verified_artifact_hash = NEW.artifact_hash
                  AND verification_type = 'authenticity'
                  AND outcome = 'conclusivo_favoravel';

                SELECT timestamp INTO STRICT integrity_time
                FROM artifact_verification_records
                WHERE artifact_verification_record_id =
                      NEW.integrity_verification_record_id
                  AND normative_artifact_id =
                      NEW.normative_artifact_id
                  AND verified_artifact_hash = NEW.artifact_hash
                  AND verification_type = 'integrity'
                  AND outcome = 'conclusivo_favoravel'
                  AND authenticity_verification_record_id =
                      NEW.authenticity_verification_record_id;

                SELECT timestamp INTO STRICT preservation_time
                FROM artifact_verification_records
                WHERE artifact_verification_record_id =
                      NEW.preservation_verification_record_id
                  AND normative_artifact_id =
                      NEW.normative_artifact_id
                  AND verified_artifact_hash = NEW.artifact_hash
                  AND verification_type = 'preservation'
                  AND outcome = 'conclusivo_favoravel'
                  AND authenticity_verification_record_id =
                      NEW.authenticity_verification_record_id
                  AND integrity_verification_record_id =
                      NEW.integrity_verification_record_id;

                IF authenticity_time > NEW.occurred_at
                   OR integrity_time > NEW.occurred_at
                   OR preservation_time > NEW.occurred_at THEN
                    RAISE EXCEPTION
                        'ADR-020 favorable verification gates are later '
                        'than ExtractionRun event';
                END IF;
            END IF;

            IF NEW.projected_state = 'em_processamento'
               AND (
                    NEW.started_at IS NULL
                    OR NEW.finished_at IS NOT NULL
               ) THEN
                RAISE EXCEPTION
                    'ADR-020 em_processamento requires started_at only';
            END IF;

            IF NEW.started_at IS NOT NULL
               AND NEW.started_at > NEW.occurred_at THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionRun started_at cannot follow '
                    'occurred_at';
            END IF;

            IF NEW.finished_at IS NOT NULL
               AND (
                    NEW.started_at IS NOT NULL
                    AND NEW.finished_at < NEW.started_at
               ) THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionRun finished_at precedes started_at';
            END IF;

            IF NEW.finished_at IS NOT NULL
               AND NEW.finished_at > NEW.occurred_at THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionRun finished_at cannot follow '
                    'occurred_at';
            END IF;

            IF NEW.projected_state IN (
                'concluida',
                'falhada',
                'cancelada'
            ) AND NEW.finished_at IS NULL THEN
                RAISE EXCEPTION
                    'ADR-020 terminal ExtractionRun requires finished_at';
            END IF;

            IF NEW.projected_state = 'falhada'
               AND (
                    NEW.structured_error IS NULL
                    OR NEW.structured_error = '{}'::jsonb
                    OR NEW.structured_error = 'null'::jsonb
               ) THEN
                RAISE EXCEPTION
                    'ADR-020 failed ExtractionRun requires structured_error';
            END IF;

            IF previous_row.projected_state = 'pendente'
               AND NEW.projected_state = 'cancelada'
               AND NEW.started_at IS NOT NULL THEN
                RAISE EXCEPTION
                    'ADR-020 pre-start cancellation cannot invent '
                    'started_at';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionRun predecessor or favorable '
                    'verification gates not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_extraction_result()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            run_finished_at timestamptz;
        BEGIN
            SELECT finished_at INTO STRICT run_finished_at
            FROM extraction_runs
            WHERE extraction_run_record_id =
                  NEW.extraction_run_record_id
              AND extraction_run_id = NEW.extraction_run_id
              AND normative_artifact_id =
                  NEW.normative_artifact_id
              AND artifact_hash = NEW.artifact_hash
              AND extractor_id = NEW.extractor_id
              AND extractor_version = NEW.extractor_version
              AND parameters_hash = NEW.parameters_hash
              AND attempt_number = NEW.attempt_number
              AND run_event = 'conclusao'
              AND projected_state = 'concluida';

            IF NEW.run_event <> 'conclusao'
               OR NEW.run_state <> 'concluida' THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionResult requires concluded '
                    'ExtractionRun';
            END IF;

            IF NEW.structured_content IS NULL
               OR NEW.structured_content = '{}'::jsonb
               OR NEW.structured_content = '[]'::jsonb
               OR NEW.structured_content = 'null'::jsonb THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionResult requires effective structured_content';
            END IF;

            IF run_finished_at IS NULL THEN
                RAISE EXCEPTION
                    'ADR-020 concluded ExtractionRun lacks finished_at';
            END IF;

            IF NEW.created_at < run_finished_at THEN
                RAISE EXCEPTION
                    'ADR-020 ExtractionResult precedes run completion';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION
                    'ADR-020 exact concluded ExtractionRun not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_extraction_runs_validate_event
        BEFORE INSERT ON extraction_runs
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_extraction_run_event();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_extraction_results_validate_content
        BEFORE INSERT ON extraction_results
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_extraction_result();
        """
    )

    for table_name in _APPEND_ONLY_TABLES:
        _create_append_only_guards(table_name)


def downgrade() -> None:
    _require_postgresql()
    raise RuntimeError(
        "ADR-020 migration 0019 is irreversible: append-only extraction "
        "history cannot be dropped, truncated, rewritten, or downgraded "
        "destructively"
    )