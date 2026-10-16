"""P1-04C2 — separate Enterprise documentary intent, immutable at PG boundary.

No checkout or payment table is altered. Does not publish any offer.
"""
from alembic import op
import sqlalchemy as sa

revision = "0061_enterprise_documental_checkout_intent"
down_revision = "0060_item_fiscal_st_observado_xml"
branch_labels = None
depends_on = None

_TABLE = "enterprise_documental_checkout_intents"
_FUNCTION = "reject_enterprise_documental_intent_mutation"
_TRIGGER = "trg_enterprise_documental_intent_append_only"
_INDEXED = (
    "user_id", "empresa_id", "relatorio_analise_id",
    "documento_fiscal_id", "offer_id",
)


def upgrade():
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checkout_idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("relatorio_analise_id", sa.Integer(), sa.ForeignKey("relatorios_analise.id"), nullable=False),
        sa.Column("documento_fiscal_id", sa.Integer(), sa.ForeignKey("documentos_fiscais.id"), nullable=False),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("checkout_offers.id"), nullable=False),
        sa.Column("offer_code", sa.String(length=120), nullable=False),
        sa.Column("offer_contract_version", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=120), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("xml_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("checkout_idempotency_key", name="uq_enterprise_documental_intent_key"),
        sa.CheckConstraint("capability = 'enterprise.diagnostic.documental'", name="ck_enterprise_documental_intent_capability"),
        sa.CheckConstraint("offer_code = 'enterprise-documental-diagnostic-one-time-company'", name="ck_enterprise_documental_intent_offer"),
        sa.CheckConstraint("offer_contract_version > 0", name="ck_enterprise_documental_intent_version"),
        sa.CheckConstraint("length(request_fingerprint) = 64 AND request_fingerprint = lower(request_fingerprint)", name="ck_enterprise_documental_intent_fingerprint"),
        sa.CheckConstraint("length(xml_sha256) = 64 AND xml_sha256 = lower(xml_sha256)", name="ck_enterprise_documental_intent_xml_hash"),
    )
    for column in _INDEXED:
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])
    op.execute(f"""
        CREATE FUNCTION {_FUNCTION}() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'enterprise_documental_checkout_intents is append-only';
        END;
        $$
    """)
    op.execute(f"""
        CREATE TRIGGER {_TRIGGER}
        BEFORE UPDATE OR DELETE ON {_TABLE}
        FOR EACH ROW EXECUTE FUNCTION {_FUNCTION}()
    """)


def downgrade():
    op.execute(f"DROP TRIGGER {_TRIGGER} ON {_TABLE}")
    op.execute(f"DROP FUNCTION {_FUNCTION}()")
    for column in reversed(_INDEXED):
        op.drop_index(f"ix_{_TABLE}_{column}", table_name=_TABLE)
    op.drop_table(_TABLE)
