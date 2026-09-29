"""Contrato RED: pagamento MEI materializa autoridade na mesma transacao."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
import app.services.checkout_offer_one_time_confirmation as confirmation


def _ambiente(*, ordem_id=701):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        plano = models.Plano(
            id=1,
            nome="controle legado",
            limite_cnpjs=1,
            limite_analises=1,
            preco=Decimal("29.90"),
            billing_type="monthly",
            ativo=True,
            tipo_acesso="relatorio",
        )

        owner = models.User(
            id=41,
            email=f"mei-confirmation-{ordem_id}@example.invalid",
            hashed_password="hash",
            plano_id=1,
        )

        empresa = models.Empresa(
            id=301,
            user_id=41,
            regime_tributario="mei",
            porte="mei",
            status_empresa="ativa",
        )

        oferta = models.CheckoutOffer(
            id=7,
            codigo="mei-das-one-time-company",
            nome_publico="MEI DAS",
            vertical="tax",
            commercial_model="one_time",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("39.90"),
            billing_period=None,
            usage_unit="competence",
            usage_limit=1,
            contract_version=1,
        )
        oferta.capabilities = [
            models.CheckoutOfferCapability(codigo="mei.das")
        ]

        key = f"mei-confirmation-order-{ordem_id}"

        intent = models.MeiCompetenciaCheckoutIntent(
            checkout_idempotency_key=key,
            user_id=41,
            empresa_id=301,
            competencia="202609",
            capability="mei.das",
            offer_code="mei-das-one-time-company",
        )

        ordem = models.OrdemCheckout(
            id=ordem_id,
            user_id=41,
            empresa_id=301,
            plano_id=None,
            offer_id=7,
            offer_code="mei-das-one-time-company",
            contract_version=1,
            vertical="tax",
            commercial_model="one_time",
            subject_type="company",
            subject_id=301,
            valor=Decimal("39.90"),
            moeda="BRL",
            estado="pending",
            idempotency_key=key,
            provider_order_id=f"provider-order-{ordem_id}",
            checkout_url=(
                f"https://checkout.example.invalid/order-{ordem_id}"
            ),
            billing_period=None,
            usage_unit="competence",
            usage_limit=1,
        )
        ordem.capabilities = [
            models.OrdemCheckoutCapability(codigo="mei.das")
        ]

        db.add(plano)
        db.flush()

        db.add(owner)
        db.flush()

        db.add(empresa)
        db.flush()

        db.add(oferta)
        db.flush()

        db.add(intent)
        db.flush()

        db.add(ordem)
        db.commit()

    return engine, Session


def _confirmar(Session, *, ordem_id=701):
    return confirmation.CheckoutOfferOneTimeConfirmer(
        Session
    ).confirmar_pagamento_autorizado(
        ordem_id,
        "8128",
        "4719",
        Decimal("39.90"),
        "BRL",
    )


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_mei_das_materializa_binding_e_replay_nao_duplica():
    engine, Session = _ambiente()

    try:
        resultado = _confirmar(Session)

        assert resultado.ordem_id == 701
        assert resultado.estado == "paid"

        with Session() as db:
            binding = db.scalars(
                select(models.MeiCompetenciaAuthorityBinding)
            ).one()

            assert binding.ordem_id == 701
            assert binding.empresa_id == 301
            assert binding.competencia == "202609"
            assert binding.capability == "mei.das"

            assert _count(db, models.EventoPagamento) == 1
            assert _count(db, models.Pagamento) == 1
            assert _count(db, models.CheckoutOfferGrant) == 1
            assert _count(
                db,
                models.MeiCompetenciaAuthorityBinding,
            ) == 1

        repetido = _confirmar(Session)
        assert repetido == resultado

        with Session() as db:
            assert _count(db, models.EventoPagamento) == 1
            assert _count(db, models.Pagamento) == 1
            assert _count(db, models.CheckoutOfferGrant) == 1
            assert _count(
                db,
                models.MeiCompetenciaAuthorityBinding,
            ) == 1
    finally:
        engine.dispose()


def test_falha_do_binding_reverte_confirmacao_inteira():
    engine, Session = _ambiente(ordem_id=702)

    def _falhar_binding(_mapper, _connection, _target):
        raise RuntimeError(
            "segredo interno que jamais pode escapar"
        )

    event.listen(
        models.MeiCompetenciaAuthorityBinding,
        "before_insert",
        _falhar_binding,
    )

    try:
        with pytest.raises(
            confirmation.CheckoutOfferOneTimeConfirmationError
        ) as capturada:
            confirmation.CheckoutOfferOneTimeConfirmer(
                Session
            ).confirmar_pagamento_autorizado(
                702,
                "8129",
                "4720",
                Decimal("39.90"),
                "BRL",
            )

        texto = f"{capturada.value!s} {capturada.value!r}".lower()
        assert "segredo" not in texto
        assert "interno" not in texto

    finally:
        event.remove(
            models.MeiCompetenciaAuthorityBinding,
            "before_insert",
            _falhar_binding,
        )

    try:
        with Session() as db:
            ordem = db.get(models.OrdemCheckout, 702)

            assert ordem is not None
            assert (ordem.estado, ordem.payment_id) == (
                "pending",
                None,
            )

            assert _count(db, models.EventoPagamento) == 0
            assert _count(db, models.Pagamento) == 0
            assert _count(db, models.CheckoutOfferGrant) == 0
            assert _count(
                db,
                models.CheckoutOfferGrantCapability,
            ) == 0
            assert _count(
                db,
                models.MeiCompetenciaAuthorityBinding,
            ) == 0
    finally:
        engine.dispose()
