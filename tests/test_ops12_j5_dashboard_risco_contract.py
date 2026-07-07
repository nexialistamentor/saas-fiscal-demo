"""J5 — contrato HTTP para GET /dashboard/risco/{empresa_id}."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import AlertaFiscal, Empresa
from app.security import tenant_empresa


def _mock_empresa(empresa_id=1):
    e = MagicMock(spec=Empresa)
    e.id = empresa_id
    return e


class _QueryFake:
    def __init__(self, alertas):
        self._alertas = alertas
        self.filter_called = False
        self.filter_args = None
        self.all_called = False

    def filter(self, *args, **_k):
        self.filter_called = True
        self.filter_args = args
        return self

    def all(self):
        self.all_called = True
        return self._alertas


class _DBFake:
    def __init__(self, alertas):
        self._alertas = alertas
        self.query_instances = []
        self.query_models = []

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


def _alerta(nivel):
    return SimpleNamespace(nivel=nivel, empresa_id=1)


def _assert_query():
    assert _db_state is not None
    assert _db_state.query_models[0] is AlertaFiscal
    q = _db_state.query_instances[0]
    assert q.filter_called is True
    assert q.all_called is True
    assert len(q.filter_args) == 1


def test_j5_score_risco_sem_alertas_retorna_0():
    global _db_state
    _db_state = None
    app.dependency_overrides[tenant_empresa] = lambda: _mock_empresa(1)
    app.dependency_overrides[get_db] = _override_db([])
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/risco/1")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {"empresa_id": 1, "score_risco": 0}
    _assert_query()


def test_j5_score_risco_calcula_por_nivel():
    global _db_state
    _db_state = None
    app.dependency_overrides[tenant_empresa] = lambda: _mock_empresa(1)
    app.dependency_overrides[get_db] = _override_db([
        _alerta("critico"), _alerta("alto"), _alerta("medio"),
    ])
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/risco/1")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {"empresa_id": 1, "score_risco": 70}
    _assert_query()


def test_j5_score_risco_limitado_a_100():
    global _db_state
    _db_state = None
    alertas = [_alerta("critico")] * 3  # 120 → cap 100
    app.dependency_overrides[tenant_empresa] = lambda: _mock_empresa(1)
    app.dependency_overrides[get_db] = _override_db(alertas)
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/risco/1")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {"empresa_id": 1, "score_risco": 100}
    _assert_query()


def test_j5_score_risco_ignora_nivel_nao_mapeado():
    global _db_state
    _db_state = None
    alertas = [_alerta("baixo"), _alerta("info"), _alerta(None)]
    app.dependency_overrides[tenant_empresa] = lambda: _mock_empresa(1)
    app.dependency_overrides[get_db] = _override_db(alertas)
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/risco/1")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {"empresa_id": 1, "score_risco": 0}
    _assert_query()


def test_j5_score_risco_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/risco/1")
    assert res.status_code == 401


def test_j5_score_risco_empresa_alheia_retorna_403():
    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")
    app.dependency_overrides[tenant_empresa] = _empresa_403
    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/risco/99")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
