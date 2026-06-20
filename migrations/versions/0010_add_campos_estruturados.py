"""DT-DOC-01: campos_estruturados em DocumentoIngerido

Revision ID: 0010_add_campos_estruturados
Revises: 0009_add_documento_sha256
Create Date: 2026-06-19

CT-DOC-001 secao 3: DocumentoIngerido deve persistir a estrutura
completa de CampoNormalizado (valor, confianca, origem,
validado_humano), nao apenas nomes de campos.

Coluna nova e paralela a campos_extraidos (nao substitui).
campos_extraidos mantem o significado actual: lista de nomes
de campos detectados (metadado historico, V1).
campos_estruturados passa a ser a base para promotion (CT-DOC-001).

Sem backfill. Sem alterar dados antigos. Sem remover colunas.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0010_add_campos_estruturados'
down_revision: str = '0009_add_documento_sha256'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'documentos_ingeridos',
        sa.Column('campos_estruturados', postgresql.JSONB, nullable=True)
    )


def downgrade() -> None:
    op.drop_column('documentos_ingeridos', 'campos_estruturados')
