"""J2 — contrato HTTP para GET /dashboard/relatorio/{relatorio_id}."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.dashboard_router as dashboard_router
from app.database import get_db
from app.main import app
from app.models import User
from app.security import get_usuario_atual


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    u.role = "user"
    return u


_fake_rel = SimpleNamespace(
    id=1, empresa_id=1, analysis_type="empresa_tax",
    xml_chave="NFe999", status="ok", tempo_execucao=2.3,
    total_alertas=3, score_resultante=90.0,
    created_at=datetime(2026, 1, 15, 10, 0, 0),
)


class _QueryRelFake:
    def __init__(self, found=True):
        self._found = found
        self.filter_called = False
        self.first_called = False

    def filter(self, *_a, **_k):
        self.filter_called = True
        return self

    def first(self):
        self.first_called = True
        return _fake_rel if self._found else None


_query_state = None


class _DBFake:
    def __init__(self, found=True):
        self._found = found

    def query(self, *_a, **_k):
        global _query_state
        _query_state = _QueryRelFake(self._found)
        return _query_state


def _override_db(found=True):
    def _inner():
        yield _DBFake(found)
    return _inner


def test_j2_detalhe_relatorio_retorna_200_com_contrato(monkeypatch):
    global _query_state
    _query_state = None
    access_calls = []

    def fake_verificar_acesso(rel, usuario, db):
        access_calls.append((rel, usuario, db))

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(found=True)
    monkeypatch.setattr(dashboard_router, "verificar_acesso_relatorio", fake_verificar_acesso)

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "id": 1,
        "empresa_id": 1,
        "analysis_type": "empresa_tax",
        "xml_chave": "NFe999",
        "status": "ok",
        "tempo_execucao": 2.3,
        "tempo_processamento_segundos": 2.3,
        "total_alertas": 3,
        "score_resultante": 90.0,
        "created_at": "2026-01-15T10:00:00",
    }
    assert _query_state is not None
    assert _query_state.filter_called is True
    assert _query_state.first_called is True
    assert len(access_calls) == 1
    assert access_calls[0][0] is _fake_rel
    assert access_calls[0][1].id == 1


def test_j2_detalhe_relatorio_inexistente_retorna_404(monkeypatch):
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(found=False)
    monkeypatch.setattr(dashboard_router, "verificar_acesso_relatorio", lambda *_a, **_k: None)

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/999")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json() == {"detail": "Relatório não encontrado"}


def test_j2_detalhe_relatorio_acesso_negado_retorna_403(monkeypatch):
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(found=True)
    monkeypatch.setattr(
        dashboard_router, "verificar_acesso_relatorio",
        lambda *_a, **_k: (_ for _ in ()).throw(HTTPException(status_code=403, detail="Acesso negado"))
    )

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}


def test_j2_detalhe_relatorio_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/relatorio/1")
    assert res.status_code == 401
