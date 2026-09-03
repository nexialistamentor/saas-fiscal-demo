"""0049_checkout_offer_limited_campaign_foundation

Persistent foundation for limited checkout offer campaigns.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0049_checkout_offer_limited_campaign_foundation"
down_revision: str = "0048_checkout_offer_grant_consumption_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkout_offer_campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=120), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("purchase_limit", sa.Integer(), nullable=False),
        sa.Column("reservation_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "codigo = lower(codigo) AND codigo = trim(codigo) "
            "AND length(codigo) > 0 AND codigo NOT LIKE '%--%'",
            name="ck_checkout_offer_campaigns_codigo_canonico",
        ),
        sa.CheckConstraint(
            "estado IN ('draft', 'active', 'retired')",
            name="ck_checkout_offer_campaigns_estado_valido",
        ),
        sa.CheckConstraint(
            "purchase_limit > 0",
            name="ck_checkout_offer_campaigns_purchase_limit_positivo",
        ),
        sa.CheckConstraint(
            "reservation_ttl_seconds > 0",
            name="ck_checkout_offer_campaigns_reservation_ttl_seconds_positivo",
        ),
        sa.CheckConstraint(
            "contract_version > 0",
            name="ck_checkout_offer_campaigns_contract_version_positivo",
        ),
        sa.ForeignKeyConstraint(["offer_id"], ["checkout_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "codigo",
            name="uq_checkout_offer_campaigns_codigo",
        ),
    )
    op.create_index(
        "uq_checkout_offer_campaigns_offer_active",
        "checkout_offer_campaigns",
        ["offer_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'active'"),
        sqlite_where=sa.text("estado = 'active'"),
    )

    for column in (
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("campaign_code", sa.String(length=120), nullable=True),
        sa.Column("campaign_contract_version", sa.Integer(), nullable=True),
        sa.Column("campaign_purchase_limit", sa.Integer(), nullable=True),
        sa.Column(
            "campaign_reservation_expires_at",
            sa.DateTime(),
            nullable=True,
        ),
    ):
        op.add_column("ordens_checkout", column)
    op.create_foreign_key(
        "fk_ordens_checkout_campaign_id",
        "ordens_checkout",
        "checkout_offer_campaigns",
        ["campaign_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_ordens_checkout_campaign_snapshot_coerente",
        "ordens_checkout",
        "(campaign_id IS NULL AND campaign_code IS NULL "
        "AND campaign_contract_version IS NULL "
        "AND campaign_purchase_limit IS NULL "
        "AND campaign_reservation_expires_at IS NULL) "
        "OR (campaign_id IS NOT NULL AND campaign_code IS NOT NULL "
        "AND campaign_contract_version IS NOT NULL "
        "AND campaign_purchase_limit IS NOT NULL "
        "AND campaign_reservation_expires_at IS NOT NULL "
        "AND campaign_contract_version > 0 "
        "AND campaign_purchase_limit > 0)",
    )

    op.create_table(
        "checkout_offer_campaign_reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("reserved_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("expired_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "estado IN ('reserved', 'confirmed', 'released', 'expired')",
            name="ck_checkout_offer_campaign_reservations_estado_valido",
        ),
        sa.CheckConstraint(
            "expires_at > reserved_at",
            name="ck_checkout_offer_campaign_reservations_intervalo_valido",
        ),
        sa.CheckConstraint(
            "(estado = 'reserved' AND confirmed_at IS NULL "
            "AND released_at IS NULL AND expired_at IS NULL) "
            "OR (estado = 'confirmed' AND confirmed_at IS NOT NULL "
            "AND released_at IS NULL AND expired_at IS NULL) "
            "OR (estado = 'released' AND confirmed_at IS NULL "
            "AND released_at IS NOT NULL AND expired_at IS NULL) "
            "OR (estado = 'expired' AND confirmed_at IS NULL "
            "AND released_at IS NULL AND expired_at IS NOT NULL)",
            name=(
                "ck_checkout_offer_campaign_reservations_"
                "timestamps_coerentes"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["checkout_offer_campaigns.id"],
        ),
        sa.ForeignKeyConstraint(["ordem_id"], ["ordens_checkout.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ordem_id",
            name="uq_checkout_offer_campaign_reservations_ordem_id",
        ),
    )
    op.create_index(
        "ix_checkout_offer_campaign_reservations_camp_estado_expires_at",
        "checkout_offer_campaign_reservations",
        ["campaign_id", "estado", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_checkout_offer_campaign_reservations_camp_estado_expires_at",
        table_name="checkout_offer_campaign_reservations",
    )
    op.drop_table("checkout_offer_campaign_reservations")

    op.drop_constraint(
        "ck_ordens_checkout_campaign_snapshot_coerente",
        "ordens_checkout",
        type_="check",
    )
    op.drop_constraint(
        "fk_ordens_checkout_campaign_id",
        "ordens_checkout",
        type_="foreignkey",
    )
    for column_name in (
        "campaign_reservation_expires_at",
        "campaign_purchase_limit",
        "campaign_contract_version",
        "campaign_code",
        "campaign_id",
    ):
        op.drop_column("ordens_checkout", column_name)

    op.drop_index(
        "uq_checkout_offer_campaigns_offer_active",
        table_name="checkout_offer_campaigns",
    )
    op.drop_table("checkout_offer_campaigns")
