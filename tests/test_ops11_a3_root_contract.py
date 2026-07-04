"""A3 — contrato HTTP para GET / (API activa / heartbeat)."""

from fastapi.testclient import TestClient

from app.main import app


def test_a3_root_retorna_200_com_status_api_ativa(client):
    res = client.get("/")

    assert res.status_code == 200
    body = res.json()

    assert body == {"status": "API Fiscal Ativa"}


def test_a3_root_acessivel_sem_autenticacao():
    with TestClient(app) as c:
        res = c.get("/")

    assert res.status_code == 200
    assert res.json()["status"] == "API Fiscal Ativa"
