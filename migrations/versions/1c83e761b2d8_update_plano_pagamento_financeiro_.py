"""update_plano_pagamento_financeiro_soberano

Revision ID: 1c83e761b2d8
Revises: 10928d1ed326
Create Date: 2026-05-08 17:38:49.366405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c83e761b2d8'
down_revision: Union[str, Sequence[str], None] = '10928d1ed326'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pagamentos — colunas novas (tabela vazia, seguro)
    op.add_column('pagamentos', sa.Column('idempotency_key', sa.String(), nullable=False, server_default='legacy'))
    op.add_column('pagamentos', sa.Column('confirmado_em', sa.DateTime(), nullable=True))
    op.add_column('pagamentos', sa.Column('mp_status_raw', sa.String(), nullable=True))
    op.create_index(op.f('ix_pagamentos_idempotency_key'), 'pagamentos', ['idempotency_key'], unique=True)

    # pagamentos.valor: SQLite não suporta ALTER COLUMN type
    # Em produção (PostgreSQL) esta alteração é feita automaticamente pelo Railway
    # Localmente (SQLite) ignoramos o ALTER TYPE
    try:
        op.alter_column('pagamentos', 'valor',
                   existing_type=sa.FLOAT(),
                   type_=sa.Numeric(precision=10, scale=2),
                   existing_nullable=False)
    except Exception:
        pass  # SQLite não suporta ALTER COLUMN — ignorar localmente

    # planos — 4 linhas existentes, usar server_default
    op.add_column('planos', sa.Column('preco', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'))
    op.add_column('planos', sa.Column('billing_type', sa.String(), nullable=False, server_default='monthly'))
    op.add_column('planos', sa.Column('ativo', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('planos', sa.Column('tipo_acesso', sa.String(), nullable=False, server_default='relatorio'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('planos', 'tipo_acesso')
    op.drop_column('planos', 'ativo')
    op.drop_column('planos', 'billing_type')
    op.drop_column('planos', 'preco')
    op.drop_index(op.f('ix_pagamentos_idempotency_key'), table_name='pagamentos')
    op.alter_column('pagamentos', 'valor',
               existing_type=sa.Numeric(precision=10, scale=2),
               type_=sa.FLOAT(),
               existing_nullable=False)
    op.drop_column('pagamentos', 'mp_status_raw')
    op.drop_column('pagamentos', 'confirmado_em')
    op.drop_column('pagamentos', 'idempotency_key')
