"""0051_mercado_pago_payment_observations

Append-only authority for approved Mercado Pago payment observations.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0051_mercado_pago_payment_observations"
down_revision: str = "0050_checkout_dispatch_claim"
branch_labels = None
depends_on = None


_TABLE_NAME = "mercado_pago_payment_observations"
_APPEND_ONLY_FUNCTION_NAME = "reject_mercado_pago_payment_observation_mutation"
_APPEND_ONLY_TRIGGER_NAME = "trg_mercado_pago_payment_observations_append_only"
_ORDER_INDEX_NAME = "ix_mercado_pago_payment_observations_ordem_id"
_PAYMENT_INDEX_NAME = "ix_mercado_pago_payment_observations_payment_id"


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("notification_id", sa.String(length=255), nullable=False),
        sa.Column("payment_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("valor", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("moeda", sa.String(length=3), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status = 'approved'",
            name="ck_mercado_pago_payment_observations_status_approved",
        ),
        sa.CheckConstraint(
            "moeda = 'BRL'",
            name="ck_mercado_pago_payment_observations_moeda_brl",
        ),
        sa.CheckConstraint(
            "valor > 0",
            name="ck_mercado_pago_payment_observations_valor_positive",
        ),
        sa.ForeignKeyConstraint(["ordem_id"], ["ordens_checkout.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            name="uq_mercado_pago_payment_observations_notification_id",
        ),
    )
    op.create_index(_ORDER_INDEX_NAME, _TABLE_NAME, ["ordem_id"])
    op.create_index(_PAYMENT_INDEX_NAME, _TABLE_NAME, ["payment_id"])
    op.execute(
        f"""
        CREATE FUNCTION {_APPEND_ONLY_FUNCTION_NAME}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'mercado_pago_payment_observations is append-only';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_APPEND_ONLY_TRIGGER_NAME}
        BEFORE UPDATE OR DELETE ON {_TABLE_NAME}
        FOR EACH ROW EXECUTE FUNCTION {_APPEND_ONLY_FUNCTION_NAME}()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER {_APPEND_ONLY_TRIGGER_NAME} ON {_TABLE_NAME}")
    op.execute(f"DROP FUNCTION {_APPEND_ONLY_FUNCTION_NAME}()")
    op.drop_index(_PAYMENT_INDEX_NAME, table_name=_TABLE_NAME)
    op.drop_index(_ORDER_INDEX_NAME, table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
