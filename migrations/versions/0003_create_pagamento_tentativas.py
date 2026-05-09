"""create pagamento_tentativas: ledger operacional auditável

Revision ID: 0003_pagamento_tentativas
Revises: 0002_expand_pagamentos
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003_pagamento_tentativas'
down_revision: str = '0002_expand_pagamentos'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pagamento_tentativas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pagamento_id', sa.Integer(), sa.ForeignKey('pagamentos.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('gateway_provider', sa.String(), nullable=False),
        sa.Column('payment_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('error_origin', sa.String(), nullable=True),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('request_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('response_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_pagamento_tentativas_pagamento_id', 'pagamento_tentativas', ['pagamento_id'])
    op.create_index('ix_pagamento_tentativas_user_id', 'pagamento_tentativas', ['user_id'])
    op.create_index('ix_pagamento_tentativas_status', 'pagamento_tentativas', ['status'])
    op.create_index('ix_pagamento_tentativas_gateway_provider', 'pagamento_tentativas', ['gateway_provider'])
    op.create_index('ix_pagamento_tentativas_error_code', 'pagamento_tentativas', ['error_code'])


def downgrade() -> None:
    op.drop_index('ix_pagamento_tentativas_error_code')
    op.drop_index('ix_pagamento_tentativas_gateway_provider')
    op.drop_index('ix_pagamento_tentativas_status')
    op.drop_index('ix_pagamento_tentativas_user_id')
    op.drop_index('ix_pagamento_tentativas_pagamento_id')
    op.drop_table('pagamento_tentativas')
