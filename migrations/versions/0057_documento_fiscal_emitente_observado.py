"""Preserve observed XML emitter without inferring legacy document identity."""
from alembic import op
import sqlalchemy as sa

revision = "0057_documento_emitente_observado"
down_revision = "0056_mei_competencia_checkout_intent"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documentos_fiscais", sa.Column("cnpj_emitente", sa.String(), nullable=True))


def downgrade():
    op.drop_column("documentos_fiscais", "cnpj_emitente")
