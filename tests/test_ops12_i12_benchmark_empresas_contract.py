"""I12 — contrato HTTP para GET /inteligencia/benchmark-empresas."""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

import app.routers.inteligencia_router as inteligencia_router
from app.database import get_db
from app.main import app
from app.models import User
from app.security import get_usuario_atual


class _DBFake:
    pass


_db_state = None


def _override_db():
    global _db_state
    _db_state = _DBFake()
    yield _db_state


def _mock_user_com_empresas(empresa_ids):
    u = MagicMock(spec=User)
    u.id = 1
    empresas = []
    for eid in empresa_ids:
        e = MagicMock()
        e.id = eid
        empresas.append(e)
    u.empresas = empresas
    return u


def test_i12_benchmark_empresas_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_svc(db, empresa_ids):
        calls.append((db, empresa_ids))
        return [{"empresa_id": 1, "score": 80.0}, {"empresa_id": 2, "score": 60.0}]

    monkeypatch.setattr(inteligencia_router, "gerar_benchmark_empresas", fake_svc)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user_com_empresas([1, 2])
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/benchmark-empresas")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == [{"empresa_id": 1, "score": 80.0}, {"empresa_id": 2, "score": 60.0}]
    assert len(calls) == 1
    assert calls[0][0] is _db_state
    assert calls[0][1] == [1, 2]


def test_i12_benchmark_empresas_sem_empresas_retorna_200_vazio(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_svc(db, empresa_ids):
        calls.append((db, empresa_ids))
        return []

    monkeypatch.setattr(inteligencia_router, "gerar_benchmark_empresas", fake_svc)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user_com_empresas([])
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/benchmark-empresas")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == []
    assert len(calls) == 1
    assert calls[0][0] is _db_state
    assert calls[0][1] == []


def test_i12_benchmark_empresas_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/inteligencia/benchmark-empresas")
    assert res.status_code == 401
