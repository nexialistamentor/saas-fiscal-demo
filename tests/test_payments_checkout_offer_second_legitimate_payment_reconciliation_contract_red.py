"""Contrato RED PostgreSQL para reconciliacao de segundo pagamento legitimo."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from collections.abc import Mapping
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
_IDEMPOTENCY_KEY = "second-legitimate-payment-reconciliation-1301"
_AMOUNT = Decimal("79.50")
_CURRENCY = "BRL"
_P1 = "910001"
_P2 = "910002"
_P3 = "910003"
_N1 = "810001"
_N2 = "810002"
_SIGNATURE = "offline-authenticated-signature-r3"
_RESERVED_AT = datetime(2025, 1, 2, 3, 4, 5, 123000)
_LIVE_EXPIRES_AT = datetime(2099, 12, 31, 23, 59, 58, 456000)

_CHECKOUT_EXISTING_AUTHORITIES = frozenset(
    {
        "ordens_checkout",
        "ordem_checkout_capabilities",
        "checkout_offer_campaign_reservations",
        "pagamentos",
        "checkout_offer_grants",
        "checkout_offer_grant_capabilities",
        "eventos_pagamento",
        "entitlements",
    }
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
        self._payments = {
            payment_id: {
                "id": payment_id,
                "external_reference": str(_ORDER_ID),
                "status": "approved",
                "transaction_amount": _AMOUNT,
                "currency_id": _CURRENCY,
            }
            for payment_id in (_P1, _P2, _P3)
        }

    def obter_pagamento(self, *, payment_id):
        self.calls.append(payment_id)
        return deepcopy(self._payments[payment_id])

    def snapshot(self):
        return deepcopy(self._payments)


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
        provider_order_id="mp-provider-order-1301",
        checkout_url=(
            "https://www.mercadopago.com.br/checkout/v1/redirect/"
            "second-legitimate-payment-1301"
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


def _order_fk_column_indexes(table, order_id_column):
    return tuple(
        index
        for index, column in enumerate(table.columns)
        if any(
            foreign_key.column is order_id_column
            for foreign_key in column.foreign_keys
        )
    )


def _provider_authority_tables(models):
    order_id = models.Base.metadata.tables["ordens_checkout"].c.id
    return tuple(
        sorted(
            (
                table
                for table in models.Base.metadata.tables.values()
                if table.name not in _CHECKOUT_EXISTING_AUTHORITIES
                and _order_fk_column_indexes(table, order_id)
            ),
            key=lambda table: table.fullname,
        )
    )


@contextmanager
def _environment(models, provider_authority_tables):
    container = f"mei-0049d2-second-payment-{uuid.uuid4().hex[:12]}"
    database = "mei_second_legitimate_payment_contract"
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
                *provider_authority_tables,
            ],
        )
        Session = sessionmaker(bind=engine, expire_on_commit=True)

        with Session.begin() as db:
            db.add(
                models.User(
                    id=_USER_ID,
                    email="second-payment-owner@example.invalid",
                    hashed_password="hash-de-teste",
                )
            )
            db.flush()
            db.add_all(
                (
                    models.Empresa(
                        id=_EMPRESA_ID,
                        razao_social="Second Payment Owner",
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

        yield engine, Session
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


def _canonical_value(value):
    if isinstance(value, Mapping):
        return (
            "mapping",
            tuple(
                sorted(
                    (str(key), _canonical_value(item))
                    for key, item in value.items()
                )
            ),
        )
    if isinstance(value, (list, tuple)):
        return ("sequence", tuple(_canonical_value(item) for item in value))
    if isinstance(value, (set, frozenset)):
        return (
            "set",
            tuple(sorted((_canonical_value(item) for item in value), key=repr)),
        )
    if isinstance(value, bytes):
        return ("bytes", value.hex())
    if isinstance(value, datetime):
        return ("datetime", value.isoformat())
    return ("scalar", None if value is None else str(value))


def _canonical_atoms(value):
    if isinstance(value, Mapping):
        return tuple(
            atom
            for item in value.values()
            for atom in _canonical_atoms(item)
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(
            atom
            for item in value
            for atom in _canonical_atoms(item)
        )
    if value is None:
        return ()
    if isinstance(value, bytes):
        return (value.hex(),)
    return (str(value),)


def _provider_authority_snapshot(db, tables):
    snapshot = []
    for table in tables:
        order_id_column = table.metadata.tables["ordens_checkout"].c.id
        rows = []
        for row in db.execute(select(table)).all():
            values = tuple(row)
            rows.append(
                (
                    tuple(_canonical_value(value) for value in values),
                    tuple(sorted(_canonical_atoms(values))),
                )
            )
        snapshot.append(
            (
                table.fullname,
                tuple(column.name for column in table.columns),
                _order_fk_column_indexes(table, order_id_column),
                tuple(sorted(rows, key=repr)),
            )
        )
    return tuple(snapshot)


def _matching_provider_evidence(snapshot, order_id, notification_id, payment_id):
    required_atoms = {str(notification_id), str(payment_id)}
    canonical_order_id = _canonical_value(order_id)
    return tuple(
        (table_name, row)
        for table_name, _columns, order_fk_indexes, rows in snapshot
        for row in rows
        if any(
            row[0][column_index] == canonical_order_id
            for column_index in order_fk_indexes
        )
        and required_atoms.issubset(set(row[1]))
    )


def _snapshot(Session, models, provider_authority_tables):
    with Session() as db:
        order = db.get(models.OrdemCheckout, _ORDER_ID)
        return {
            "order": (order.estado, order.payment_id),
            "campaign_snapshot": (
                order.campaign_id,
                order.campaign_code,
                order.campaign_contract_version,
                order.campaign_purchase_limit,
                order.campaign_reservation_expires_at,
            ),
            "payments": _rows(db, models.Pagamento),
            "grants": _rows(db, models.CheckoutOfferGrant),
            "events": tuple(
                (event.ordem_id, event.notification_id, event.payment_id)
                for event in db.scalars(
                    select(models.EventoPagamento).order_by(
                        models.EventoPagamento.notification_id
                    )
                ).all()
            ),
            "entitlement_count": db.scalar(
                select(func.count()).select_from(models.Entitlement)
            ),
            "provider_authority": _provider_authority_snapshot(
                db, provider_authority_tables
            ),
        }


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


def _envelope(notification_id, payment_id):
    return {
        "notification_id": notification_id,
        "payment_id": payment_id,
        "request_id": f"offline-r3-{notification_id}-{payment_id}",
    }


def _attempt(orchestrator, orchestration, notification_id, payment_id):
    try:
        return orchestrator.processar(
            _envelope(notification_id, payment_id),
            _SIGNATURE,
        ), None
    except orchestration.MercadoPagoWebhookOrchestrationError as error:
        return None, error


def _assert_sanitized_public_error(error, orchestration, *identities):
    assert type(error) is orchestration.MercadoPagoWebhookOrchestrationError
    assert error.__cause__ is None
    for representation in (str(error), repr(error)):
        rendered = representation.lower()
        for forbidden in (
            _SIGNATURE,
            "external_reference",
            "transaction_amount",
            "currency_id",
            "select ",
            "insert ",
            "update ",
            "delete ",
            *identities,
        ):
            assert str(forbidden).lower() not in rendered


def test_payments_checkout_offer_second_legitimate_payment_reconciliation_contract_red():
    from app import models
    from app.services import checkout_offer_one_time_confirmation as confirmation
    from app.services import mercado_pago_payment_resolution as resolution
    from app.services import mercado_pago_webhook_orchestration as orchestration

    violations = []

    def require(condition, marker):
        if not condition and marker not in violations:
            violations.append(marker)

    expected_provider_payments = {
        payment_id: {
            "id": payment_id,
            "external_reference": str(_ORDER_ID),
            "status": "approved",
            "transaction_amount": _AMOUNT,
            "currency_id": _CURRENCY,
        }
        for payment_id in (_P1, _P2, _P3)
    }
    primary_event = ((_ORDER_ID, _N1, _P1),)
    provider_authority_tables = _provider_authority_tables(models)

    with _environment(models, provider_authority_tables) as (_engine, Session):
        provider = _ReadOnlyFakePaymentClient()
        verifier = _AlwaysValidSignatureVerifier()
        resolver = resolution.MercadoPagoPaymentResolver(provider)
        confirmer = confirmation.CheckoutOfferOneTimeConfirmer(Session)
        orchestrator = orchestration.MercadoPagoWebhookOrchestrator(
            verificador_assinatura=verifier,
            resolvedor_pagamento=resolver,
            checkout_core=confirmer,
        )

        assert provider.snapshot() == expected_provider_payments
        preflight = _snapshot(Session, models, provider_authority_tables)
        assert preflight["order"] == ("pending", None)
        assert preflight["payments"] == ()
        assert preflight["grants"] == ()
        assert preflight["events"] == ()
        assert preflight["entitlement_count"] == 0
        assert (
            _matching_provider_evidence(
                preflight["provider_authority"], _ORDER_ID, _N2, _P2
            )
            == ()
        )

        # C1: P1/N1 aprovado percorre resolver, orquestrador e confirmer reais.
        first_result = orchestrator.processar(_envelope(_N1, _P1), _SIGNATURE)
        assert first_result is not None
        assert (
            first_result.ordem_id,
            first_result.estado,
            first_result.payment_id,
        ) == (_ORDER_ID, "paid", _P1)
        assert provider.calls == [_P1]

        after_first = _snapshot(Session, models, provider_authority_tables)
        assert after_first["order"] == ("paid", _P1)
        assert len(after_first["payments"]) == 1
        assert after_first["payments"][0][1] == _USER_ID
        assert after_first["payments"][0][4] == _ORDER_ID
        assert after_first["payments"][0][9] == _P1
        assert len(after_first["grants"]) == 1
        assert after_first["events"] == primary_event
        assert after_first["entitlement_count"] == 0
        first_payment = after_first["payments"][0]
        first_payment_id = first_payment[0]
        first_grant_id = after_first["grants"][0][0]
        assert first_result.grant_id == first_grant_id

        # C2: P2 e um pagamento aprovado real, distinto, para a mesma ordem.
        _second_result, second_error = _attempt(
            orchestrator, orchestration, _N2, _P2
        )
        if second_error is not None:
            _assert_sanitized_public_error(
                second_error, orchestration, _N2, _P2, _ORDER_ID
            )
        assert provider.calls == [_P1, _P2]

        after_second = _snapshot(Session, models, provider_authority_tables)
        require(
            after_second["order"] == ("paid", _P1),
            "SECOND_PAYMENT_MUTATED_PRIMARY_PAYMENT",
        )
        require(
            len(after_second["payments"]) == 1
            and after_second["payments"][0][0] == first_payment_id
            and after_second["payments"][0] == first_payment,
            "SECOND_PAYMENT_CREATED_DUPLICATE_PAYMENT",
        )
        require(
            len(after_second["grants"]) == 1
            and after_second["grants"][0][0] == first_grant_id,
            "SECOND_PAYMENT_CREATED_DUPLICATE_GRANT",
        )
        require(
            after_second["entitlement_count"] == 0,
            "SECOND_PAYMENT_CREATED_ENTITLEMENT",
        )
        require(
            after_second["events"] == primary_event,
            "SECOND_PAYMENT_MUTATED_PRIMARY_EVENT_EVIDENCE",
        )
        second_evidence = _matching_provider_evidence(
            after_second["provider_authority"], _ORDER_ID, _N2, _P2
        )
        require(
            len(second_evidence) == 1,
            "SECOND_LEGITIMATE_PAYMENT_NOT_DURABLY_PRESERVED",
        )

        # C3: replay exato N2/P2 converge sem duplicar a evidencia.
        _replay_result, replay_error = _attempt(
            orchestrator, orchestration, _N2, _P2
        )
        if replay_error is not None:
            _assert_sanitized_public_error(
                replay_error, orchestration, _N2, _P2, _ORDER_ID
            )
        assert provider.calls == [_P1, _P2, _P2]

        after_replay = _snapshot(Session, models, provider_authority_tables)
        replay_evidence = _matching_provider_evidence(
            after_replay["provider_authority"], _ORDER_ID, _N2, _P2
        )
        require(
            after_replay["events"] == primary_event,
            "SECOND_PAYMENT_MUTATED_PRIMARY_EVENT_EVIDENCE",
        )
        require(
            len(replay_evidence) >= 1,
            "SECOND_LEGITIMATE_PAYMENT_NOT_DURABLY_PRESERVED",
        )
        require(
            len(replay_evidence) <= 1,
            "SECOND_PAYMENT_REPLAY_DUPLICATED_EVIDENCE",
        )
        require(
            after_replay["order"] == ("paid", _P1),
            "SECOND_PAYMENT_MUTATED_PRIMARY_PAYMENT",
        )
        require(
            len(after_replay["payments"]) == 1
            and after_replay["payments"][0] == first_payment,
            "SECOND_PAYMENT_CREATED_DUPLICATE_PAYMENT",
        )
        require(
            len(after_replay["grants"]) == 1
            and after_replay["grants"][0][0] == first_grant_id,
            "SECOND_PAYMENT_CREATED_DUPLICATE_GRANT",
        )
        require(
            after_replay["entitlement_count"] == 0,
            "SECOND_PAYMENT_CREATED_ENTITLEMENT",
        )

        # C4: N2/P3 divergente nao pode substituir a evidencia N2/P2.
        _divergent_result, divergent_error = _attempt(
            orchestrator, orchestration, _N2, _P3
        )
        require(
            divergent_error is not None,
            "SECOND_PAYMENT_DIVERGENT_REPLAY_NOT_FAIL_CLOSED",
        )
        if divergent_error is not None:
            _assert_sanitized_public_error(
                divergent_error, orchestration, _N2, _P3, _ORDER_ID
            )
        assert provider.calls == [_P1, _P2, _P2, _P3]

        after_divergent = _snapshot(Session, models, provider_authority_tables)
        divergent_evidence = _matching_provider_evidence(
            after_divergent["provider_authority"], _ORDER_ID, _N2, _P2
        )
        require(
            after_divergent["events"] == primary_event,
            "SECOND_PAYMENT_MUTATED_PRIMARY_EVENT_EVIDENCE",
        )
        require(
            not replay_evidence
            or all(evidence in divergent_evidence for evidence in replay_evidence),
            "SECOND_PAYMENT_DIVERGENT_REPLAY_OVERWROTE_EVIDENCE",
        )
        require(
            after_divergent["order"] == ("paid", _P1),
            "SECOND_PAYMENT_MUTATED_PRIMARY_PAYMENT",
        )
        require(
            len(after_divergent["payments"]) == 1
            and after_divergent["payments"][0] == first_payment,
            "SECOND_PAYMENT_CREATED_DUPLICATE_PAYMENT",
        )
        require(
            len(after_divergent["grants"]) == 1
            and after_divergent["grants"][0][0] == first_grant_id,
            "SECOND_PAYMENT_CREATED_DUPLICATE_GRANT",
        )
        require(
            after_divergent["entitlement_count"] == 0,
            "SECOND_PAYMENT_CREATED_ENTITLEMENT",
        )

        with Session() as db:
            reservations = db.scalars(
                select(models.CheckoutOfferCampaignReservation).where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == _ORDER_ID
                )
            ).all()
            assert len(reservations) == 1
            assert _reservation_is_structurally_coherent(reservations[0])
        assert after_divergent["campaign_snapshot"] == (
            _CAMPAIGN_ID,
            _CAMPAIGN_CODE,
            11,
            50,
            _LIVE_EXPIRES_AT,
        )

    assert not violations, ",".join(violations)
