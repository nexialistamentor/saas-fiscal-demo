"""0052_tax_report_acquisition_bindings

Append-only binding entre consumo tax.report e snapshot adquirido.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0052_tax_report_acquisition_bindings"
down_revision: str = "0051_mercado_pago_payment_observations"
branch_labels = None
depends_on = None


_TABLE_NAME = "tax_report_acquisition_bindings"
_INDEX_NAME = "ix_tax_report_acquisition_bindings_relatorio_analise_id"
_FUNCTION_NAME = "reject_tax_report_acquisition_binding_mutation"
_TRIGGER_NAME = "trg_tax_report_acquisition_bindings_append_only"


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("consumption_id", sa.Integer(), nullable=False),
        sa.Column("relatorio_analise_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resultado_json_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["consumption_id"], ["checkout_offer_grant_consumptions.id"]
        ),
        sa.ForeignKeyConstraint(["relatorio_analise_id"], ["relatorios_analise.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consumption_id"),
    )
    op.create_index(_INDEX_NAME, _TABLE_NAME, ["relatorio_analise_id"])
    op.execute(
        f"""
        CREATE FUNCTION {_FUNCTION_NAME}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'tax_report_acquisition_bindings is append-only';
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
    op.drop_index(_INDEX_NAME, table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
