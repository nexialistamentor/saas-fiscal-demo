"""Contrato RED do consumo atomico de checkout offer grants."""

import ast
import socket
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from importlib import import_module
from inspect import getsource
from pathlib import Path
from threading import Barrier
from unittest.mock import patch


_ROOT = Path(__file__).resolve().parents[1]
_CAPABILITY = "document.extract"
_RESULT_FIELDS = (
    "grant_id",
    "user_id",
    "empresa_id",
    "capability",
    "idempotency_key",
    "request_fingerprint",
    "units",
    "usage_before",
    "usage_after",
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
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine

    suffix = uuid.uuid4().hex[:12]
    container = f"mp8d2-grant-usage-{suffix}"
    database = f"mp8d2_{suffix}"
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
                "mission=MEI-MP8D2-ATOMIC-GRANT-USAGE",
                "-e",
                "POSTGRES_USER=mp8d2",
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
                    "mp8d2",
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

        url = (
            f"postgresql+psycopg2://mp8d2:{password}"
            f"@127.0.0.1:{port}/{database}"
        )
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={
                "options": "-c lock_timeout=5000 -c statement_timeout=20000"
            },
        )

        base_tables = (
            models.Plano.__table__,
            models.User.__table__,
            models.Empresa.__table__,
            models.CheckoutOffer.__table__,
            models.CheckoutOfferCapability.__table__,
            models.CheckoutOfferCampaign.__table__,
            models.OrdemCheckout.__table__,
            models.OrdemCheckoutCapability.__table__,
            models.DocumentoIngerido.__table__,
        )
        with engine.begin() as connection:
            models.Base.metadata.create_all(connection, tables=base_tables)
            for module_name in (
                "migrations.versions.0047_one_time_offer_grants",
                "migrations.versions.0048_checkout_offer_grant_consumption_ledger",
            ):
                migration = import_module(module_name)
                original_op = migration.op
                try:
                    migration.op = Operations(MigrationContext.configure(connection))
                    migration.upgrade()
                finally:
                    migration.op = original_op

        assert engine.dialect.name == "postgresql"
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        _run_docker(["docker", "rm", "--force", container])


def _order(models, spec):
    order = models.OrdemCheckout(
        id=spec["order_id"],
        user_id=spec["user_id"],
        empresa_id=spec["empresa_id"],
        plano_id=None,
        offer_id=7,
        offer_code="document-one-time-company",
        contract_version=3,
        vertical="document",
        commercial_model="one_time",
        subject_type="company",
        subject_id=spec["empresa_id"],
        valor=Decimal("79.50"),
        moeda="BRL",
        estado=spec["order_state"],
        idempotency_key=f"mp8d2-order-{spec['order_id']}",
        payment_id=(
            f"mp8d2-payment-{spec['order_id']}"
            if spec["order_state"] == "paid"
            else None
        ),
        billing_period=None,
        usage_unit="document",
        usage_limit=spec["usage_limit"],
    )
    order.capabilities = [
        models.OrdemCheckoutCapability(codigo=code)
        for code in spec["capabilities"]
    ]
    grant = models.CheckoutOfferGrant(
        id=spec["grant_id"],
        usage_unit="document",
        usage_limit=spec["usage_limit"],
        usage_consumed=spec["usage_consumed"],
        estado=spec["grant_state"],
        created_at=spec["created_at"],
    )
    grant.capabilities = [
        models.CheckoutOfferGrantCapability(codigo=code)
        for code in spec["capabilities"]
    ]
    order.grant = grant
    return order


def _seed(models, Session):
    day_1 = datetime(2026, 1, 1, 12, 0, 0)
    day_2 = datetime(2026, 1, 2, 12, 0, 0)
    day_3 = datetime(2026, 1, 3, 12, 0, 0)
    day_4 = datetime(2026, 1, 4, 12, 0, 0)
    specs = (
        # Mais antigos, mas inelegiveis por cada regra independente.
        dict(order_id=101, grant_id=101, user_id=41, empresa_id=301,
             order_state="pending", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_1,
             capabilities=(_CAPABILITY,)),
        dict(order_id=102, grant_id=102, user_id=41, empresa_id=301,
             order_state="paid", grant_state="revoked", usage_limit=1,
             usage_consumed=0, created_at=day_1,
             capabilities=(_CAPABILITY,)),
        dict(order_id=103, grant_id=103, user_id=41, empresa_id=301,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_1,
             capabilities=("document.validate",)),
        dict(order_id=104, grant_id=104, user_id=41, empresa_id=301,
             order_state="paid", grant_state="exhausted", usage_limit=1,
             usage_consumed=1, created_at=day_1,
             capabilities=(_CAPABILITY,)),
        dict(order_id=105, grant_id=105, user_id=42, empresa_id=302,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_1,
             capabilities=(_CAPABILITY,)),
        dict(order_id=106, grant_id=106, user_id=41, empresa_id=303,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_1,
             capabilities=(_CAPABILITY,)),
        # Elegiveis: created_at e depois id definem a ordem total.
        dict(order_id=110, grant_id=110, user_id=41, empresa_id=301,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_2,
             capabilities=(_CAPABILITY,)),
        dict(order_id=120, grant_id=120, user_id=41, empresa_id=301,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_3,
             capabilities=(_CAPABILITY,)),
        dict(order_id=121, grant_id=121, user_id=41, empresa_id=301,
             order_state="paid", grant_state="active", usage_limit=2,
             usage_consumed=0, created_at=day_3,
             capabilities=(_CAPABILITY,)),
        # Alvo exclusivo da prova de rollback do boundary de ingestao.
        dict(order_id=130, grant_id=130, user_id=41, empresa_id=301,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_4,
             capabilities=(_CAPABILITY,)),
        # Escopo isolado para duas sessoes PostgreSQL concorrentes.
        dict(order_id=140, grant_id=140, user_id=41, empresa_id=304,
             order_state="paid", grant_state="active", usage_limit=1,
             usage_consumed=0, created_at=day_1,
             capabilities=(_CAPABILITY,)),
    )

    with Session.begin() as db:
        db.add_all(
            (
                models.User(
                    id=41,
                    email="mp8d2-owner@example.invalid",
                    hashed_password="hash-de-teste",
                ),
                models.User(
                    id=42,
                    email="mp8d2-other@example.invalid",
                    hashed_password="hash-de-teste",
                ),
                models.Empresa(id=301, razao_social="Empresa alvo", user_id=41),
                models.Empresa(id=302, razao_social="Empresa alheia", user_id=42),
                models.Empresa(id=303, razao_social="Outra empresa", user_id=41),
                models.Empresa(id=304, razao_social="Empresa concorrente", user_id=41),
            )
        )
        offer = models.CheckoutOffer(
            id=7,
            codigo="document-one-time-company",
            nome_publico="Documentos avulsos",
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("79.50"),
            billing_period=None,
            usage_unit="document",
            usage_limit=2,
            contract_version=3,
        )
        offer.capabilities = [
            models.CheckoutOfferCapability(codigo=_CAPABILITY),
            models.CheckoutOfferCapability(codigo="document.validate"),
        ]
        db.add(offer)
        db.flush()
        db.add_all(_order(models, spec) for spec in specs)


def _projection(result):
    return {field: getattr(result, field) for field in _RESULT_FIELDS}


def _consume(
    usage,
    db,
    *,
    user_id=41,
    empresa_id=301,
    capability=_CAPABILITY,
    idempotency_key,
    request_fingerprint,
):
    return usage.CheckoutOfferGrantUsage(db).consumir(
        user_id=user_id,
        empresa_id=empresa_id,
        capability=capability,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )


def _committed_consume(usage, Session, **arguments):
    with Session.begin() as db:
        return _projection(_consume(usage, db, **arguments))


def _state(models, Session):
    from sqlalchemy import func, select

    with Session() as db:
        grants = {
            grant.id: (grant.usage_consumed, grant.estado)
            for grant in db.scalars(
                select(models.CheckoutOfferGrant).order_by(
                    models.CheckoutOfferGrant.id
                )
            ).all()
        }
        consumptions = tuple(
            tuple(getattr(row, field) for field in _RESULT_FIELDS)
            for row in db.scalars(
                select(models.CheckoutOfferGrantConsumption).order_by(
                    models.CheckoutOfferGrantConsumption.id
                )
            ).all()
        )
        documents = db.scalar(
            select(func.count()).select_from(models.DocumentoIngerido)
        )
    return {
        "grants": grants,
        "consumptions": consumptions,
        "documents": documents,
    }


def _assert_rejected(usage, Session, **arguments):
    import pytest

    db = Session()
    try:
        with pytest.raises(usage.CheckoutOfferGrantUsageError):
            _consume(usage, db, **arguments)
        db.rollback()
    finally:
        db.close()


def _assert_caller_owns_transaction(usage):
    tree = ast.parse(getsource(usage))
    forbidden = {"close", "commit", "rollback"}
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert calls.isdisjoint(forbidden)


def test_payments_checkout_offer_grant_usage_contract_red():
    usage = import_module("app.services.checkout_offer_grant_usage")

    from sqlalchemy import func, select
    from sqlalchemy.orm import sessionmaker

    from app import models

    assert usage.__file__ is not None
    assert Path(usage.__file__).resolve() == (
        _ROOT / "app" / "services" / "checkout_offer_grant_usage.py"
    ).resolve()
    assert hasattr(usage, "CheckoutOfferGrantUsage")
    assert hasattr(usage, "CheckoutOfferGrantUsageError")
    _assert_caller_owns_transaction(usage)

    with _postgresql(models) as engine:
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        _seed(models, Session)

        # Capability unica e escopo user/empresa sao sempre fail-closed.
        invalid_calls = (
            dict(user_id=41, empresa_id=301, capability="document.validate"),
            dict(user_id=41, empresa_id=301, capability="Document.extract"),
            dict(user_id=42, empresa_id=301, capability=_CAPABILITY),
            dict(user_id=41, empresa_id=302, capability=_CAPABILITY),
        )
        for number, invalid in enumerate(invalid_calls, start=1):
            before = _state(models, Session)
            _assert_rejected(
                usage,
                Session,
                **invalid,
                idempotency_key=f"mp8d2-invalid-{number}",
                request_fingerprint=f"opaque:v1:invalid-{number}",
            )
            assert _state(models, Session) == before

        # Grants inelegiveis sao ignorados; os elegiveis usam FIFO total.
        fifo = tuple(
            _committed_consume(
                usage,
                Session,
                idempotency_key=f"mp8d2-fifo-{number}",
                request_fingerprint=f"opaque:v1:fifo-{number}",
            )
            for number in range(1, 4)
        )
        assert [item["grant_id"] for item in fifo] == [110, 120, 121]
        assert [
            (item["units"], item["usage_before"], item["usage_after"])
            for item in fifo
        ] == [(1, 0, 1), (1, 0, 1), (1, 0, 1)]
        assert all(
            item["user_id"] == 41
            and item["empresa_id"] == 301
            and item["capability"] == _CAPABILITY
            for item in fifo
        )
        after_fifo = _state(models, Session)
        assert {
            grant_id: after_fifo["grants"][grant_id]
            for grant_id in (101, 102, 103, 104, 105, 106)
        } == {
            101: (0, "active"),
            102: (0, "revoked"),
            103: (0, "active"),
            104: (1, "exhausted"),
            105: (0, "active"),
            106: (0, "active"),
        }
        assert after_fifo["grants"][110] == (1, "exhausted")
        assert after_fifo["grants"][120] == (1, "exhausted")
        assert after_fifo["grants"][121] == (1, "active")
        assert len(after_fifo["consumptions"]) == 3

        # Replay convergente devolve o mesmo resultado e nao debita novamente.
        replay_before = _state(models, Session)
        replay = _committed_consume(
            usage,
            Session,
            idempotency_key="mp8d2-fifo-3",
            request_fingerprint="opaque:v1:fifo-3",
        )
        assert replay == fifo[2]
        assert _state(models, Session) == replay_before

        # A mesma chave com outra operacao/fingerprint nunca converge.
        divergent_before = _state(models, Session)
        _assert_rejected(
            usage,
            Session,
            idempotency_key="mp8d2-fifo-3",
            request_fingerprint="opaque:v2:divergent-operation",
        )
        assert _state(models, Session) == divergent_before

        # A ultima unidade esgota o grant exatamente na fronteira zero.
        last_unit = _committed_consume(
            usage,
            Session,
            idempotency_key="mp8d2-fifo-4",
            request_fingerprint="opaque:v1:fifo-4",
        )
        assert (
            last_unit["grant_id"],
            last_unit["units"],
            last_unit["usage_before"],
            last_unit["usage_after"],
        ) == (121, 1, 1, 2)
        after_last_unit = _state(models, Session)
        assert after_last_unit["grants"][121] == (2, "exhausted")
        assert len(after_last_unit["consumptions"]) == 4

        # O boundary que persiste DocumentoIngerido conserva commit/rollback.
        rollback_before = _state(models, Session)
        db = Session()
        try:
            db.add(
                models.DocumentoIngerido(
                    user_id=41,
                    empresa_id=301,
                    conteudo_sha256="a" * 64,
                    evidencia_em=datetime(2026, 1, 5, 12, 0, 0),
                    versao_pipeline="mp8d2-test",
                    tipo_documento="nfe",
                    score_confianca=1.0,
                    decisao="aceitar",
                    requereu_ocr=False,
                    validado_humano=False,
                    tamanho_bytes=1,
                )
            )
            db.flush()
            with (
                patch.object(db, "commit", wraps=db.commit) as commit_spy,
                patch.object(db, "close", wraps=db.close) as close_spy,
            ):
                rolled_back = _projection(
                    _consume(
                        usage,
                        db,
                        idempotency_key="mp8d2-boundary-rollback",
                        request_fingerprint="opaque:v1:boundary-rollback",
                    )
                )
                db.flush()
                assert rolled_back["grant_id"] == 130
                assert commit_spy.call_count == 0
                assert close_spy.call_count == 0
                assert db.in_transaction()
                assert db.scalar(
                    select(func.count()).select_from(models.DocumentoIngerido)
                ) == 1
                assert db.scalar(
                    select(func.count())
                    .select_from(models.CheckoutOfferGrantConsumption)
                    .where(
                        models.CheckoutOfferGrantConsumption.idempotency_key
                        == "mp8d2-boundary-rollback"
                    )
                ) == 1
                grant = db.get(models.CheckoutOfferGrant, 130)
                assert (grant.usage_consumed, grant.estado) == (1, "exhausted")
            db.rollback()
        finally:
            if db.in_transaction():
                db.rollback()
            db.close()
        assert _state(models, Session) == rollback_before

        # Duas sessoes reais disputam o unico saldo enquanto a vencedora
        # ainda mantem a sua transacao aberta.
        barrier = Barrier(2)

        def _contender():
            contender_db = Session()
            try:
                barrier.wait(timeout=5)
                try:
                    result = _projection(
                        _consume(
                            usage,
                            contender_db,
                            user_id=41,
                            empresa_id=304,
                            idempotency_key="mp8d2-race-b",
                            request_fingerprint="opaque:v1:race-b",
                        )
                    )
                except usage.CheckoutOfferGrantUsageError:
                    contender_db.rollback()
                    return "rejected", None
                contender_db.commit()
                return "consumed", result
            finally:
                contender_db.close()

        winner_db = Session()
        try:
            winner = _projection(
                _consume(
                    usage,
                    winner_db,
                    user_id=41,
                    empresa_id=304,
                    idempotency_key="mp8d2-race-a",
                    request_fingerprint="opaque:v1:race-a",
                )
            )
            winner_db.flush()
            assert winner_db.in_transaction()

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_contender)
                barrier.wait(timeout=5)
                try:
                    contender_outcome = future.result(timeout=0.25)
                except FutureTimeout:
                    contender_outcome = None
                winner_db.commit()
                if contender_outcome is None:
                    contender_outcome = future.result(timeout=10)
        finally:
            if winner_db.in_transaction():
                winner_db.rollback()
            winner_db.close()

        assert (
            winner["grant_id"],
            winner["units"],
            winner["usage_before"],
            winner["usage_after"],
        ) == (140, 1, 0, 1)
        assert contender_outcome == ("rejected", None)

        final_state = _state(models, Session)
        assert final_state["grants"][140] == (1, "exhausted")
        assert all(consumed >= 0 for consumed, _state_name in final_state["grants"].values())
        race_events = tuple(
            row
            for row in final_state["consumptions"]
            if row[_RESULT_FIELDS.index("idempotency_key")].startswith("mp8d2-race-")
        )
        assert len(race_events) == 1
        assert race_events[0][_RESULT_FIELDS.index("idempotency_key")] == "mp8d2-race-a"
        assert len(final_state["consumptions"]) == 5
        assert final_state["documents"] == 0
