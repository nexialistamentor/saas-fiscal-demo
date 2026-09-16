"""RED: falha de persistencia dentro de ``acquire()`` deve ser opaca."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.routes import relatorio_router
from app.security import get_usuario_atual


def test_acquire_persistence_error_returns_generic_503_and_rolls_back(monkeypatch):
    events = []

    class FakeDb:
        commit_calls = 0
        rollback_calls = 0

        def commit(self):
            self.commit_calls += 1
            events.append("commit")

        def rollback(self):
            self.rollback_calls += 1
            events.append("rollback")

    db = FakeDb()

    class FakeTaxReportAcquisition:
        def __init__(self, received_db):
            assert received_db is db

        def acquire(self, **kwargs):
            events.append("acquire")
            raise SQLAlchemyError("persistencia-interna-segredo")

    monkeypatch.setattr(
        relatorio_router,
        "TaxReportAcquisition",
        FakeTaxReportAcquisition,
    )
    app = FastAPI()
    app.include_router(relatorio_router.router, prefix="/relatorio")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(id=11)

    with TestClient(app) as client:
        response = client.post(
            "/relatorio/empresas/21/acquisitions",
            headers={"Idempotency-Key": "acquisition-http-db-error-001"},
            json={
                "relatorio_id": 501,
                "request_fingerprint": "a" * 64,
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Aquisição temporariamente indisponível."
    }
    assert db.rollback_calls == 1
    assert db.commit_calls == 0
    assert events == ["acquire", "rollback"]
    response_text = response.text.lower()
    for forbidden in (
        "persistencia-interna-segredo",
        "sqlalchemy",
        "grant",
        "consumption",
        "fingerprint",
    ):
        assert forbidden not in response_text
