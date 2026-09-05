"""Contrato RED PostgreSQL: approved confirma a reservation da campanha."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import subprocess
import time
import uuid

import psycopg2
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker


_USER_ID = 41
_EMPRESA_ID = 301
_OFFER_ID = 101
_OFFER_CODE = "document-one-time-company"
_CAMPAIGN_ID = 501
_CAMPAIGN_CODE = "document-campaign-2026"
_ORDER_ID = 1301
_RESERVATION_ID = 2301
_AMOUNT = Decimal("79.50")
_CURRENCY = "BRL"
_P1 = "910001"
_N1 = "810001"
_SIGNATURE = "offline-authenticated-signature-e1"
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)
_CAMPAIGN_SNAPSHOT = (
    _CAMPAIGN_ID,
    _CAMPAIGN_CODE,
    11,
    50,
    _LIVE_EXPIRES_AT,
)


class _AlwaysValidSignatureVerifier:
    def __init__(self):
        self.calls = []

    def verificar(self, event, signature):
        self.calls.append((deepcopy(event), signature))
        return True


class _ReadOnlyFakePaymentClient:
    def __init__(self):
        self.calls = []
        self._payment = {
            "id": _P1,
            "external_reference": str(_ORDER_ID),
            "status": "approved",
            "transaction_amount": _AMOUNT,
            "currency_id": _CURRENCY,
        }

    def obter_pagamento(self, *, payment_id):
        self.calls.append(payment_id)
        assert payment_id == _P1
        return deepcopy(self._payment)

    def snapshot(self):
        return deepcopy(self._payment)


def _run(*args):
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _published_port(container):
    published = _run("docker", "port", container, "5432/tcp")
    assert published.returncode == 0, published.stderr
    mappings = [
        line.strip() for line in published.stdout.splitlines() if line.strip()
    ]
    assert len(mappings) == 1, mappings
    host, separator, raw_port = mappings[0].rpartition(":")
    assert separator == ":", mappings[0]
    assert host == "127.0.0.1", host
    assert raw_port.isascii() and raw_port.isdigit(), raw_port
    port = int(raw_port)
    assert 1 <= port <= 65535, port
    return port


def _wait_for_postgresql(port, database, password):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        connection = None
        try:
            connection = psycopg2.connect(
                host="127.0.0.1",
                port=port,
                dbname=database,
                user="postgres",
                password=password,
                connect_timeout=1,
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                probe = cursor.fetchone()
            assert probe == (1,), probe
            return
        except psycopg2.Error:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.25, remaining))
        finally:
            if connection is not None:
                connection.close()
    raise AssertionError(
        "PostgreSQL 16 Alpine did not become ready over "
        f"127.0.0.1:{port}"
    )


def _offer(models):
    offer = models.CheckoutOffer(
        id=_OFFER_ID,
        codigo=_OFFER_CODE,
        nome_publico="Documentos one-time",
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        estado="published",
        moeda=_CURRENCY,
        preco=_AMOUNT,
        billing_period=None,
        usage_unit="document",
        usage_limit=7,
        contract_version=3,
    )
    offer.capabilities = [
        models.CheckoutOfferCapability(codigo="document.extract"),
        models.CheckoutOfferCapability(codigo="document.validate"),
    ]
    return offer


def _order(models):
    order = models.OrdemCheckout(
        id=_ORDER_ID,
        user_id=_USER_ID,
        empresa_id=_EMPRESA_ID,
        plano_id=None,
        offer_id=_OFFER_ID,
        offer_code=_OFFER_CODE,
        contract_version=3,
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        subject_id=_EMPRESA_ID,
        valor=_AMOUNT,
        moeda=_CURRENCY,
        estado="pending",
        idempotency_key="campaign-reservation-confirmation-1301",
        provider_order_id="mp-provider-order-1301",
        checkout_url=(
            "https://www.mercadopago.com.br/checkout/v1/redirect/"
            "campaign-reservation-confirmation-1301"
        ),
        payment_id=None,
        billing_period=None,
        usage_unit="document",
        usage_limit=7,
        campaign_id=_CAMPAIGN_ID,
        campaign_code=_CAMPAIGN_CODE,
        campaign_contract_version=11,
        campaign_purchase_limit=50,
        campaign_reservation_expires_at=_LIVE_EXPIRES_AT,
    )
    order.capabilities = [
        models.OrdemCheckoutCapability(codigo="document.extract"),
        models.OrdemCheckoutCapability(codigo="document.validate"),
    ]
    return order


def _reservation(models):
    return models.CheckoutOfferCampaignReservation(
        id=_RESERVATION_ID,
        campaign_id=_CAMPAIGN_ID,
        ordem_id=_ORDER_ID,
        estado="reserved",
        reserved_at=_RESERVED_AT,
        expires_at=_LIVE_EXPIRES_AT,
        confirmed_at=None,
        released_at=None,
        expired_at=None,
    )


@contextmanager
def _environment(models):
    container = f"mei-0049d2-reservation-e1-{uuid.uuid4().hex[:12]}"
    database = "mei_campaign_reservation_confirmation_contract"
    password = uuid.uuid4().hex
    engine = None
    container_started = False

    try:
        started = _run(
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            container,
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={database}",
            "-p",
            "127.0.0.1::5432",
            "postgres:16-alpine",
        )
        assert started.returncode == 0, started.stderr
        container_started = True

        port = _published_port(container)
        _wait_for_postgresql(port, database, password)
        engine = create_engine(
            f"postgresql+psycopg2://postgres:{password}"
            f"@127.0.0.1:{port}/{database}",
            connect_args={
                "connect_timeout": 5,
                "options": (
                    "-c timezone=UTC -c lock_timeout=5000 "
                    "-c statement_timeout=10000"
                ),
            },
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            assert connection.execute(text("SHOW TIME ZONE")).scalar_one() == "UTC"

        models.Base.metadata.create_all(
            engine,
            tables=[
                models.Plano.__table__,
                models.User.__table__,
                models.Empresa.__table__,
                models.CheckoutOffer.__table__,
                models.CheckoutOfferCapability.__table__,
                models.CheckoutOfferCampaign.__table__,
                models.OrdemCheckout.__table__,
                models.OrdemCheckoutCapability.__table__,
                models.CheckoutOfferCampaignReservation.__table__,
                models.RelatorioAnalise.__table__,
                models.Pagamento.__table__,
                models.CheckoutOfferGrant.__table__,
                models.CheckoutOfferGrantCapability.__table__,
                models.EventoPagamento.__table__,
                models.Entitlement.__table__,
                models.MercadoPagoPaymentObservation.__table__,
            ],
        )
        Session = sessionmaker(bind=engine, expire_on_commit=True)

        with Session.begin() as db:
            db.add(
                models.User(
                    id=_USER_ID,
                    email="reservation-confirmation-owner@example.invalid",
                    hashed_password="hash-de-teste",
                )
            )
            db.flush()
            db.add_all(
                (
                    models.Empresa(
                        id=_EMPRESA_ID,
                        razao_social="Reservation Confirmation Owner",
                        user_id=_USER_ID,
                    ),
                    _offer(models),
                )
            )
            db.flush()
            db.add(
                models.CheckoutOfferCampaign(
                    id=_CAMPAIGN_ID,
                    codigo=_CAMPAIGN_CODE,
                    offer_id=_OFFER_ID,
                    estado="active",
                    purchase_limit=50,
                    reservation_ttl_seconds=3600,
                    contract_version=11,
                    criado_em=datetime(2024, 1, 1, 0, 0, 0),
                    atualizado_em=datetime(2024, 1, 1, 0, 0, 0),
                )
            )
            db.flush()
            db.add(_order(models))
            db.flush()
            db.add(_reservation(models))

        yield Session
    finally:
        if engine is not None:
            engine.dispose()
        if container_started:
            _run("docker", "rm", "--force", container)


def _rows(db, model):
    columns = tuple(model.__table__.columns)
    return tuple(
        tuple(getattr(row, column.name) for column in columns)
        for row in db.scalars(select(model).order_by(model.id)).all()
    )


def _campaign_snapshot(order):
    return (
        order.campaign_id,
        order.campaign_code,
        order.campaign_contract_version,
        order.campaign_purchase_limit,
        order.campaign_reservation_expires_at,
    )


def _reservation_confirmation_is_valid(reservations):
    if len(reservations) != 1:
        return False
    reservation = reservations[0]
    return (
        reservation.id == _RESERVATION_ID
        and reservation.campaign_id == _CAMPAIGN_ID
        and reservation.ordem_id == _ORDER_ID
        and reservation.estado == "confirmed"
        and type(reservation.confirmed_at) is datetime
        and reservation.released_at is None
        and reservation.expired_at is None
        and reservation.reserved_at == _RESERVED_AT
        and reservation.expires_at == _LIVE_EXPIRES_AT
    )


def _envelope():
    return {
        "notification_id": _N1,
        "payment_id": _P1,
        "request_id": "offline-e1-810001-910001",
    }


def test_approved_payment_confirms_campaign_reservation_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_confirmation as confirmation
    from app.services import mercado_pago_payment_resolution as resolution
    from app.services import mercado_pago_webhook_orchestration as orchestration

    violations = []

    with _environment(models) as Session:
        provider = _ReadOnlyFakePaymentClient()
        verifier = _AlwaysValidSignatureVerifier()
        orchestrator = orchestration.MercadoPagoWebhookOrchestrator(
            verificador_assinatura=verifier,
            resolvedor_pagamento=resolution.MercadoPagoPaymentResolver(provider),
            checkout_core=confirmation.CheckoutOfferOneTimeConfirmer(Session),
        )
        provider_before = provider.snapshot()

        first_result = orchestrator.processar(_envelope(), _SIGNATURE)
        assert first_result is not None
        assert (
            first_result.ordem_id,
            first_result.estado,
            first_result.payment_id,
        ) == (_ORDER_ID, "paid", _P1)
        assert provider.calls == [_P1]
        assert provider.snapshot() == provider_before

        with Session() as db:
            order = db.get(models.OrdemCheckout, _ORDER_ID)
            payments = _rows(db, models.Pagamento)
            events = _rows(db, models.EventoPagamento)
            grants = _rows(db, models.CheckoutOfferGrant)
            entitlement_count = db.scalar(
                select(func.count()).select_from(models.Entitlement)
            )
            reservations = tuple(
                db.scalars(
                    select(models.CheckoutOfferCampaignReservation)
                    .where(
                        models.CheckoutOfferCampaignReservation.ordem_id
                        == _ORDER_ID
                    )
                    .order_by(models.CheckoutOfferCampaignReservation.id)
                ).all()
            )

            assert (order.estado, order.payment_id) == ("paid", _P1)
            assert len(payments) == 1
            assert len(events) == 1
            assert len(grants) == 1
            assert entitlement_count == 0
            assert _campaign_snapshot(order) == _CAMPAIGN_SNAPSHOT

            first_payment = payments[0]
            first_event = events[0]
            first_grant = grants[0]
            first_confirmation_valid = _reservation_confirmation_is_valid(
                reservations
            )
            if not first_confirmation_valid:
                violations.append(
                    "CAMPAIGN_RESERVATION_NOT_CONFIRMED_BY_APPROVED_PAYMENT"
                )

            if first_confirmation_valid:
                confirmed_at = reservations[0].confirmed_at
                replay_result = orchestrator.processar(_envelope(), _SIGNATURE)
                assert replay_result is not None
                assert (
                    replay_result.ordem_id,
                    replay_result.estado,
                    replay_result.payment_id,
                ) == (_ORDER_ID, "paid", _P1)
                assert provider.calls == [_P1, _P1]
                assert provider.snapshot() == provider_before

                db.expire_all()
                replay_order = db.get(models.OrdemCheckout, _ORDER_ID)
                replay_payments = _rows(db, models.Pagamento)
                replay_events = _rows(db, models.EventoPagamento)
                replay_grants = _rows(db, models.CheckoutOfferGrant)
                replay_entitlement_count = db.scalar(
                    select(func.count()).select_from(models.Entitlement)
                )
                replay_reservations = tuple(
                    db.scalars(
                        select(models.CheckoutOfferCampaignReservation)
                        .where(
                            models.CheckoutOfferCampaignReservation.ordem_id
                            == _ORDER_ID
                        )
                        .order_by(models.CheckoutOfferCampaignReservation.id)
                    ).all()
                )

                assert (replay_order.estado, replay_order.payment_id) == (
                    "paid",
                    _P1,
                )
                assert len(replay_payments) == 1
                assert replay_payments[0] == first_payment
                assert len(replay_events) == 1
                assert replay_events[0] == first_event
                assert len(replay_grants) == 1
                assert replay_grants[0] == first_grant
                assert replay_entitlement_count == 0
                assert _campaign_snapshot(replay_order) == _CAMPAIGN_SNAPSHOT

                replay_confirmation_valid = (
                    _reservation_confirmation_is_valid(replay_reservations)
                    and replay_reservations[0].confirmed_at == confirmed_at
                )
                if not replay_confirmation_valid:
                    violations.append(
                        "CAMPAIGN_RESERVATION_REPLAY_MUTATED_CONFIRMATION"
                    )

    assert not violations, ",".join(violations)
