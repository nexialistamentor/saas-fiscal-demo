"""J10/J11 — contrato HTTP para PATCH /dashboard/alertas/silenciar e /restaurar."""

from types import SimpleNamespace
from unittest.mock import MagicMock

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


def _make_db_fake(alerta_found=True, silenciado_inicial=False):
    alerta = (
        SimpleNamespace(
            id=1,
            empresa_id=1,
            silenciado=silenciado_inicial,
        )
        if alerta_found
        else None
    )
    state = SimpleNamespace(alerta=alerta, commits=0)

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return alerta

    class _DB:
        def query(self, *_args, **_kwargs):
            return _Query()

        def commit(self):
            state.commits += 1

    def _override():
        yield _DB()

    return _override, state


# ---------------------------------------------------------------------------
# J10 — silenciar
# ---------------------------------------------------------------------------

def test_j10_silenciar_alerta_retorna_200_e_marca_silenciado(monkeypatch):
    override_db, state = _make_db_fake(alerta_found=True, silenciado_inicial=False)

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(
        dashboard_router,
        "verificar_empresa_do_usuario",
        lambda *_args, **_kwargs: None,
    )

    try:
        with TestClient(app) as c:
            res = c.patch("/dashboard/alertas/silenciar/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"status": "alerta silenciado", "alerta_id": 1}
    assert state.alerta.silenciado is True
    assert state.commits == 1


def test_j10_silenciar_alerta_inexistente_retorna_404():
    override_db, state = _make_db_fake(alerta_found=False)

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as c:
            res = c.patch("/dashboard/alertas/silenciar/999")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json()["detail"] == "alerta não encontrado"
    assert state.commits == 0


def test_j10_silenciar_sem_auth_retorna_401():
    app.dependency_overrides.clear()

    with TestClient(app) as c:
        res = c.patch("/dashboard/alertas/silenciar/1")

    assert res.status_code == 401


def test_j10_silenciar_empresa_alheia_retorna_403(monkeypatch):
    override_db, state = _make_db_fake(alerta_found=True)

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = override_db

    def _bloquear_empresa_alheia(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="Acesso negado")

    monkeypatch.setattr(
        dashboard_router,
        "verificar_empresa_do_usuario",
        _bloquear_empresa_alheia,
    )

    try:
        with TestClient(app) as c:
            res = c.patch("/dashboard/alertas/silenciar/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert state.commits == 0


# ---------------------------------------------------------------------------
# J11 — restaurar
# ---------------------------------------------------------------------------

def test_j11_restaurar_alerta_retorna_200_e_remove_silenciado(monkeypatch):
    override_db, state = _make_db_fake(alerta_found=True, silenciado_inicial=True)

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(
        dashboard_router,
        "verificar_empresa_do_usuario",
        lambda *_args, **_kwargs: None,
    )

    try:
        with TestClient(app) as c:
            res = c.patch("/dashboard/alertas/restaurar/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"status": "alerta restaurado", "alerta_id": 1}
    assert state.alerta.silenciado is False
    assert state.commits == 1


def test_j11_restaurar_alerta_inexistente_retorna_404():
    override_db, state = _make_db_fake(alerta_found=False)

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as c:
            res = c.patch("/dashboard/alertas/restaurar/999")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json()["detail"] == "alerta não encontrado"
    assert state.commits == 0


def test_j11_restaurar_sem_auth_retorna_401():
    app.dependency_overrides.clear()

    with TestClient(app) as c:
        res = c.patch("/dashboard/alertas/restaurar/1")

    assert res.status_code == 401


def test_j11_restaurar_empresa_alheia_retorna_403(monkeypatch):
    override_db, state = _make_db_fake(alerta_found=True)

    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = override_db

    def _bloquear_empresa_alheia(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="Acesso negado")

    monkeypatch.setattr(
        dashboard_router,
        "verificar_empresa_do_usuario",
        _bloquear_empresa_alheia,
    )

    try:
        with TestClient(app) as c:
            res = c.patch("/dashboard/alertas/restaurar/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert state.commits == 0
