"""Preserve XML operation observations without classifying legacy documents."""
from alembic import op
import sqlalchemy as sa

revision = "0058_documento_operacao_observada"
down_revision = "0057_documento_emitente_observado"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documentos_fiscais", sa.Column("natureza_operacao_observada", sa.String(), nullable=True))
    op.add_column("documentos_fiscais", sa.Column("finalidade_emissao_observada", sa.String(), nullable=True))


def downgrade():
    op.drop_column("documentos_fiscais", "finalidade_emissao_observada")
    op.drop_column("documentos_fiscais", "natureza_operacao_observada")
