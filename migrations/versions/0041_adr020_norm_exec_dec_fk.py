"""ADR-020 exact normative activation/execution/decision binding."""

from alembic import op


revision = "0041_adr020_norm_exec_dec_fk"
down_revision = "0040_adr020_norm_gen_decision_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "ADR-020 migration 0041 requires PostgreSQL"
        )

    op.execute("""
        ALTER TABLE normative_activations
        ADD CONSTRAINT fk_normative_activations_exact_execution_decision
        FOREIGN KEY (
            activation_execution_id,
            activation_decision_id,
            activation_decision_record_hash
        )
        REFERENCES activation_executions (
            activation_execution_id,
            activation_decision_id,
            activation_decision_record_hash
        )
        MATCH SIMPLE
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
        NOT DEFERRABLE
        INITIALLY IMMEDIATE
        NOT VALID;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "ADR-020 migration 0041 is irreversible: "
        "exact normative-execution-decision binding cannot be removed"
    )
