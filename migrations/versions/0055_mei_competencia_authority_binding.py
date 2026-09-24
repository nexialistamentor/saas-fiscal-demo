"""0055_mei_competencia_authority_binding

Autoridade comercial soberana por empresa + competencia + capability MEI.
A ordem de checkout e proveniencia comercial; nao e identidade da autoridade.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0055_mei_competencia_authority_binding"
down_revision: str = "0054_empresa_cnpj_unique"
branch_labels = None
depends_on = None


_TABLE = "mei_competencia_authority_bindings"
_FUNCTION = "reject_mei_competencia_authority_binding_mutation"
_TRIGGER = "trg_mei_competencia_authority_bindings_append_only"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("competencia", sa.String(length=6), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(competencia) = 6",
            name="ck_mei_competencia_authority_competencia_tamanho",
        ),
        sa.CheckConstraint(
            "substr(competencia, 1, 1) between '0' and '9' "
            "AND substr(competencia, 2, 1) between '0' and '9' "
            "AND substr(competencia, 3, 1) between '0' and '9' "
            "AND substr(competencia, 4, 1) between '0' and '9' "
            "AND substr(competencia, 5, 1) between '0' and '9' "
            "AND substr(competencia, 6, 1) between '0' and '9' "
            "AND substr(competencia, 5, 2) between '01' and '12'",
            name="ck_mei_competencia_authority_competencia_yyyymm",
        ),
        sa.CheckConstraint(
            "capability = lower(capability) "
            "AND capability = trim(capability) "
            "AND length(capability) > 0",
            name="ck_mei_competencia_authority_capability_canonica",
        ),
        sa.ForeignKeyConstraint(
            ["ordem_id"],
            ["ordens_checkout.id"],
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"],
            ["empresas.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "empresa_id",
            "competencia",
            "capability",
            name="uq_mei_competencia_authority_scope",
        ),
    )

    op.create_index(
        "ix_mei_competencia_authority_bindings_ordem_id",
        _TABLE,
        ["ordem_id"],
    )
    op.create_index(
        "ix_mei_competencia_authority_bindings_empresa_id",
        _TABLE,
        ["empresa_id"],
    )

    op.execute(
        f"""
        CREATE FUNCTION {_FUNCTION}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'mei_competencia_authority_bindings is append-only';
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
    op.drop_index(
        "ix_mei_competencia_authority_bindings_empresa_id",
        table_name=_TABLE,
    )
    op.drop_index(
        "ix_mei_competencia_authority_bindings_ordem_id",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
