"""0048_checkout_offer_grant_consumption_ledger

Ledger append-only de consumos confirmados de grants one-time.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0048_checkout_offer_grant_consumption_ledger"
down_revision: str = "0047_one_time_offer_grants"
branch_labels = None
depends_on = None


_TABLE_NAME = "checkout_offer_grant_consumptions"
_APPEND_ONLY_FUNCTION_NAME = "reject_checkout_offer_grant_consumption_mutation"
_APPEND_ONLY_TRIGGER_NAME = "trg_checkout_offer_grant_consumptions_append_only"
_GRANT_INDEX_NAME = "ix_checkout_offer_grant_consumptions_grant_id"
_SCOPE_INDEX_NAME = "ix_checkout_offer_grant_consumptions_scope_created_at"


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("usage_before", sa.Integer(), nullable=False),
        sa.Column("usage_after", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "units > 0",
            name="ck_checkout_offer_grant_consumptions_units_positive",
        ),
        sa.CheckConstraint(
            "usage_before >= 0",
            name="ck_checkout_offer_grant_consumptions_usage_before_nonnegative",
        ),
        sa.CheckConstraint(
            "usage_after = usage_before + units",
            name="ck_checkout_offer_grant_consumptions_usage_after_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["checkout_offer_grants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_checkout_offer_grant_consumptions_idempotency_key",
        ),
    )
    op.create_index(_GRANT_INDEX_NAME, _TABLE_NAME, ["grant_id"])
    op.create_index(
        _SCOPE_INDEX_NAME,
        _TABLE_NAME,
        ["user_id", "empresa_id", "capability", "created_at"],
    )
    op.execute(
        f"""
        CREATE FUNCTION {_APPEND_ONLY_FUNCTION_NAME}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'checkout_offer_grant_consumptions is append-only';
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
    op.execute(
        f"DROP TRIGGER {_APPEND_ONLY_TRIGGER_NAME} ON {_TABLE_NAME}"
    )
    op.execute(f"DROP FUNCTION {_APPEND_ONLY_FUNCTION_NAME}()")
    op.drop_index(_SCOPE_INDEX_NAME, table_name=_TABLE_NAME)
    op.drop_index(_GRANT_INDEX_NAME, table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
