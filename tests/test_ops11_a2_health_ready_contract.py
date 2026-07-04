"""A2 — contrato HTTP para GET /health/ready."""

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db


def test_a2_health_ready_retorna_200_com_bd_ok(client):
    res = client.get("/health/ready")

    assert res.status_code == 200
    body = res.json()

    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] in {"ok", "not_configured", "unavailable"}


def test_a2_health_ready_retorna_503_com_bd_indisponivel():
    class DBIndisponivel:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db indisponivel em teste")

    def override_get_db():
        yield DBIndisponivel()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            res = c.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 503
    body = res.json()

    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["redis"] in {"ok", "not_configured", "unavailable"}
