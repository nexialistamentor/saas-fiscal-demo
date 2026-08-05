"""ADR-020 exact normative activation/generation/decision binding."""

from alembic import op


revision = "0040_adr020_norm_gen_decision_fk"
down_revision = "0039_adr020_gen_exec_decision_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "ADR-020 migration 0040 requires PostgreSQL"
        )

    op.create_unique_constraint(
        "uq_activation_generations_generation_exact_decision",
        "activation_generations",
        [
            "activation_generation_id",
            "activation_decision_id",
            "activation_decision_record_hash",
        ],
    )
    op.execute("""
        ALTER TABLE normative_activations
        ADD CONSTRAINT fk_normative_activations_generation_exact_decision
        FOREIGN KEY (
            activation_generation_id,
            activation_decision_id,
            activation_decision_record_hash
        )
        REFERENCES activation_generations (
            activation_generation_id,
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
        "ADR-020 migration 0040 is irreversible: "
        "exact normative-generation-decision binding cannot be removed"
    )
