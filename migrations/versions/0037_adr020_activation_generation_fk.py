"""ADR-020 ActivationGeneration existence link (PostgreSQL-only)."""

from alembic import op

revision = "0037_adr020_generation_fk"
down_revision = "0036_adr020_review_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Migration 0037_adr020_generation_fk is PostgreSQL-only")
    op.execute("""
        ALTER TABLE normative_activations
        ADD CONSTRAINT fk_normative_activations_activation_generation
        FOREIGN KEY (activation_generation_id)
        REFERENCES activation_generations (activation_generation_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
        NOT VALID;
    """)


def downgrade():
    raise RuntimeError(
        "Migration 0037_adr020_generation_fk is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
