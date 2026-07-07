"""I3 — contrato HTTP para GET /inteligencia/mapa-oportunidades/{empresa_id}."""

from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.inteligencia_router as inteligencia_router
from app.database import get_db
from app.main import app
from app.models import Empresa, User
from app.security import get_usuario_atual, tenant_empresa


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


def _mock_user(consulta_paga=True):
    u = MagicMock(spec=User)
    u.id = 1
    u.consulta_paga = consulta_paga
    return u


def test_i3_mapa_oportunidades_retorna_200_com_consulta_paga(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_svc(db, empresa_id):
        calls.append((db, empresa_id))
        return {"oportunidades": [{"ncm": "12345678", "valor": 500.0}]}

    monkeypatch.setattr(inteligencia_router, "gerar_mapa_oportunidades", fake_svc)
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(consulta_paga=True)

    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/mapa-oportunidades/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body == {
        "oportunidades": [{"ncm": "12345678", "valor": 500.0}],
        "consulta_paga": True,
    }
    assert len(calls) == 1
    assert calls[0][0] is _db_state
    assert calls[0][1] == 1


def test_i3_mapa_oportunidades_consulta_nao_paga(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_svc(db, empresa_id):
        calls.append((db, empresa_id))
        return {"oportunidades": []}

    monkeypatch.setattr(inteligencia_router, "gerar_mapa_oportunidades", fake_svc)
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(consulta_paga=False)

    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/mapa-oportunidades/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "oportunidades": [],
        "consulta_paga": False,
    }
    assert len(calls) == 1
    assert calls[0][0] is _db_state
    assert calls[0][1] == 1


def test_i3_mapa_oportunidades_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/inteligencia/mapa-oportunidades/1")
    assert res.status_code == 401


def test_i3_mapa_oportunidades_empresa_alheia_retorna_403():
    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")
    app.dependency_overrides[tenant_empresa] = _empresa_403
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()
    try:
        with TestClient(app) as c:
            res = c.get("/inteligencia/mapa-oportunidades/99")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
