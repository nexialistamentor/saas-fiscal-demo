"""J9 — contrato HTTP para GET /dashboard/alertas/agentes/{empresa_id}."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Empresa, User
from app.security import get_usuario_atual, tenant_empresa


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    u.role = "user"
    return u


def _mock_empresa():
    e = MagicMock(spec=Empresa)
    e.id = 1
    e.user_id = 1
    return e


class _QueryAlertasAgenteFake:
    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return [
            SimpleNamespace(agente="AgenteST", empresa_id=1),
            SimpleNamespace(agente="AgenteST", empresa_id=1),
            SimpleNamespace(agente="AgenteIVA", empresa_id=1),
            SimpleNamespace(agente=None, empresa_id=1),
        ]


class _DBAgenteFake:
    def query(self, *_args, **_kwargs):
        return _QueryAlertasAgenteFake()


def _override_get_db():
    yield _DBAgenteFake()


def test_j9_alertas_por_agente_retorna_200_com_contrato():
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[tenant_empresa] = _mock_empresa
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/agentes/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body == {
        "empresa_id": 1,
        "alertas_por_agente": {
            "AgenteST": 2,
            "AgenteIVA": 1,
            "nao_definido": 1,
        },
    }


def test_j9_alertas_por_agente_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/alertas/agentes/1")
    assert res.status_code == 401


def test_j9_alertas_por_agente_empresa_alheia_retorna_403():
    app.dependency_overrides[get_usuario_atual] = _mock_user

    def _empresa_403():
        raise HTTPException(status_code=403, detail="Acesso negado")

    app.dependency_overrides[tenant_empresa] = _empresa_403

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/alertas/agentes/99")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
