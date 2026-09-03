"""Contrato RED da composicao atomica de ordem e reserva de campanha."""

import ast
import socket
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from threading import Barrier, Lock


_ROOT = Path(__file__).resolve().parents[1]
_COMPOSER_PATH = (
    _ROOT / "app" / "services" / "checkout_offer_order_composition.py"
)
_PUBLIC_ERROR = "Nao foi possivel criar a ordem de checkout"
_CAUSAL_MARKER = "COMPOSER_RESERVATION_AUTHORITY_NOT_INTEGRATED"
_CAMPAIGN_FIELDS = (
    "campaign_id",
    "campaign_code",
    "campaign_contract_version",
    "campaign_purchase_limit",
    "campaign_reservation_expires_at",
)
_PUBLIC_SNAPSHOT_FIELDS = (
    "id",
    "offer_id",
    "offer_code",
    "contract_version",
    "vertical",
    "commercial_model",
    "subject_type",
    "subject_id",
    "user_id",
    "valor",
    "moeda",
    "billing_period",
    "usage_unit",
    "usage_limit",
    "capabilities",
    "idempotency_key",
    "estado",
    "plano_id",
)
_DOCKER_STARTED = False


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _enclosing_function(tree, target):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if target in ast.walk(node):
                return node
    return None


def _assert_composer_uses_reservation_authority():
    source = _COMPOSER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_COMPOSER_PATH))
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _call_name(node.func)
        == "CheckoutOfferCampaignReservationAuthority"
        and len(node.args) == 1
        and not node.keywords
    ]

    integrated = False
    for constructor in constructors:
        function = _enclosing_function(tree, constructor)
        if function is None:
            continue
        assigned_names = set()
        for node in ast.walk(function):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is not constructor:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            assigned_names.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )

        for call in ast.walk(function):
            if not isinstance(call, ast.Call):
                continue
            method = call.func
            if not (
                isinstance(method, ast.Attribute)
                and method.attr == "reservar_para_ordem"
            ):
                continue
            receiver_is_instance = (
                isinstance(method.value, ast.Name)
                and method.value.id in assigned_names
            )
            receiver_is_constructor = method.value is constructor
            keywords = {keyword.arg for keyword in call.keywords}
            if (
                (receiver_is_instance or receiver_is_constructor)
                and not call.args
                and keywords
                == {"authenticated_user_id", "empresa_id", "ordem_id"}
            ):
                integrated = True
                break
        if integrated:
            break

    assert integrated, _CAUSAL_MARKER


def _run_docker(arguments):
    return subprocess.run(
        arguments,
        cwd=_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def _postgresql(models):
    from sqlalchemy import create_engine

    global _DOCKER_STARTED
    suffix = uuid.uuid4().hex[:12]
    container = f"mei0049c-{suffix}"
    database = f"mei0049c_{suffix}"
    password = uuid.uuid4().hex
    port = _free_port()
    engine = None

    try:
        _DOCKER_STARTED = True
        started = _run_docker(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--label",
                "mission=MEI_0049C_CAMPAIGN_ORDER_COMPOSITION_RED",
                "-e",
                "POSTGRES_USER=mei0049c",
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-e",
                f"POSTGRES_DB={database}",
                "-p",
                f"127.0.0.1:{port}:5432",
                "postgres:16-alpine",
            ]
        )
        assert started.returncode == 0, started.stderr

        consecutive_ready = 0
        last_readiness = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            last_readiness = _run_docker(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_isready",
                    "-U",
                    "mei0049c",
                    "-d",
                    database,
                ]
            )
            consecutive_ready = (
                consecutive_ready + 1 if last_readiness.returncode == 0 else 0
            )
            if consecutive_ready == 2:
                break
            time.sleep(0.25)
        else:
            raise AssertionError(
                "PostgreSQL 16 nao ficou pronto: "
                f"{last_readiness.stdout}{last_readiness.stderr}"
            )

        engine = create_engine(
            f"postgresql+psycopg2://mei0049c:{password}"
            f"@127.0.0.1:{port}/{database}",
            pool_pre_ping=True,
            connect_args={
                "options": "-c lock_timeout=5000 -c statement_timeout=20000"
            },
        )
        tables = (
            models.Plano.__table__,
            models.User.__table__,
            models.Empresa.__table__,
            models.CheckoutOffer.__table__,
            models.CheckoutOfferCapability.__table__,
            models.CheckoutOfferCampaign.__table__,
            models.OrdemCheckout.__table__,
            models.OrdemCheckoutCapability.__table__,
            models.CheckoutOfferCampaignReservation.__table__,
        )
        with engine.begin() as connection:
            models.Base.metadata.create_all(connection, tables=tables)
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.server_version_info[:1] == (16,)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        _run_docker(["docker", "rm", "--force", container])


def _tracked_session_class():
    from sqlalchemy.orm import Session as SASession

    class TrackedSession(SASession):
        instances = []
        guard = Lock()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.commit_calls = 0
            self.rollback_calls = 0
            self.close_calls = 0
            with self.guard:
                self.instances.append(self)

        def commit(self):
            self.commit_calls += 1
            return super().commit()

        def rollback(self):
            self.rollback_calls += 1
            return super().rollback()

        def close(self):
            self.close_calls += 1
            return super().close()

    return TrackedSession


def _offer(models, identity, *, code=None):
    offer = models.CheckoutOffer(
        id=identity,
        codigo=code or f"composition-offer-{identity}",
        nome_publico=f"Oferta {identity}",
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        estado="published",
        moeda="BRL",
        preco=Decimal("49.90"),
        billing_period=None,
        usage_unit="document",
        usage_limit=3,
        contract_version=2,
    )
    offer.capabilities = [
        models.CheckoutOfferCapability(codigo="document.extract"),
        models.CheckoutOfferCapability(codigo="document.validate"),
    ]
    return offer


def _campaign(models, identity, offer_id, *, limit=1, ttl=1800):
    now = datetime.utcnow()
    return models.CheckoutOfferCampaign(
        id=identity,
        codigo=f"composition-campaign-{identity}",
        offer_id=offer_id,
        estado="active",
        purchase_limit=limit,
        reservation_ttl_seconds=ttl,
        contract_version=4,
        criado_em=now,
        atualizado_em=now,
    )


def _seed_principals(models, Session):
    with Session.begin() as db:
        db.add_all(
            (
                models.Plano(
                    id=1,
                    nome="Plano de teste",
                    limite_cnpjs=1,
                    limite_analises=1,
                    preco=Decimal("1.00"),
                    billing_type="monthly",
                    ativo=True,
                    tipo_acesso="relatorio",
                ),
                models.User(
                    id=1,
                    email="owner@example.invalid",
                    hashed_password="hash-de-teste",
                ),
                models.User(
                    id=2,
                    email="other@example.invalid",
                    hashed_password="hash-de-teste",
                ),
                models.Empresa(id=11, razao_social="Empresa alvo", user_id=1),
                models.Empresa(id=12, razao_social="Empresa alheia", user_id=2),
            )
        )


def _start(
    composer,
    *,
    offer_code,
    key,
    user_id=1,
    empresa_id=11,
):
    return composer.iniciar_checkout_empresa(
        authenticated_user_id=user_id,
        empresa_id=empresa_id,
        offer_code=offer_code,
        idempotency_key=key,
    )


def _expect_public_error(composition, callback):
    import pytest

    with pytest.raises(composition.CheckoutOfferOrderCompositionError) as caught:
        callback()
    assert type(caught.value) is composition.CheckoutOfferOrderCompositionError
    assert str(caught.value) == _PUBLIC_ERROR


def _campaign_snapshot(order):
    return tuple(getattr(order, field) for field in _CAMPAIGN_FIELDS)


def _row(model, instance):
    return tuple(getattr(instance, column.name) for column in model.__table__.columns)


def _persisted_for_key(models, Session, key):
    from sqlalchemy import select

    with Session() as db:
        order = db.scalar(
            select(models.OrdemCheckout).where(
                models.OrdemCheckout.idempotency_key == key
            )
        )
        reservations = tuple(
            _row(models.CheckoutOfferCampaignReservation, reservation)
            for reservation in db.scalars(
                select(models.CheckoutOfferCampaignReservation)
                .where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == (order.id if order is not None else -1)
                )
                .order_by(models.CheckoutOfferCampaignReservation.id)
            )
        )
        return (
            None if order is None else _row(models.OrdemCheckout, order),
            reservations,
        )


def _assert_public_snapshot(composition, result, *, key, offer_id, offer_code):
    assert type(result) is composition.CheckoutOfferOrderSnapshot
    assert tuple(type(result).__annotations__) == _PUBLIC_SNAPSHOT_FIELDS
    assert tuple(vars(result)) == _PUBLIC_SNAPSHOT_FIELDS
    assert set(vars(result)).isdisjoint(_CAMPAIGN_FIELDS)
    assert vars(result) == {
        "id": result.id,
        "offer_id": offer_id,
        "offer_code": offer_code,
        "contract_version": 2,
        "vertical": "document",
        "commercial_model": "one_time",
        "subject_type": "company",
        "subject_id": 11,
        "user_id": 1,
        "valor": Decimal("49.90"),
        "moeda": "BRL",
        "billing_period": None,
        "usage_unit": "document",
        "usage_limit": 3,
        "capabilities": ("document.extract", "document.validate"),
        "idempotency_key": key,
        "estado": "pending",
        "plano_id": None,
    }


def _prove_unbound_and_non_retroactive(
    composition, models, Session, composer
):
    from sqlalchemy import func, select

    offer = _offer(models, 100)
    with Session.begin() as db:
        db.add(offer)

    instance_index = len(Session.class_.instances)
    first = _start(composer, offer_code=offer.codigo, key="unbound-order")
    _assert_public_snapshot(
        composition,
        first,
        key="unbound-order",
        offer_id=100,
        offer_code=offer.codigo,
    )
    composer_sessions = Session.class_.instances[instance_index:]
    assert len(composer_sessions) == 1
    assert composer_sessions[0].commit_calls == 1
    assert composer_sessions[0].rollback_calls == 0
    assert composer_sessions[0].close_calls == 1

    with Session() as db:
        order = db.get(models.OrdemCheckout, first.id)
        assert _campaign_snapshot(order) == (None,) * 5
        assert db.scalar(
            select(func.count()).select_from(
                models.CheckoutOfferCampaignReservation
            )
        ) == 0

    for arguments in (
        dict(user_id=2, empresa_id=12, offer_code=offer.codigo),
        dict(user_id=1, empresa_id=12, offer_code=offer.codigo),
        dict(user_id=1, empresa_id=11, offer_code="different-offer-code"),
    ):
        _expect_public_error(
            composition,
            lambda arguments=arguments: _start(
                composer,
                key="unbound-order",
                **arguments,
            ),
        )

    with Session.begin() as db:
        db.add(_campaign(models, 100, 100, limit=3))
    retried = _start(composer, offer_code=offer.codigo, key="unbound-order")
    assert retried.id == first.id
    with Session() as db:
        order = db.get(models.OrdemCheckout, first.id)
        assert _campaign_snapshot(order) == (None,) * 5
        assert db.scalar(
            select(func.count()).select_from(
                models.CheckoutOfferCampaignReservation
            )
        ) == 0


def _prove_bound_atomicity_and_retry(
    composition, models, Session, composer
):
    from sqlalchemy import func, select

    offer = _offer(models, 200)
    campaign = _campaign(models, 200, 200, limit=1, ttl=2400)
    with Session.begin() as db:
        db.add_all((offer, campaign))

    instance_index = len(Session.class_.instances)
    first = _start(composer, offer_code=offer.codigo, key="bound-order")
    composer_sessions = Session.class_.instances[instance_index:]
    assert len(composer_sessions) == 1
    assert composer_sessions[0].commit_calls == 1
    assert composer_sessions[0].rollback_calls == 0
    assert composer_sessions[0].close_calls == 1
    _assert_public_snapshot(
        composition,
        first,
        key="bound-order",
        offer_id=200,
        offer_code=offer.codigo,
    )
    with Session() as db:
        order = db.get(models.OrdemCheckout, first.id)
        reservations = tuple(
            db.scalars(
                select(models.CheckoutOfferCampaignReservation).where(
                    models.CheckoutOfferCampaignReservation.ordem_id == first.id
                )
            )
        )
        assert len(reservations) == 1
        reservation = reservations[0]
        assert reservation.estado == "reserved"
        original_reservation_id = reservation.id
        original_snapshot = _campaign_snapshot(order)
        assert original_snapshot == (
            campaign.id,
            campaign.codigo,
            campaign.contract_version,
            campaign.purchase_limit,
            reservation.expires_at,
        )
        assert order.campaign_reservation_expires_at == reservation.expires_at

    before_capacity_failure = _persisted_for_key(
        models, Session, "bound-order"
    )
    _expect_public_error(
        composition,
        lambda: _start(
            composer,
            offer_code=offer.codigo,
            key="capacity-must-rollback",
        ),
    )
    assert _persisted_for_key(models, Session, "capacity-must-rollback") == (
        None,
        (),
    )
    assert _persisted_for_key(models, Session, "bound-order") == (
        before_capacity_failure
    )
    with Session() as db:
        assert db.scalar(
            select(func.count()).select_from(models.OrdemCheckout)
        ) == 2
        assert db.scalar(
            select(func.count()).select_from(
                models.CheckoutOfferCampaignReservation
            )
        ) == 1

    retried = _start(composer, offer_code=offer.codigo, key="bound-order")
    assert retried.id == first.id
    with Session() as db:
        order = db.get(models.OrdemCheckout, first.id)
        reservations = tuple(
            db.scalars(
                select(models.CheckoutOfferCampaignReservation).where(
                    models.CheckoutOfferCampaignReservation.ordem_id == first.id
                )
            )
        )
        assert len(reservations) == 1
        assert reservations[0].id == original_reservation_id
        assert _campaign_snapshot(order) == original_snapshot

    with Session.begin() as db:
        mutable_campaign = db.get(models.CheckoutOfferCampaign, campaign.id)
        mutable_campaign.estado = "retired"
        mutable_campaign.codigo = "composition-campaign-200-retired"
        mutable_campaign.contract_version = 9
        mutable_campaign.purchase_limit = 17
        mutable_campaign.reservation_ttl_seconds = 123
    before_retired_retry = _persisted_for_key(models, Session, "bound-order")
    retired_retry = _start(
        composer, offer_code=offer.codigo, key="bound-order"
    )
    assert retired_retry.id == first.id
    assert _persisted_for_key(models, Session, "bound-order") == (
        before_retired_retry
    )

    with Session.begin() as db:
        reservation = db.get(
            models.CheckoutOfferCampaignReservation,
            original_reservation_id,
        )
        reservation.estado = "released"
        reservation.released_at = datetime.utcnow()
    before_invalid_retry = _persisted_for_key(models, Session, "bound-order")
    _expect_public_error(
        composition,
        lambda: _start(composer, offer_code=offer.codigo, key="bound-order"),
    )
    assert _persisted_for_key(models, Session, "bound-order") == (
        before_invalid_retry
    )


def _prove_same_key_concurrency(composition, models, Session, composer):
    from sqlalchemy import func, select

    offer = _offer(models, 300)
    campaign = _campaign(models, 300, 300, limit=2, ttl=3600)
    with Session.begin() as db:
        db.add_all((offer, campaign))

    barrier = Barrier(4)

    def _worker(_index):
        barrier.wait(timeout=10)
        return _start(
            composer,
            offer_code=offer.codigo,
            key="concurrent-same-key",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = tuple(pool.map(_worker, range(4)))
    assert len(results) == 4
    assert {result.id for result in results} == {results[0].id}
    for result in results:
        _assert_public_snapshot(
            composition,
            result,
            key="concurrent-same-key",
            offer_id=300,
            offer_code=offer.codigo,
        )

    with Session() as db:
        orders = tuple(
            db.scalars(
                select(models.OrdemCheckout).where(
                    models.OrdemCheckout.idempotency_key
                    == "concurrent-same-key"
                )
            )
        )
        assert len(orders) == 1
        reservations = tuple(
            db.scalars(
                select(models.CheckoutOfferCampaignReservation).where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == orders[0].id
                )
            )
        )
        assert len(reservations) == 1
        reservation = reservations[0]
        assert _campaign_snapshot(orders[0]) == (
            campaign.id,
            campaign.codigo,
            campaign.contract_version,
            campaign.purchase_limit,
            reservation.expires_at,
        )
        live = db.scalar(
            select(func.count())
            .select_from(models.CheckoutOfferCampaignReservation)
            .where(
                models.CheckoutOfferCampaignReservation.campaign_id
                == campaign.id,
                models.CheckoutOfferCampaignReservation.estado == "reserved",
                models.CheckoutOfferCampaignReservation.expires_at
                > func.current_timestamp(),
            )
        )
        orphan = db.scalar(
            select(func.count())
            .select_from(models.CheckoutOfferCampaignReservation)
            .outerjoin(
                models.OrdemCheckout,
                models.OrdemCheckout.id
                == models.CheckoutOfferCampaignReservation.ordem_id,
            )
            .where(models.OrdemCheckout.id.is_(None))
        )
        assert (live, orphan) == (1, 0)


def _prove_corrupt_retry_fail_closed(
    composition, models, Session, composer, engine
):
    from sqlalchemy import func, select, text, update

    partial_offer = _offer(models, 400)
    missing_identity_offer = _offer(models, 401)
    with Session.begin() as db:
        db.add_all((partial_offer, missing_identity_offer))
    partial = _start(
        composer, offer_code=partial_offer.codigo, key="partial-snapshot"
    )
    missing_identity = _start(
        composer,
        offer_code=missing_identity_offer.codigo,
        key="missing-offer-identity",
    )

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE ordens_checkout DROP CONSTRAINT "
                "ck_ordens_checkout_campaign_snapshot_coerente"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE ordens_checkout DROP CONSTRAINT "
                "ck_ordens_checkout_formato_coerente"
            )
        )
    with Session.begin() as db:
        db.execute(
            update(models.OrdemCheckout)
            .where(models.OrdemCheckout.id == partial.id)
            .values(campaign_code="partial-corruption")
        )
        db.execute(
            update(models.OrdemCheckout)
            .where(models.OrdemCheckout.id == missing_identity.id)
            .values(offer_id=None)
        )

    for result, offer, key in (
        (partial, partial_offer, "partial-snapshot"),
        (missing_identity, missing_identity_offer, "missing-offer-identity"),
    ):
        before = _persisted_for_key(models, Session, key)
        _expect_public_error(
            composition,
            lambda offer=offer, key=key: _start(
                composer, offer_code=offer.codigo, key=key
            ),
        )
        assert _persisted_for_key(models, Session, key) == before
        with Session() as db:
            assert db.scalar(
                select(func.count())
                .select_from(models.CheckoutOfferCampaignReservation)
                .where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == result.id
                )
            ) == 0


def _prove_null_snapshot_with_reservation_fail_closed(
    composition, models, Session, composer
):
    from sqlalchemy import select

    offer = _offer(models, 500)
    with Session.begin() as db:
        db.add(offer)

    key = "campaign-order-null-snapshot-with-reservation"
    first = _start(composer, offer_code=offer.codigo, key=key)
    _assert_public_snapshot(
        composition,
        first,
        key=key,
        offer_id=offer.id,
        offer_code=offer.codigo,
    )

    with Session.begin() as db:
        order = db.scalar(
            select(models.OrdemCheckout).where(
                models.OrdemCheckout.idempotency_key == key
            )
        )
        assert order is not None
        assert _campaign_snapshot(order) == (None, None, None, None, None)

        campaign = _campaign(models, 500, offer.id)
        db.add(campaign)
        db.flush()

        reserved_at = datetime.utcnow()
        db.add(
            models.CheckoutOfferCampaignReservation(
                campaign_id=campaign.id,
                ordem_id=order.id,
                estado="reserved",
                reserved_at=reserved_at,
                expires_at=reserved_at + timedelta(hours=1),
                confirmed_at=None,
                released_at=None,
                expired_at=None,
            )
        )

    before = _persisted_for_key(models, Session, key)
    assert before[0] is not None
    assert len(before[1]) == 1
    _expect_public_error(
        composition,
        lambda: _start(composer, offer_code=offer.codigo, key=key),
    )
    after = _persisted_for_key(models, Session, key)
    assert after == before
    assert len(after[1]) == 1


def test_payments_checkout_offer_campaign_order_composition_contract_red():
    try:
        _assert_composer_uses_reservation_authority()
    except AssertionError:
        assert _DOCKER_STARTED is False
        raise

    composition = import_module("app.services.checkout_offer_order_composition")
    models = import_module("app.models")

    from sqlalchemy.orm import sessionmaker

    assert tuple(composition.CheckoutOfferOrderSnapshot.__annotations__) == (
        _PUBLIC_SNAPSHOT_FIELDS
    )
    with _postgresql(models) as engine:
        TrackedSession = _tracked_session_class()
        Session = sessionmaker(
            bind=engine,
            class_=TrackedSession,
            expire_on_commit=False,
        )
        _seed_principals(models, Session)
        composer = composition.CheckoutOfferOrderComposer(Session)
        _prove_unbound_and_non_retroactive(
            composition, models, Session, composer
        )
        _prove_bound_atomicity_and_retry(
            composition, models, Session, composer
        )
        _prove_same_key_concurrency(
            composition, models, Session, composer
        )
        _prove_corrupt_retry_fail_closed(
            composition, models, Session, composer, engine
        )
        _prove_null_snapshot_with_reservation_fail_closed(
            composition, models, Session, composer
        )
