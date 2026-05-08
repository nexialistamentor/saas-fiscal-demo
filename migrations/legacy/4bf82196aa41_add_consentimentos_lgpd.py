"""add_consentimentos_lgpd

Revision ID: 4bf82196aa41
Revises: 34664977463a
Create Date: 2026-05-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4bf82196aa41"
down_revision: Union[str, Sequence[str], None] = "34664977463a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "consentimentos_lgpd",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("versao_politica", sa.String(length=50), nullable=False),
        sa.Column("finalidade", sa.String(length=200), nullable=False),
        sa.Column("consentiu", sa.Boolean(), nullable=False),
        sa.Column("consentiu_em", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consentimentos_lgpd_id"),
        "consentimentos_lgpd",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_consentimentos_lgpd_id"), table_name="consentimentos_lgpd")
    op.drop_table("consentimentos_lgpd")
