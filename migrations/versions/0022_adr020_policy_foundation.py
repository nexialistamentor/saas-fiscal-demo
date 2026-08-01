"""ADR-020: immutable institutional policy authority foundation.

Revision ID: 0022_adr020_policy
Revises: 0021_adr020_relation_foundation
Create Date: 2026-08-01

Creates exactly PolicyVersion, PolicyDecision and BootstrapAuthorityRecord.
This PostgreSQL-only migration does not authorize activation, automation,
calculation, workers, scheduling, deploy or production.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0022_adr020_policy"
down_revision: str = "0021_adr020_relation_foundation"
branch_labels = None
depends_on = None

_POLICY_TYPES = "'activation_authority', 'automation_envelope', 'normative_precedence', 'normative_continuity', 'coverage_contract'"
_APPEND_ONLY_TABLES = ("policy_versions", "policy_decisions", "bootstrap_authority_records")


def _require_postgresql() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0022_adr020_policy is PostgreSQL-only by ratified ADR-020. "
            f"Detected dialect: {bind.dialect.name}"
        )


def _jsonb(name: str) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=False)


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
        "policy_versions",
        sa.Column("policy_version_record_id", sa.String(64), primary_key=True),
        sa.Column("policy_type", sa.String(32), nullable=False),
        sa.Column("policy_id", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        _jsonb("scope"), _jsonb("declared_material_applicability"),
        _jsonb("modalities"), _jsonb("permitted_authorization_classes"),
        _jsonb("permitted_execution_modes"), _jsonb("gates"),
        _jsonb("roles"), _jsonb("segregation_of_duties"),
        _jsonb("limits"), _jsonb("rules"), _jsonb("exact_references"),
        _jsonb("origin_evidence"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("policy_id", "policy_version", name="uq_policy_versions_identity"),
        sa.UniqueConstraint("policy_id", "policy_version", "policy_hash", name="uq_policy_versions_exact_subject"),
        sa.UniqueConstraint("policy_hash", name="uq_policy_versions_policy_hash"),
        sa.UniqueConstraint("record_hash", name="uq_policy_versions_record_hash"),
        sa.CheckConstraint("policy_version > 0", name="ck_policy_versions_version_positive"),
        sa.CheckConstraint(f"policy_type IN ({_POLICY_TYPES})", name="ck_policy_versions_policy_type_valid"),
        sa.CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$'", name="ck_policy_versions_policy_hash_sha256"),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'", name="ck_policy_versions_record_hash_sha256"),
        sa.CheckConstraint("length(trim(policy_id)) > 0 AND length(trim(domain)) > 0", name="ck_policy_versions_identity_not_empty"),
    )

    op.create_table(
        "policy_decisions",
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("decision_event", sa.String(32), nullable=False),
        sa.Column("policy_type", sa.String(32), nullable=False),
        sa.Column("policy_id", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("institutional_role", sa.String(64), nullable=False),
        _jsonb("evidence"), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("previous_decision_id", sa.String(64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["policy_id", "policy_version", "policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_policy_decisions_exact_policy_version", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_decision_id"], ["policy_decisions.decision_id"], name="fk_policy_decisions_previous_decision", ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key", name="uq_policy_decisions_idempotency_key"),
        sa.UniqueConstraint("record_hash", name="uq_policy_decisions_record_hash"),
        sa.CheckConstraint(f"policy_type IN ({_POLICY_TYPES})", name="ck_policy_decisions_policy_type_valid"),
        sa.CheckConstraint("decision_event IN ('submetida', 'auditoria_iniciada', 'auditada_favoravelmente', 'auditada_desfavoravelmente', 'ratificada', 'rejeitada', 'cancelada')", name="ck_policy_decisions_event_valid"),
        sa.CheckConstraint("institutional_role IN ('proponente_institucional', 'auditor_independente', 'autoridade_constitucional_final', 'autoridade_institucional_competente')", name="ck_policy_decisions_role_valid"),
        sa.CheckConstraint("policy_version > 0", name="ck_policy_decisions_version_positive"),
        sa.CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$' AND record_hash ~ '^[0-9a-f]{64}$'", name="ck_policy_decisions_hashes_sha256"),
    )

    op.create_table(
        "bootstrap_authority_records",
        sa.Column("bootstrap_authority_record_id", sa.String(64), primary_key=True),
        sa.Column("policy_type", sa.String(32), nullable=False),
        sa.Column("policy_id", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False), _jsonb("scope"),
        sa.Column("actor_proponente", sa.String(255), nullable=False),
        sa.Column("actor_auditor", sa.String(255), nullable=False),
        sa.Column("independent_audit_result", sa.String(32), nullable=False),
        sa.Column("constitutional_authority_declaration", sa.Text(), nullable=False),
        sa.Column("actor_ratificador", sa.String(255), nullable=False),
        _jsonb("segregation_evidence"), _jsonb("evidence"),
        sa.Column("validity", sa.String(32), nullable=False),
        sa.Column("submission_mode", sa.String(16), nullable=False),
        sa.Column("audit_mode", sa.String(16), nullable=False),
        sa.Column("ratification_mode", sa.String(16), nullable=False),
        sa.Column("activation_mode", sa.String(16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        _jsonb("provenance"), sa.Column("record_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["policy_id", "policy_version", "policy_hash"], ["policy_versions.policy_id", "policy_versions.policy_version", "policy_versions.policy_hash"], name="fk_bootstrap_authority_records_exact_policy_version", ondelete="RESTRICT"),
        sa.UniqueConstraint("record_hash", name="uq_bootstrap_authority_records_record_hash"),
        sa.CheckConstraint("policy_type = 'activation_authority'", name="ck_bootstrap_authority_records_policy_type"),
        sa.CheckConstraint("independent_audit_result = 'favoravel'", name="ck_bootstrap_authority_records_audit_favorable"),
        sa.CheckConstraint("validity = 'valida'", name="ck_bootstrap_authority_records_validity"),
        sa.CheckConstraint("submission_mode = 'manual' AND audit_mode = 'manual' AND ratification_mode = 'manual' AND activation_mode = 'manual'", name="ck_bootstrap_authority_records_manual_only"),
        sa.CheckConstraint("actor_proponente <> actor_auditor AND actor_proponente <> actor_ratificador AND actor_auditor <> actor_ratificador", name="ck_bootstrap_authority_records_actor_segregation"),
        sa.CheckConstraint("policy_version > 0 AND policy_hash ~ '^[0-9a-f]{64}$' AND record_hash ~ '^[0-9a-f]{64}$'", name="ck_bootstrap_authority_records_exact_hashes"),
    )

    op.execute("""
        CREATE FUNCTION adr020_validate_policy_decision_chain() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE predecessor policy_decisions%ROWTYPE;
        BEGIN
            IF NEW.decision_event = 'submetida' THEN
                IF NEW.previous_decision_id IS NOT NULL OR NEW.institutional_role <> 'proponente_institucional' THEN
                    RAISE EXCEPTION 'ADR-020 invalid institutional submission'; END IF;
                RETURN NEW;
            END IF;
            IF NEW.previous_decision_id IS NULL THEN
                RAISE EXCEPTION 'ADR-020 decision requires exact predecessor'; END IF;
            SELECT * INTO STRICT predecessor FROM policy_decisions WHERE decision_id = NEW.previous_decision_id;
            IF (predecessor.policy_type, predecessor.policy_id, predecessor.policy_version, predecessor.policy_hash)
               IS DISTINCT FROM (NEW.policy_type, NEW.policy_id, NEW.policy_version, NEW.policy_hash) THEN
                RAISE EXCEPTION 'ADR-020 decision identity diverges from predecessor'; END IF;
            IF predecessor.decision_event IN ('auditada_desfavoravelmente', 'ratificada', 'rejeitada', 'cancelada') THEN
                RAISE EXCEPTION 'ADR-020 terminal decision cannot be reopened'; END IF;
            IF NEW.decision_event = 'ratificada'
               AND NOT (
                   predecessor.decision_event = 'auditada_favoravelmente'
                   AND NEW.institutional_role = 'autoridade_constitucional_final'
               ) THEN
                RAISE EXCEPTION 'ADR-020 ratification requires favorable independent audit and constitutional authority';
            END IF;
            IF NEW.actor = predecessor.actor
               AND NEW.decision_event NOT IN ('auditada_favoravelmente', 'auditada_desfavoravelmente') THEN
                RAISE EXCEPTION 'ADR-020 institutional segregation violation'; END IF;
            IF NOT ((NEW.decision_event = 'auditoria_iniciada' AND predecessor.decision_event = 'submetida' AND NEW.institutional_role = 'auditor_independente')
                OR (NEW.decision_event IN ('auditada_favoravelmente', 'auditada_desfavoravelmente') AND predecessor.decision_event = 'auditoria_iniciada' AND NEW.institutional_role = 'auditor_independente' AND NEW.actor = predecessor.actor)
                OR (NEW.decision_event = 'ratificada' AND predecessor.decision_event = 'auditada_favoravelmente' AND NEW.institutional_role = 'autoridade_constitucional_final')
                OR (NEW.decision_event IN ('rejeitada', 'cancelada') AND NEW.institutional_role = 'autoridade_institucional_competente')) THEN
                RAISE EXCEPTION 'ADR-020 forbidden PolicyDecision transition'; END IF;
            RETURN NEW;
        EXCEPTION WHEN NO_DATA_FOUND THEN RAISE EXCEPTION 'ADR-020 exact predecessor decision not found';
        END; $$;
    """)
    op.execute("CREATE TRIGGER trg_policy_decisions_validate_insert BEFORE INSERT ON policy_decisions FOR EACH ROW EXECUTE FUNCTION adr020_validate_policy_decision_chain();")
    for table_name in _APPEND_ONLY_TABLES:
        _append_only(table_name)


def downgrade() -> None:
    raise RuntimeError(
        "Migration 0022_adr020_policy is irreversible by ratified ADR-020 append-only requirements"
    )
