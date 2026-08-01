"""ADR-020: append-only normative relation foundation.

Revision ID: 0021_adr020_relation_foundation
Revises: 0020_adr020_rule_foundation
Create Date: 2026-08-01

Creates exactly:
- NormativeRelationVersion
- RelationReviewRecord

This PostgreSQL-only migration records immutable relational content and
review evidence. It does not authorize activation, calculation, resolver
effects, operational precedence, workers, scheduling, or execution.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0021_adr020_relation_foundation"
down_revision: str = "0020_adr020_rule_foundation"
branch_labels = None
depends_on = None


_APPEND_ONLY_TABLES = (
    "normative_relation_versions",
    "relation_review_records",
)


def _require_postgresql() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0021_adr020_relation_foundation is "
            "PostgreSQL-only by ratified ADR-020. "
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
        "normative_relation_versions",
        sa.Column(
            "normative_relation_version_record_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "normative_relation_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "normative_relation_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "normative_relation_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "source_subject_type",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "source_subject_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "source_subject_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source_subject_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "target_subject_type",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "target_subject_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "target_subject_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "target_subject_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "relation_type",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "declared_material_validity",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
        sa.UniqueConstraint(
            "normative_relation_id",
            "normative_relation_version",
            name="uq_normative_relation_versions_identity",
        ),
        sa.UniqueConstraint(
            "normative_relation_id",
            "normative_relation_version",
            "normative_relation_hash",
            name=(
                "uq_normative_relation_versions_"
                "exact_subject"
            ),
        ),
        sa.UniqueConstraint(
            "normative_relation_hash",
            name=(
                "uq_normative_relation_versions_"
                "relation_hash"
            ),
        ),
        sa.UniqueConstraint(
            "record_hash",
            name=(
                "uq_normative_relation_versions_"
                "record_hash"
            ),
        ),
        sa.CheckConstraint(
            "normative_relation_version > 0",
            name=(
                "ck_normative_relation_versions_"
                "version_positive"
            ),
        ),
        sa.CheckConstraint(
            "source_subject_version > 0",
            name=(
                "ck_normative_relation_versions_"
                "source_version_positive"
            ),
        ),
        sa.CheckConstraint(
            "target_subject_version > 0",
            name=(
                "ck_normative_relation_versions_"
                "target_version_positive"
            ),
        ),
        sa.CheckConstraint(
            """
            relation_type IN (
                'rectifica',
                'republica',
                'altera',
                'substitui',
                'revoga',
                'complementa',
                'referencia',
                'sucede'
            )
            """,
            name=(
                "ck_normative_relation_versions_"
                "relation_type_valid"
            ),
        ),
        sa.CheckConstraint(
            "normative_relation_hash ~ '^[0-9a-f]{64}$'",
            name=(
                "ck_normative_relation_versions_"
                "relation_hash_sha256"
            ),
        ),
        sa.CheckConstraint(
            "source_subject_hash ~ '^[0-9a-f]{64}$'",
            name=(
                "ck_normative_relation_versions_"
                "source_hash_sha256"
            ),
        ),
        sa.CheckConstraint(
            "target_subject_hash ~ '^[0-9a-f]{64}$'",
            name=(
                "ck_normative_relation_versions_"
                "target_hash_sha256"
            ),
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name=(
                "ck_normative_relation_versions_"
                "record_hash_sha256"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(source_subject_type)) > 0",
            name=(
                "ck_normative_relation_versions_"
                "source_type_not_empty"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(source_subject_id)) > 0",
            name=(
                "ck_normative_relation_versions_"
                "source_id_not_empty"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(target_subject_type)) > 0",
            name=(
                "ck_normative_relation_versions_"
                "target_type_not_empty"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(target_subject_id)) > 0",
            name=(
                "ck_normative_relation_versions_"
                "target_id_not_empty"
            ),
        ),
    )

    op.create_index(
        "ix_normative_relation_versions_relation_id",
        "normative_relation_versions",
        ["normative_relation_id"],
    )
    op.create_index(
        "ix_normative_relation_versions_relation_hash",
        "normative_relation_versions",
        ["normative_relation_hash"],
    )
    op.create_index(
        "ix_normative_relation_versions_source_subject",
        "normative_relation_versions",
        [
            "source_subject_type",
            "source_subject_id",
            "source_subject_version",
        ],
    )
    op.create_index(
        "ix_normative_relation_versions_target_subject",
        "normative_relation_versions",
        [
            "target_subject_type",
            "target_subject_id",
            "target_subject_version",
        ],
    )
    op.create_index(
        "ix_normative_relation_versions_relation_type",
        "normative_relation_versions",
        ["relation_type"],
    )
    op.create_index(
        "ix_normative_relation_versions_created_at",
        "normative_relation_versions",
        ["created_at"],
    )

    op.create_table(
        "relation_review_records",
        sa.Column(
            "relation_review_record_id",
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
                (
                    "normative_relation_versions."
                    "normative_relation_id"
                ),
                (
                    "normative_relation_versions."
                    "normative_relation_version"
                ),
                (
                    "normative_relation_versions."
                    "normative_relation_hash"
                ),
            ],
            name="fk_relation_review_records_exact_relation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "record_hash",
            name=(
                "uq_relation_review_records_"
                "record_hash"
            ),
        ),
        sa.CheckConstraint(
            "subject_version > 0",
            name=(
                "ck_relation_review_records_"
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
            name=(
                "ck_relation_review_records_"
                "event_valid"
            ),
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
            name=(
                "ck_relation_review_records_"
                "outcome_valid"
            ),
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
                review_event =
                    'revisao_reservada_iniciada'
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
            name=(
                "ck_relation_review_records_"
                "event_outcome_pair"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(subject_id)) > 0",
            name=(
                "ck_relation_review_records_"
                "subject_id_not_empty"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(reviewer)) > 0",
            name=(
                "ck_relation_review_records_"
                "reviewer_not_empty"
            ),
        ),
        sa.CheckConstraint(
            "subject_hash ~ '^[0-9a-f]{64}$'",
            name=(
                "ck_relation_review_records_"
                "subject_hash_sha256"
            ),
        ),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'",
            name=(
                "ck_relation_review_records_"
                "record_hash_sha256"
            ),
        ),
    )

    op.create_index(
        "ix_relation_review_records_subject",
        "relation_review_records",
        [
            "subject_id",
            "subject_version",
            "subject_hash",
        ],
    )
    op.create_index(
        "ix_relation_review_records_review_event",
        "relation_review_records",
        ["review_event"],
    )
    op.create_index(
        "ix_relation_review_records_outcome",
        "relation_review_records",
        ["outcome"],
    )
    op.create_index(
        "ix_relation_review_records_timestamp",
        "relation_review_records",
        ["timestamp"],
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_normative_relation_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.structured_content IN (
                '{}'::jsonb,
                '[]'::jsonb
            ) THEN
                RAISE EXCEPTION
                    'ADR-020 NormativeRelationVersion '
                    'requires effective structured content';
            END IF;

            IF NEW.declared_material_validity IS NULL
               OR NEW.normative_references IS NULL
               OR NEW.exact_precedence_policy_reference IS NULL
               OR NEW.evidence IS NULL
               OR NEW.provenance IS NULL
            THEN
                RAISE EXCEPTION
                    'ADR-020 NormativeRelationVersion '
                    'requires complete immutable content';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_relation_review_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            relation_created_at timestamptz;
        BEGIN
            SELECT created_at INTO STRICT relation_created_at
            FROM normative_relation_versions
            WHERE normative_relation_id = NEW.subject_id
              AND normative_relation_version =
                  NEW.subject_version
              AND normative_relation_hash =
                  NEW.subject_hash;

            IF NEW.timestamp < relation_created_at THEN
                RAISE EXCEPTION
                    'ADR-020 RelationReviewRecord precedes '
                    'NormativeRelationVersion creation';
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
                    'ADR-020 forbidden RelationReviewRecord transition: '
                    'review_event and outcome are distinct';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION
                    'ADR-020 exact NormativeRelationVersion '
                    'not found';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER
            trg_normative_relation_versions_validate_insert
        BEFORE INSERT ON normative_relation_versions
        FOR EACH ROW
        EXECUTE FUNCTION
            adr020_validate_normative_relation_version();
        """
    )

    op.execute(
        """
        CREATE TRIGGER
            trg_relation_review_records_validate_insert
        BEFORE INSERT ON relation_review_records
        FOR EACH ROW
        EXECUTE FUNCTION
            adr020_validate_relation_review_event();
        """
    )

    for table_name in _APPEND_ONLY_TABLES:
        _create_append_only_guards(table_name)


def downgrade() -> None:
    raise RuntimeError(
        "Migration 0021_adr020_relation_foundation is irreversible "
        "by ratified ADR-020 append-only requirements"
    )
