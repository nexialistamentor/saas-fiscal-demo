"""0044_payments_durable_ledger

Ledger SQLAlchemy duravel para ordens, eventos e entitlements de checkout.

Revision ID: 0044_payments_durable_ledger
Revises: 0043_reconcile_tabela_mva_schema
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0044_payments_durable_ledger"
down_revision: str = "0043_reconcile_tabela_mva_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ordens_checkout",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("plano_id", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Numeric(10, 2), nullable=False),
        sa.Column("moeda", sa.String(length=3), server_default="BRL", nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("provider_order_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_url", sa.String(length=2000), nullable=True),
        sa.Column("payment_id", sa.String(length=255), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("moeda = 'BRL'", name="ck_ordens_checkout_moeda_brl"),
        sa.CheckConstraint(
            "estado IN ('pending', 'paid', 'cancelled')",
            name="ck_ordens_checkout_estado_valido",
        ),
        sa.CheckConstraint("valor > 0", name="ck_ordens_checkout_valor_positivo"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["plano_id"], ["planos.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_ordens_checkout_idempotency_key"),
        sa.UniqueConstraint("payment_id", name="uq_ordens_checkout_payment_id"),
        sa.UniqueConstraint("provider_order_id", name="uq_ordens_checkout_provider_order_id"),
    )
    for coluna in ("user_id", "empresa_id", "plano_id", "estado"):
        op.create_index(f"ix_ordens_checkout_{coluna}", "ordens_checkout", [coluna])

    op.add_column(
        "pagamentos",
        sa.Column("ordem_checkout_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pagamentos_ordem_checkout_id",
        "pagamentos",
        "ordens_checkout",
        ["ordem_checkout_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_pagamentos_ordem_checkout_id",
        "pagamentos",
        ["ordem_checkout_id"],
    )

    op.create_table(
        "eventos_pagamento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("notification_id", sa.String(length=255), nullable=False),
        sa.Column("payment_id", sa.String(length=255), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ordem_id"], ["ordens_checkout.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", name="uq_eventos_pagamento_notification_id"),
    )
    for coluna in ("ordem_id", "payment_id"):
        op.create_index(f"ix_eventos_pagamento_{coluna}", "eventos_pagamento", [coluna])

    op.create_table(
        "entitlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("plano_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('active', 'under_review', 'suspended')",
            name="ck_entitlements_estado_valido",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["ordem_id"], ["ordens_checkout.id"]),
        sa.ForeignKeyConstraint(["plano_id"], ["planos.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ordem_id", name="uq_entitlements_ordem_id"),
    )
    for coluna in ("user_id", "empresa_id", "plano_id", "estado"):
        op.create_index(f"ix_entitlements_{coluna}", "entitlements", [coluna])


def downgrade() -> None:
    op.drop_table("entitlements")
    op.drop_table("eventos_pagamento")
    op.drop_constraint("uq_pagamentos_ordem_checkout_id", "pagamentos", type_="unique")
    op.drop_constraint("fk_pagamentos_ordem_checkout_id", "pagamentos", type_="foreignkey")
    op.drop_column("pagamentos", "ordem_checkout_id")
    op.drop_table("ordens_checkout")
