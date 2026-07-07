"""J7 — contrato HTTP para GET /dashboard/alertas/{empresa_id}."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import AlertaFiscal, Empresa
from app.security import tenant_empresa

_fake_alerta = SimpleNamespace(
    id=5, agente="AgenteST", tipo="ICMS_ST",
    descricao="ST divergente", nivel="alto",
    criado_em=datetime(2026, 2, 1, 8, 0, 0),
)


def _mock_empresa():
    e = MagicMock(spec=Empresa)
    e.id = 1
    return e


class _QueryFake:
    def __init__(self, alertas):
        self._alertas = alertas
        self.filter_called = False
        self.filter_args = None
        self.order_by_called = False
        self.all_called = False

    def filter(self, *args, **_k):
        self.filter_called = True
        self.filter_args = args
        return self

    def order_by(self, *_a, **_k):
        self.order_by_called = True
        return self

    def all(self):
        self.all_called = True
        return self._alertas


class _DBFake:
    def __init__(self, alertas):
        self.query_instances = []
        self.query_models = []
        self._alertas = alertas

    def query(self, *args, **_k):
        self.query_models.append(args[0] if args else None)
        q = _QueryFake(self._alertas)
        self.query_instances.append(q)
        return q


_db_state = None


def _override_db(alertas=None):
    def _inner():
        global _db_state
        _db_state = _DBFake(alertas or [])
        yield _db_state
    return _inner


def _assert_query():
    assert _db_state is not None
    assert len(_db_state.query_instances) == 1
    assert len(_db_state.query_models) == 1
    assert _db_state.query_models[0] is AlertaFiscal
    q = _db_state.query_instances[0]
    assert q.filter_called is True
    assert q.order_by_called is True
    assert q.all_called is True
    assert len(q.filter_args) == 2  # empresa_id + silenciado != True


def test_j7_listar_alertas_retorna_200_com_contrato():
    global _db_state
    _db_state = None
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db([_fake_alerta])
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/1")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == [
        {
            "id": 5, "agente": "AgenteST", "tipo": "ICMS_ST",
            "descricao": "ST divergente", "nivel": "alto",
            "data": "2026-02-01T08:00:00",
        }
    ]
    _assert_query()


def test_j7_listar_alertas_lista_vazia():
    global _db_state
    _db_state = None
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db([])
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/1")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == []
    _assert_query()


def test_j7_listar_alertas_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/alertas/1")
    assert res.status_code == 401


def test_j7_listar_alertas_empresa_alheia_retorna_403():
    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")
    app.dependency_overrides[tenant_empresa] = _empresa_403
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/99")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
