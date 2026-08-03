"""ADR-020 exact bootstrap authority record binding gate (PostgreSQL-only)."""

from alembic import op


revision = "0031_adr020_bootstrap_binding"
down_revision = "0030_adr020_policy_binding_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0031_adr020_bootstrap_binding is PostgreSQL-only"
        )

    op.execute(
        """
        ALTER TABLE bootstrap_authority_records
        ADD CONSTRAINT uq_bootstrap_authority_records_exact_record
        UNIQUE (bootstrap_authority_record_id, record_hash);
        """
    )
    op.execute(
        """
        ALTER TABLE policy_activation_executions
        ADD CONSTRAINT fk_policy_activation_executions_exact_bootstrap_record
        FOREIGN KEY (
            bootstrap_authority_record_id,
            bootstrap_authority_record_hash
        )
        REFERENCES bootstrap_authority_records (
            bootstrap_authority_record_id,
            record_hash
        )
        NOT VALID;
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0031_adr020_bootstrap_binding is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
