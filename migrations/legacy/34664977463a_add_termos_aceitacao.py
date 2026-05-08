"""add_termos_aceitacao

Revision ID: 34664977463a
Revises: 6607d5149e78
Create Date: 2026-05-06 17:47:11.301640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34664977463a'
down_revision: Union[str, Sequence[str], None] = '6607d5149e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "termos_aceitacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("versao_termos", sa.String(length=50), nullable=False),
        sa.Column("aceite_em", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_termos_aceitacao_id"), "termos_aceitacao", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_termos_aceitacao_id"), table_name="termos_aceitacao")
    op.drop_table("termos_aceitacao")
