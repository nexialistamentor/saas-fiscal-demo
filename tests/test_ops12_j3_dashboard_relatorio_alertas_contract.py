"""J3 — contrato HTTP para GET /dashboard/relatorio/{id}/alertas."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.dashboard_router as dashboard_router
from app.database import get_db
from app.main import app
from app.models import AlertaFiscal, RelatorioAnalise, User
from app.security import get_usuario_atual

_fake_rel = SimpleNamespace(id=1, empresa_id=1, tempo_execucao=1.5)
_fake_alerta = SimpleNamespace(
    id=10, agente="AgenteST", tipo="ICMS_ST",
    descricao="ST divergente", nivel="alto",
    criado_em=datetime(2026, 1, 20, 8, 0, 0),
)


class _QueryFake:
    def __init__(self, rel_found, alertas):
        self._rel_found = rel_found
        self._alertas = alertas
        self.filter_called = False
        self.filter_args = None
        self.order_by_called = False
        self.first_called = False
        self.all_called = False

    def filter(self, *args, **_k):
        self.filter_called = True
        self.filter_args = args
        return self

    def order_by(self, *_a, **_k):
        self.order_by_called = True
        return self

    def first(self):
        self.first_called = True
        return _fake_rel if self._rel_found else None

    def all(self):
        self.all_called = True
        return self._alertas


class _DBFake:
    def __init__(self, rel_found=True, alertas=None):
        self._rel_found = rel_found
        self._alertas = alertas or []
        self.query_instances = []
        self.query_models = []

    def query(self, *args, **_k):
        self.query_models.append(args[0] if args else None)
        q = _QueryFake(self._rel_found, self._alertas)
        self.query_instances.append(q)
        return q


_db_state = None


def _override_db(rel_found=True, alertas=None):
    def _inner():
        global _db_state
        _db_state = _DBFake(rel_found, alertas)
        yield _db_state
    return _inner


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    u.role = "user"
    return u


def test_j3_alertas_por_relatorio_retorna_200_com_contrato(monkeypatch):
    global _db_state
    _db_state = None
    access_calls = []

    monkeypatch.setattr(
        dashboard_router, "verificar_acesso_relatorio",
        lambda rel, u, db: access_calls.append((rel, u, db))
    )
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel_found=True, alertas=[_fake_alerta])

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1/alertas")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "relatorio_id": 1,
        "tempo_processamento_segundos": 1.5,
        "total_alertas": 1,
        "alertas": [
            {
                "id": 10,
                "agente": "AgenteST",
                "tipo": "ICMS_ST",
                "descricao": "ST divergente",
                "nivel": "alto",
                "data": "2026-01-20T08:00:00",
            }
        ],
    }
    assert _db_state is not None
    assert len(_db_state.query_instances) == 2
    assert _db_state.query_models[0] is RelatorioAnalise
    assert _db_state.query_models[1] is AlertaFiscal

    rel_query = _db_state.query_instances[0]
    assert rel_query.filter_called is True
    assert rel_query.first_called is True
    assert len(rel_query.filter_args) == 1

    alertas_query = _db_state.query_instances[1]
    assert alertas_query.filter_called is True
    assert alertas_query.order_by_called is True
    assert alertas_query.all_called is True
    assert len(alertas_query.filter_args) == 2

    assert len(access_calls) == 1
    assert access_calls[0][0] is _fake_rel
    assert access_calls[0][1].id == 1
    assert access_calls[0][2] is _db_state


def test_j3_alertas_relatorio_inexistente_retorna_404(monkeypatch):
    monkeypatch.setattr(dashboard_router, "verificar_acesso_relatorio", lambda *_a: None)
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel_found=False)

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/999/alertas")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json() == {"detail": "Relatório não encontrado"}


def test_j3_alertas_acesso_negado_retorna_403(monkeypatch):
    global _db_state
    _db_state = None

    monkeypatch.setattr(
        dashboard_router, "verificar_acesso_relatorio",
        lambda *_a, **_k: (_ for _ in ()).throw(HTTPException(status_code=403, detail="Acesso negado"))
    )
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel_found=True)

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1/alertas")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
    assert _db_state is not None
    assert len(_db_state.query_instances) == 1
    assert _db_state.query_models[0] is RelatorioAnalise


def test_j3_alertas_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/relatorio/1/alertas")
    assert res.status_code == 401
