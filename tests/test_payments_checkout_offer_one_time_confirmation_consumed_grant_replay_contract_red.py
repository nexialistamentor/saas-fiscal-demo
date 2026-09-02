"""Contrato RED do replay apos consumo legitimo de grant one-time."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


_CONFIRMATION = (701, "8128", "4719", Decimal("79.50"), "BRL")


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _ativar_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=True)
    with Session.begin() as db:
        plano_legado = models.Plano(
            id=7,
            nome="Plano legado de controle",
            limite_cnpjs=1,
            limite_analises=1,
            preco=Decimal("29.90"),
            billing_type="monthly",
        )
        owner = models.User(
            id=41,
            email="consumed-replay-owner@example.invalid",
            hashed_password="hash-de-teste",
        )
        empresa = models.Empresa(
            id=301,
            razao_social="Empresa consumed replay",
            user_id=41,
        )
        oferta = models.CheckoutOffer(
            id=7,
            codigo="document-one-time-company",
            nome_publico="Documentos avulsos",
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
        oferta.capabilities = [
            models.CheckoutOfferCapability(codigo="document.extract"),
            models.CheckoutOfferCapability(codigo="document.validate"),
        ]
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
            idempotency_key="consumed-replay-order-701",
            provider_order_id="provider-consumed-replay-701",
            checkout_url="https://checkout.example.invalid/consumed-replay-701",
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
        )
        ordem.capabilities = [
            models.OrdemCheckoutCapability(codigo="document.extract"),
            models.OrdemCheckoutCapability(codigo="document.validate"),
        ]
        db.add_all((plano_legado, owner, empresa, oferta))
        db.flush()
        db.add(ordem)
    return engine, Session


def _confirmar(confirmation, Session, argumentos=_CONFIRMATION):
    return confirmation.CheckoutOfferOneTimeConfirmer(
        Session
    ).confirmar_pagamento_autorizado(*argumentos)


def _linhas(db, model):
    colunas = tuple(model.__table__.columns)
    return tuple(
        tuple(getattr(row, coluna.name) for coluna in colunas)
        for row in db.scalars(select(model).order_by(model.id)).all()
    )


def _estado_persistido(Session, models):
    with Session() as db:
        return {
            model.__name__: _linhas(db, model)
            for model in (
                models.OrdemCheckout,
                models.OrdemCheckoutCapability,
                models.EventoPagamento,
                models.Pagamento,
                models.CheckoutOfferGrant,
                models.CheckoutOfferGrantCapability,
                models.Entitlement,
            )
        }


def _contagens(Session, models):
    with Session() as db:
        return {
            model.__name__: db.scalar(select(func.count()).select_from(model))
            for model in (
                models.EventoPagamento,
                models.Pagamento,
                models.CheckoutOfferGrant,
                models.CheckoutOfferGrantCapability,
                models.Entitlement,
            )
        }


def _grant_imutavel(Session, models):
    with Session() as db:
        grant = db.scalars(select(models.CheckoutOfferGrant)).one()
        return (
            grant.id,
            grant.ordem_id,
            grant.usage_unit,
            grant.usage_limit,
            grant.created_at,
            tuple(
                (capability.id, capability.grant_id, capability.codigo)
                for capability in grant.capabilities
            ),
        )


def _confirmado(confirmation, models):
    engine, Session = _ambiente(models)
    resultado = _confirmar(confirmation, Session)
    return engine, Session, resultado


def _corromper(Session, models, caso):
    with Session.begin() as db:
        if caso == "ordem_corrompida":
            db.get(models.OrdemCheckout, 701).usage_limit = 6
        elif caso == "pagamento_ausente":
            db.delete(db.scalars(select(models.Pagamento)).one())
        elif caso == "pagamento_corrompido":
            db.scalars(select(models.Pagamento)).one().status = "refunded"
        elif caso == "grant_ausente":
            db.delete(db.scalars(select(models.CheckoutOfferGrant)).one())
        elif caso == "grant_corrompido":
            db.scalars(
                select(models.CheckoutOfferGrant)
            ).one().usage_unit = "report"
        else:
            raise AssertionError(f"caso de corrupcao desconhecido: {caso}")


def _assert_replay_recusado(confirmation, models, caso):
    engine, Session, _resultado = _confirmado(confirmation, models)
    try:
        _corromper(Session, models, caso)
        antes = _estado_persistido(Session, models)
        with pytest.raises(confirmation.CheckoutOfferOneTimeConfirmationError):
            _confirmar(confirmation, Session)
        assert _estado_persistido(Session, models) == antes
    finally:
        engine.dispose()


def test_payments_checkout_offer_one_time_confirmation_consumed_grant_replay_contract_red():
    import app.services.checkout_offer_one_time_confirmation as confirmation

    from app import models

    engine, Session, primeiro = _confirmado(confirmation, models)
    try:
        assert vars(primeiro) == {
            "ordem_id": 701,
            "user_id": 41,
            "empresa_id": 301,
            "estado": "paid",
            "payment_id": "4719",
            "grant_id": primeiro.grant_id,
            "usage_unit": "document",
            "usage_limit": 7,
            "usage_consumed": 0,
            "capabilities": ("document.extract", "document.validate"),
        }
        assert _contagens(Session, models) == {
            "EventoPagamento": 1,
            "Pagamento": 1,
            "CheckoutOfferGrant": 1,
            "CheckoutOfferGrantCapability": 2,
            "Entitlement": 0,
        }

        # O replay convergente de controle prova que todo o restante e valido.
        antes_controle = _estado_persistido(Session, models)
        assert _confirmar(confirmation, Session) == primeiro
        assert _estado_persistido(Session, models) == antes_controle

        # Identidades e termos divergentes permanecem fail-closed e imutaveis.
        for argumentos in (
            (701, "8129", "4719", Decimal("79.50"), "BRL"),
            (701, "8128", "4720", Decimal("79.50"), "BRL"),
            (701, "8128", "4719", Decimal("79.51"), "BRL"),
            (701, "8128", "4719", Decimal("79.50"), "USD"),
            (999999, "8128", "4719", Decimal("79.50"), "BRL"),
        ):
            antes_divergente = _estado_persistido(Session, models)
            with pytest.raises(
                confirmation.CheckoutOfferOneTimeConfirmationError
            ):
                _confirmar(confirmation, Session, argumentos)
            assert _estado_persistido(Session, models) == antes_divergente

        # Ausencia ou corrupcao de ordem, pagamento e grant nunca converge.
        for caso in (
            "ordem_corrompida",
            "pagamento_ausente",
            "pagamento_corrompido",
            "grant_ausente",
            "grant_corrompido",
        ):
            _assert_replay_recusado(confirmation, models, caso)

        imutavel = _grant_imutavel(Session, models)
        falhas = []
        for usage_consumed, estado in ((1, "active"), (7, "exhausted")):
            with Session.begin() as db:
                grant = db.scalars(select(models.CheckoutOfferGrant)).one()
                grant.usage_consumed = usage_consumed
                grant.estado = estado
            assert _grant_imutavel(Session, models) == imutavel
            antes_replay = _estado_persistido(Session, models)
            try:
                repetido = _confirmar(confirmation, Session)
            except confirmation.CheckoutOfferOneTimeConfirmationError:
                falhas.append(f"{estado}/usage_consumed={usage_consumed}")
            else:
                assert vars(repetido) == {
                    **vars(primeiro),
                    "usage_consumed": usage_consumed,
                }
            assert _estado_persistido(Session, models) == antes_replay
            assert _grant_imutavel(Session, models) == imutavel
            assert _contagens(Session, models) == {
                "EventoPagamento": 1,
                "Pagamento": 1,
                "CheckoutOfferGrant": 1,
                "CheckoutOfferGrantCapability": 2,
                "Entitlement": 0,
            }

        assert not falhas, (
            "replay legitimo recusado somente apos consumo do grant: "
            + ", ".join(falhas)
        )
    finally:
        engine.dispose()
