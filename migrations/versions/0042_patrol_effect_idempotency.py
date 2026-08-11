"""0042_patrol_effect_idempotency

Physical idempotency identity for sovereign patrol alert effects.

- Adds nullable effect_idempotency_key for historical compatibility.
- New patrol effects must persist a non-null canonical SHA-256 key.
- Enforces uniqueness physically in PostgreSQL.
- Multiple historical NULL values remain valid.

Revision ID: 0042_patrol_effect_idempotency
Revises: 0041_adr020_norm_exec_dec_fk
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0042_patrol_effect_idempotency"
down_revision: str = "0041_adr020_norm_exec_dec_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Patrol effect idempotency migration 0042 requires PostgreSQL"
        )

    op.add_column(
        "alertas_fiscais",
        sa.Column(
            "effect_idempotency_key",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_alertas_fiscais_effect_idempotency_key",
        "alertas_fiscais",
        ["effect_idempotency_key"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Patrol effect idempotency migration 0042 requires PostgreSQL"
        )

    op.drop_constraint(
        "uq_alertas_fiscais_effect_idempotency_key",
        "alertas_fiscais",
        type_="unique",
    )

    op.drop_column(
        "alertas_fiscais",
        "effect_idempotency_key",
    )
