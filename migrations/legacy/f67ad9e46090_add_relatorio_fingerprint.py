"""add_relatorio_fingerprint

Revision ID: f67ad9e46090
Revises: c3a91f0d1b2c
Create Date: 2026-04-27 16:44:50.247324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f67ad9e46090'
down_revision: Union[str, Sequence[str], None] = 'c3a91f0d1b2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'relatorios_analise',
        sa.Column('fingerprint', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('relatorios_analise', 'fingerprint')
