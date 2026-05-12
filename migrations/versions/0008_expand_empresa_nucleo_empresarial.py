"""expand empresa: nucleo empresarial soberano

Revision ID: 0008_expand_empresa
Revises: 0007_constraint_perfil_contador
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0008_expand_empresa'
down_revision: str = '0007_constraint_perfil_contador'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('empresas', sa.Column('cnae_principal', sa.String(10), nullable=True))
    op.add_column('empresas', sa.Column('cnae_secundarios', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('empresas', sa.Column('municipio', sa.String(100), nullable=True))
    op.add_column('empresas', sa.Column('uf', sa.String(2), nullable=True))
    op.add_column('empresas', sa.Column('porte', sa.String(20), nullable=True))
    op.add_column('empresas', sa.Column('status_empresa', sa.String(20), nullable=True, server_default='ativa'))
    op.add_column('empresas', sa.Column('data_abertura', sa.Date(), nullable=True))
    op.add_column('empresas', sa.Column('capital_social', sa.Numeric(15, 2), nullable=True))
    op.add_column('empresas', sa.Column('optante_simples', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('empresas', sa.Column('optante_mei', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('empresas', sa.Column('faturamento_anual', sa.Numeric(15, 2), nullable=True))
    op.add_column('empresas', sa.Column('folha_anual', sa.Numeric(15, 2), nullable=True))

    # Índices operacionais
    op.create_index('ix_empresas_cnae_principal', 'empresas', ['cnae_principal'])
    op.create_index('ix_empresas_uf', 'empresas', ['uf'])
    op.create_index('ix_empresas_porte', 'empresas', ['porte'])
    op.create_index('ix_empresas_status_empresa', 'empresas', ['status_empresa'])

    # Constraints de domínio
    op.create_check_constraint(
        'ck_empresas_status_valido',
        'empresas',
        "status_empresa IN ('ativa', 'em_abertura', 'suspensa', 'encerrada')",
    )
    op.create_check_constraint(
        'ck_empresas_porte_valido',
        'empresas',
        "porte IN ('mei', 'me', 'epp', 'medio', 'grande')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_empresas_porte_valido', 'empresas', type_='check')
    op.drop_constraint('ck_empresas_status_valido', 'empresas', type_='check')
    op.drop_index('ix_empresas_status_empresa')
    op.drop_index('ix_empresas_porte')
    op.drop_index('ix_empresas_uf')
    op.drop_index('ix_empresas_cnae_principal')
    op.drop_column('empresas', 'folha_anual')
    op.drop_column('empresas', 'faturamento_anual')
    op.drop_column('empresas', 'optante_mei')
    op.drop_column('empresas', 'optante_simples')
    op.drop_column('empresas', 'capital_social')
    op.drop_column('empresas', 'data_abertura')
    op.drop_column('empresas', 'status_empresa')
    op.drop_column('empresas', 'porte')
    op.drop_column('empresas', 'uf')
    op.drop_column('empresas', 'municipio')
    op.drop_column('empresas', 'cnae_secundarios')
    op.drop_column('empresas', 'cnae_principal')
