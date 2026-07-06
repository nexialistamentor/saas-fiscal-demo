"""J12 — contrato HTTP para GET /dashboard/alertas/grafico/{empresa_id}."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Empresa, User
from app.security import get_usuario_atual, tenant_empresa


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    u.role = "user"
    return u


def _mock_empresa():
    e = MagicMock(spec=Empresa)
    e.id = 1
    e.user_id = 1
    return e


class _QueryGraficoFake:
    def filter(self, *_a, **_k): return self
    def all(self):
        return [
            SimpleNamespace(nivel="critico", empresa_id=1),
            SimpleNamespace(nivel="critico", empresa_id=1),
            SimpleNamespace(nivel="alto", empresa_id=1),
            SimpleNamespace(nivel="medio", empresa_id=1),
        ]


class _DBGraficoFake:
    def query(self, *_a, **_k): return _QueryGraficoFake()


def _override_get_db():
    yield _DBGraficoFake()


def test_j12_grafico_alertas_retorna_200_com_contrato():
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/grafico/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "empresa_id": 1,
        "grafico_alertas": {
            "critico": 2,
            "alto": 1,
            "medio": 1,
        },
    }


def test_j12_grafico_alertas_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/alertas/grafico/1")
    assert res.status_code == 401


def test_j12_grafico_alertas_empresa_alheia_retorna_403():
    app.dependency_overrides[get_usuario_atual] = _mock_user

    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")

    app.dependency_overrides[tenant_empresa] = _empresa_403

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/grafico/99")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
