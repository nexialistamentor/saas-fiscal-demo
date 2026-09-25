"""Contrato RED: entrada HTTP da intencao duravel MEI por competencia.

Nao cria ordem, pagamento, grant, binding ou autorizacao SERPRO.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.routes import imposto_router
from app.security import get_usuario_atual
from app.services.mei_competencia_checkout_intent import (
    MeiCompetenciaCheckoutIntentError,
)


ROUTE_PATH = "/mei/{empresa_id}/checkout-intents"
REQUEST_PATH = "/imposto/mei/21/checkout-intents"
KEY = "mei-21-202609-checkout-001"
BODY = {
    "competencia": "202609",
    "offer_code": "mei-das-one-time-company",
}


def _route():
    return next(
        (
            route
            for route in imposto_router.router.routes
            if isinstance(route, APIRoute)
            and route.path == ROUTE_PATH
            and route.methods == {"POST"}
        ),
        None,
    )


class _DB:
    def __init__(self, commit_error=None):
        self.events = []
        self.commit_error = commit_error

    def commit(self):
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.events.append("rollback")


def _client(db):
    app = FastAPI()
    app.include_router(imposto_router.router, prefix="/imposto")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_usuario_atual] = (
        lambda: SimpleNamespace(id=11)
    )
    return TestClient(app)


def _post(client, body=None, headers=None):
    if headers is None:
        headers = {"Idempotency-Key": KEY}
    return client.post(
        REQUEST_PATH,
        json=BODY if body is None else body,
        headers=headers,
    )


def test_http_mei_intent_route_authentication_and_schema_red():
    route = _route()
    assert route is not None, f"ausente POST {ROUTE_PATH}"

    assert route.status_code == 204
    assert any(
        dependency.call is get_usuario_atual
        for dependency in route.dependant.dependencies
    ), "a identidade deve vir da autenticacao"

    assert any(
        dependency.call is get_db
        for dependency in route.dependant.dependencies
    ), "a rota deve receber sessao transacional"

    fields = route.body_field.type_.model_fields
    assert tuple(fields) == ("competencia", "offer_code")
    assert route.body_field.type_.model_config.get("extra") == "forbid"

    headers = route.dependant.header_params
    assert len(headers) == 1
    assert headers[0].alias == "Idempotency-Key"

    operation = FastAPI()
    operation.include_router(imposto_router.router, prefix="/imposto")
    header = next(
        item for item in operation.openapi()["paths"][
            "/imposto" + ROUTE_PATH
        ]["post"]["parameters"]
        if item["name"] == "Idempotency-Key"
        and item["in"] == "header"
    )
    assert header["required"] is True


def test_http_mei_intent_persists_exact_identity_and_commits_red(monkeypatch):
    db = _DB()
    received = []

    class FakeIntent:
        def __init__(self, session):
            assert session is db

        def persist(self, **kwargs):
            db.events.append("persist")
            received.append(kwargs)
            return SimpleNamespace(intent_id=51)

    monkeypatch.setattr(
        imposto_router, "MeiCompetenciaCheckoutIntent", FakeIntent
    )

    with _client(db) as client:
        response = _post(client)

    assert response.status_code == 204
    assert response.content == b""
    assert received == [{
        "user_id": 11,
        "empresa_id": 21,
        "competencia": "202609",
        "offer_code": "mei-das-one-time-company",
        "checkout_idempotency_key": KEY,
    }]
    assert db.events == ["persist", "commit"]


@pytest.mark.parametrize(
    "body",
    [
        {"competencia": "202609"},
        {"offer_code": "mei-das-one-time-company"},
        {**BODY, "user_id": 99},
        {**BODY, "empresa_id": 99},
        {**BODY, "capability": "mei.das"},
        {**BODY, "competencia": "202613"},
        {**BODY, "competencia": "202600"},
        {**BODY, "competencia": "2026-09"},
        {**BODY, "competencia": 202609},
        {**BODY, "offer_code": "MEI DAS"},
    ],
)
def test_http_mei_intent_rejects_invalid_body_before_service_red(
    monkeypatch, body
):
    db = _DB()

    class ForbiddenIntent:
        def __init__(self, session):
            pytest.fail("entrada invalida alcancou o servico")

    monkeypatch.setattr(
        imposto_router, "MeiCompetenciaCheckoutIntent", ForbiddenIntent
    )

    with _client(db) as client:
        response = _post(client, body=body)

    assert response.status_code == 422
    assert db.events == []


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Idempotency-Key": "chave com espacos"},
        {"Idempotency-Key": "x" * 256},
        [("Idempotency-Key", KEY), ("Idempotency-Key", KEY)],
    ],
)
def test_http_mei_intent_rejects_invalid_or_duplicate_key_red(
    monkeypatch, headers
):
    db = _DB()

    class ForbiddenIntent:
        def __init__(self, session):
            pytest.fail("chave invalida alcancou o servico")

    monkeypatch.setattr(
        imposto_router, "MeiCompetenciaCheckoutIntent", ForbiddenIntent
    )

    with _client(db) as client:
        response = _post(client, headers=headers)

    assert response.status_code == 422
    assert db.events == []


@pytest.mark.parametrize(
    "failure, expected_status, expected_events",
    [
        ("domain", 409, ["persist", "rollback"]),
        ("storage", 503, ["persist", "rollback"]),
        ("commit", 503, ["persist", "commit", "rollback"]),
    ],
)
def test_http_mei_intent_fail_closed_transaction_red(
    monkeypatch, failure, expected_status, expected_events
):
    db = _DB(
        commit_error=SQLAlchemyError("falha simulada")
        if failure == "commit"
        else None
    )

    class FakeIntent:
        def __init__(self, session):
            assert session is db

        def persist(self, **kwargs):
            db.events.append("persist")
            if failure == "domain":
                raise MeiCompetenciaCheckoutIntentError()
            if failure == "storage":
                raise SQLAlchemyError("falha simulada")
            return SimpleNamespace(intent_id=51)

    monkeypatch.setattr(
        imposto_router, "MeiCompetenciaCheckoutIntent", FakeIntent
    )

    with _client(db) as client:
        response = _post(client)

    assert response.status_code == expected_status
    assert db.events == expected_events


def test_http_mei_intent_has_no_payment_or_serpro_side_effects_red():
    route = _route()
    assert route is not None, f"ausente POST {ROUTE_PATH}"

    source = inspect.getsource(route.endpoint)

    assert "MeiCompetenciaCheckoutIntent" in source
    assert ".persist(" in source

    for forbidden in (
        "CheckoutOfferOrderComposer",
        "CheckoutOfferGrant(",
        "MeiCompetenciaAuthorityBinding(",
        "CheckoutOfferOneTimeConfirmer",
        "_get_serpro_pgmei_client",
        "compose_serpro_pgmei",
        "MercadoPago",
    ):
        assert forbidden not in source, (
            f"efeito proibido na rota de intencao: {forbidden}"
        )
