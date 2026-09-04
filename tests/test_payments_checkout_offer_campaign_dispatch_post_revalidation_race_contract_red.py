"""Contrato RED da corrida posterior a revalidacao da reservation."""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
import socket
import subprocess
import threading
import time
import uuid

import psycopg2
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker


_PUBLIC_ERROR = "Nao foi possivel despachar a ordem de checkout"
_CAMPAIGN_ID = 501
_CAMPAIGN_CODE = "document-campaign-2026"
_ORDER_ID = 1201
_RESERVATION_ID = 2201
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_RELEASED_AT = datetime(2026, 1, 2, 3, 4, 6, 234000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)
_PROVIDER_ORDER_ID = "mp-pref-post-revalidation-race"
_CHECKOUT_URL = (
    "https://www.mercadopago.com.br/checkout/v1/redirect/"
    "post-revalidation-race"
)
_THREAD_READY_TIMEOUT_SECONDS = 5.0
_CONCURRENT_COMMIT_WAIT_SECONDS = 5.0
_THREAD_JOIN_TIMEOUT_SECONDS = 5.0


class _FakeGateway:
    def __init__(self):
        self.calls = []
        self.compensations = []

    def criar_cobranca(self, **data):
        self.calls.append(dict(data))
        return {
            "provider_order_id": _PROVIDER_ORDER_ID,
            "checkout_url": _CHECKOUT_URL,
        }

    def cancelar_cobranca(self, **data):
        self.compensations.append(dict(data))


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run(*args):
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
    )


def _offer(models):
    return models.CheckoutOffer(
        id=101,
        codigo="document-one-time-company",
        nome_publico="Documentos one-time",
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


def _order(models):
    order = models.OrdemCheckout(
        id=_ORDER_ID,
        user_id=41,
        empresa_id=301,
        plano_id=None,
        offer_id=101,
        offer_code="document-one-time-company",
        contract_version=3,
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        subject_id=301,
        valor=Decimal("79.50"),
        moeda="BRL",
        estado="pending",
        idempotency_key="dispatch-post-revalidation-race-1201",
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
    container = f"mei-0049d1-post-revalidation-{uuid.uuid4().hex[:12]}"
    database = "mei_post_revalidation_race_contract"
    password = uuid.uuid4().hex
    port = _free_port()
    engine = None
    started_ok = False

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
            f"127.0.0.1:{port}:5432",
            "postgres:16-alpine",
        )
        assert started.returncode == 0, started.stderr
        started_ok = True

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            connection = None
            cursor = None
            try:
                connection = psycopg2.connect(
                    host="127.0.0.1",
                    port=port,
                    dbname=database,
                    user="postgres",
                    password=password,
                    connect_timeout=1,
                )
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                break
            except psycopg2.OperationalError:
                time.sleep(0.25)
            finally:
                if cursor is not None:
                    cursor.close()
                if connection is not None:
                    connection.close()
        else:
            raise AssertionError(
                "PostgreSQL 16 Alpine final TCP server did not become ready "
                f"at 127.0.0.1:{port}"
            )

        configured = _run(
            "docker",
            "exec",
            container,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-c",
            f"ALTER DATABASE {database} SET TIME ZONE 'UTC'",
        )
        assert configured.returncode == 0, configured.stderr

        engine = create_engine(
            f"postgresql+psycopg2://postgres:{password}"
            f"@127.0.0.1:{port}/{database}"
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
                models.CheckoutOfferCampaign.__table__,
                models.OrdemCheckout.__table__,
                models.OrdemCheckoutCapability.__table__,
                models.CheckoutOfferCampaignReservation.__table__,
            ],
        )
        Session = sessionmaker(bind=engine, expire_on_commit=True)

        with Session.begin() as db:
            db.add(
                models.User(
                    id=41,
                    email="post-revalidation-owner@example.invalid",
                    hashed_password="hash",
                )
            )
            db.flush()
            db.add_all(
                [
                    models.Empresa(
                        id=301,
                        razao_social="Post Revalidation Owner",
                        user_id=41,
                    ),
                    _offer(models),
                ]
            )
            db.flush()
            db.add(
                models.CheckoutOfferCampaign(
                    id=_CAMPAIGN_ID,
                    codigo=_CAMPAIGN_CODE,
                    offer_id=101,
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
            db.flush()

        yield engine, Session
    finally:
        if engine is not None:
            engine.dispose()
        if started_ok:
            _run("docker", "rm", "--force", container)


def _attempt(dispatch_module, dispatcher):
    try:
        result = dispatcher.despachar(
            authenticated_user_id=41,
            empresa_id=301,
            ordem_id=_ORDER_ID,
        )
    except dispatch_module.CheckoutOfferOneTimeDispatchError as error:
        return None, error
    return result, None


def _opaque(error, dispatch_module):
    return (
        type(error) is dispatch_module.CheckoutOfferOneTimeDispatchError
        and str(error) == _PUBLIC_ERROR
    )


def test_payments_checkout_offer_campaign_dispatch_post_revalidation_race_contract_red():
    from app import models
    from app.services import checkout_offer_campaign_reservation as authority
    from app.services import checkout_offer_one_time_dispatch as dispatch

    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    with _environment(models) as (_engine, Session):
        with Session() as db:
            initial_campaign_count = db.scalar(
                select(func.count()).select_from(models.CheckoutOfferCampaign)
            )
            initial_reservation_count = db.scalar(
                select(func.count()).select_from(
                    models.CheckoutOfferCampaignReservation
                )
            )

        gateway = _FakeGateway()
        dispatcher = dispatch.CheckoutOfferOneTimeDispatcher(
            session_factory=Session,
            gateway=gateway,
        )
        authority_class = authority.CheckoutOfferCampaignReservationAuthority
        original = authority_class.reservar_para_ordem
        same_order_calls = 0
        concurrent_commit_before_return = False
        concurrent_commit_attempted = threading.Event()
        concurrent_committed = threading.Event()
        concurrent_finished = threading.Event()
        thread_errors = []
        race_thread = None

        def release_concurrently():
            try:
                with Session.begin() as db:
                    reservation = db.get(
                        models.CheckoutOfferCampaignReservation,
                        _RESERVATION_ID,
                    )
                    if reservation is None or reservation.ordem_id != _ORDER_ID:
                        raise AssertionError("CONCURRENT_RESERVATION_NOT_FOUND")
                    reservation.estado = "released"
                    reservation.released_at = _RELEASED_AT
                    reservation.confirmed_at = None
                    reservation.expired_at = None
                    concurrent_commit_attempted.set()
                concurrent_committed.set()
            except BaseException as error:
                thread_errors.append(error)
            finally:
                concurrent_finished.set()

        def hooked_reservation(self, **data):
            nonlocal same_order_calls
            nonlocal concurrent_commit_before_return
            nonlocal race_thread

            projection = original(self, **data)
            if data.get("ordem_id") != _ORDER_ID:
                return projection

            same_order_calls += 1
            if same_order_calls == 2:
                race_thread = threading.Thread(
                    target=release_concurrently,
                    name="post-revalidation-reservation-release",
                    daemon=True,
                )
                race_thread.start()
                concurrent_commit_attempted.wait(_THREAD_READY_TIMEOUT_SECONDS)
                concurrent_commit_before_return = concurrent_committed.wait(
                    _CONCURRENT_COMMIT_WAIT_SECONDS
                )
            return projection

        result = None
        error = None
        authority_class.reservar_para_ordem = hooked_reservation
        try:
            result, error = _attempt(dispatch, dispatcher)
        finally:
            authority_class.reservar_para_ordem = original
            if race_thread is not None:
                race_thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)

        require(same_order_calls == 2, "TWO_AUTHORITY_CHECKS")
        require(race_thread is not None, "CONCURRENT_THREAD_STARTED")
        require(
            concurrent_commit_attempted.is_set(),
            "CONCURRENT_COMMIT_ATTEMPTED",
        )
        require(concurrent_finished.is_set(), "CONCURRENT_THREAD_TERMINATED")
        require(not thread_errors, "CONCURRENT_THREAD_NO_ERROR")

        with Session() as db:
            order = db.get(models.OrdemCheckout, _ORDER_ID)
            reservation = db.get(
                models.CheckoutOfferCampaignReservation,
                _RESERVATION_ID,
            )
            final_campaign_count = db.scalar(
                select(func.count()).select_from(models.CheckoutOfferCampaign)
            )
            final_reservation_count = db.scalar(
                select(func.count()).select_from(
                    models.CheckoutOfferCampaignReservation
                )
            )
            provider_link = order.provider_order_id, order.checkout_url
            reservation_state = (
                reservation.estado,
                reservation.released_at,
                reservation.confirmed_at,
                reservation.expired_at,
            )
            campaign_snapshot = (
                order.campaign_id,
                order.campaign_code,
                order.campaign_contract_version,
                order.campaign_purchase_limit,
                order.campaign_reservation_expires_at,
            )

        require(len(gateway.calls) == 1, "PROVIDER_ONCE")
        require(gateway.compensations == [], "NO_EXTERNAL_COMPENSATION")
        require(
            not (
                concurrent_commit_before_return
                and provider_link[0] is not None
            ),
            "POST_REVALIDATION_STALE_PROVIDER_LINK",
        )

        if concurrent_commit_before_return:
            require(
                result is None and _opaque(error, dispatch),
                "CONCURRENT_WIN_FAIL_CLOSED",
            )
            require(provider_link == (None, None), "CONCURRENT_WIN_NO_PROVIDER_LINK")
        else:
            require(error is None and result is not None, "SERIALIZED_DISPATCH_OK")
            require(
                result is not None
                and result.ordem_id == _ORDER_ID
                and result.provider_order_id == _PROVIDER_ORDER_ID
                and result.checkout_url == _CHECKOUT_URL,
                "SERIALIZED_PROJECTION_VALID",
            )
            require(
                provider_link == (_PROVIDER_ORDER_ID, _CHECKOUT_URL),
                "SERIALIZED_PROVIDER_LINK_PERSISTED",
            )

        require(
            reservation_state == ("released", _RELEASED_AT, None, None),
            "FINAL_RESERVATION_RELEASED",
        )
        require(
            campaign_snapshot
            == (_CAMPAIGN_ID, _CAMPAIGN_CODE, 11, 50, _LIVE_EXPIRES_AT),
            "NO_CAMPAIGN_SNAPSHOT_REPAIR",
        )
        require(
            final_campaign_count == initial_campaign_count,
            "NO_NEW_CAMPAIGN",
        )
        require(
            final_reservation_count == initial_reservation_count,
            "NO_NEW_RESERVATION",
        )

    assert not violations, ",".join(violations)
