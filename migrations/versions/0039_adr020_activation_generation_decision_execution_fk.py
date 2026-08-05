"""ADR-020 exact generation/execution/decision binding (PostgreSQL-only)."""

from alembic import op


revision = "0039_adr020_gen_exec_decision_fk"
down_revision = "0038_adr020_generation_exec_gate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "ADR-020 migration 0039 requires PostgreSQL"
        )

    op.create_unique_constraint(
        "uq_activation_executions_exact_decision_binding",
        "activation_executions",
        [
            "activation_execution_id",
            "activation_decision_id",
            "activation_decision_record_hash",
        ],
    )
    op.execute("""
        ALTER TABLE activation_generations
        ADD CONSTRAINT fk_activation_generations_exact_execution_decision
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
        "ADR-020 migration 0039 is irreversible: "
        "exact generation-execution-decision binding cannot be removed"
    )
