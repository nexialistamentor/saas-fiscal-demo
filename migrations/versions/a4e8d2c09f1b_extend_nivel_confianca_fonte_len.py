"""extend nivel_confianca_fonte length for convenio_base_sem_aliquota

Revision ID: a4e8d2c09f1b
Revises: f3b79fa74df8
Create Date: 2026-04-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4e8d2c09f1b"
down_revision: Union[str, Sequence[str], None] = "f3b79fa74df8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("tabela_mva", schema=None) as batch_op:
            batch_op.alter_column(
                "nivel_confianca_fonte",
                existing_type=sa.String(length=20),
                type_=sa.String(length=40),
                existing_nullable=True,
            )
    else:
        op.alter_column(
            "tabela_mva",
            "nivel_confianca_fonte",
            existing_type=sa.String(length=20),
            type_=sa.String(length=40),
            existing_nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("tabela_mva", schema=None) as batch_op:
            batch_op.alter_column(
                "nivel_confianca_fonte",
                existing_type=sa.String(length=40),
                type_=sa.String(length=20),
                existing_nullable=True,
            )
    else:
        op.alter_column(
            "tabela_mva",
            "nivel_confianca_fonte",
            existing_type=sa.String(length=40),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
