"""expand pagamentos: gateway metadata soberano

Revision ID: 0002_expand_pagamentos
Revises: 0001_expand_planos
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002_expand_pagamentos'
down_revision: str = '0001_expand_planos'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('pagamentos', sa.Column('checkout_url', sa.String(), nullable=True))
    op.add_column('pagamentos', sa.Column('checkout_expires_at', sa.DateTime(), nullable=True))
    op.add_column('pagamentos', sa.Column('gateway_provider', sa.String(), nullable=True, server_default='mercadopago'))
    op.add_column('pagamentos', sa.Column('gateway_payment_type', sa.String(), nullable=True))
    op.add_column('pagamentos', sa.Column('gateway_external_reference', sa.String(), nullable=True))
    op.add_column('pagamentos', sa.Column('boleto_url', sa.String(), nullable=True))
    op.add_column('pagamentos', sa.Column('boleto_barcode', sa.String(), nullable=True))
    op.add_column('pagamentos', sa.Column('gateway_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('pagamentos', 'gateway_payload')
    op.drop_column('pagamentos', 'boleto_barcode')
    op.drop_column('pagamentos', 'boleto_url')
    op.drop_column('pagamentos', 'gateway_external_reference')
    op.drop_column('pagamentos', 'gateway_payment_type')
    op.drop_column('pagamentos', 'gateway_provider')
    op.drop_column('pagamentos', 'checkout_expires_at')
    op.drop_column('pagamentos', 'checkout_url')
