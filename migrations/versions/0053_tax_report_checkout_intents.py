"""Intencao duravel e append-only do checkout tax.report."""

from alembic import op
import sqlalchemy as sa


revision: str = "0053_tax_report_checkout_intents"
down_revision: str = "0052_tax_report_acquisition_bindings"
branch_labels = None
depends_on = None


_TABLE_NAME = "tax_report_checkout_intents"
_USER_INDEX = "ix_tax_report_checkout_intents_user_id"
_EMPRESA_INDEX = "ix_tax_report_checkout_intents_empresa_id"
_RELATORIO_INDEX = "ix_tax_report_checkout_intents_relatorio_analise_id"
_FUNCTION_NAME = "reject_tax_report_checkout_intent_mutation"
_TRIGGER_NAME = "trg_tax_report_checkout_intents_append_only"


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checkout_idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("relatorio_analise_id", sa.Integer(), nullable=False),
        sa.Column("offer_code", sa.String(length=120), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(
            ["relatorio_analise_id"], ["relatorios_analise.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkout_idempotency_key"),
    )
    op.create_index(_USER_INDEX, _TABLE_NAME, ["user_id"])
    op.create_index(_EMPRESA_INDEX, _TABLE_NAME, ["empresa_id"])
    op.create_index(_RELATORIO_INDEX, _TABLE_NAME, ["relatorio_analise_id"])
    op.execute(
        f"""
        CREATE FUNCTION {_FUNCTION_NAME}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'tax_report_checkout_intents is append-only';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_TRIGGER_NAME}
        BEFORE UPDATE OR DELETE ON {_TABLE_NAME}
        FOR EACH ROW EXECUTE FUNCTION {_FUNCTION_NAME}()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER {_TRIGGER_NAME} ON {_TABLE_NAME}")
    op.execute(f"DROP FUNCTION {_FUNCTION_NAME}()")
    op.drop_index(_RELATORIO_INDEX, table_name=_TABLE_NAME)
    op.drop_index(_EMPRESA_INDEX, table_name=_TABLE_NAME)
    op.drop_index(_USER_INDEX, table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
