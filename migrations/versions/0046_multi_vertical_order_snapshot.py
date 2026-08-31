"""0046_multi_vertical_order_snapshot

Snapshot comercial duravel para ordens baseadas em ofertas.
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0046_multi_vertical_order_snapshot"
down_revision: str = "0045_multi_vertical_checkout_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ordens_checkout", "empresa_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("ordens_checkout", "plano_id", existing_type=sa.Integer(), nullable=True)
    for coluna in (
        sa.Column("offer_id", sa.Integer(), nullable=True),
        sa.Column("offer_code", sa.String(length=120), nullable=True),
        sa.Column("contract_version", sa.Integer(), nullable=True),
        sa.Column("vertical", sa.String(length=20), nullable=True),
        sa.Column("commercial_model", sa.String(length=20), nullable=True),
        sa.Column("subject_type", sa.String(length=20), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("billing_period", sa.String(length=20), nullable=True),
        sa.Column("usage_unit", sa.String(length=50), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
    ):
        op.add_column("ordens_checkout", coluna)
    op.create_foreign_key(
        "fk_ordens_checkout_offer_id", "ordens_checkout", "checkout_offers",
        ["offer_id"], ["id"],
    )
    op.create_index("ix_ordens_checkout_offer_id", "ordens_checkout", ["offer_id"])
    checks = (
        ("ck_ordens_checkout_formato_coerente", "(offer_id IS NULL AND plano_id IS NOT NULL AND empresa_id IS NOT NULL AND offer_code IS NULL AND contract_version IS NULL AND vertical IS NULL AND commercial_model IS NULL AND subject_type IS NULL AND subject_id IS NULL AND billing_period IS NULL AND usage_unit IS NULL AND usage_limit IS NULL) OR (offer_id IS NOT NULL AND plano_id IS NULL AND offer_code IS NOT NULL AND contract_version IS NOT NULL AND vertical IS NOT NULL AND commercial_model IS NOT NULL AND subject_type IS NOT NULL AND subject_id IS NOT NULL)"),
        ("ck_ordens_checkout_offer_commercial_model", "offer_id IS NULL OR commercial_model IN ('monthly', 'one_time')"),
        ("ck_ordens_checkout_offer_vertical", "offer_id IS NULL OR vertical IN ('tax', 'document')"),
        ("ck_ordens_checkout_offer_subject_type", "offer_id IS NULL OR subject_type IN ('cpf', 'company', 'institution')"),
        ("ck_ordens_checkout_offer_identidade_positiva", "offer_id IS NULL OR (contract_version > 0 AND subject_id > 0)"),
        ("ck_ordens_checkout_offer_company_coerente", "offer_id IS NULL OR subject_type <> 'company' OR (empresa_id IS NOT NULL AND subject_id = empresa_id)"),
        ("ck_ordens_checkout_offer_monthly_coerente", "offer_id IS NULL OR commercial_model <> 'monthly' OR (billing_period = 'month' AND usage_unit IS NULL AND usage_limit IS NULL)"),
        ("ck_ordens_checkout_offer_one_time_coerente", "offer_id IS NULL OR commercial_model <> 'one_time' OR (billing_period IS NULL AND usage_unit IS NOT NULL AND length(trim(usage_unit)) > 0 AND usage_limit > 0)"),
    )
    for nome, expressao in checks:
        op.create_check_constraint(nome, "ordens_checkout", expressao)
    op.create_table(
        "ordem_checkout_capabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ordem_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=120), nullable=False),
        sa.CheckConstraint("codigo = lower(codigo) AND codigo = trim(codigo) AND length(codigo) > 0", name="ck_ordem_checkout_capabilities_codigo_canonico"),
        sa.ForeignKeyConstraint(["ordem_id"], ["ordens_checkout.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ordem_id", "codigo", name="uq_ordem_checkout_capabilities_ordem_codigo"),
    )
    op.create_index("ix_ordem_checkout_capabilities_ordem_id", "ordem_checkout_capabilities", ["ordem_id"])


def downgrade() -> None:
    op.drop_index("ix_ordem_checkout_capabilities_ordem_id", table_name="ordem_checkout_capabilities")
    op.drop_table("ordem_checkout_capabilities")
    for nome in (
        "ck_ordens_checkout_offer_one_time_coerente",
        "ck_ordens_checkout_offer_monthly_coerente",
        "ck_ordens_checkout_offer_company_coerente",
        "ck_ordens_checkout_offer_identidade_positiva",
        "ck_ordens_checkout_offer_subject_type",
        "ck_ordens_checkout_offer_vertical",
        "ck_ordens_checkout_offer_commercial_model",
        "ck_ordens_checkout_formato_coerente",
    ):
        op.drop_constraint(nome, "ordens_checkout", type_="check")
    op.drop_index("ix_ordens_checkout_offer_id", table_name="ordens_checkout")
    op.drop_constraint("fk_ordens_checkout_offer_id", "ordens_checkout", type_="foreignkey")
    for nome in (
        "usage_limit", "usage_unit", "billing_period", "subject_id", "subject_type",
        "commercial_model", "vertical", "contract_version", "offer_code", "offer_id",
    ):
        op.drop_column("ordens_checkout", nome)
    op.alter_column("ordens_checkout", "plano_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("ordens_checkout", "empresa_id", existing_type=sa.Integer(), nullable=False)
