"""Contrato RED: uma ordem concorrente produz no maximo um efeito externo."""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
import subprocess
import threading
import time
import uuid

import psycopg2
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker


_PUBLIC_ERROR = "Nao foi possivel despachar a ordem de checkout"
_USER_ID = 41
_EMPRESA_ID = 301
_OFFER_ID = 101
_OFFER_CODE = "document-one-time-company"
_CAMPAIGN_ID = 501
_CAMPAIGN_CODE = "document-campaign-2026"
_ORDER_ID = 1301
_RESERVATION_ID = 2301
_IDEMPOTENCY_KEY = "same-order-single-provider-effect-1301"
_AMOUNT = Decimal("79.50")
_CURRENCY = "BRL"
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)
_START_TIMEOUT_SECONDS = 5.0
_SECOND_PROVIDER_WAIT_SECONDS = 2.0
_THREAD_JOIN_TIMEOUT_SECONDS = 10.0


class _ConcurrentFakeGateway:
    def __init__(self):
        self._lock = threading.Lock()
        self._calls = []
        self._call_count = 0
        self.first_provider_entered = threading.Event()
        self.second_provider_entered = threading.Event()

    def criar_cobranca(self, **data):
        with self._lock:
            self._call_count += 1
            call_number = self._call_count
            self._calls.append(dict(data))
            if call_number == 1:
                self.first_provider_entered.set()
            elif call_number == 2:
                self.second_provider_entered.set()

        if call_number == 1:
            self.second_provider_entered.wait(_SECOND_PROVIDER_WAIT_SECONDS)

        return {
            "provider_order_id": f"mp-same-order-effect-{call_number}",
            "checkout_url": (
                "https://www.mercadopago.com.br/checkout/v1/redirect/"
                f"same-order-effect-{call_number}"
            ),
        }

    def snapshot(self):
        with self._lock:
            return self._call_count, tuple(
                dict(call) for call in self._calls
            )


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
        idempotency_key=_IDEMPOTENCY_KEY,
        provider_order_id=None,
        checkout_url=None,
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
    container = f"mei-0049d2-same-order-{uuid.uuid4().hex[:12]}"
    database = "mei_same_order_provider_effect_contract"
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
                models.Entitlement.__table__,
            ],
        )
        Session = sessionmaker(bind=engine, expire_on_commit=True)

        with Session.begin() as db:
            db.add(
                models.User(
                    id=_USER_ID,
                    email="same-order-owner@example.invalid",
                    hashed_password="hash",
                )
            )
            db.flush()
            db.add_all(
                [
                    models.Empresa(
                        id=_EMPRESA_ID,
                        razao_social="Same Order Owner",
                        user_id=_USER_ID,
                    ),
                    _offer(models),
                ]
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

        yield engine, Session
    finally:
        if engine is not None:
            engine.dispose()
        if container_started:
            _run("docker", "rm", "--force", container)


def _opaque(error, dispatch_module):
    return (
        type(error) is dispatch_module.CheckoutOfferOneTimeDispatchError
        and str(error) == _PUBLIC_ERROR
    )


def _reservation_is_structurally_coherent(reservation):
    state_timestamps = (
        reservation.estado,
        reservation.confirmed_at,
        reservation.released_at,
        reservation.expired_at,
    )
    return (
        reservation.id == _RESERVATION_ID
        and reservation.campaign_id == _CAMPAIGN_ID
        and reservation.ordem_id == _ORDER_ID
        and reservation.reserved_at == _RESERVED_AT
        and reservation.expires_at == _LIVE_EXPIRES_AT
        and reservation.expires_at > reservation.reserved_at
        and (
            state_timestamps == ("reserved", None, None, None)
            or (
                reservation.estado == "confirmed"
                and type(reservation.confirmed_at) is datetime
                and reservation.released_at is None
                and reservation.expired_at is None
            )
            or (
                reservation.estado == "released"
                and reservation.confirmed_at is None
                and type(reservation.released_at) is datetime
                and reservation.expired_at is None
            )
            or (
                reservation.estado == "expired"
                and reservation.confirmed_at is None
                and reservation.released_at is None
                and type(reservation.expired_at) is datetime
            )
        )
    )


def test_payments_checkout_offer_same_order_single_provider_effect_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_dispatch as dispatch

    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    with _environment(models) as (_engine, Session):
        with Session() as db:
            persisted_order = db.get(models.OrdemCheckout, _ORDER_ID)
            persisted_reservation = db.get(
                models.CheckoutOfferCampaignReservation,
                _RESERVATION_ID,
            )
            expected_gateway_call = {
                "ordem_id": persisted_order.id,
                "user_id": persisted_order.user_id,
                "empresa_id": persisted_order.empresa_id,
                "offer_code": persisted_order.offer_code,
                "valor": persisted_order.valor,
                "moeda": persisted_order.moeda,
                "idempotency_key": persisted_order.idempotency_key,
                "expiration_date_from": persisted_reservation.reserved_at,
                "expiration_date_to": persisted_reservation.expires_at,
            }

        gateway = _ConcurrentFakeGateway()
        dispatcher = dispatch.CheckoutOfferOneTimeDispatcher(
            session_factory=Session,
            gateway=gateway,
        )
        start = threading.Barrier(3, timeout=_START_TIMEOUT_SECONDS)
        results = [None, None]
        public_errors = [None, None]
        thread_errors = [None, None]

        def dispatch_concurrently(index):
            try:
                start.wait()
                results[index] = dispatcher.despachar(
                    authenticated_user_id=_USER_ID,
                    empresa_id=_EMPRESA_ID,
                    ordem_id=_ORDER_ID,
                )
            except dispatch.CheckoutOfferOneTimeDispatchError as error:
                public_errors[index] = error
            except BaseException as error:
                thread_errors[index] = error

        threads = [
            threading.Thread(
                target=dispatch_concurrently,
                args=(index,),
                name=f"same-order-dispatch-{index + 1}",
                daemon=True,
            )
            for index in range(2)
        ]
        for thread in threads:
            thread.start()

        barrier_error = None
        try:
            start.wait()
        except threading.BrokenBarrierError as error:
            barrier_error = error

        first_provider_observed = gateway.first_provider_entered.wait(
            _START_TIMEOUT_SECONDS
        )
        for thread in threads:
            thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)

        provider_call_count, gateway_calls = gateway.snapshot()

        require(barrier_error is None, "CONCURRENT_START_BARRIER")
        require(first_provider_observed, "FIRST_PROVIDER_ENTERED")
        require(not any(thread.is_alive() for thread in threads), "THREADS_TERMINATED")
        require(not any(thread_errors), "THREADS_NO_UNEXPECTED_ERROR")
        require(
            all(
                result is not None
                or public_error is not None
                or thread_error is not None
                for result, public_error, thread_error in zip(
                    results, public_errors, thread_errors
                )
            ),
            "BOTH_THREADS_REPORTED_OUTCOME",
        )
        require(
            all(
                error is None or _opaque(error, dispatch)
                for error in public_errors
            ),
            "THREAD_FAILURE_PUBLIC_ERROR_SANITIZED",
        )
        require(
            provider_call_count <= 1,
            "SAME_ORDER_DUPLICATE_PROVIDER_EFFECT",
        )
        require(provider_call_count == 1, "PROVIDER_CALL_COUNT_NOT_ONE")
        require(
            provider_call_count == len(gateway_calls),
            "PROVIDER_COUNTER_AND_CALL_LOG_COHERENT",
        )
        require(
            provider_call_count >= 1
            and all(call == expected_gateway_call for call in gateway_calls),
            "PROVIDER_CALL_ARGS_MATCH_PERSISTED_ORDER_AND_RESERVATION",
        )

        with Session() as db:
            final_order = db.get(models.OrdemCheckout, _ORDER_ID)
            final_reservation = db.get(
                models.CheckoutOfferCampaignReservation,
                _RESERVATION_ID,
            )
            payment_count = db.scalar(
                select(func.count()).select_from(models.Pagamento)
            )
            entitlement_count = db.scalar(
                select(func.count()).select_from(models.Entitlement)
            )
            reservation_count = db.scalar(
                select(func.count())
                .select_from(models.CheckoutOfferCampaignReservation)
                .where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == _ORDER_ID
                )
            )
            provider_link = (
                final_order.provider_order_id,
                final_order.checkout_url,
            )
            campaign_snapshot = (
                final_order.campaign_id,
                final_order.campaign_code,
                final_order.campaign_contract_version,
                final_order.campaign_purchase_limit,
                final_order.campaign_reservation_expires_at,
            )

        possible_provider_links = {
            (None, None),
            *{
                (
                    f"mp-same-order-effect-{index}",
                    "https://www.mercadopago.com.br/checkout/v1/redirect/"
                    f"same-order-effect-{index}",
                )
                for index in range(1, provider_call_count + 1)
            },
        }
        require(provider_link in possible_provider_links, "AT_MOST_ONE_INTERNAL_LINK")
        require(payment_count == 0, "NO_PAYMENT_CREATED")
        require(entitlement_count == 0, "NO_ENTITLEMENT_CREATED")
        require(reservation_count == 1, "SINGLE_RESERVATION_PRESERVED")
        require(
            _reservation_is_structurally_coherent(final_reservation),
            "RESERVATION_STRUCTURALLY_COHERENT",
        )
        require(
            campaign_snapshot
            == (
                _CAMPAIGN_ID,
                _CAMPAIGN_CODE,
                11,
                50,
                _LIVE_EXPIRES_AT,
            ),
            "FIVE_FIELD_CAMPAIGN_SNAPSHOT_COHERENT",
        )

    assert not violations, ",".join(violations)
