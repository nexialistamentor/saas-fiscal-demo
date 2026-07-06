"""N2 — contrato HTTP para GET /estoque/divergencias."""

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


class _QueryDivergenciasFake:
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
                id=1, empresa_id=1, ncm="12345678",
                estoque_fiscal=100.0, estoque_erp=90.0,
                diferenca=10.0, risco_desvio="alto",
                created_at=None,
            ),
        ]


_query_state = None


class _DBFake:
    def query(self, *_a, **_k):
        global _query_state
        _query_state = _QueryDivergenciasFake()
        return _query_state


def _override_db():
    yield _DBFake()


def test_n2_divergencias_retorna_200_com_contrato():
    global _query_state
    _query_state = None

    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            res = c.get("/estoque/divergencias")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == [
        {
            "id": 1,
            "empresa_id": 1,
            "ncm": "12345678",
            "estoque_fiscal": 100.0,
            "estoque_erp": 90.0,
            "diferenca": 10.0,
            "risco_desvio": "alto",
            "created_at": None,
        }
    ]
    assert _query_state is not None
    assert _query_state.filter_called is True
    assert _query_state.order_by_called is True
    assert _query_state.limit_value == 100
    assert _query_state.all_called is True


def test_n2_divergencias_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/estoque/divergencias")
    assert res.status_code == 401


def test_n2_divergencias_empresa_alheia_retorna_403():
    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")

    app.dependency_overrides[tenant_empresa] = _empresa_403
    try:
        with TestClient(app) as c:
            res = c.get("/estoque/divergencias")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
