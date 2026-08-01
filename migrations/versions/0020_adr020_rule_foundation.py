"""ADR-020: append-only normative rule foundation.

Revision ID: 0020_adr020_rule_foundation
Revises: 0019_adr020_extraction
Create Date: 2026-08-01

Creates exactly two append-only persistence tables:
- RuleVersion
- RuleReviewRecord

The migration is PostgreSQL-only and irreversible by design. It establishes
immutable normative content and review evidence only. It does not authorize
activation, calculation, resolver effects, workers, scheduling, or execution.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0020_adr020_rule_foundation"
down_revision: str = "0019_adr020_extraction"
branch_labels = None
depends_on = None


_APPEND_ONLY_TABLES = (
    "rule_versions",
    "rule_review_records",
)


def _require_postgresql() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0020_adr020_rule_foundation is PostgreSQL-only "
            "by ratified ADR-020. "
            f"Detected dialect: {bind.dialect.name}"
        )


def _create_append_only_guards(table_name: str) -> None:
    mutation_trigger = (
        f"trg_{table_name}_append_only_mutation"
    )
    truncate_trigger = (
        f"trg_{table_name}_append_only_truncate"
    )

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
        "rule_versions",
        sa.Column(
            "rule_version_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "rule_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "rule_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "rule_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "extraction_result_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "extraction_result_record_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "structured_content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "declared_material_validity",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "normative_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "exact_precedence_policy_reference",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "record_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            [
                "extraction_result_id",
                "extraction_result_record_hash",
            ],
            [
                "extraction_results.extraction_result_id",
                "extraction_results.record_hash",
            ],
            name="fk_rule_versions_exact_extraction_result",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "rule_id",
            "rule_version",
            name="uq_rule_versions_identity",
        ),
        sa.UniqueConstraint(
            "rule_id",
            "rule_version",
            "rule_hash",
            name="uq_rule_versions_exact_subject",
        ),
        sa.UniqueConstraint(
            "rule_hash",
            name="uq_rule_versions_rule_hash",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_rule_versions_record_hash",
        ),
        sa.CheckConstraint(
            "rule_version > 0",
            name="ck_rule_versions_version_positive",
        ),
        sa.CheckConstraint(
            "rule_hash ~ '^[0-9a-f]{64}$'",
            name="ck_rule_versions_rule_hash_sha256",
        ),
        sa.CheckConstraint(
            """
            extraction_result_record_hash
            ~ '^[0-9a-f]{64}$'
            """,
            name="ck_rule_versions_result_hash_sha256",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_rule_versions_record_hash_sha256",
        ),
    )

    op.create_index(
        "ix_rule_versions_rule_id",
        "rule_versions",
        ["rule_id"],
    )
    op.create_index(
        "ix_rule_versions_rule_hash",
        "rule_versions",
        ["rule_hash"],
    )
    op.create_index(
        "ix_rule_versions_extraction_result_id",
        "rule_versions",
        ["extraction_result_id"],
    )
    op.create_index(
        "ix_rule_versions_created_at",
        "rule_versions",
        ["created_at"],
    )

    op.create_table(
        "rule_review_records",
        sa.Column(
            "rule_review_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "subject_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "subject_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "subject_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "reviewer",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "review_event",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "record_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            [
                "subject_id",
                "subject_version",
                "subject_hash",
            ],
            [
                "rule_versions.rule_id",
                "rule_versions.rule_version",
                "rule_versions.rule_hash",
            ],
            name="fk_rule_review_records_exact_rule_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name="uq_rule_review_records_record_hash",
        ),
        sa.CheckConstraint(
            "subject_version > 0",
            name=(
                "ck_rule_review_records_"
                "subject_version_positive"
            ),
        ),
        sa.CheckConstraint(
            """
            review_event IN (
                'extracao_registada',
                'quarentena_registada',
                'validacao_iniciada',
                'revisao_reservada_iniciada',
                'revisao_concluida',
                'retirada_registada'
            )
            """,
            name="ck_rule_review_records_event_valid",
        ),
        sa.CheckConstraint(
            """
            outcome IN (
                'pendente',
                'validada',
                'rejeitada',
                'bloqueada',
                'retirada'
            )
            """,
            name="ck_rule_review_records_outcome_valid",
        ),
        sa.CheckConstraint(
            """
            (
                review_event = 'extracao_registada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'quarentena_registada'
                AND outcome IN ('pendente', 'bloqueada')
            )
            OR (
                review_event = 'validacao_iniciada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'revisao_reservada_iniciada'
                AND outcome = 'pendente'
            )
            OR (
                review_event = 'revisao_concluida'
                AND outcome IN (
                    'validada',
                    'rejeitada',
                    'bloqueada'
                )
            )
            OR (
                review_event = 'retirada_registada'
                AND outcome = 'retirada'
            )
            """,
            name="ck_rule_review_records_event_outcome_pair",
        ),
        sa.CheckConstraint(
            "length(trim(reviewer)) > 0",
            name="ck_rule_review_records_reviewer_not_empty",
        ),
        sa.CheckConstraint(
            "subject_hash ~ '^[0-9a-f]{64}$'",
            name="ck_rule_review_records_subject_hash_sha256",
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name="ck_rule_review_records_record_hash_sha256",
        ),
    )

    op.create_index(
        "ix_rule_review_records_subject_id",
        "rule_review_records",
        ["subject_id"],
    )
    op.create_index(
        "ix_rule_review_records_subject_hash",
        "rule_review_records",
        ["subject_hash"],
    )
    op.create_index(
        "ix_rule_review_records_review_event",
        "rule_review_records",
        ["review_event"],
    )
    op.create_index(
        "ix_rule_review_records_outcome",
        "rule_review_records",
        ["outcome"],
    )
    op.create_index(
        "ix_rule_review_records_timestamp",
        "rule_review_records",
        ["timestamp"],
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_rule_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            exact_result_count integer;
        BEGIN
            SELECT count(*) INTO exact_result_count
            FROM extraction_results
            WHERE extraction_result_id =
                  NEW.extraction_result_id
              AND record_hash =
                  NEW.extraction_result_record_hash;

            IF exact_result_count <> 1 THEN
                RAISE EXCEPTION
                    'ADR-020 exact ExtractionResult not found';
            END IF;

            IF NEW.structured_content IN (
                '{}'::jsonb,
                '[]'::jsonb
            ) THEN
                RAISE EXCEPTION
                    'ADR-020 RuleVersion requires '
                    'effective structured content';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_rule_review_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            rule_created_at timestamptz;
        BEGIN
            SELECT created_at INTO STRICT rule_created_at
            FROM rule_versions
            WHERE rule_id = NEW.subject_id
              AND rule_version = NEW.subject_version
              AND rule_hash = NEW.subject_hash;

            IF NEW.timestamp < rule_created_at THEN
                RAISE EXCEPTION
                    'ADR-020 RuleReviewRecord precedes '
                    'RuleVersion creation';
            END IF;

            IF NOT (
                (
                    NEW.review_event =
                        'extracao_registada'
                    AND NEW.outcome = 'pendente'
                )
                OR (
                    NEW.review_event =
                        'quarentena_registada'
                    AND NEW.outcome IN (
                        'pendente',
                        'bloqueada'
                    )
                )
                OR (
                    NEW.review_event =
                        'validacao_iniciada'
                    AND NEW.outcome = 'pendente'
                )
                OR (
                    NEW.review_event =
                        'revisao_reservada_iniciada'
                    AND NEW.outcome = 'pendente'
                )
                OR (
                    NEW.review_event =
                        'revisao_concluida'
                    AND NEW.outcome IN (
                        'validada',
                        'rejeitada',
                        'bloqueada'
                    )
                )
                OR (
                    NEW.review_event =
                        'retirada_registada'
                    AND NEW.outcome = 'retirada'
                )
            ) THEN
                RAISE EXCEPTION
                    'ADR-020 forbidden RuleReviewRecord transition: '
                    'review_event and outcome are distinct';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION
                    'ADR-020 exact RuleVersion not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_rule_versions_validate_insert
        BEFORE INSERT ON rule_versions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_rule_version();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_rule_review_records_validate_insert
        BEFORE INSERT ON rule_review_records
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_rule_review_event();
        """
    )

    for table_name in _APPEND_ONLY_TABLES:
        _create_append_only_guards(table_name)


def downgrade() -> None:
    raise RuntimeError(
        "Migration 0020_adr020_rule_foundation is irreversible "
        "by ratified ADR-020 append-only requirements"
    )
