"""Presença documental ST; históricos permanecem UNKNOWN (NULL)."""
from alembic import op
import sqlalchemy as sa

revision = "0060_item_fiscal_st_observado_xml"
down_revision = "0059_mei_receita_informada"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itens_fiscais", sa.Column("st_observado_xml", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("itens_fiscais", "st_observado_xml")
