"""create perfis_contador: entidade regulatoria contador parceiro

Revision ID: 0005_perfis_contador
Revises: 0004_documentos_ingeridos
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision: str = '0005_perfis_contador'
down_revision: str = '0004_documentos_ingeridos'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'perfis_contador',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('crc', sa.String(20), nullable=False),
        sa.Column('uf_crc', sa.String(2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),
        sa.Column('reputacao_score', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('aprovado_em', sa.DateTime(), nullable=True),
        sa.Column('aprovado_por', sa.String(255), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_perfis_contador_user_id', 'perfis_contador', ['user_id'], unique=True)
    op.create_index('ix_perfis_contador_crc', 'perfis_contador', ['crc'], unique=True)
    op.create_index('ix_perfis_contador_status', 'perfis_contador', ['status'])


def downgrade() -> None:
    op.drop_index('ix_perfis_contador_status')
    op.drop_index('ix_perfis_contador_crc')
    op.drop_index('ix_perfis_contador_user_id')
    op.drop_table('perfis_contador')
