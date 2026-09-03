"""Contrato RED offline da vigencia de campanha na preference Mercado Pago."""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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


def _environment(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
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
        "partial": _order(
            models,
            order_id=1005,
            idempotency_key="campaign-expiry-partial-1005",
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
            models.Empresa(id=301, razao_social="Campaign Owner", user_id=41),
            _offer(models),
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
            *orders.values(),
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

    # O banco protege snapshots parciais. Este row deliberadamente corrompido
    # representa historico preexistente que o dispatcher deve rejeitar.
    with engine.begin() as connection:
        connection.execute(text("PRAGMA ignore_check_constraints = ON"))
        connection.execute(
            text(
                "UPDATE ordens_checkout SET campaign_id = :campaign_id "
                "WHERE id = :order_id"
            ),
            {"campaign_id": _CAMPAIGN_ID, "order_id": 1005},
        )
        connection.execute(text("PRAGMA ignore_check_constraints = OFF"))

    return engine, Session


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

    _engine, Session = _environment(models)
    with Session() as db:
        initial_campaign_count = db.scalar(
            select(func.count()).select_from(models.CheckoutOfferCampaign)
        )

    # A: historico unbound permanece unbound mesmo com campanha ativa elegivel.
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

    # A reserva historica continua valida depois de a campanha ser aposentada
    # e de os seus termos comerciais mutaveis divergirem do snapshot da ordem.
    with Session.begin() as db:
        campaign = db.get(models.CheckoutOfferCampaign, _CAMPAIGN_ID)
        campaign.estado = "retired"
        campaign.codigo = "document-campaign-retired"
        campaign.purchase_limit = 1
        campaign.reservation_ttl_seconds = 30
        campaign.contract_version = 99

    with Session() as db:
        bound_reservation = db.get(
            models.CheckoutOfferCampaignReservation, 2002
        )
        expected_expiry = {
            "expires": True,
            "expiration_date_from": _utc_iso(bound_reservation.reserved_at),
            "expiration_date_to": _utc_iso(bound_reservation.expires_at),
        }

    # B: bound/live entrega ao provider exatamente a vigencia persistida.
    client_b = _FakePreferenceClient("bound")
    result_b, error_b = _attempt(
        dispatch,
        _dispatcher(dispatch, mercado_pago, Session, client_b),
        1002,
    )

    # C: falha do provider nao altera o snapshot temporal usado no retry.
    client_c = _FakePreferenceClient("retry", fail_first=True)
    dispatcher_c = _dispatcher(dispatch, mercado_pago, Session, client_c)
    _first_c, first_error_c = _attempt(dispatch, dispatcher_c, 1003)
    with Session() as db:
        provider_after_first_c = db.get(
            models.OrdemCheckout, 1003
        ).provider_order_id
    result_c, second_error_c = _attempt(dispatch, dispatcher_c, 1003)

    # D: reserva expirada pelo relogio do banco falha antes do provider.
    client_d = _FakePreferenceClient("stale")
    result_d, error_d = _attempt(
        dispatch,
        _dispatcher(dispatch, mercado_pago, Session, client_d),
        1004,
    )

    # E: snapshot parcial e reserva contraditoria nao sao reparados.
    contradiction_results = {}
    for label, order_id in (
        ("partial", 1005),
        ("null_with_reservation", 1006),
    ):
        client = _FakePreferenceClient(label)
        result, error = _attempt(
            dispatch,
            _dispatcher(dispatch, mercado_pago, Session, client),
            order_id,
        )
        contradiction_results[label] = (result, error, client)

    with Session() as db:
        final_campaign_count = db.scalar(
            select(func.count()).select_from(models.CheckoutOfferCampaign)
        )
        final_orders = {
            order_id: db.get(models.OrdemCheckout, order_id)
            for order_id in (1004, 1005, 1006)
        }
        final_snapshots = {
            order_id: _snapshot(order)
            for order_id, order in final_orders.items()
        }
        final_reservation_counts = {
            order_id: db.scalar(
                select(func.count())
                .select_from(models.CheckoutOfferCampaignReservation)
                .where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == order_id
                )
            )
            for order_id in (1005, 1006)
        }

    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    require(error_a is None and result_a is not None, "A_UNBOUND_DISPATCH")
    require(len(client_a.calls) == 1, "A_PROVIDER_ONCE")
    require(
        len(client_a.calls) == 1
        and not any(key in client_a.calls[0]["payload"] for key in _EXPIRY_KEYS),
        "A_NO_EXPIRY_FIELDS",
    )
    require(unbound_snapshot == (None,) * 5, "A_REMAINS_UNBOUND")
    require(unbound_reservations == 0, "A_NO_RETROACTIVE_RESERVATION")

    require(error_b is None and result_b is not None, "B_BOUND_DISPATCH")
    require(len(client_b.calls) == 1, "B_PROVIDER_ONCE")
    require(
        len(client_b.calls) == 1
        and _expiry_slice(client_b.calls[0]) == expected_expiry,
        "B_PERSISTED_EXPIRY_PAYLOAD",
    )

    require(_opaque(first_error_c, dispatch), "C_FIRST_FAILURE_OPAQUE")
    require(provider_after_first_c is None, "C_FIRST_FAILURE_NOT_PERSISTED")
    require(second_error_c is None and result_c is not None, "C_RETRY_SUCCESS")
    require(len(client_c.calls) == 2, "C_PROVIDER_TWICE")
    require(
        len(client_c.calls) == 2
        and _expiry_slice(client_c.calls[0]) == expected_expiry
        and _expiry_slice(client_c.calls[1]) == expected_expiry,
        "C_PERSISTED_EXPIRY_REUSED",
    )
    require(
        len(client_c.calls) == 2
        and _expiry_slice(client_c.calls[0]) == _expiry_slice(client_c.calls[1]),
        "C_EXPIRY_STRUCTURALLY_IDENTICAL",
    )
    require(
        len(client_c.calls) == 2
        and {
            call["idempotency_key"] for call in client_c.calls
        } == {"campaign-expiry-retry-1003"},
        "C_SAME_IDEMPOTENCY_KEY",
    )

    require(result_d is None and _opaque(error_d, dispatch), "D_FAIL_CLOSED")
    require(client_d.calls == [], "D_ZERO_PROVIDER_CALLS")
    require(final_orders[1004].provider_order_id is None, "D_NO_PROVIDER_LINK")

    partial_result, partial_error, partial_client = contradiction_results["partial"]
    null_result, null_error, null_client = contradiction_results[
        "null_with_reservation"
    ]
    require(
        partial_result is None and _opaque(partial_error, dispatch),
        "E_PARTIAL_FAIL_CLOSED",
    )
    require(partial_client.calls == [], "E_PARTIAL_ZERO_PROVIDER_CALLS")
    require(
        null_result is None and _opaque(null_error, dispatch),
        "E_NULL_RESERVATION_FAIL_CLOSED",
    )
    require(null_client.calls == [], "E_NULL_RESERVATION_ZERO_PROVIDER_CALLS")
    require(
        final_snapshots[1005] == (_CAMPAIGN_ID, None, None, None, None),
        "E_PARTIAL_NOT_REPAIRED",
    )
    require(final_snapshots[1006] == (None,) * 5, "E_NULL_NOT_REPAIRED")
    require(
        final_reservation_counts == {1005: 0, 1006: 1},
        "E_RESERVATIONS_NOT_REPAIRED",
    )
    require(
        final_orders[1005].provider_order_id is None
        and final_orders[1006].provider_order_id is None,
        "E_NO_PROVIDER_LINK",
    )
    require(final_campaign_count == initial_campaign_count, "NO_NEW_CAMPAIGN")

    assert not violations, ",".join(violations)
