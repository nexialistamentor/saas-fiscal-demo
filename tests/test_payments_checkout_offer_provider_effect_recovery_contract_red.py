"""Contrato RED: incerteza e recuperacao do efeito externo de checkout."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid

import httpx
import psycopg2
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker


_PUBLIC_ERROR = "Nao foi possivel despachar a ordem de checkout"
_USER_ID = 41
_EMPRESA_ID = 301
_OFFER_ID = 101
_OFFER_CODE = "document-one-time-company"
_CAMPAIGN_ID = 501
_CAMPAIGN_CODE = "document-campaign-2026"
_AMOUNT = Decimal("79.50")
_CURRENCY = "BRL"
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)
_NOTIFICATION_URL = "https://payments.example.invalid/webhooks/mercado-pago"
_BACK_URLS = {
    "success": "https://app.example.invalid/checkout/success",
    "failure": "https://app.example.invalid/checkout/failure",
    "pending": "https://app.example.invalid/checkout/pending",
}
_ACCESS_TOKEN = "TEST-opaque-access-token-never-networked"
_STARTUP_DEADLINE_SECONDS = 60.0


class _InjectedPersistenceFailure(RuntimeError):
    pass


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = deepcopy(payload)

    def json(self):
        return deepcopy(self._payload)


class _ThreadSafeHttpProvider:
    """Provider fake: somente ``post`` pode criar efeito externo."""

    def __init__(self, *, first_post):
        if first_post not in {"success", "timeout_after", "timeout_before"}:
            raise ValueError("invalid fake provider mode")
        self._first_post = first_post
        self._lock = threading.Lock()
        self._post_attempt_count = 0
        self._actual_create_count = 0
        self._created_preferences = []
        self._reconciliation_read_count = 0
        self._retry_events = []
        self._observing_retry = False

    def post(self, *, url, headers, json, **_kwargs):
        with self._lock:
            self._post_attempt_count += 1
            attempt = self._post_attempt_count
            if self._observing_retry:
                self._retry_events.append(("POST", attempt))

            if attempt == 1 and self._first_post == "timeout_before":
                failure = "timeout_before"
                response_payload = None
            else:
                preference = self._create_preference(
                    payload=json,
                    idempotency_key=headers.get("X-Idempotency-Key"),
                )
                response_payload = {
                    "id": preference["id"],
                    "init_point": preference["init_point"],
                }
                failure = (
                    "timeout_after"
                    if attempt == 1 and self._first_post == "timeout_after"
                    else None
                )

        if failure is not None:
            raise httpx.ReadTimeout(
                "provider response not observed",
                request=httpx.Request("POST", url),
            )
        return _FakeResponse(201, response_payload)

    def get(self, url=None, *, params=None, **_kwargs):
        return self._read(url=url, params=params)

    def request(self, method, url=None, **kwargs):
        normalized = str(method).upper()
        if normalized == "GET":
            return self._read(url=url, params=kwargs.get("params"))
        if normalized == "POST":
            return self.post(
                url=url,
                headers=kwargs.get("headers", {}),
                json=kwargs.get("json"),
            )
        raise AssertionError("fake provider accepts only GET and POST")

    def begin_retry_observation(self):
        with self._lock:
            self._retry_events.clear()
            self._observing_retry = True

    @property
    def actual_create_count(self):
        with self._lock:
            return self._actual_create_count

    @property
    def created_preferences(self):
        with self._lock:
            return deepcopy(self._created_preferences)

    @property
    def reconciliation_read_count(self):
        with self._lock:
            return self._reconciliation_read_count

    def snapshot(self):
        with self._lock:
            return {
                "actual_create_count": self._actual_create_count,
                "created_preferences": deepcopy(self._created_preferences),
                "reconciliation_read_count": self._reconciliation_read_count,
                "retry_events": tuple(self._retry_events),
            }

    def _create_preference(self, *, payload, idempotency_key):
        self._actual_create_count += 1
        sequence = self._actual_create_count
        preference = {
            "id": f"mp-recovery-effect-{sequence}",
            "init_point": (
                "https://www.mercadopago.com.br/checkout/v1/redirect/"
                f"recovery-effect-{sequence}"
            ),
            "idempotency_key": idempotency_key,
            "payload": deepcopy(payload),
        }
        self._created_preferences.append(preference)
        return preference

    def _read(self, *, url, params):
        external_reference = _external_reference_from_request(url, params)
        with self._lock:
            self._reconciliation_read_count += 1
            if self._observing_retry:
                self._retry_events.append(("READ", external_reference))
            candidates = [
                _search_document(preference)
                for preference in self._created_preferences
                if preference["payload"].get("external_reference")
                == external_reference
            ]
        return _FakeResponse(
            200,
            {
                "elements": candidates,
                "next_offset": len(candidates),
                "total": len(candidates),
            },
        )


def _external_reference_from_request(url, params):
    if isinstance(params, dict):
        value = params.get("external_reference")
        if isinstance(value, (list, tuple)):
            return value[0] if value else None
        if value is not None:
            return str(value)
    if isinstance(url, str):
        values = parse_qs(urlsplit(url).query).get("external_reference", [])
        if values:
            return values[0]
    return None


def _search_document(preference):
    document = deepcopy(preference["payload"])
    document.update(
        id=preference["id"],
        init_point=preference["init_point"],
    )
    return document


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
    deadline = time.monotonic() + _STARTUP_DEADLINE_SECONDS
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


def _order(models, *, order_id, idempotency_key):
    order = models.OrdemCheckout(
        id=order_id,
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
        idempotency_key=idempotency_key,
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


def _reservation(models, *, order_id, reservation_id):
    return models.CheckoutOfferCampaignReservation(
        id=reservation_id,
        campaign_id=_CAMPAIGN_ID,
        ordem_id=order_id,
        estado="reserved",
        reserved_at=_RESERVED_AT,
        expires_at=_LIVE_EXPIRES_AT,
        confirmed_at=None,
        released_at=None,
        expired_at=None,
    )


@contextmanager
def _environment(models, *, order_id, reservation_id, idempotency_key):
    container = f"mei-0049d2-recovery-{uuid.uuid4().hex[:12]}"
    database = "mei_provider_effect_recovery_contract"
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
            assert connection.dialect.server_version_info[:1] == (16,)

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
                    email=f"provider-recovery-{order_id}@example.invalid",
                    hashed_password="hash",
                )
            )
            db.flush()
            db.add_all(
                [
                    models.Empresa(
                        id=_EMPRESA_ID,
                        razao_social="Provider Recovery Owner",
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
            db.add(
                _order(
                    models,
                    order_id=order_id,
                    idempotency_key=idempotency_key,
                )
            )
            db.flush()
            db.add(
                _reservation(
                    models,
                    order_id=order_id,
                    reservation_id=reservation_id,
                )
            )

        yield engine, Session
    finally:
        if engine is not None:
            engine.dispose()
        if container_started:
            _run("docker", "rm", "--force", container)


def _dispatcher(dispatch, mercado_pago, Session, provider):
    client = mercado_pago.MercadoPagoPreferenceClient(
        http_client=provider,
        access_token=_ACCESS_TOKEN,
        timeout_seconds=2.0,
    )
    from app.services.mercado_pago_checkout_offer_one_time import (
        MercadoPagoCheckoutOfferOneTimeGateway,
    )

    gateway = MercadoPagoCheckoutOfferOneTimeGateway(
        client,
        _NOTIFICATION_URL,
        dict(_BACK_URLS),
    )
    return dispatch.CheckoutOfferOneTimeDispatcher(
        session_factory=Session,
        gateway=gateway,
    )


def _attempt(dispatch, dispatcher, order_id):
    try:
        return (
            dispatcher.despachar(
                authenticated_user_id=_USER_ID,
                empresa_id=_EMPRESA_ID,
                ordem_id=order_id,
            ),
            None,
            None,
        )
    except dispatch.CheckoutOfferOneTimeDispatchError as error:
        return None, error, None
    except BaseException as error:
        return None, None, error


def _opaque(error, dispatch):
    return (
        type(error) is dispatch.CheckoutOfferOneTimeDispatchError
        and str(error) == _PUBLIC_ERROR
    )


def _database_snapshot(models, Session, order_id, reservation_id):
    with Session() as db:
        order = db.get(models.OrdemCheckout, order_id)
        reservation = db.get(
            models.CheckoutOfferCampaignReservation,
            reservation_id,
        )
        return {
            "provider_link": (order.provider_order_id, order.checkout_url),
            "payment_id": order.payment_id,
            "idempotency_key": order.idempotency_key,
            "campaign_snapshot": (
                order.campaign_id,
                order.campaign_code,
                order.campaign_contract_version,
                order.campaign_purchase_limit,
                order.campaign_reservation_expires_at,
            ),
            "reservation": (
                reservation.id,
                reservation.campaign_id,
                reservation.ordem_id,
                reservation.estado,
                reservation.reserved_at,
                reservation.expires_at,
                reservation.confirmed_at,
                reservation.released_at,
                reservation.expired_at,
            ),
            "payment_count": db.scalar(
                select(func.count()).select_from(models.Pagamento)
            ),
            "entitlement_count": db.scalar(
                select(func.count()).select_from(models.Entitlement)
            ),
        }


def _database_is_coherent(snapshot, *, order_id, reservation_id, idempotency_key):
    reservation = snapshot["reservation"]
    reservation_coherent = (
        reservation
        == (
            reservation_id,
            _CAMPAIGN_ID,
            order_id,
            "reserved",
            _RESERVED_AT,
            _LIVE_EXPIRES_AT,
            None,
            None,
            None,
        )
        and reservation[5] > reservation[4]
    )
    return (
        snapshot["payment_id"] is None
        and snapshot["idempotency_key"] == idempotency_key
        and snapshot["campaign_snapshot"]
        == (
            _CAMPAIGN_ID,
            _CAMPAIGN_CODE,
            11,
            50,
            _LIVE_EXPIRES_AT,
        )
        and reservation_coherent
        and snapshot["payment_count"] == 0
        and snapshot["entitlement_count"] == 0
    )


def _valid_https_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _utc_instant(value):
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    return parsed.astimezone(timezone.utc)


def _preference_identity_is_coherent(preference, *, order_id, idempotency_key):
    payload = preference.get("payload")
    if not isinstance(payload, dict):
        return False
    items = payload.get("items")
    try:
        amount_matches = (
            len(items) == 1
            and Decimal(str(items[0].get("unit_price"))) == _AMOUNT
        )
        expiry_matches = (
            _utc_instant(payload.get("expiration_date_from"))
            == _RESERVED_AT.replace(tzinfo=timezone.utc)
            and _utc_instant(payload.get("expiration_date_to"))
            == _LIVE_EXPIRES_AT.replace(tzinfo=timezone.utc)
        )
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return False
    return (
        preference.get("idempotency_key") == idempotency_key
        and payload.get("external_reference") == str(order_id)
        and len(items) == 1
        and items[0].get("id") == _OFFER_CODE
        and items[0].get("title") == _OFFER_CODE
        and items[0].get("quantity") == 1
        and amount_matches
        and items[0].get("currency_id") == _CURRENCY
        and payload.get("expires") is True
        and expiry_matches
        and payload.get("notification_url") == _NOTIFICATION_URL
        and _valid_https_url(payload.get("notification_url"))
        and payload.get("back_urls") == _BACK_URLS
        and all(_valid_https_url(url) for url in payload["back_urls"].values())
    )


def _all_created_preferences_are_coherent(snapshot, *, order_id, idempotency_key):
    preferences = snapshot["created_preferences"]
    return len(preferences) == snapshot["actual_create_count"] and all(
        _preference_identity_is_coherent(
            preference,
            order_id=order_id,
            idempotency_key=idempotency_key,
        )
        for preference in preferences
    )


def _first_effect(snapshot):
    preferences = snapshot["created_preferences"]
    if not preferences:
        return None
    first = preferences[0]
    return first["id"], first["init_point"]


def _projection_matches(result, provider_link):
    return (
        result is not None
        and getattr(result, "provider_order_id", None) == provider_link[0]
        and getattr(result, "checkout_url", None) == provider_link[1]
    )


def _retry_started_with_read(snapshot, *, order_id):
    events = snapshot["retry_events"]
    return (
        snapshot["reconciliation_read_count"] >= 1
        and bool(events)
        and events[0] == ("READ", str(order_id))
    )


def _retry_has_no_final_provider_claim(result):
    if result is None:
        return True
    if isinstance(result, dict):
        return (
            result.get("provider_order_id") is None
            and result.get("checkout_url") is None
        )
    return (
        getattr(result, "provider_order_id", None) is None
        and getattr(result, "checkout_url", None) is None
    )


def test_b1_known_external_success_internal_persistence_failure_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_dispatch as dispatch
    from app.services import mercado_pago_preference_client as mercado_pago

    order_id = 1401
    reservation_id = 2401
    idempotency_key = "provider-recovery-known-success-1401"
    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    with _environment(
        models,
        order_id=order_id,
        reservation_id=reservation_id,
        idempotency_key=idempotency_key,
    ) as (_engine, Session):
        provider = _ThreadSafeHttpProvider(first_post="success")
        dispatcher = _dispatcher(
            dispatch, mercado_pago, Session, provider
        )

        def fail_provider_link_persistence(_mapper, _connection, candidate):
            if (
                candidate.id == order_id
                and candidate.provider_order_id is not None
                and candidate.checkout_url is not None
            ):
                raise _InjectedPersistenceFailure()

        event.listen(
            models.OrdemCheckout,
            "before_update",
            fail_provider_link_persistence,
        )
        try:
            first_result, first_error, first_unexpected = _attempt(
                dispatch, dispatcher, order_id
            )
        finally:
            event.remove(
                models.OrdemCheckout,
                "before_update",
                fail_provider_link_persistence,
            )

        after_first_provider = provider.snapshot()
        first_effect = _first_effect(after_first_provider)
        after_first_database = _database_snapshot(
            models, Session, order_id, reservation_id
        )

        require(first_result is None, "B1_FIRST_DISPATCH_NOT_SUCCESS")
        require(first_unexpected is None, "B1_FIRST_UNEXPECTED_ERROR")
        require(_opaque(first_error, dispatch), "B1_FIRST_ERROR_NOT_SANITIZED")
        require(
            after_first_provider["actual_create_count"] == 1,
            "B1_FIRST_EXTERNAL_EFFECT_NOT_EXACTLY_ONE",
        )
        require(first_effect is not None, "B1_ORIGINAL_EXTERNAL_EFFECT_MISSING")
        require(
            _all_created_preferences_are_coherent(
                after_first_provider,
                order_id=order_id,
                idempotency_key=idempotency_key,
            ),
            "B1_CREATED_PREFERENCE_IDENTITY",
        )
        require(
            after_first_database["provider_link"] == (None, None),
            "B1_INTERNAL_ROLLBACK_DID_NOT_REMOVE_PROVIDER_LINK",
        )
        require(
            _database_is_coherent(
                after_first_database,
                order_id=order_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
            ),
            "B1_DATABASE_NOT_COHERENT_AFTER_ROLLBACK",
        )

        provider.begin_retry_observation()
        dispatcher = _dispatcher(
            dispatch, mercado_pago, Session, provider
        )
        retry_result, retry_error, retry_unexpected = _attempt(
            dispatch, dispatcher, order_id
        )
        final_provider = provider.snapshot()
        final_database = _database_snapshot(
            models, Session, order_id, reservation_id
        )

        require(retry_unexpected is None, "B1_RETRY_UNEXPECTED_ERROR")
        require(
            retry_error is None or _opaque(retry_error, dispatch),
            "B1_RETRY_ERROR_NOT_SANITIZED",
        )
        require(
            final_provider["actual_create_count"] == 1,
            "DUPLICATE_EXTERNAL_EFFECT_AFTER_PERSISTENCE_FAILURE",
        )
        recovered = (
            first_effect is not None
            and retry_error is None
            and _projection_matches(retry_result, first_effect)
            and final_database["provider_link"] == first_effect
        )
        require(recovered, "ORIGINAL_EXTERNAL_EFFECT_NOT_RECOVERED")
        require(
            _all_created_preferences_are_coherent(
                final_provider,
                order_id=order_id,
                idempotency_key=idempotency_key,
            ),
            "B1_FINAL_PREFERENCE_IDENTITY",
        )
        require(
            _database_is_coherent(
                final_database,
                order_id=order_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
            ),
            "B1_FINAL_DATABASE_NOT_COHERENT",
        )

    assert not violations, ",".join(violations)


def test_b2_ambiguous_timeout_after_external_effect_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_dispatch as dispatch
    from app.services import mercado_pago_preference_client as mercado_pago

    order_id = 1402
    reservation_id = 2402
    idempotency_key = "provider-recovery-timeout-after-1402"
    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    with _environment(
        models,
        order_id=order_id,
        reservation_id=reservation_id,
        idempotency_key=idempotency_key,
    ) as (_engine, Session):
        provider = _ThreadSafeHttpProvider(first_post="timeout_after")
        dispatcher = _dispatcher(
            dispatch, mercado_pago, Session, provider
        )

        first_result, first_error, first_unexpected = _attempt(
            dispatch, dispatcher, order_id
        )
        after_first_provider = provider.snapshot()
        first_effect = _first_effect(after_first_provider)
        after_first_database = _database_snapshot(
            models, Session, order_id, reservation_id
        )

        require(first_result is None, "B2_FIRST_DISPATCH_NOT_SUCCESS")
        require(first_unexpected is None, "B2_FIRST_UNEXPECTED_ERROR")
        require(_opaque(first_error, dispatch), "B2_FIRST_ERROR_NOT_SANITIZED")
        require(
            after_first_provider["actual_create_count"] == 1,
            "B2_FIRST_EXTERNAL_EFFECT_NOT_EXACTLY_ONE",
        )
        require(first_effect is not None, "B2_ORIGINAL_EXTERNAL_EFFECT_MISSING")
        require(
            _all_created_preferences_are_coherent(
                after_first_provider,
                order_id=order_id,
                idempotency_key=idempotency_key,
            ),
            "B2_CREATED_PREFERENCE_IDENTITY",
        )
        require(
            after_first_database["provider_link"] == (None, None),
            "B2_INVENTED_PROVIDER_LINK_AFTER_TIMEOUT",
        )
        require(
            _database_is_coherent(
                after_first_database,
                order_id=order_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
            ),
            "B2_DATABASE_NOT_COHERENT_AFTER_TIMEOUT",
        )

        provider.begin_retry_observation()
        dispatcher = _dispatcher(
            dispatch, mercado_pago, Session, provider
        )
        retry_result, retry_error, retry_unexpected = _attempt(
            dispatch, dispatcher, order_id
        )
        final_provider = provider.snapshot()
        final_database = _database_snapshot(
            models, Session, order_id, reservation_id
        )

        require(retry_unexpected is None, "B2_RETRY_UNEXPECTED_ERROR")
        require(
            retry_error is None or _opaque(retry_error, dispatch),
            "B2_RETRY_ERROR_NOT_SANITIZED",
        )
        require(
            _retry_started_with_read(final_provider, order_id=order_id),
            "NO_RECONCILIATION_BEFORE_RETRY_CREATE",
        )
        require(
            final_provider["actual_create_count"] == 1,
            "DUPLICATE_EXTERNAL_EFFECT_AFTER_AMBIGUOUS_TIMEOUT",
        )
        recovered = (
            first_effect is not None
            and retry_error is None
            and _projection_matches(retry_result, first_effect)
            and final_database["provider_link"] == first_effect
        )
        require(recovered, "AMBIGUOUS_ORIGINAL_EFFECT_NOT_RECOVERED")
        require(
            _all_created_preferences_are_coherent(
                final_provider,
                order_id=order_id,
                idempotency_key=idempotency_key,
            ),
            "B2_FINAL_PREFERENCE_IDENTITY",
        )
        require(
            _database_is_coherent(
                final_database,
                order_id=order_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
            ),
            "B2_FINAL_DATABASE_NOT_COHERENT",
        )

    assert not violations, ",".join(violations)


def test_b3_ambiguous_timeout_before_external_effect_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_dispatch as dispatch
    from app.services import mercado_pago_preference_client as mercado_pago

    order_id = 1403
    reservation_id = 2403
    idempotency_key = "provider-recovery-timeout-before-1403"
    violations = []

    def require(condition, marker):
        if not condition:
            violations.append(marker)

    with _environment(
        models,
        order_id=order_id,
        reservation_id=reservation_id,
        idempotency_key=idempotency_key,
    ) as (_engine, Session):
        provider = _ThreadSafeHttpProvider(first_post="timeout_before")
        dispatcher = _dispatcher(
            dispatch, mercado_pago, Session, provider
        )

        first_result, first_error, first_unexpected = _attempt(
            dispatch, dispatcher, order_id
        )
        after_first_provider = provider.snapshot()
        after_first_database = _database_snapshot(
            models, Session, order_id, reservation_id
        )

        require(first_result is None, "B3_FIRST_DISPATCH_NOT_SUCCESS")
        require(first_unexpected is None, "B3_FIRST_UNEXPECTED_ERROR")
        require(_opaque(first_error, dispatch), "B3_FIRST_ERROR_NOT_SANITIZED")
        require(
            after_first_provider["actual_create_count"] == 0,
            "B3_TIMEOUT_BEFORE_EFFECT_CREATED_PREFERENCE",
        )
        require(
            after_first_provider["created_preferences"] == [],
            "B3_PROVIDER_STORAGE_NOT_EMPTY_AFTER_FIRST_TIMEOUT",
        )
        require(
            after_first_database["provider_link"] == (None, None),
            "B3_INVENTED_PROVIDER_LINK_AFTER_TIMEOUT",
        )
        require(
            _database_is_coherent(
                after_first_database,
                order_id=order_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
            ),
            "B3_DATABASE_NOT_COHERENT_AFTER_TIMEOUT",
        )

        provider.begin_retry_observation()
        dispatcher = _dispatcher(
            dispatch, mercado_pago, Session, provider
        )
        retry_result, retry_error, retry_unexpected = _attempt(
            dispatch, dispatcher, order_id
        )
        final_provider = provider.snapshot()
        final_database = _database_snapshot(
            models, Session, order_id, reservation_id
        )

        require(retry_unexpected is None, "B3_RETRY_UNEXPECTED_ERROR")
        require(
            retry_error is None or _opaque(retry_error, dispatch),
            "B3_RETRY_ERROR_NOT_SANITIZED",
        )
        require(
            _retry_started_with_read(final_provider, order_id=order_id),
            "NO_RECONCILIATION_AFTER_AMBIGUOUS_NO_EFFECT_TIMEOUT",
        )
        no_immediate_recreate = (
            final_provider["actual_create_count"] == 0
            and final_provider["created_preferences"] == []
            and final_database["provider_link"] == (None, None)
            and _retry_has_no_final_provider_claim(retry_result)
        )
        require(
            no_immediate_recreate,
            "IMMEDIATE_RECREATE_AFTER_UNPROVEN_NEGATIVE_RECONCILIATION",
        )
        require(
            _all_created_preferences_are_coherent(
                final_provider,
                order_id=order_id,
                idempotency_key=idempotency_key,
            ),
            "B3_FINAL_PREFERENCE_IDENTITY",
        )
        require(
            _database_is_coherent(
                final_database,
                order_id=order_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
            ),
            "B3_FINAL_DATABASE_NOT_COHERENT",
        )

    assert not violations, ",".join(violations)
