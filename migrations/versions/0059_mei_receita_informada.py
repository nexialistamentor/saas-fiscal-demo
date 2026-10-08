"""Persist user-informed revenue without classifying fiscal documents."""
from alembic import op
import sqlalchemy as sa

revision = "0059_mei_receita_informada"
down_revision = "0058_documento_operacao_observada"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "mei_receitas_informadas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("identidade_receita", sa.String(36), nullable=False),
        sa.Column("data_receita", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(15, 2), nullable=False),
        sa.Column("categoria", sa.String(32), nullable=False),
        sa.Column("origem", sa.String(32), nullable=False, server_default="informada_sem_nota"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("empresa_id", "identidade_receita", name="uq_mei_receita_informada_identidade"),
        sa.CheckConstraint("valor >= 0 AND valor <= 9999999999999.99", name="ck_mei_receita_informada_valor"),
        sa.CheckConstraint("categoria IN ('comercio_industria','servicos')", name="ck_mei_receita_informada_categoria"),
        sa.CheckConstraint("origem = 'informada_sem_nota'", name="ck_mei_receita_informada_origem"),
        sa.CheckConstraint("length(identidade_receita) = 36", name="ck_mei_receita_informada_identidade"),
    )
    op.create_index("ix_mei_receita_informada_empresa_data", "mei_receitas_informadas", ["empresa_id", "data_receita"])

def downgrade():
    op.drop_index("ix_mei_receita_informada_empresa_data", table_name="mei_receitas_informadas")
    op.drop_table("mei_receitas_informadas")
