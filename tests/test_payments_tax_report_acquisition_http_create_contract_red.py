"""RED: criacao HTTP canonica de uma aquisicao ``tax.report``."""

from inspect import getsource
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.routes import relatorio_router
from app.security import get_usuario_atual
from app.services.tax_report_acquisition import TaxReportAcquisitionError


ROUTE_PATH = "/empresas/{empresa_id}/acquisitions"
REQUEST_PATH = "/relatorio/empresas/21/acquisitions"
VALID_BODY = {
    "relatorio_id": 501,
    "request_fingerprint": "a" * 64,
}
VALID_KEY = "acquisition-http-001"


def _route():
    matches = [
        route
        for route in relatorio_router.router.routes
        if getattr(route, "path", None) == ROUTE_PATH
        and "POST" in getattr(route, "methods", set())
    ]
    assert len(matches) == 1, (
        "rota canonica POST /relatorio/empresas/{empresa_id}/acquisitions "
        "ainda nao existe"
    )
    return matches[0]


class FakeDb:
    def __init__(self, events, *, commit_error=None):
        self.events = events
        self.commit_error = commit_error
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self):
        self.events.append("commit")
        self.commit_calls += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.events.append("rollback")
        self.rollback_calls += 1


def _client(db):
    app = FastAPI()
    app.include_router(relatorio_router.router, prefix="/relatorio")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(id=11)
    return TestClient(app)


def _post(client, *, body=None, key=VALID_KEY):
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post(
        REQUEST_PATH,
        headers=headers,
        json=VALID_BODY if body is None else body,
    )


def test_tax_report_acquisition_http_create_positive_contract_red(monkeypatch):
    _route()
    events = []
    db = FakeDb(events)
    calls = []

    class FakeTaxReportAcquisition:
        def __init__(self, received_db):
            assert received_db is db

        def acquire(self, **kwargs):
            events.append("acquire")
            calls.append(kwargs)
            return SimpleNamespace(id=601, relatorio_analise_id=501)

    monkeypatch.setattr(
        relatorio_router, "TaxReportAcquisition", FakeTaxReportAcquisition
    )
    with _client(db) as client:
        response = _post(client)

    assert response.status_code == 200
    assert response.json() == {
        "acquisition_id": 601,
        "relatorio_analise_id": 501,
    }
    assert set(response.json()) == {"acquisition_id", "relatorio_analise_id"}
    assert calls == [{
        "user_id": 11,
        "empresa_id": 21,
        "relatorio_id": 501,
        "idempotency_key": VALID_KEY,
        "request_fingerprint": "a" * 64,
    }]
    assert events == ["acquire", "commit"]
    assert db.commit_calls == 1
    assert db.rollback_calls == 0


def test_tax_report_acquisition_http_create_input_contract_red(monkeypatch):
    _route()
    calls = []
    db = FakeDb([])

    class FakeTaxReportAcquisition:
        def __init__(self, received_db):
            assert received_db is db

        def acquire(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id=601, relatorio_analise_id=501)

    monkeypatch.setattr(
        relatorio_router, "TaxReportAcquisition", FakeTaxReportAcquisition
    )
    invalid_bodies = [
        {"request_fingerprint": "a" * 64},
        {"relatorio_id": 501},
        {**VALID_BODY, "extra": "forbidden"},
        {**VALID_BODY, "relatorio_id": True},
        {**VALID_BODY, "relatorio_id": False},
        {**VALID_BODY, "relatorio_id": 0},
        {**VALID_BODY, "relatorio_id": -1},
        {**VALID_BODY, "request_fingerprint": "A" * 64},
        {**VALID_BODY, "request_fingerprint": "g" * 64},
        {**VALID_BODY, "request_fingerprint": "a" * 63},
        {**VALID_BODY, "request_fingerprint": "a" * 65},
    ]
    with _client(db) as client:
        for body in invalid_bodies:
            assert _post(client, body=body).status_code == 422

    assert calls == []
    assert db.commit_calls == 0
    assert db.rollback_calls == 0


def test_tax_report_acquisition_http_create_idempotency_header_contract_red(
    monkeypatch,
):
    _route()
    calls = []
    db = FakeDb([])

    class FakeTaxReportAcquisition:
        def __init__(self, received_db):
            assert received_db is db

        def acquire(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id=601, relatorio_analise_id=501)

    monkeypatch.setattr(
        relatorio_router, "TaxReportAcquisition", FakeTaxReportAcquisition
    )
    with _client(db) as client:
        assert _post(client, key=None).status_code == 422
        assert _post(client, key="").status_code == 422
        assert _post(client, key="a" * 256).status_code == 422
        assert _post(client, key="key\tcontrol").status_code == 422
        duplicate = client.post(
            REQUEST_PATH,
            headers=[
                ("Idempotency-Key", "first-key"),
                ("Idempotency-Key", "second-key"),
            ],
            json=VALID_BODY,
        )
        assert duplicate.status_code == 422

    assert calls == []
    assert db.commit_calls == 0
    assert db.rollback_calls == 0


def test_tax_report_acquisition_http_create_domain_error_contract_red(monkeypatch):
    _route()
    events = []
    db = FakeDb(events)

    class FakeTaxReportAcquisition:
        def __init__(self, received_db):
            assert received_db is db

        def acquire(self, **kwargs):
            events.append("acquire")
            raise TaxReportAcquisitionError(
                "grant_id=777 consumption_id=888 fingerprint=segredo"
            )

    monkeypatch.setattr(
        relatorio_router, "TaxReportAcquisition", FakeTaxReportAcquisition
    )
    with _client(db) as client:
        response = _post(client)

    assert response.status_code == 409
    assert response.json() == {"detail": "Aquisição indisponível."}
    assert events == ["acquire", "rollback"]
    assert db.commit_calls == 0
    assert db.rollback_calls == 1
    for secret in ("grant", "777", "consumption", "888", "fingerprint", "segredo"):
        assert secret not in response.text


def test_tax_report_acquisition_http_create_persistence_error_contract_red(
    monkeypatch,
):
    _route()
    events = []
    db = FakeDb(events, commit_error=SQLAlchemyError("persistencia-segredo"))

    class FakeTaxReportAcquisition:
        def __init__(self, received_db):
            assert received_db is db

        def acquire(self, **kwargs):
            events.append("acquire")
            return SimpleNamespace(id=601, relatorio_analise_id=501)

    monkeypatch.setattr(
        relatorio_router, "TaxReportAcquisition", FakeTaxReportAcquisition
    )
    with _client(db) as client:
        response = _post(client)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Aquisição temporariamente indisponível."
    }
    assert events == ["acquire", "commit", "rollback"]
    assert db.commit_calls == 1
    assert db.rollback_calls == 1
    assert "persistencia-segredo" not in response.text


def test_tax_report_acquisition_http_create_response_ids_are_positive_red(
    monkeypatch,
):
    _route()

    class FakeTaxReportAcquisition:
        def __init__(self, db):
            pass

        def acquire(self, **kwargs):
            return SimpleNamespace(id=True, relatorio_analise_id=0)

    monkeypatch.setattr(
        relatorio_router, "TaxReportAcquisition", FakeTaxReportAcquisition
    )
    with _client(FakeDb([])) as client:
        response = _post(client)

    assert response.status_code >= 500
    assert response.json() != {
        "acquisition_id": True,
        "relatorio_analise_id": 0,
    }


def test_tax_report_acquisition_http_create_route_and_authority_contract_red():
    route = _route()
    dependant = route.dependant
    assert [parameter.name for parameter in dependant.path_params] == ["empresa_id"]
    assert len(dependant.body_params) == 1
    assert len(dependant.header_params) == 1
    header = dependant.header_params[0]
    assert header.alias == "Idempotency-Key"
    assert header.required is True
    dependency_calls = {dependency.call for dependency in dependant.dependencies}
    assert dependency_calls == {get_usuario_atual, get_db}

    app = FastAPI()
    app.include_router(relatorio_router.router, prefix="/relatorio")
    operation = app.openapi()["paths"][REQUEST_PATH.replace("21", "{empresa_id}")][
        "post"
    ]
    header_schema = next(
        parameter["schema"]
        for parameter in operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert header_schema["minLength"] == 1
    assert header_schema["maxLength"] == 255
    assert header_schema["pattern"] == r"^[\x21-\x7e]+$"

    body_model = dependant.body_params[0].type_
    assert set(body_model.model_fields) == {"relatorio_id", "request_fingerprint"}
    assert body_model.model_config.get("extra") == "forbid"

    source = getsource(route.endpoint)
    assert "TaxReportAcquisition" in source
    for forbidden in (
        "_pagamento_confirmado",
        "consulta_paga",
        ".pago",
        "Entitlement",
        "CheckoutOfferGrant",
        "CheckoutOfferGrantConsumption",
        "OrdemCheckout",
        "RelatorioAnalise",
        "verificar_empresa_do_usuario",
        "executar_analise",
        "executar_e_registrar_analise_xml",
    ):
        assert forbidden not in source
