"""A4 — contrato HTTP para GET /system/metrics."""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.security import get_usuario_atual


def _make_user(role="admin"):
    mock = MagicMock()
    mock.role = role
    return mock


def test_a4_system_metrics_admin_retorna_200():
    app.dependency_overrides[get_usuario_atual] = lambda: _make_user("admin")
    try:
        with TestClient(app) as c:
            res = c.get("/system/metrics")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert "metricas_operacionais" in body
    assert "engines" in body
    assert "circuit_breaker" in body
    assert "cache" in body
    assert "alertas" in body


def test_a4_system_metrics_sem_auth_retorna_401():
    with TestClient(app) as c:
        res = c.get("/system/metrics")
    assert res.status_code == 401


def test_a4_system_metrics_role_user_retorna_403():
    app.dependency_overrides[get_usuario_atual] = lambda: _make_user("user")
    try:
        with TestClient(app) as c:
            res = c.get("/system/metrics")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
