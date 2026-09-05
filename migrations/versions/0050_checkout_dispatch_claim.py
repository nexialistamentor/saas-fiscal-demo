"""0050_checkout_dispatch_claim

Durable short claim for checkout provider dispatch.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0050_checkout_dispatch_claim"
down_revision: str = "0049_checkout_offer_limited_campaign_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ordens_checkout",
        sa.Column(
            "checkout_dispatch_claimed_at",
            sa.DateTime(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ordens_checkout", "checkout_dispatch_claimed_at")
