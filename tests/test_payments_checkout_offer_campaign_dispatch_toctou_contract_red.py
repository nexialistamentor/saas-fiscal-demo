"""Contrato RED PostgreSQL do TOCTOU de reservation no dispatch one-time."""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
import socket
import subprocess
import time
import uuid

import psycopg2
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker


_PUBLIC_ERROR = "Nao foi possivel despachar a ordem de checkout"
_CAMPAIGN_ID = 501
_CAMPAIGN_CODE = "document-campaign-2026"
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_RELEASED_AT = datetime(2026, 1, 2, 3, 4, 6, 234000)
_CONFIRMED_AT = datetime(2026, 1, 3, 4, 5, 6, 345000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)


class _FakeGateway:
    def __init__(self, label, during_call=None):
        self.label = label
        self.during_call = during_call
        self.calls = []

    def criar_cobranca(self, **data):
        self.calls.append(dict(data))
        if self.during_call is not None:
            self.during_call()
        return {
            "provider_order_id": f"mp-pref-{self.label}-{len(self.calls)}",
            "checkout_url": (
                "https://www.mercadopago.com.br/checkout/v1/redirect/"
                f"{self.label}-{len(self.calls)}"
            ),
        }


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


def _order(models, *, order_id, label, bound, existing_provider=False):
    order = models.OrdemCheckout(
        id=order_id,
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
        idempotency_key=f"dispatch-toctou-{label}-{order_id}",
        provider_order_id=f"mp-existing-{label}" if existing_provider else None,
        checkout_url=(
            "https://www.mercadopago.com.br/checkout/v1/redirect/"
            f"existing-{label}"
            if existing_provider
            else None
        ),
        payment_id=None,
        billing_period=None,
        usage_unit="document",
        usage_limit=7,
        campaign_id=_CAMPAIGN_ID if bound else None,
        campaign_code=_CAMPAIGN_CODE if bound else None,
        campaign_contract_version=11 if bound else None,
        campaign_purchase_limit=50 if bound else None,
        campaign_reservation_expires_at=_LIVE_EXPIRES_AT if bound else None,
    )
    order.capabilities = [
        models.OrdemCheckoutCapability(codigo="document.extract"),
        models.OrdemCheckoutCapability(codigo="document.validate"),
    ]
    return order


def _reservation(models, *, reservation_id, order_id, estado="reserved"):
    return models.CheckoutOfferCampaignReservation(
        id=reservation_id,
        campaign_id=_CAMPAIGN_ID,
        ordem_id=order_id,
        estado=estado,
        reserved_at=_RESERVED_AT,
        expires_at=_LIVE_EXPIRES_AT,
        confirmed_at=_CONFIRMED_AT if estado == "confirmed" else None,
        released_at=_RELEASED_AT if estado == "released" else None,
        expired_at=None,
    )


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


@contextmanager
def _environment(models):
    container = f"mei-0049d1-dispatch-toctou-{uuid.uuid4().hex[:12]}"
    database = "mei_dispatch_toctou_contract"
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
                    email="dispatch-toctou-owner@example.invalid",
                    hashed_password="hash",
                )
            )
            db.flush()

            db.add_all(
                [
                    models.Empresa(
                        id=301,
                        razao_social="Dispatch TOCTOU Owner",
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

            db.add_all(
                [
                    _order(models, order_id=1101, label="a", bound=True),
                    _order(models, order_id=1102, label="b", bound=False),
                    _order(
                        models,
                        order_id=1103,
                        label="c",
                        bound=True,
                        existing_provider=True,
                    ),
                    _order(
                        models,
                        order_id=1104,
                        label="d",
                        bound=True,
                        existing_provider=True,
                    ),
                    _order(
                        models,
                        order_id=1105,
                        label="e",
                        bound=False,
                        existing_provider=True,
                    ),
                ]
            )
            db.flush()

            db.add_all(
                [
                    _reservation(models, reservation_id=2101, order_id=1101),
                    _reservation(
                        models,
                        reservation_id=2103,
                        order_id=1103,
                        estado="confirmed",
                    ),
                    _reservation(models, reservation_id=2105, order_id=1105),
                ]
            )
            db.flush()

        yield engine, Session
    finally:
        if engine is not None:
            engine.dispose()
        if started_ok:
            _run("docker", "rm", "--force", container)


def _dispatcher(dispatch_module, Session, gateway):
    return dispatch_module.CheckoutOfferOneTimeDispatcher(
        session_factory=Session,
        gateway=gateway,
    )


def _attempt(dispatch_module, dispatcher, order_id):
    try:
        result = dispatcher.despachar(
            authenticated_user_id=41,
            empresa_id=301,
            ordem_id=order_id,
        )
    except dispatch_module.CheckoutOfferOneTimeDispatchError as error:
        return None, error
    return result, None


def _opaque(error, dispatch_module):
    return (
        type(error) is dispatch_module.CheckoutOfferOneTimeDispatchError
        and str(error) == _PUBLIC_ERROR
    )


def _campaign_snapshot(order):
    return (
        order.campaign_id,
        order.campaign_code,
        order.campaign_contract_version,
        order.campaign_purchase_limit,
        order.campaign_reservation_expires_at,
    )


def _provider_link(order):
    return order.provider_order_id, order.checkout_url


def _row_state(row):
    return tuple(getattr(row, column.name) for column in row.__table__.columns)


def _reservation_count(db, models, order_id):
    return db.scalar(
        select(func.count())
        .select_from(models.CheckoutOfferCampaignReservation)
        .where(models.CheckoutOfferCampaignReservation.ordem_id == order_id)
    )


def test_payments_checkout_offer_campaign_dispatch_toctou_contract_red():
    from app import models
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
            c_order_before = _row_state(db.get(models.OrdemCheckout, 1103))
            c_reservation_before = _row_state(
                db.get(models.CheckoutOfferCampaignReservation, 2103)
            )

        def release_a():
            with Session.begin() as db:
                reservation = db.get(
                    models.CheckoutOfferCampaignReservation, 2101
                )
                reservation.estado = "released"
                reservation.released_at = _RELEASED_AT
                db.flush()

        gateway_a = _FakeGateway("a", during_call=release_a)
        result_a, error_a = _attempt(
            dispatch,
            _dispatcher(dispatch, Session, gateway_a),
            1101,
        )
        with Session() as db:
            order_a = db.get(models.OrdemCheckout, 1101)
            reservation_a = db.get(
                models.CheckoutOfferCampaignReservation, 2101
            )
            a_reservation_count = _reservation_count(db, models, 1101)

        require(result_a is None and _opaque(error_a, dispatch), "A_FAIL_CLOSED")
        require(len(gateway_a.calls) == 1, "A_PROVIDER_ONCE")
        require(_provider_link(order_a) == (None, None), "A_PROVIDER_NOT_PERSISTED")
        require(
            reservation_a.estado == "released"
            and reservation_a.released_at == _RELEASED_AT
            and reservation_a.confirmed_at is None
            and reservation_a.expired_at is None,
            "A_RELEASED_REMAINS_RELEASED",
        )
        require(
            _campaign_snapshot(order_a)
            == (_CAMPAIGN_ID, _CAMPAIGN_CODE, 11, 50, _LIVE_EXPIRES_AT),
            "A_BOUND_SNAPSHOT_NOT_REPAIRED",
        )
        require(a_reservation_count == 1, "A_NO_RESERVATION_REPAIR")

        def insert_b():
            with Session.begin() as db:
                db.add(
                    _reservation(models, reservation_id=2102, order_id=1102)
                )
                db.flush()

        gateway_b = _FakeGateway("b", during_call=insert_b)
        result_b, error_b = _attempt(
            dispatch,
            _dispatcher(dispatch, Session, gateway_b),
            1102,
        )
        with Session() as db:
            order_b = db.get(models.OrdemCheckout, 1102)
            reservation_b = db.get(
                models.CheckoutOfferCampaignReservation, 2102
            )
            b_reservation_count = _reservation_count(db, models, 1102)
            campaign_count_after_b = db.scalar(
                select(func.count()).select_from(models.CheckoutOfferCampaign)
            )

        require(result_b is None and _opaque(error_b, dispatch), "B_FAIL_CLOSED")
        require(len(gateway_b.calls) == 1, "B_PROVIDER_ONCE")
        require(_provider_link(order_b) == (None, None), "B_PROVIDER_NOT_PERSISTED")
        require(_campaign_snapshot(order_b) == (None,) * 5, "B_REMAINS_UNBOUND")
        require(
            reservation_b is not None
            and reservation_b.campaign_id == _CAMPAIGN_ID
            and reservation_b.ordem_id == 1102
            and reservation_b.estado == "reserved"
            and reservation_b.reserved_at == _RESERVED_AT
            and reservation_b.expires_at == _LIVE_EXPIRES_AT,
            "B_CONCURRENT_RESERVATION_REMAINS",
        )
        require(b_reservation_count == 1, "B_NO_RESERVATION_REPAIR")
        require(
            campaign_count_after_b == initial_campaign_count,
            "B_NO_RETROACTIVE_CAMPAIGN",
        )

        gateway_c = _FakeGateway("c")
        result_c, error_c = _attempt(
            dispatch,
            _dispatcher(dispatch, Session, gateway_c),
            1103,
        )
        with Session() as db:
            order_c = db.get(models.OrdemCheckout, 1103)
            reservation_c = db.get(
                models.CheckoutOfferCampaignReservation, 2103
            )
            c_order_after = _row_state(order_c)
            c_reservation_after = _row_state(reservation_c)

        require(error_c is None and result_c is not None, "C_EXISTING_RETURNED")
        require(
            result_c is not None
            and result_c.ordem_id == 1103
            and result_c.provider_order_id == "mp-existing-c"
            and result_c.checkout_url.endswith("/existing-c"),
            "C_EXISTING_PROJECTION",
        )
        require(gateway_c.calls == [], "C_ZERO_PROVIDER_CALLS")
        require(
            reservation_c.estado == "confirmed"
            and reservation_c.confirmed_at == _CONFIRMED_AT,
            "C_CONFIRMED_ACCEPTED",
        )
        require(
            c_order_after == c_order_before
            and c_reservation_after == c_reservation_before,
            "C_NO_MUTATION",
        )

        gateway_d = _FakeGateway("d")
        result_d, error_d = _attempt(
            dispatch,
            _dispatcher(dispatch, Session, gateway_d),
            1104,
        )
        with Session() as db:
            order_d = db.get(models.OrdemCheckout, 1104)
            d_reservation_count = _reservation_count(db, models, 1104)

        require(result_d is None and _opaque(error_d, dispatch), "D_FAIL_CLOSED")
        require(gateway_d.calls == [], "D_ZERO_PROVIDER_CALLS")
        require(
            _provider_link(order_d)
            == (
                "mp-existing-d",
                "https://www.mercadopago.com.br/checkout/v1/redirect/existing-d",
            ),
            "D_PROVIDER_EVIDENCE_PRESERVED",
        )
        require(
            _campaign_snapshot(order_d)
            == (_CAMPAIGN_ID, _CAMPAIGN_CODE, 11, 50, _LIVE_EXPIRES_AT),
            "D_BOUND_NOT_REPAIRED",
        )
        require(d_reservation_count == 0, "D_NO_RESERVATION_CREATED")

        gateway_e = _FakeGateway("e")
        result_e, error_e = _attempt(
            dispatch,
            _dispatcher(dispatch, Session, gateway_e),
            1105,
        )
        with Session() as db:
            order_e = db.get(models.OrdemCheckout, 1105)
            reservation_e = db.get(
                models.CheckoutOfferCampaignReservation, 2105
            )
            e_reservation_count = _reservation_count(db, models, 1105)
            final_campaign_count = db.scalar(
                select(func.count()).select_from(models.CheckoutOfferCampaign)
            )
            final_reservation_count = db.scalar(
                select(func.count()).select_from(
                    models.CheckoutOfferCampaignReservation
                )
            )

        require(result_e is None and _opaque(error_e, dispatch), "E_FAIL_CLOSED")
        require(gateway_e.calls == [], "E_ZERO_PROVIDER_CALLS")
        require(
            _provider_link(order_e)
            == (
                "mp-existing-e",
                "https://www.mercadopago.com.br/checkout/v1/redirect/existing-e",
            ),
            "E_PROVIDER_EVIDENCE_PRESERVED",
        )
        require(_campaign_snapshot(order_e) == (None,) * 5, "E_REMAINS_UNBOUND")
        require(
            reservation_e is not None
            and reservation_e.campaign_id == _CAMPAIGN_ID
            and reservation_e.ordem_id == 1105
            and reservation_e.estado == "reserved"
            and reservation_e.reserved_at == _RESERVED_AT
            and reservation_e.expires_at == _LIVE_EXPIRES_AT,
            "E_RESERVATION_PRESERVED",
        )
        require(e_reservation_count == 1, "E_NO_RESERVATION_REPAIR")
        require(final_campaign_count == initial_campaign_count, "NO_NEW_CAMPAIGN")
        require(
            final_reservation_count == initial_reservation_count + 1,
            "ONLY_CONCURRENT_RESERVATION_ADDED",
        )

    assert not violations, ",".join(violations)
