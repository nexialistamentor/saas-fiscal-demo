"""Contrato RED offline da vigencia de campanha na preference Mercado Pago."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import socket
import subprocess
import time
import uuid

import psycopg2
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker


_PUBLIC_ERROR = "Nao foi possivel despachar a ordem de checkout"
_EXPIRY_KEYS = (
    "expires",
    "expiration_date_from",
    "expiration_date_to",
)
_CAMPAIGN_ID = 501
_CAMPAIGN_CODE = "document-campaign-2026"
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)
_STALE_RESERVED_AT = datetime(2019, 1, 2, 3, 4, 5, 123000)
_STALE_EXPIRES_AT = datetime(2020, 1, 2, 3, 4, 5, 456000)


class _FakePreferenceClient:
    def __init__(self, label, *, fail_first=False):
        self.label = label
        self.fail_first = fail_first
        self.calls = []

    def criar_preferencia(self, *, payload, idempotency_key):
        self.calls.append({
            "payload": deepcopy(payload),
            "idempotency_key": idempotency_key,
        })
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("provider unavailable before preference creation")
        return {
            "id": f"mp-pref-{self.label}-{len(self.calls)}",
            "init_point": (
                "https://www.mercadopago.com.br/checkout/v1/redirect/"
                f"{self.label}-{len(self.calls)}"
            ),
        }


def _offer(models):
    offer = models.CheckoutOffer(
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
    offer.capabilities = [
        models.CheckoutOfferCapability(codigo="document.extract"),
        models.CheckoutOfferCapability(codigo="document.validate"),
    ]
    return offer


def _order(
    models,
    *,
    order_id,
    idempotency_key,
    expires_at=None,
    bound=False,
):
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
        idempotency_key=idempotency_key,
        provider_order_id=None,
        checkout_url=None,
        payment_id=None,
        billing_period=None,
        usage_unit="document",
        usage_limit=7,
        campaign_id=_CAMPAIGN_ID if bound else None,
        campaign_code=_CAMPAIGN_CODE if bound else None,
        campaign_contract_version=11 if bound else None,
        campaign_purchase_limit=50 if bound else None,
        campaign_reservation_expires_at=expires_at if bound else None,
    )
    order.capabilities = [
        models.OrdemCheckoutCapability(codigo="document.extract"),
        models.OrdemCheckoutCapability(codigo="document.validate"),
    ]
    return order


def _reservation(
    models,
    *,
    reservation_id,
    order_id,
    reserved_at,
    expires_at,
):
    return models.CheckoutOfferCampaignReservation(
        id=reservation_id,
        campaign_id=_CAMPAIGN_ID,
        ordem_id=order_id,
        estado="reserved",
        reserved_at=reserved_at,
        expires_at=expires_at,
        confirmed_at=None,
        released_at=None,
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
    container = f"mei-0049d1-expiry-{uuid.uuid4().hex[:12]}"
    database = "mei_campaign_expiry_contract"
    password = uuid.uuid4().hex
    port = _free_port()
    engine = None

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
                f"PostgreSQL 16 Alpine final TCP server did not become ready "
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
                models.CheckoutOfferCapability.__table__,
                models.CheckoutOfferCampaign.__table__,
                models.OrdemCheckout.__table__,
                models.OrdemCheckoutCapability.__table__,
                models.CheckoutOfferCampaignReservation.__table__,
            ],
        )
        Session = sessionmaker(bind=engine, expire_on_commit=True)

        orders = {
            "unbound": _order(
            models,
            order_id=1001,
            idempotency_key="campaign-expiry-unbound-1001",
        ),
        "bound": _order(
            models,
            order_id=1002,
            idempotency_key="campaign-expiry-bound-1002",
            expires_at=_LIVE_EXPIRES_AT,
            bound=True,
        ),
        "retry": _order(
            models,
            order_id=1003,
            idempotency_key="campaign-expiry-retry-1003",
            expires_at=_LIVE_EXPIRES_AT,
            bound=True,
        ),
        "stale": _order(
            models,
            order_id=1004,
            idempotency_key="campaign-expiry-stale-1004",
            expires_at=_STALE_EXPIRES_AT,
            bound=True,
        ),
            "null_with_reservation": _order(
            models,
            order_id=1006,
            idempotency_key="campaign-expiry-null-reservation-1006",
        ),
        }

        with Session.begin() as db:
            db.add_all([
                models.User(
                    id=41,
                    email="campaign-expiry-owner@example.invalid",
                    hashed_password="hash",
                ),
            ])
            db.flush()

            db.add_all([
                models.Empresa(
                    id=301,
                    razao_social="Campaign Owner",
                    user_id=41,
                ),
                _offer(models),
            ])
            db.flush()

            db.add_all([
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
                ),
            ])
            db.flush()

            db.add_all(list(orders.values()))
            db.flush()

            db.add_all([
                _reservation(
                    models,
                    reservation_id=2002,
                    order_id=1002,
                    reserved_at=_RESERVED_AT,
                    expires_at=_LIVE_EXPIRES_AT,
                ),
                _reservation(
                    models,
                    reservation_id=2003,
                    order_id=1003,
                    reserved_at=_RESERVED_AT,
                    expires_at=_LIVE_EXPIRES_AT,
                ),
                _reservation(
                    models,
                    reservation_id=2004,
                    order_id=1004,
                    reserved_at=_STALE_RESERVED_AT,
                    expires_at=_STALE_EXPIRES_AT,
                ),
                _reservation(
                    models,
                    reservation_id=2006,
                    order_id=1006,
                    reserved_at=_RESERVED_AT,
                    expires_at=_LIVE_EXPIRES_AT,
                ),
            ])
            db.flush()

        yield engine, Session
    finally:
        if engine is not None:
            engine.dispose()
        _run("docker", "rm", "--force", container)


def _gateway(gateway_module, client):
    return gateway_module.MercadoPagoCheckoutOfferOneTimeGateway(
        cliente_preferencias=client,
        notification_url="https://fisco.example.invalid/webhooks/mercado-pago",
        back_urls={
            "success": "https://fisco.example.invalid/checkout/success",
            "failure": "https://fisco.example.invalid/checkout/failure",
            "pending": "https://fisco.example.invalid/checkout/pending",
        },
    )


def _dispatcher(dispatch_module, gateway_module, Session, client):
    return dispatch_module.CheckoutOfferOneTimeDispatcher(
        session_factory=Session,
        gateway=_gateway(gateway_module, client),
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


def _snapshot(order):
    return (
        order.campaign_id,
        order.campaign_code,
        order.campaign_contract_version,
        order.campaign_purchase_limit,
        order.campaign_reservation_expires_at,
    )


def _utc_iso(value):
    if type(value) is not datetime or value.tzinfo is not None:
        raise AssertionError("persisted campaign timestamps must be naive UTC")
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="milliseconds")


def _expiry_slice(call):
    payload = call["payload"]
    return {key: payload[key] for key in _EXPIRY_KEYS if key in payload}


def test_payments_checkout_offer_campaign_preference_expiry_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_dispatch as dispatch
    from app.services import mercado_pago_checkout_offer_one_time as mercado_pago

    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    # E1: o CHECK do PostgreSQL torna o estado parcial impersistivel. A defesa
    # em profundidade e exercitada diretamente num objeto ORM transitorio.
    partial_order = _order(
        models,
        order_id=1005,
        idempotency_key="campaign-expiry-partial-1005",
    )
    partial_order.campaign_id = _CAMPAIGN_ID
    partial_client = _FakePreferenceClient("partial")
    partial_error = None
    try:
        dispatch.CheckoutOfferOneTimeDispatcher._snapshot(
            partial_order, 41, 301
        )
    except dispatch.CheckoutOfferOneTimeDispatchError as error:
        partial_error = error

    require(
        _opaque(partial_error, dispatch),
        "E1_PARTIAL_FAIL_CLOSED",
    )
    require(partial_client.calls == [], "E1_PARTIAL_ZERO_PROVIDER_CALLS")
    require(
        _snapshot(partial_order) == (_CAMPAIGN_ID, None, None, None, None),
        "E1_PARTIAL_NOT_REPAIRED",
    )

    with _environment(models) as (_engine, Session):
        with Session() as db:
            initial_campaign_count = db.scalar(
                select(func.count()).select_from(models.CheckoutOfferCampaign)
            )

        # A: historico unbound permanece unbound com campanha ativa elegivel.
        client_a = _FakePreferenceClient("unbound")
        result_a, error_a = _attempt(
            dispatch,
            _dispatcher(dispatch, mercado_pago, Session, client_a),
            1001,
        )
        with Session() as db:
            unbound_snapshot = _snapshot(db.get(models.OrdemCheckout, 1001))
            unbound_reservations = db.scalar(
                select(func.count())
                .select_from(models.CheckoutOfferCampaignReservation)
                .where(models.CheckoutOfferCampaignReservation.ordem_id == 1001)
            )

        require(error_a is None and result_a is not None, "A_UNBOUND_DISPATCH")
        require(len(client_a.calls) == 1, "A_PROVIDER_ONCE")
        require(
            len(client_a.calls) == 1
            and not any(
                key in client_a.calls[0]["payload"] for key in _EXPIRY_KEYS
            ),
            "A_NO_EXPIRY_FIELDS",
        )
        require(unbound_snapshot == (None,) * 5, "A_REMAINS_UNBOUND")
        require(unbound_reservations == 0, "A_NO_RETROACTIVE_RESERVATION")

        # A reserva historica continua valida depois de a campanha ser
        # aposentada e os seus termos mutaveis divergirem do snapshot.
        with Session.begin() as db:
            campaign = db.get(models.CheckoutOfferCampaign, _CAMPAIGN_ID)
            campaign.estado = "retired"
            campaign.codigo = "document-campaign-retired"
            campaign.purchase_limit = 1
            campaign.reservation_ttl_seconds = 30
            campaign.contract_version = 99

        with Session() as db:
            bound_order = db.get(models.OrdemCheckout, 1002)
            bound_reservation = db.get(
                models.CheckoutOfferCampaignReservation, 2002
            )
            expected_expiry = {
                "expires": True,
                "expiration_date_from": _utc_iso(bound_reservation.reserved_at),
                "expiration_date_to": _utc_iso(bound_reservation.expires_at),
            }
            bound_snapshot_before = _snapshot(bound_order)
            bound_reservation_state = bound_reservation.estado

        # B: bound/live entrega exatamente a vigencia persistida ao provider.
        client_b = _FakePreferenceClient("bound")
        result_b, error_b = _attempt(
            dispatch,
            _dispatcher(dispatch, mercado_pago, Session, client_b),
            1002,
        )
        with Session() as db:
            bound_snapshot_after = _snapshot(
                db.get(models.OrdemCheckout, 1002)
            )

        require(error_b is None and result_b is not None, "B_BOUND_DISPATCH")
        require(len(client_b.calls) == 1, "B_PROVIDER_ONCE")
        require(
            bound_snapshot_before
            == (
                _CAMPAIGN_ID,
                _CAMPAIGN_CODE,
                11,
                50,
                _LIVE_EXPIRES_AT,
            )
            and bound_snapshot_after == bound_snapshot_before
            and bound_reservation_state == "reserved",
            "B_BOUND_HISTORY_COHERENT",
        )
        require(
            len(client_b.calls) == 1
            and _expiry_slice(client_b.calls[0]) == expected_expiry,
            "B_PERSISTED_EXPIRY_PAYLOAD",
        )

        # C: falha do provider nao altera o instante usado no retry.
        client_c = _FakePreferenceClient("retry", fail_first=True)
        dispatcher_c = _dispatcher(dispatch, mercado_pago, Session, client_c)
        with Session() as db:
            retry_reservation_before = db.get(
                models.CheckoutOfferCampaignReservation, 2003
            )
            expected_retry_expiry = {
                "expires": True,
                "expiration_date_from": _utc_iso(
                    retry_reservation_before.reserved_at
                ),
                "expiration_date_to": _utc_iso(
                    retry_reservation_before.expires_at
                ),
            }
        _first_c, first_error_c = _attempt(dispatch, dispatcher_c, 1003)
        with Session() as db:
            retry_order = db.get(models.OrdemCheckout, 1003)
            retry_reservation = db.get(
                models.CheckoutOfferCampaignReservation, 2003
            )
            provider_after_first_c = retry_order.provider_order_id
            reserved_after_first_c = retry_reservation.reserved_at
        result_c, second_error_c = _attempt(dispatch, dispatcher_c, 1003)
        with Session() as db:
            reserved_after_second_c = db.get(
                models.CheckoutOfferCampaignReservation, 2003
            ).reserved_at

        require(_opaque(first_error_c, dispatch), "C_FIRST_FAILURE_OPAQUE")
        require(provider_after_first_c is None, "C_FIRST_FAILURE_NOT_PERSISTED")
        require(second_error_c is None and result_c is not None, "C_RETRY_SUCCESS")
        require(len(client_c.calls) == 2, "C_PROVIDER_TWICE")
        require(
            len(client_c.calls) == 2
            and _expiry_slice(client_c.calls[0]) == expected_retry_expiry
            and _expiry_slice(client_c.calls[1]) == expected_retry_expiry,
            "C_PERSISTED_EXPIRY_REUSED",
        )
        require(
            len(client_c.calls) == 2
            and _expiry_slice(client_c.calls[0])
            == _expiry_slice(client_c.calls[1]),
            "C_EXPIRY_STRUCTURALLY_IDENTICAL",
        )
        require(
            len(client_c.calls) == 2
            and {call["idempotency_key"] for call in client_c.calls}
            == {"campaign-expiry-retry-1003"},
            "C_SAME_IDEMPOTENCY_KEY",
        )
        require(
            reserved_after_first_c == _RESERVED_AT
            and reserved_after_second_c == _RESERVED_AT,
            "C_RESERVED_AT_NOT_RECALCULATED",
        )

        # D: reserva expirada falha antes da fronteira externa.
        client_d = _FakePreferenceClient("stale")
        result_d, error_d = _attempt(
            dispatch,
            _dispatcher(dispatch, mercado_pago, Session, client_d),
            1004,
        )

        # E2: all-five-null com reserva persistida nao pode ser reparado.
        client_e2 = _FakePreferenceClient("null_with_reservation")
        result_e2, error_e2 = _attempt(
            dispatch,
            _dispatcher(dispatch, mercado_pago, Session, client_e2),
            1006,
        )

        with Session() as db:
            final_campaign_count = db.scalar(
                select(func.count()).select_from(models.CheckoutOfferCampaign)
            )
            stale_order = db.get(models.OrdemCheckout, 1004)
            null_order = db.get(models.OrdemCheckout, 1006)
            null_reservation_count = db.scalar(
                select(func.count())
                .select_from(models.CheckoutOfferCampaignReservation)
                .where(models.CheckoutOfferCampaignReservation.ordem_id == 1006)
            )

        require(result_d is None and _opaque(error_d, dispatch), "D_FAIL_CLOSED")
        require(client_d.calls == [], "D_ZERO_PROVIDER_CALLS")
        require(stale_order.provider_order_id is None, "D_NO_PROVIDER_LINK")
        require(
            result_e2 is None and _opaque(error_e2, dispatch),
            "E2_NULL_RESERVATION_FAIL_CLOSED",
        )
        require(client_e2.calls == [], "E2_NULL_RESERVATION_ZERO_PROVIDER_CALLS")
        require(_snapshot(null_order) == (None,) * 5, "E2_NULL_NOT_REPAIRED")
        require(null_reservation_count == 1, "E2_RESERVATION_NOT_REPAIRED")
        require(null_order.provider_order_id is None, "E2_NO_PROVIDER_LINK")
        require(final_campaign_count == initial_campaign_count, "NO_NEW_CAMPAIGN")

    assert not violations, ",".join(violations)
