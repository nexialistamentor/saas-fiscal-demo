"""merge_baseline_com_chain_incremental

Revision ID: 6f0cd796fe94
Revises: 0000_baseline, 1c83e761b2d8
Create Date: 2026-05-08 19:29:23.646293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f0cd796fe94'
down_revision: Union[str, Sequence[str], None] = ('0000_baseline', '1c83e761b2d8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
