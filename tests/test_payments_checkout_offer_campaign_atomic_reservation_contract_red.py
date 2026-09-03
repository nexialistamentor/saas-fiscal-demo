"""Contrato RED da reserva atomica de campanha de checkout."""

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
from inspect import Parameter, getsource, signature
from pathlib import Path
from threading import Barrier


_ROOT = Path(__file__).resolve().parents[1]
_ERROR_MESSAGE = "Nao foi possivel reservar a campanha de checkout"
_SNAPSHOT_FIELDS = (
    "campaign_id",
    "campaign_code",
    "campaign_contract_version",
    "campaign_purchase_limit",
    "campaign_reservation_expires_at",
)
_PROJECTION_FIELDS = (
    "reservation_id",
    "ordem_id",
    "campaign_id",
    "campaign_code",
    "campaign_contract_version",
    "campaign_purchase_limit",
    "estado",
    "reserved_at",
    "expires_at",
)


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

    suffix = uuid.uuid4().hex[:12]
    container = f"mei0049b-{suffix}"
    database = f"mei0049b_{suffix}"
    password = uuid.uuid4().hex
    port = _free_port()
    engine = None

    try:
        started = _run_docker(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                container,
                "--label",
                "mission=MEI_0049B_ATOMIC_CAMPAIGN_RESERVATION_RED",
                "-e",
                "POSTGRES_USER=mei0049b",
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
                    "mei0049b",
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
            f"postgresql+psycopg2://mei0049b:{password}"
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
            models.CheckoutOfferCampaign.__table__,
            models.OrdemCheckout.__table__,
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


def _offer(models, identity):
    return models.CheckoutOffer(
        id=identity,
        codigo=f"campaign-offer-{identity}",
        nome_publico=f"Oferta {identity}",
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        estado="published",
        moeda="BRL",
        preco=Decimal("49.90"),
        billing_period=None,
        usage_unit="document",
        usage_limit=1,
        contract_version=2,
    )


def _campaign(models, identity, offer_id, *, limit=1, state="active", ttl=900):
    now = datetime.utcnow()
    return models.CheckoutOfferCampaign(
        id=identity,
        codigo=f"campaign-{identity}",
        offer_id=offer_id,
        estado=state,
        purchase_limit=limit,
        reservation_ttl_seconds=ttl,
        contract_version=4,
        criado_em=now,
        atualizado_em=now,
    )


def _order(models, identity, offer_id, *, user_id=1, empresa_id=11, **changes):
    values = dict(
        id=identity,
        user_id=user_id,
        empresa_id=empresa_id,
        plano_id=None,
        offer_id=offer_id,
        offer_code=f"campaign-offer-{offer_id}",
        contract_version=2,
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        subject_id=empresa_id,
        valor=Decimal("49.90"),
        moeda="BRL",
        estado="pending",
        idempotency_key=f"mei0049b-order-{identity}",
        provider_order_id=None,
        checkout_url=None,
        payment_id=None,
        billing_period=None,
        usage_unit="document",
        usage_limit=1,
    )
    values.update(changes)
    return models.OrdemCheckout(**values)


def _reservation(
    models,
    identity,
    campaign_id,
    order_id,
    state,
    *,
    expired=False,
):
    now = datetime.utcnow()
    reserved_at = now - timedelta(hours=2) if expired else now
    expires_at = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    lifecycle = {
        "confirmed_at": now if state == "confirmed" else None,
        "released_at": now if state == "released" else None,
        "expired_at": now if state == "expired" else None,
    }
    return models.CheckoutOfferCampaignReservation(
        id=identity,
        campaign_id=campaign_id,
        ordem_id=order_id,
        estado=state,
        reserved_at=reserved_at,
        expires_at=expires_at,
        **lifecycle,
    )


def _snapshot(order):
    return tuple(getattr(order, field) for field in _SNAPSHOT_FIELDS)


def _projection(module, result):
    assert type(result) is module.CheckoutOfferCampaignReservationProjection
    assert tuple(type(result).__annotations__) == _PROJECTION_FIELDS
    values = {field: getattr(result, field) for field in _PROJECTION_FIELDS}
    assert values["estado"] == "reserved"
    return values


def _reserve(module, db, *, user_id=1, empresa_id=11, order_id):
    return module.CheckoutOfferCampaignReservationAuthority(db).reservar_para_ordem(
        authenticated_user_id=user_id,
        empresa_id=empresa_id,
        ordem_id=order_id,
    )


def _state(models, Session, order_ids):
    from sqlalchemy import func, select

    with Session() as db:
        reservations = db.scalar(
            select(func.count()).select_from(
                models.CheckoutOfferCampaignReservation
            )
        )
        snapshots = {
            order_id: _snapshot(db.get(models.OrdemCheckout, order_id))
            for order_id in order_ids
        }
    return reservations, snapshots


def _persisted_state(models, Session, order_ids, campaign_ids):
    from sqlalchemy import select

    def _row(model, instance):
        return tuple(
            getattr(instance, column.name) for column in model.__table__.columns
        )

    with Session() as db:
        orders = tuple(
            _row(models.OrdemCheckout, instance)
            for instance in db.scalars(
                select(models.OrdemCheckout)
                .where(models.OrdemCheckout.id.in_(order_ids))
                .order_by(models.OrdemCheckout.id)
            )
        )
        reservations = tuple(
            _row(models.CheckoutOfferCampaignReservation, instance)
            for instance in db.scalars(
                select(models.CheckoutOfferCampaignReservation)
                .where(
                    models.CheckoutOfferCampaignReservation.ordem_id.in_(
                        order_ids
                    )
                )
                .order_by(models.CheckoutOfferCampaignReservation.id)
            )
        )
        campaigns = tuple(
            _row(models.CheckoutOfferCampaign, instance)
            for instance in db.scalars(
                select(models.CheckoutOfferCampaign)
                .where(models.CheckoutOfferCampaign.id.in_(campaign_ids))
                .order_by(models.CheckoutOfferCampaign.id)
            )
        )
    return orders, reservations, campaigns


def _persisted_order_reservation_state(models, Session, order_ids):
    orders, reservations, _campaigns = _persisted_state(
        models,
        Session,
        order_ids,
        (),
    )
    return orders, reservations


def _expect_error(module, db, **arguments):
    import pytest

    with pytest.raises(module.CheckoutOfferCampaignReservationError) as caught:
        _reserve(module, db, **arguments)
    assert str(caught.value) == _ERROR_MESSAGE


def _assert_structure(module):
    assert module.__file__ is not None
    assert Path(module.__file__).resolve() == (
        _ROOT / "app" / "services" / "checkout_offer_campaign_reservation.py"
    ).resolve()
    assert issubclass(module.CheckoutOfferCampaignReservationError, Exception)
    assert str(module.CheckoutOfferCampaignReservationError()) == _ERROR_MESSAGE
    assert tuple(
        module.CheckoutOfferCampaignReservationProjection.__annotations__
    ) == _PROJECTION_FIELDS

    constructor = signature(module.CheckoutOfferCampaignReservationAuthority)
    assert tuple(constructor.parameters) == ("session",)
    method = signature(
        module.CheckoutOfferCampaignReservationAuthority.reservar_para_ordem
    )
    assert tuple(method.parameters) == (
        "self",
        "authenticated_user_id",
        "empresa_id",
        "ordem_id",
    )
    assert all(
        method.parameters[name].kind is Parameter.KEYWORD_ONLY
        for name in ("authenticated_user_id", "empresa_id", "ordem_id")
    )

    tree = ast.parse(getsource(module))
    attribute_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    direct_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    imported_roots = set()
    imported_clock_names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                imported_roots.add(root)
                if alias.name in {"datetime", "time"}:
                    imported_clock_names[alias.asname or alias.name] = (alias.name,)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
            if node.module in {"datetime", "time"}:
                for alias in node.names:
                    imported_clock_names[alias.asname or alias.name] = (
                        node.module,
                        alias.name,
                    )

    def _qualified_name(callable_node):
        parts = []
        while isinstance(callable_node, ast.Attribute):
            parts.append(callable_node.attr)
            callable_node = callable_node.value
        if not isinstance(callable_node, ast.Name):
            return ()
        imported = imported_clock_names.get(callable_node.id)
        return (*imported, *reversed(parts)) if imported else ()

    process_clock_calls = {
        _qualified_name(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert attribute_calls.isdisjoint({"commit", "rollback", "close"})
    assert direct_calls.isdisjoint(
        {"sessionmaker", "create_engine", "Session", "session_factory"}
    )
    assert identifiers.isdisjoint(
        {"sessionmaker", "create_engine", "session_factory"}
    )
    assert imported_roots.isdisjoint(
        {"requests", "httpx", "mercadopago", "redis", "secrets", "cryptography"}
    )
    assert process_clock_calls.isdisjoint(
        {
            ("datetime", "datetime", "utcnow"),
            ("datetime", "datetime", "now"),
            ("time", "time"),
        }
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
                models.Empresa(id=13, razao_social="Outra empresa", user_id=1),
            )
        )


def _prove_no_active_campaign(module, models, Session):
    with Session.begin() as db:
        db.add(_offer(models, 100))
        db.add(_order(models, 1000, 100))

    before = _state(models, Session, (1000,))
    with Session.begin() as db:
        assert _reserve(module, db, order_id=1000) is None
    assert _state(models, Session, (1000,)) == before

    with Session.begin() as db:
        db.add(_campaign(models, 100, 100, state="retired"))
        db.add(_order(models, 1001, 100))
    before = _state(models, Session, (1001,))
    with Session.begin() as db:
        assert _reserve(module, db, order_id=1001) is None
    assert _state(models, Session, (1001,)) == before


def _prove_eligibility_and_opaque_errors(module, models, Session):
    with Session.begin() as db:
        db.add(_offer(models, 110))
        db.add(_campaign(models, 110, 110, limit=20))
        db.add_all(
            (
                _order(models, 1100, 110, user_id=2, empresa_id=12),
                _order(models, 1101, 110, empresa_id=13),
                _order(models, 1102, 110, estado="cancelled"),
                _order(
                    models,
                    1103,
                    None,
                    plano_id=1,
                    offer_code=None,
                    contract_version=None,
                    vertical=None,
                    commercial_model=None,
                    subject_type=None,
                    subject_id=None,
                    usage_unit=None,
                    usage_limit=None,
                ),
                _order(
                    models,
                    1104,
                    110,
                    provider_order_id="provider-secret",
                    checkout_url="https://provider-secret.invalid",
                ),
                _order(models, 1105, 110, checkout_url="https://secret.invalid"),
                _order(models, 1106, 110, payment_id="payment-secret"),
                _order(
                    models,
                    1107,
                    110,
                    campaign_id=110,
                    campaign_code="campaign-110",
                    campaign_contract_version=4,
                    campaign_purchase_limit=20,
                    campaign_reservation_expires_at=datetime.utcnow()
                    + timedelta(minutes=10),
                ),
            )
        )

    cases = (
        dict(order_id=999999991),
        dict(order_id=1100),
        dict(order_id=1101),
        dict(order_id=1102),
        dict(order_id=1103),
        dict(order_id=1104),
        dict(order_id=1105),
        dict(order_id=1106),
        dict(order_id=1107),
        dict(order_id=1100, user_id=999999992, empresa_id=999999993),
    )
    tracked_orders = tuple(range(1100, 1108))
    before = _state(models, Session, tracked_orders)
    for case in cases:
        db = Session()
        try:
            _expect_error(module, db, **case)
            db.rollback()
        finally:
            db.close()
    assert _state(models, Session, tracked_orders) == before


def _prove_capacity_semantics(module, models, Session):
    from sqlalchemy import DateTime, cast, func, select

    cases = (
        ("confirmed", True, True),
        ("reserved", False, True),
        ("reserved", True, False),
        ("released", False, False),
        ("expired", True, False),
    )
    with Session.begin() as db:
        database_now = db.scalar(select(cast(func.current_timestamp(), DateTime)))
        for offset, (state, stale, _counts) in enumerate(cases):
            offer_id = 200 + offset
            campaign_id = 200 + offset
            occupied_order = 2000 + offset * 2
            candidate_order = occupied_order + 1
            db.add(_offer(models, offer_id))
            db.add(_campaign(models, campaign_id, offer_id, limit=1))
            db.add_all(
                (
                    _order(models, occupied_order, offer_id),
                    _order(models, candidate_order, offer_id),
                )
            )
            db.flush()
            reservation = _reservation(
                models,
                200 + offset,
                campaign_id,
                occupied_order,
                state,
                expired=stale,
            )
            reservation.reserved_at = database_now - timedelta(hours=2)
            reservation.expires_at = database_now + (
                -timedelta(hours=1) if stale else timedelta(hours=1)
            )
            db.add(reservation)

    for offset, (_state_name, _stale, counts) in enumerate(cases):
        candidate_order = 2000 + offset * 2 + 1
        db = Session()
        try:
            if counts:
                before = _state(models, Session, (candidate_order,))
                _expect_error(module, db, order_id=candidate_order)
                db.rollback()
                assert _state(models, Session, (candidate_order,)) == before
            else:
                projection = _projection(
                    module, _reserve(module, db, order_id=candidate_order)
                )
                assert projection["ordem_id"] == candidate_order
                db.commit()
        finally:
            if db.in_transaction():
                db.rollback()
            db.close()


def _prove_ttl_idempotency_retired_and_lifecycle(module, models, Session):
    from sqlalchemy import DateTime, cast, func, select

    ttl = 737
    with Session.begin() as db:
        db.add(_offer(models, 300))
        db.add(_campaign(models, 300, 300, limit=2, ttl=ttl))
        db.add(_order(models, 3000, 300))

    with Session.begin() as db:
        transaction_now = db.scalar(
            select(cast(func.current_timestamp(), DateTime))
        )
        first = _projection(module, _reserve(module, db, order_id=3000))
        db.flush()
        order = db.get(models.OrdemCheckout, 3000)
        row = db.get(models.CheckoutOfferCampaignReservation, first["reservation_id"])
        assert row.confirmed_at is None
        assert row.released_at is None
        assert row.expired_at is None
        assert row.reserved_at == transaction_now
        assert row.expires_at > row.reserved_at
        assert row.expires_at - row.reserved_at == timedelta(seconds=ttl)
        assert _snapshot(order) == (
            300,
            "campaign-300",
            4,
            2,
            row.expires_at,
        )
        assert first == {
            "reservation_id": row.id,
            "ordem_id": 3000,
            "campaign_id": 300,
            "campaign_code": "campaign-300",
            "campaign_contract_version": 4,
            "campaign_purchase_limit": 2,
            "estado": "reserved",
            "reserved_at": row.reserved_at,
            "expires_at": row.expires_at,
        }

    original_snapshot = _state(models, Session, (3000,))[1][3000]
    before_retry = _persisted_order_reservation_state(
        models, Session, (3000,)
    )
    with Session.begin() as db:
        second = _projection(module, _reserve(module, db, order_id=3000))
    assert second == first
    assert (
        _persisted_order_reservation_state(models, Session, (3000,))
        == before_retry
    )

    with Session.begin() as db:
        campaign = db.get(models.CheckoutOfferCampaign, 300)
        campaign.estado = "retired"
        campaign.codigo = "campaign-300-retired"
        campaign.contract_version = 9
        campaign.purchase_limit = 17
        campaign.reservation_ttl_seconds = 123
    assert _state(models, Session, (3000,))[1][3000] == original_snapshot
    before_retired_retry = _persisted_order_reservation_state(
        models, Session, (3000,)
    )
    with Session.begin() as db:
        retired_retry = _projection(module, _reserve(module, db, order_id=3000))
    assert retired_retry == first
    assert (
        _persisted_order_reservation_state(models, Session, (3000,))
        == before_retired_retry
    )

    lifecycle_changes = (
        dict(estado="confirmed", confirmed_at=datetime.utcnow()),
        dict(estado="released", confirmed_at=None, released_at=datetime.utcnow()),
        dict(estado="expired", released_at=None, expired_at=datetime.utcnow()),
        dict(
            estado="reserved",
            expired_at=None,
            reserved_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        ),
    )
    for changes in lifecycle_changes:
        with Session.begin() as db:
            row = db.get(
                models.CheckoutOfferCampaignReservation,
                first["reservation_id"],
            )
            for name, value in changes.items():
                setattr(row, name, value)
        before = _state(models, Session, (3000,))
        db = Session()
        try:
            _expect_error(module, db, order_id=3000)
            db.rollback()
        finally:
            db.close()
        assert _state(models, Session, (3000,)) == before


def _prove_persisted_contradictions_fail_closed(module, models, Session):
    with Session.begin() as db:
        db.add_all(
            (
                _offer(models, 600),
                _offer(models, 601),
                _offer(models, 602),
                _offer(models, 603),
                _campaign(models, 600, 600),
                _campaign(models, 601, 601),
                _campaign(models, 602, 602),
                _campaign(models, 603, 603),
            )
        )
        db.add_all(
            (
                _order(
                    models,
                    6000,
                    600,
                    campaign_id=600,
                    campaign_code="campaign-600",
                    campaign_contract_version=4,
                    campaign_purchase_limit=1,
                    campaign_reservation_expires_at=datetime.utcnow()
                    + timedelta(hours=1),
                ),
                _order(models, 6001, 602),
                _order(
                    models,
                    6002,
                    603,
                    campaign_id=603,
                    campaign_code="campaign-603",
                    campaign_contract_version=4,
                    campaign_purchase_limit=1,
                    campaign_reservation_expires_at=datetime.utcnow()
                    + timedelta(hours=3),
                ),
            )
        )
        db.flush()
        campaign_mismatch = _reservation(
            models, 600, 601, 6000, "reserved"
        )
        null_snapshot = _reservation(models, 601, 602, 6001, "reserved")
        expiry_mismatch = _reservation(models, 602, 603, 6002, "reserved")
        db.get(
            models.OrdemCheckout, 6000
        ).campaign_reservation_expires_at = campaign_mismatch.expires_at
        db.get(models.OrdemCheckout, 6002).campaign_reservation_expires_at = (
            expiry_mismatch.expires_at + timedelta(hours=1)
        )
        db.add_all((campaign_mismatch, null_snapshot, expiry_mismatch))

    order_ids = (6000, 6001, 6002)
    campaign_ids = (600, 601, 602, 603)
    before = _persisted_state(models, Session, order_ids, campaign_ids)
    for order_id in order_ids:
        db = Session()
        try:
            _expect_error(module, db, order_id=order_id)
            db.rollback()
        finally:
            db.close()
        assert _persisted_state(models, Session, order_ids, campaign_ids) == before


def _prove_external_rollback(module, models, Session):
    with Session.begin() as db:
        db.add(_offer(models, 400))
        db.add(_campaign(models, 400, 400, limit=1))
        db.add(_order(models, 4000, 400))

    before = _state(models, Session, (4000,))
    db = Session()
    try:
        result = _projection(module, _reserve(module, db, order_id=4000))
        db.flush()
        assert result["reservation_id"] is not None
        assert _snapshot(db.get(models.OrdemCheckout, 4000)) != (None,) * 5
        assert db.in_transaction()
        db.rollback()
    finally:
        db.close()
    assert _state(models, Session, (4000,)) == before


def _prove_same_order_concurrency(module, models, Session):
    from sqlalchemy import func, select

    order_id = 7000
    with Session.begin() as db:
        db.add(_offer(models, 700))
        db.add(_campaign(models, 700, 700, limit=2))
        db.add(_order(models, order_id, 700))

    barrier = Barrier(8)

    def _worker():
        db = Session()
        try:
            barrier.wait(timeout=10)
            try:
                projection = _projection(
                    module, _reserve(module, db, order_id=order_id)
                )
            except module.CheckoutOfferCampaignReservationError as error:
                db.rollback()
                return "error", error
            db.commit()
            return "success", projection
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = tuple(pool.map(lambda _index: _worker(), range(8)))

    successes = tuple(value for result, value in outcomes if result == "success")
    errors = tuple(value for result, value in outcomes if result == "error")
    assert len(successes) == 8
    assert errors == ()
    assert {projection["reservation_id"] for projection in successes} == {
        successes[0]["reservation_id"]
    }
    assert {projection["reserved_at"] for projection in successes} == {
        successes[0]["reserved_at"]
    }
    assert {projection["expires_at"] for projection in successes} == {
        successes[0]["expires_at"]
    }

    with Session() as db:
        reservations = tuple(
            db.scalars(
                select(models.CheckoutOfferCampaignReservation).where(
                    models.CheckoutOfferCampaignReservation.ordem_id == order_id
                )
            )
        )
        assert len(reservations) == 1
        reservation = reservations[0]
        assert reservation.id == successes[0]["reservation_id"]
        assert reservation.reserved_at == successes[0]["reserved_at"]
        assert reservation.expires_at == successes[0]["expires_at"]
        live = db.scalar(
            select(func.count())
            .select_from(models.CheckoutOfferCampaignReservation)
            .where(
                models.CheckoutOfferCampaignReservation.campaign_id == 700,
                (
                    (models.CheckoutOfferCampaignReservation.estado == "confirmed")
                    | (
                        (
                            models.CheckoutOfferCampaignReservation.estado
                            == "reserved"
                        )
                        & (
                            models.CheckoutOfferCampaignReservation.expires_at
                            > func.current_timestamp()
                        )
                    )
                ),
            )
        )
        total = db.scalar(
            select(func.count())
            .select_from(models.CheckoutOfferCampaignReservation)
            .where(
                models.CheckoutOfferCampaignReservation.campaign_id == 700
            )
        )
        order = db.get(models.OrdemCheckout, order_id)
        assert _snapshot(order) == (
            700,
            "campaign-700",
            4,
            2,
            reservation.expires_at,
        )
    assert (live, total) == (1, 1)


def _prove_concurrency(module, models, Session):
    from sqlalchemy import func, select

    order_ids = tuple(range(5000, 5008))
    with Session.begin() as db:
        db.add(_offer(models, 500))
        db.add(_campaign(models, 500, 500, limit=3))
        db.add_all(_order(models, order_id, 500) for order_id in order_ids)

    barrier = Barrier(8)

    def _worker(order_id):
        db = Session()
        try:
            barrier.wait(timeout=10)
            try:
                projection = _projection(
                    module, _reserve(module, db, order_id=order_id)
                )
            except module.CheckoutOfferCampaignReservationError as error:
                assert str(error) == _ERROR_MESSAGE
                db.rollback()
                return "error", order_id
            db.commit()
            return "success", projection["ordem_id"]
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = tuple(pool.map(_worker, order_ids))
    successes = {order_id for result, order_id in outcomes if result == "success"}
    errors = {order_id for result, order_id in outcomes if result == "error"}
    assert len(successes) == 3
    assert len(errors) == 5
    assert successes | errors == set(order_ids)

    with Session() as db:
        now = datetime.utcnow()
        live = db.scalar(
            select(func.count())
            .select_from(models.CheckoutOfferCampaignReservation)
            .where(
                models.CheckoutOfferCampaignReservation.campaign_id == 500,
                (
                    (models.CheckoutOfferCampaignReservation.estado == "confirmed")
                    | (
                        (models.CheckoutOfferCampaignReservation.estado == "reserved")
                        & (models.CheckoutOfferCampaignReservation.expires_at > now)
                    )
                ),
            )
        )
        snapshotted = db.scalar(
            select(func.count())
            .select_from(models.OrdemCheckout)
            .where(
                models.OrdemCheckout.id.in_(order_ids),
                models.OrdemCheckout.campaign_id == 500,
            )
        )
        total = db.scalar(
            select(func.count())
            .select_from(models.CheckoutOfferCampaignReservation)
            .where(models.CheckoutOfferCampaignReservation.campaign_id == 500)
        )
    assert (live, total, snapshotted) == (3, 3, 3)


def test_payments_checkout_offer_campaign_atomic_reservation_contract_red():
    reservation = import_module("app.services.checkout_offer_campaign_reservation")

    from sqlalchemy.orm import sessionmaker

    from app import models

    _assert_structure(reservation)
    with _postgresql(models) as engine:
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        _seed_principals(models, Session)
        _prove_no_active_campaign(reservation, models, Session)
        _prove_eligibility_and_opaque_errors(reservation, models, Session)
        _prove_capacity_semantics(reservation, models, Session)
        _prove_ttl_idempotency_retired_and_lifecycle(reservation, models, Session)
        _prove_persisted_contradictions_fail_closed(reservation, models, Session)
        _prove_external_rollback(reservation, models, Session)
        _prove_same_order_concurrency(reservation, models, Session)
        _prove_concurrency(reservation, models, Session)
