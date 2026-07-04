"""J8 — contrato HTTP para GET /dashboard/alertas/timeline/{empresa_id}."""

from datetime import datetime
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


class _QueryAlertasTimelineFake:
    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return [
            SimpleNamespace(
                criado_em=datetime(2026, 1, 10, 9, 30, 0),
                nivel="alto",
                tipo="ICMS_ST",
            ),
            SimpleNamespace(
                criado_em=datetime(2026, 1, 11, 10, 45, 0),
                nivel="medio",
                tipo="QUALIDADE_DADOS",
            ),
        ]


class _DBTimelineFake:
    def query(self, *_args, **_kwargs):
        return _QueryAlertasTimelineFake()


def _override_get_db():
    yield _DBTimelineFake()


def test_j8_timeline_alertas_retorna_200_com_contrato_lista():
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/timeline/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()

    assert body == [
        {
            "data": "2026-01-10T09:30:00",
            "nivel": "alto",
            "tipo": "ICMS_ST",
        },
        {
            "data": "2026-01-11T10:45:00",
            "nivel": "medio",
            "tipo": "QUALIDADE_DADOS",
        },
    ]


def test_j8_timeline_alertas_sem_auth_retorna_401():
    app.dependency_overrides.clear()

    with TestClient(app) as c:
        res = c.get("/dashboard/alertas/timeline/1")

    assert res.status_code == 401


def test_j8_timeline_alertas_empresa_alheia_retorna_403():
    app.dependency_overrides[get_usuario_atual] = _mock_user

    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")

    app.dependency_overrides[tenant_empresa] = _empresa_403

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/timeline/99")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
