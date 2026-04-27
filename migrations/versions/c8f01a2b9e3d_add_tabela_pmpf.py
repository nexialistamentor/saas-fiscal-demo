"""add_tabela_pmpf

Revision ID: c8f01a2b9e3d
Revises: a4e8d2c09f1b
Create Date: 2026-04-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f01a2b9e3d"
down_revision: Union[str, Sequence[str], None] = "a4e8d2c09f1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tabela_pmpf",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=2), nullable=False),
        sa.Column("ncm", sa.String(length=20), nullable=False),
        sa.Column("cest", sa.String(length=9), nullable=True),
        sa.Column("marca", sa.String(length=200), nullable=False),
        sa.Column("embalagem_ml", sa.Integer(), nullable=True),
        sa.Column("pmpf_reais", sa.Float(), nullable=False),
        sa.Column("aliquota_interna", sa.Float(), nullable=False),
        sa.Column("vigencia_inicio", sa.Date(), nullable=False),
        sa.Column("vigencia_fim", sa.Date(), nullable=True),
        sa.Column("fonte_legal", sa.String(length=500), nullable=True),
        sa.Column("url_fonte", sa.String(length=1000), nullable=True),
        sa.Column("nivel_confianca_fonte", sa.String(length=40), nullable=True),
        sa.Column("importado_por", sa.String(length=100), nullable=True),
        sa.Column("importado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "estado",
            "ncm",
            "marca",
            "embalagem_ml",
            "vigencia_inicio",
            name="uq_pmpf_estado_ncm_marca_embalagem_vigencia",
        ),
    )
    op.create_index(op.f("ix_tabela_pmpf_estado"), "tabela_pmpf", ["estado"], unique=False)
    op.create_index(op.f("ix_tabela_pmpf_id"), "tabela_pmpf", ["id"], unique=False)
    op.create_index(op.f("ix_tabela_pmpf_ncm"), "tabela_pmpf", ["ncm"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tabela_pmpf_ncm"), table_name="tabela_pmpf")
    op.drop_index(op.f("ix_tabela_pmpf_id"), table_name="tabela_pmpf")
    op.drop_index(op.f("ix_tabela_pmpf_estado"), table_name="tabela_pmpf")
    op.drop_table("tabela_pmpf")
