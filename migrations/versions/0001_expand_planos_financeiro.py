"""expand planos: campos financeiros soberanos

Revision ID: 0001_expand_planos
Revises: 0000_baseline
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision: str = '0001_expand_planos'
down_revision: str = '0000_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('planos', sa.Column('preco', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('planos', sa.Column('billing_type', sa.String(), nullable=False, server_default='monthly'))
    op.add_column('planos', sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('planos', sa.Column('tipo_acesso', sa.String(), nullable=False, server_default='relatorio'))


def downgrade() -> None:
    op.drop_column('planos', 'tipo_acesso')
    op.drop_column('planos', 'ativo')
    op.drop_column('planos', 'billing_type')
    op.drop_column('planos', 'preco')
