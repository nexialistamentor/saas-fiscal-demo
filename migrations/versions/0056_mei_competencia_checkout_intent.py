"""Intencao duravel e append-only do checkout por competencia MEI."""

from alembic import op
import sqlalchemy as sa


revision: str = "0056_mei_competencia_checkout_intent"
down_revision: str = "0055_mei_competencia_authority_binding"
branch_labels = None
depends_on = None


_TABLE = "mei_competencia_checkout_intents"
_USER_INDEX = "ix_mei_competencia_checkout_intents_user_id"
_EMPRESA_INDEX = "ix_mei_competencia_checkout_intents_empresa_id"
_FUNCTION = "reject_mei_competencia_checkout_intent_mutation"
_TRIGGER = "trg_mei_competencia_checkout_intents_append_only"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "checkout_idempotency_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("competencia", sa.String(length=6), nullable=False),
        sa.Column("capability", sa.String(length=120), nullable=False),
        sa.Column("offer_code", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(competencia) = 6",
            name="ck_mei_competencia_checkout_intent_competencia_tamanho",
        ),
        sa.CheckConstraint(
            "substr(competencia, 1, 1) between '0' and '9' "
            "AND substr(competencia, 2, 1) between '0' and '9' "
            "AND substr(competencia, 3, 1) between '0' and '9' "
            "AND substr(competencia, 4, 1) between '0' and '9' "
            "AND substr(competencia, 5, 1) between '0' and '9' "
            "AND substr(competencia, 6, 1) between '0' and '9' "
            "AND substr(competencia, 5, 2) between '01' and '12'",
            name="ck_mei_competencia_checkout_intent_competencia_yyyymm",
        ),
        sa.CheckConstraint(
            "capability = 'mei.das'",
            name="ck_mei_competencia_checkout_intent_capability",
        ),
        sa.CheckConstraint(
            "offer_code = lower(offer_code) "
            "AND offer_code = trim(offer_code) "
            "AND length(offer_code) > 0 "
            "AND offer_code NOT LIKE '%--%'",
            name="ck_mei_competencia_checkout_intent_offer_code_canonico",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "checkout_idempotency_key",
            name="uq_mei_competencia_checkout_intent_checkout_idempotency_key",
        ),
    )

    op.create_index(_USER_INDEX, _TABLE, ["user_id"])
    op.create_index(_EMPRESA_INDEX, _TABLE, ["empresa_id"])

    op.execute(
        f"""
        CREATE FUNCTION {_FUNCTION}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'mei_competencia_checkout_intents is append-only';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_TRIGGER}
        BEFORE UPDATE OR DELETE ON {_TABLE}
        FOR EACH ROW EXECUTE FUNCTION {_FUNCTION}()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER {_TRIGGER} ON {_TABLE}")
    op.execute(f"DROP FUNCTION {_FUNCTION}()")
    op.drop_index(_EMPRESA_INDEX, table_name=_TABLE)
    op.drop_index(_USER_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
