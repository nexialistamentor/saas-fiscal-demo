"""Contrato RED offline da persistencia do grant one_time compartilhado.

Este contrato cobre somente o modelo persistente. Nao confirma pagamentos,
nao consome saldo e nao cria grants automaticamente a partir de ordens.
"""

from decimal import Decimal
from importlib import import_module

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


def test_payments_multi_vertical_one_time_grant_persistence_contract_red():
    from app import models

    assert hasattr(models, "CheckoutOfferGrant")
    assert hasattr(models, "CheckoutOfferGrantCapability")

    migration = import_module("migrations.versions.0047_one_time_offer_grants")

    assert migration.revision == "0047_one_time_offer_grants"
    assert migration.down_revision == "0046_multi_vertical_order_snapshot"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)

    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _ativar_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session.begin() as db:
        user = models.User(
            id=41,
            email="grant-owner@example.invalid",
            hashed_password="hash-de-teste",
        )
        empresa = models.Empresa(
            id=301,
            razao_social="Empresa grant one time",
            user_id=41,
        )
        oferta = models.CheckoutOffer(
            id=7,
            codigo="document-one-time-company",
            nome_publico="Documentos one time",
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("79.50"),
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
            contract_version=3,
        )
        ordem = models.OrdemCheckout(
            id=701,
            user_id=41,
            empresa_id=301,
            plano_id=None,
            offer_id=7,
            offer_code="document-one-time-company",
            contract_version=3,
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            subject_id=301,
            valor=Decimal("79.50"),
            moeda="BRL",
            estado="pending",
            idempotency_key="grant-order-701",
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
        )
        ordem.capabilities = [
            models.OrdemCheckoutCapability(codigo="document.extract"),
            models.OrdemCheckoutCapability(codigo="document.validate"),
        ]
        ordem_negativos = models.OrdemCheckout(
            id=702,
            user_id=41,
            empresa_id=301,
            plano_id=None,
            offer_id=7,
            offer_code="document-one-time-company",
            contract_version=3,
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            subject_id=301,
            valor=Decimal("79.50"),
            moeda="BRL",
            estado="pending",
            idempotency_key="grant-negative-order-702",
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
        )
        db.add_all([user, empresa, oferta, ordem, ordem_negativos])

    with Session.begin() as db:
        grant = models.CheckoutOfferGrant(
            ordem_id=701,
            usage_unit="document",
            usage_limit=7,
            usage_consumed=0,
            estado="active",
        )
        grant.capabilities = [
            models.CheckoutOfferGrantCapability(codigo="document.extract"),
            models.CheckoutOfferGrantCapability(codigo="document.validate"),
        ]
        db.add(grant)
        db.flush()
        grant_id = grant.id

    with Session() as db:
        ordem = db.get(models.OrdemCheckout, 701)
        grant = db.get(models.CheckoutOfferGrant, grant_id)
        codigos = tuple(capability.codigo for capability in grant.capabilities)

        assert ordem.grant is grant
        assert grant.ordem is ordem
        assert grant.ordem_id == ordem.id
        assert grant.usage_unit == "document"
        assert grant.usage_limit == 7
        assert grant.usage_consumed == 0
        assert grant.estado == "active"
        assert grant.created_at is not None
        assert codigos == ("document.extract", "document.validate")
        assert len(grant.capabilities) == 2
        assert all(capability.grant is grant for capability in grant.capabilities)
        assert all(capability.grant_id == grant.id for capability in grant.capabilities)
        assert all(not hasattr(capability, "usage_limit") for capability in grant.capabilities)
        assert all(not hasattr(capability, "usage_consumed") for capability in grant.capabilities)
        assert db.scalar(select(func.count()).select_from(models.CheckoutOfferGrant)) == 1
        assert db.scalar(
            select(func.count()).select_from(models.CheckoutOfferGrantCapability)
        ) == 2
        assert db.scalar(select(func.count()).select_from(models.Entitlement)) == 0
        user = db.get(models.User, 41)
        assert user.plano_id is None
        assert user.consulta_paga is False

    def contagens(db):
        return (
            db.scalar(select(func.count()).select_from(models.CheckoutOfferGrant)),
            db.scalar(
                select(func.count()).select_from(models.CheckoutOfferGrantCapability)
            ),
        )

    def rejeitar(instancia):
        with Session() as db:
            antes = contagens(db)
            db.add(instancia)
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
            assert contagens(db) == antes

    rejeitar(models.CheckoutOfferGrant(
        ordem_id=701, usage_unit="document", usage_limit=1,
        usage_consumed=0, estado="active",
    ))
    rejeitar(models.CheckoutOfferGrant(
        ordem_id=None, usage_unit="document", usage_limit=1,
        usage_consumed=0, estado="active",
    ))
    rejeitar(models.CheckoutOfferGrant(
        ordem_id=999999, usage_unit="document", usage_limit=1,
        usage_consumed=0, estado="active",
    ))
    for limite in (0, -1):
        rejeitar(models.CheckoutOfferGrant(
            ordem_id=702, usage_unit="document", usage_limit=limite,
            usage_consumed=0, estado="active",
        ))
    rejeitar(models.CheckoutOfferGrant(
        ordem_id=702, usage_unit="document", usage_limit=7,
        usage_consumed=-1, estado="active",
    ))
    rejeitar(models.CheckoutOfferGrant(
        ordem_id=702, usage_unit="document", usage_limit=7,
        usage_consumed=8, estado="active",
    ))
    rejeitar(models.CheckoutOfferGrant(
        ordem_id=702, usage_unit="document", usage_limit=7,
        usage_consumed=0, estado="invalid",
    ))
    for unidade in (None, "", " ", "Document", " document", "document "):
        rejeitar(models.CheckoutOfferGrant(
            ordem_id=702, usage_unit=unidade, usage_limit=7,
            usage_consumed=0, estado="active",
        ))

    rejeitar(models.CheckoutOfferGrantCapability(
        grant_id=None, codigo="document.extract",
    ))
    rejeitar(models.CheckoutOfferGrantCapability(
        grant_id=999999, codigo="document.extract",
    ))
    for codigo in (None, "", " "):
        rejeitar(models.CheckoutOfferGrantCapability(
            grant_id=grant_id, codigo=codigo,
        ))
    rejeitar(models.CheckoutOfferGrantCapability(
        grant_id=grant_id, codigo="document.extract",
    ))

    with Session() as db:
        grant_com_defaults = models.CheckoutOfferGrant(
            ordem_id=702,
            usage_unit="document",
            usage_limit=1,
        )
        db.add(grant_com_defaults)
        db.flush()
        assert grant_com_defaults.usage_consumed == 0
        assert grant_com_defaults.estado == "active"
        db.rollback()
        assert contagens(db) == (1, 2)
