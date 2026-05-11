"""create homologacoes_documentais: homologacao humana por contador parceiro

Revision ID: 0006_homologacoes_documentais
Revises: 0005_perfis_contador
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision: str = '0006_homologacoes_documentais'
down_revision: str = '0005_perfis_contador'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'homologacoes_documentais',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('documento_ingerido_id', sa.Integer(), sa.ForeignKey('documentos_ingeridos.id'), nullable=False),
        sa.Column('contador_id', sa.Integer(), sa.ForeignKey('perfis_contador.id'), nullable=False),
        sa.Column('tipo_decisao', sa.String(50), nullable=False, server_default='homologacao_documental'),
        sa.Column('versao_parecer', sa.String(10), nullable=False, server_default='1.0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),
        sa.Column('parecer_texto', sa.Text(), nullable=True),
        sa.Column('assinatura_logica', sa.String(64), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('decidido_em', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_homologacoes_documento_ingerido_id', 'homologacoes_documentais', ['documento_ingerido_id'])
    op.create_index('ix_homologacoes_contador_id', 'homologacoes_documentais', ['contador_id'])
    op.create_index('ix_homologacoes_status', 'homologacoes_documentais', ['status'])
    op.create_index('ix_homologacoes_criado_em', 'homologacoes_documentais', ['criado_em'])


def downgrade() -> None:
    op.drop_index('ix_homologacoes_criado_em')
    op.drop_index('ix_homologacoes_status')
    op.drop_index('ix_homologacoes_contador_id')
    op.drop_index('ix_homologacoes_documento_ingerido_id')
    op.drop_table('homologacoes_documentais')
