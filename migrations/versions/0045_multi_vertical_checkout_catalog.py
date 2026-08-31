"""0045_multi_vertical_checkout_catalog

Catalogo duravel de ofertas multi-vertical, sem publicacao ou seeds.

Revision ID: 0045_multi_vertical_checkout_catalog
Revises: 0044_payments_durable_ledger
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0045_multi_vertical_checkout_catalog"
down_revision: str = "0044_payments_durable_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkout_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=120), nullable=False),
        sa.Column("nome_publico", sa.String(length=255), nullable=False),
        sa.Column("vertical", sa.String(length=20), nullable=False),
        sa.Column("commercial_model", sa.String(length=20), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("moeda", sa.String(length=3), nullable=True),
        sa.Column("preco", sa.Numeric(12, 2), nullable=True),
        sa.Column("billing_period", sa.String(length=20), nullable=True),
        sa.Column("usage_unit", sa.String(length=50), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("vertical IN ('tax', 'document')", name="ck_checkout_offers_vertical"),
        sa.CheckConstraint("commercial_model IN ('monthly', 'one_time', 'negotiated')", name="ck_checkout_offers_commercial_model"),
        sa.CheckConstraint("subject_type IN ('cpf', 'company', 'institution')", name="ck_checkout_offers_subject_type"),
        sa.CheckConstraint("estado IN ('draft', 'published', 'retired')", name="ck_checkout_offers_estado"),
        sa.CheckConstraint("contract_version > 0", name="ck_checkout_offers_contract_version"),
        sa.CheckConstraint("codigo = lower(codigo) AND codigo = trim(codigo) AND length(codigo) > 0 AND codigo NOT LIKE '%--%'", name="ck_checkout_offers_codigo_canonico"),
        sa.CheckConstraint("(commercial_model = 'monthly' AND moeda = 'BRL' AND preco > 0 AND billing_period = 'month' AND usage_unit IS NULL AND usage_limit IS NULL) OR (commercial_model = 'one_time' AND moeda = 'BRL' AND preco > 0 AND billing_period IS NULL AND usage_unit IS NOT NULL AND length(trim(usage_unit)) > 0 AND usage_limit > 0) OR (commercial_model = 'negotiated' AND moeda IS NULL AND preco IS NULL AND billing_period IS NULL AND usage_unit IS NULL AND usage_limit IS NULL)", name="ck_checkout_offers_commercial_configuration"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_checkout_offers_codigo"),
    )
    op.create_index("ix_checkout_offers_codigo", "checkout_offers", ["codigo"], unique=False)

    op.create_table(
        "checkout_offer_capabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=120), nullable=False),
        sa.CheckConstraint("codigo = lower(codigo) AND codigo = trim(codigo) AND length(codigo) > 0", name="ck_checkout_offer_capabilities_codigo_canonico"),
        sa.ForeignKeyConstraint(["offer_id"], ["checkout_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("offer_id", "codigo", name="uq_checkout_offer_capabilities_offer_codigo"),
    )
    op.create_index("ix_checkout_offer_capabilities_offer_id", "checkout_offer_capabilities", ["offer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_checkout_offer_capabilities_offer_id", table_name="checkout_offer_capabilities")
    op.drop_table("checkout_offer_capabilities")
    op.drop_index("ix_checkout_offers_codigo", table_name="checkout_offers")
    op.drop_table("checkout_offers")
