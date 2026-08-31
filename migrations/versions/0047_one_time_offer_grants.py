"""0047_one_time_offer_grants

Persistencia do grant one_time com saldo compartilhado entre capabilities.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0047_one_time_offer_grants"
down_revision: str = "0046_multi_vertical_order_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkout_offer_grants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("usage_unit", sa.String(length=50), nullable=False),
        sa.Column("usage_limit", sa.Integer(), nullable=False),
        sa.Column("usage_consumed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "usage_unit = lower(usage_unit) AND usage_unit = trim(usage_unit) "
            "AND length(usage_unit) > 0",
            name="ck_checkout_offer_grants_usage_unit_canonico",
        ),
        sa.CheckConstraint(
            "usage_limit > 0",
            name="ck_checkout_offer_grants_usage_limit_positivo",
        ),
        sa.CheckConstraint(
            "usage_consumed >= 0 AND usage_consumed <= usage_limit",
            name="ck_checkout_offer_grants_usage_consumed_valido",
        ),
        sa.CheckConstraint(
            "estado IN ('active', 'exhausted', 'revoked')",
            name="ck_checkout_offer_grants_estado_valido",
        ),
        sa.ForeignKeyConstraint(
            ["ordem_id"], ["ordens_checkout.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ordem_id", name="uq_checkout_offer_grants_ordem_id"),
    )

    op.create_table(
        "checkout_offer_grant_capabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "length(trim(codigo)) > 0",
            name="ck_checkout_offer_grant_capabilities_codigo_nao_vazio",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["checkout_offer_grants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "grant_id",
            "codigo",
            name="uq_checkout_offer_grant_capabilities_grant_codigo",
        ),
    )
    op.create_index(
        "ix_checkout_offer_grant_capabilities_grant_id",
        "checkout_offer_grant_capabilities",
        ["grant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_checkout_offer_grant_capabilities_grant_id",
        table_name="checkout_offer_grant_capabilities",
    )
    op.drop_table("checkout_offer_grant_capabilities")
    op.drop_table("checkout_offer_grants")
