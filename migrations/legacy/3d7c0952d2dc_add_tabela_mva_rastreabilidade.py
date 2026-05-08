"""add_tabela_mva_rastreabilidade

Revision ID: 3d7c0952d2dc
Revises: f67ad9e46090
Create Date: 2026-04-27 17:44:21.449501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d7c0952d2dc'
down_revision: Union[str, Sequence[str], None] = 'f67ad9e46090'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apenas rastreabilidade em tabela_mva."""
    op.add_column('tabela_mva', sa.Column('fonte_legal', sa.String(length=500), nullable=True))
    op.add_column('tabela_mva', sa.Column('url_fonte', sa.String(length=1000), nullable=True))
    op.add_column('tabela_mva', sa.Column('importado_em', sa.DateTime(), nullable=True))
    op.add_column('tabela_mva', sa.Column('importado_por', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('tabela_mva', 'importado_por')
    op.drop_column('tabela_mva', 'importado_em')
    op.drop_column('tabela_mva', 'url_fonte')
    op.drop_column('tabela_mva', 'fonte_legal')
