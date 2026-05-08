"""add_documentos_rendimento

Revision ID: 2e580ff68ad3
Revises: 9196733fb8a5
Create Date: 2026-04-22 18:53:23.783933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e580ff68ad3'
down_revision: Union[str, Sequence[str], None] = '9196733fb8a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('documentos_rendimento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('tipo_rendimento', sa.String(length=20), nullable=False),
    sa.Column('descricao', sa.String(), nullable=True),
    sa.Column('valor', sa.Float(), nullable=True),
    sa.Column('ano_referencia', sa.Integer(), nullable=True),
    sa.Column('mes_referencia', sa.Integer(), nullable=True),
    sa.Column('arquivo_nome', sa.String(), nullable=True),
    sa.Column('arquivo_path', sa.String(), nullable=True),
    sa.Column('fonte_pagadora', sa.String(), nullable=True),
    sa.Column('confianca_extracao', sa.String(length=10), nullable=True),
    sa.Column('campos_corrigidos', sa.JSON(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documentos_rendimento_id'), 'documentos_rendimento', ['id'], unique=False)
    op.create_index(op.f('ix_documentos_rendimento_user_id'), 'documentos_rendimento', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documentos_rendimento_user_id'), table_name='documentos_rendimento')
    op.drop_index(op.f('ix_documentos_rendimento_id'), table_name='documentos_rendimento')
    op.drop_table('documentos_rendimento')
