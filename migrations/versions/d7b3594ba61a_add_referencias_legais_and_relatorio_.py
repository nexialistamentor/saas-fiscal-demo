"""add_referencias_legais_and_relatorio_pago

Revision ID: d7b3594ba61a
Revises: 2e580ff68ad3
Create Date: 2026-04-27 08:18:39.107223

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7b3594ba61a'
down_revision: Union[str, Sequence[str], None] = '2e580ff68ad3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('referencias_legais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=50), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('fundamento', sa.Text(), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('uf', sa.String(length=2), nullable=True),
    sa.Column('vigencia_inicio', sa.Date(), nullable=False),
    sa.Column('vigencia_fim', sa.Date(), nullable=True),
    sa.Column('fonte_url', sa.String(length=500), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=True),
    sa.Column('atualizado_em', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_referencias_legais_codigo'), 'referencias_legais', ['codigo'], unique=True)
    op.create_index(op.f('ix_referencias_legais_id'), 'referencias_legais', ['id'], unique=False)
    op.create_index(op.f('ix_referencias_legais_uf'), 'referencias_legais', ['uf'], unique=False)
    op.add_column('relatorios_analise', sa.Column('pago', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('relatorios_analise', sa.Column('memorial_gerado', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('relatorios_analise', 'memorial_gerado')
    op.drop_column('relatorios_analise', 'pago')
    op.drop_index(op.f('ix_referencias_legais_uf'), table_name='referencias_legais')
    op.drop_index(op.f('ix_referencias_legais_id'), table_name='referencias_legais')
    op.drop_index(op.f('ix_referencias_legais_codigo'), table_name='referencias_legais')
    op.drop_table('referencias_legais')
