"""add_alerta_fiscal_auditoria

Revision ID: 6607d5149e78
Revises: c8f01a2b9e3d
Create Date: 2026-04-27 19:53:05.444584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6607d5149e78'
down_revision: Union[str, Sequence[str], None] = 'c8f01a2b9e3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "alertas_fiscais",
        sa.Column("processado", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "alertas_fiscais",
        sa.Column("processado_em", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "alertas_fiscais",
        sa.Column("processado_por", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "alertas_fiscais",
        sa.Column("notas_resolucao", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("alertas_fiscais", "notas_resolucao")
    op.drop_column("alertas_fiscais", "processado_por")
    op.drop_column("alertas_fiscais", "processado_em")
    op.drop_column("alertas_fiscais", "processado")
