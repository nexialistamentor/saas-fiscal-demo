"""add_tabela_mva_nivel_confianca_fonte

Revision ID: f3b79fa74df8
Revises: 3d7c0952d2dc
Create Date: 2026-04-27 17:49:35.041757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b79fa74df8'
down_revision: Union[str, Sequence[str], None] = '3d7c0952d2dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'tabela_mva',
        sa.Column('nivel_confianca_fonte', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tabela_mva', 'nivel_confianca_fonte')
