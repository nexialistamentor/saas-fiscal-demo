"""I18 — contrato HTTP para GET /inteligencia/complexidade-tributaria/{empresa_id}."""

from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.inteligencia_router as inteligencia_router
from app.database import get_db
from app.main import app
from app.models import Empresa
from app.security import tenant_empresa


class _DBFake:
    pass


_db_state = None


def _override_db():
    global _db_state
    _db_state = _DBFake()
    yield _db_state


def _mock_empresa():
    e = MagicMock(spec=Empresa)
    e.id = 1
    return e


def test_i18_complexidade_tributaria_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_svc(db, empresa_id):
        calls.append((db, empresa_id))
        return [{"ncm": "12345678", "nivel_complexidade": "alto", "score_complexidade": 88.0}]

    monkeypatch.setattr(inteligencia_router, "calcular_complexidade_tributaria", fake_svc)
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/complexidade-tributaria/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == [{"ncm": "12345678", "nivel_complexidade": "alto", "score_complexidade": 88.0}]
    assert len(calls) == 1
    assert calls[0][0] is _db_state
    assert calls[0][1] == 1


def test_i18_complexidade_tributaria_lista_vazia(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_svc(db, empresa_id):
        calls.append((db, empresa_id))
        return []

    monkeypatch.setattr(inteligencia_router, "calcular_complexidade_tributaria", fake_svc)
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/complexidade-tributaria/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == []
    assert len(calls) == 1
    assert calls[0][0] is _db_state
    assert calls[0][1] == 1


def test_i18_complexidade_tributaria_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/inteligencia/complexidade-tributaria/1")
    assert res.status_code == 401


def test_i18_complexidade_tributaria_empresa_alheia_retorna_403():
    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")
    app.dependency_overrides[tenant_empresa] = _empresa_403
    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/complexidade-tributaria/99")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
