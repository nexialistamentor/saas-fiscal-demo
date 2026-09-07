"""0044a_alembic_version_capacity

Expande a capacidade do identificador de revision do Alembic.

Revision ID: 0044a_alembic_version_capacity
Revises: 0044_payments_durable_ledger
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0044a_alembic_version_capacity"
down_revision: str = "0044_payments_durable_ledger"
branch_labels = None
depends_on = None

_LEGACY_VERSION_LENGTH = 32
_EXPANDED_VERSION_LENGTH = 64


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=_LEGACY_VERSION_LENGTH),
        type_=sa.String(length=_EXPANDED_VERSION_LENGTH),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=_EXPANDED_VERSION_LENGTH),
        type_=sa.String(length=_LEGACY_VERSION_LENGTH),
        existing_nullable=False,
    )
