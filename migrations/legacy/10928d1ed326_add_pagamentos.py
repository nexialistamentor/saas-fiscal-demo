"""add_pagamentos

Revision ID: 10928d1ed326
Revises: 4bf82196aa41
Create Date: 2026-05-08 17:13:08.871650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10928d1ed326'
down_revision: Union[str, Sequence[str], None] = '4bf82196aa41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pagamentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plano_id", sa.Integer(), nullable=True),
        sa.Column("relatorio_analise_id", sa.Integer(), nullable=True),
        sa.Column("mp_payment_id", sa.String(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payment_method_id", sa.String(), nullable=False),
        sa.Column("qr_code", sa.String(), nullable=True),
        sa.Column("qr_code_base64", sa.String(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["plano_id"], ["planos.id"]),
        sa.ForeignKeyConstraint(["relatorio_analise_id"], ["relatorios_analise.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pagamentos_id"), "pagamentos", ["id"], unique=False)
    op.create_index(
        op.f("ix_pagamentos_mp_payment_id"),
        "pagamentos",
        ["mp_payment_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_pagamentos_mp_payment_id"), table_name="pagamentos")
    op.drop_index(op.f("ix_pagamentos_id"), table_name="pagamentos")
    op.drop_table("pagamentos")
