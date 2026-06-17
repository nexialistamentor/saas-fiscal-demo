"""add conteudo_sha256 to documentos_fiscais

Revision ID: 0009_add_documento_sha256

Revises: 0008_expand_empresa

Create Date: 2026-06-17

"""

from alembic import op

import sqlalchemy as sa

revision: str = '0009_add_documento_sha256'

down_revision: str = '0008_expand_empresa'

branch_labels = None

depends_on = None


def upgrade() -> None:
    op.add_column(
        'documentos_fiscais',
        sa.Column('conteudo_sha256', sa.String(64), nullable=True)
    )
    op.create_unique_constraint(
        'uq_documentos_fiscais_empresa_conteudo_sha256',
        'documentos_fiscais',
        ['empresa_id', 'conteudo_sha256']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_documentos_fiscais_empresa_conteudo_sha256',
        'documentos_fiscais',
        type_='unique'
    )
    op.drop_column('documentos_fiscais', 'conteudo_sha256')
