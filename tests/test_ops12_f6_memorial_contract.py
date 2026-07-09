"""F6 — contrato HTTP para GET /relatorio/memorial/{relatorio_id}."""

from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
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


def _mock_user(user_id=1):
    u = MagicMock(spec=User)
    u.id = user_id
    return u


def _contexto_fake(user_id=1, pago=True):
    return {
        "relatorio": {"user_id": user_id, "pago": pago, "id": 1},
        "alertas": [],
        "oportunidades": [],
    }


# ---------------------------------------------------------------------------
# F6.1 — 200 memorial acessível (pago)
# ---------------------------------------------------------------------------

def test_f6_memorial_retorna_200_com_contexto(monkeypatch):
    global _db_state
    _db_state = None
    contexto_calls = []
    marcar_calls = []

    def fake_coletar(db, relatorio_id):
        contexto_calls.append((db, relatorio_id))
        return _contexto_fake(user_id=1, pago=True)

    def fake_marcar(db, relatorio_id):
        marcar_calls.append((db, relatorio_id))

    monkeypatch.setattr(relatorio_router, "coletar_contexto_memorial", fake_coletar)
    monkeypatch.setattr(relatorio_router, "marcar_memorial_gerado", fake_marcar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/memorial/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == _contexto_fake(user_id=1, pago=True)
    assert len(contexto_calls) == 1
    assert contexto_calls[0][0] is _db_state
    assert contexto_calls[0][1] == 1
    assert len(marcar_calls) == 1
    assert marcar_calls[0][0] is _db_state
    assert marcar_calls[0][1] == 1


# ---------------------------------------------------------------------------
# F6.2 — 404 relatório inexistente
# ---------------------------------------------------------------------------

def test_f6_memorial_inexistente_retorna_404(monkeypatch):
    global _db_state
    _db_state = None
    contexto_calls = []
    marcar_calls = []

    def fake_coletar(db, relatorio_id):
        contexto_calls.append((db, relatorio_id))
        return None

    def fake_marcar(db, relatorio_id):
        marcar_calls.append((db, relatorio_id))

    monkeypatch.setattr(relatorio_router, "coletar_contexto_memorial", fake_coletar)
    monkeypatch.setattr(relatorio_router, "marcar_memorial_gerado", fake_marcar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/memorial/999")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json() == {"detail": "Relatório não encontrado."}
    assert len(contexto_calls) == 1
    assert contexto_calls[0][0] is _db_state
    assert contexto_calls[0][1] == 999
    assert marcar_calls == []


# ---------------------------------------------------------------------------
# F6.3 — 403 relatório de outro utilizador
# ---------------------------------------------------------------------------

def test_f6_memorial_outro_utilizador_retorna_403(monkeypatch):
    global _db_state
    _db_state = None
    contexto_calls = []
    marcar_calls = []

    def fake_coletar(db, relatorio_id):
        contexto_calls.append((db, relatorio_id))
        return _contexto_fake(user_id=99, pago=True)

    def fake_marcar(db, relatorio_id):
        marcar_calls.append((db, relatorio_id))

    monkeypatch.setattr(relatorio_router, "coletar_contexto_memorial", fake_coletar)
    monkeypatch.setattr(relatorio_router, "marcar_memorial_gerado", fake_marcar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/memorial/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado."}
    assert len(contexto_calls) == 1
    assert contexto_calls[0][0] is _db_state
    assert contexto_calls[0][1] == 1
    assert marcar_calls == []


# ---------------------------------------------------------------------------
# F6.4 — 402 relatório não pago
# ---------------------------------------------------------------------------

def test_f6_memorial_nao_pago_retorna_402(monkeypatch):
    global _db_state
    _db_state = None
    contexto_calls = []
    marcar_calls = []

    def fake_coletar(db, relatorio_id):
        contexto_calls.append((db, relatorio_id))
        return _contexto_fake(user_id=1, pago=False)

    def fake_marcar(db, relatorio_id):
        marcar_calls.append((db, relatorio_id))

    monkeypatch.setattr(relatorio_router, "coletar_contexto_memorial", fake_coletar)
    monkeypatch.setattr(relatorio_router, "marcar_memorial_gerado", fake_marcar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/memorial/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 402
    assert res.json() == {"detail": "Pagamento necessário para aceder ao memorial."}
    assert len(contexto_calls) == 1
    assert contexto_calls[0][0] is _db_state
    assert contexto_calls[0][1] == 1
    assert marcar_calls == []


# ---------------------------------------------------------------------------
# F6.5 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_f6_memorial_sem_auth_retorna_401(monkeypatch):
    def fail_coletar(*_a, **_k):
        raise AssertionError("coletar_contexto_memorial não devia ser chamado sem auth")

    def fail_marcar(*_a, **_k):
        raise AssertionError("marcar_memorial_gerado não devia ser chamado sem auth")

    monkeypatch.setattr(relatorio_router, "coletar_contexto_memorial", fail_coletar)
    monkeypatch.setattr(relatorio_router, "marcar_memorial_gerado", fail_marcar)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/memorial/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
