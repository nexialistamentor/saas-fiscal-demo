"""J1 — contrato HTTP para GET /dashboard/analises/{empresa_id}."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Empresa
from app.security import tenant_empresa


def _mock_empresa():
    e = MagicMock(spec=Empresa)
    e.id = 1
    e.user_id = 1
    return e


class _QueryAnaliseFake:
    def __init__(self):
        self.filter_called = False
        self.order_by_called = False
        self.limit_value = None
        self.all_called = False

    def filter(self, *_a, **_k):
        self.filter_called = True
        return self

    def order_by(self, *_a, **_k):
        self.order_by_called = True
        return self

    def limit(self, n):
        self.limit_value = n
        return self

    def all(self):
        self.all_called = True
        return [
            SimpleNamespace(
                id=1, xml_chave="NFe123", status="ok",
                tempo_execucao=1.5, total_alertas=2,
                score_resultante=85.0, created_at=datetime(2026, 1, 10, 9, 0, 0),
            ),
        ]


_query_state = None


class _DBFake:
    def query(self, *_a, **_k):
        global _query_state
        _query_state = _QueryAnaliseFake()
        return _query_state


def _override_db():
    yield _DBFake()


def test_j1_dashboard_analises_retorna_200_com_contrato():
    global _query_state
    _query_state = None

    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/analises/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == [
        {
            "id": 1,
            "xml_chave": "NFe123",
            "status": "ok",
            "tempo_execucao": 1.5,
            "total_alertas": 2,
            "score": 85.0,
            "data": "2026-01-10T09:00:00",
        }
    ]
    assert _query_state is not None
    assert _query_state.filter_called is True
    assert _query_state.order_by_called is True
    assert _query_state.limit_value == 50
    assert _query_state.all_called is True


def test_j1_dashboard_analises_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/analises/1")
    assert res.status_code == 401


def test_j1_dashboard_analises_empresa_alheia_retorna_403():
    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")

    app.dependency_overrides[tenant_empresa] = _empresa_403
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/analises/99")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
