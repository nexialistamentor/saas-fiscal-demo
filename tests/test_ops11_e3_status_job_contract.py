"""E3 — contrato HTTP para GET /fiscal/analise/status/{job_id}."""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.routes.fiscal_router as fiscal_router
from app.main import app
from app.models import User
from app.security import get_usuario_atual


def _mock_user(user_id=1):
    u = MagicMock(spec=User)
    u.id = user_id
    u.role = "user"
    return u


@pytest.fixture(autouse=True)
def _mock_redis_queue_module(monkeypatch):
    fake_module = types.ModuleType("app.queue.redis_queue")
    fake_module.redis_conn = MagicMock()
    fake_module.analysis_queue = MagicMock()
    monkeypatch.setitem(sys.modules, "app.queue.redis_queue", fake_module)


def test_e3_status_sync_job_retorna_200_finished():
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.get(f"/fiscal/analise/status/{fiscal_router._SYNC_JOB}")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "finished"
    assert body["job_id"] == fiscal_router._SYNC_JOB
    assert body["result"]["tem_resultado"] is False


def test_e3_status_job_inexistente_retorna_404():
    from rq.exceptions import NoSuchJobError

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.side_effect = NoSuchJobError("not found")
        try:
            with TestClient(app) as c:
                res = c.get("/fiscal/analise/status/job-inexistente-999")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json()["detail"] == "Job não encontrado"


def test_e3_status_job_outro_utilizador_retorna_403():
    fake_job = SimpleNamespace(
        id="job-alheio-123",
        meta={"owner_id": 99},
        result=None,
        get_status=lambda: "started",
    )

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.return_value = fake_job
        try:
            with TestClient(app) as c:
                res = c.get("/fiscal/analise/status/job-alheio-123")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json()["detail"] == "Acesso negado a este job"


def test_e3_status_job_proprio_retorna_200_com_contrato():
    fake_job = SimpleNamespace(
        id="job-proprio-456",
        meta={"owner_id": 1},
        result={"relatorio_id": 42},
        get_status=lambda: "finished",
    )

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.return_value = fake_job
        try:
            with TestClient(app) as c:
                res = c.get("/fiscal/analise/status/job-proprio-456")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "job_id": "job-proprio-456",
        "status": "finished",
        "result": {
            "relatorio_id": 42,
            "tem_resultado": True,
        },
    }


def test_e3_status_job_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/fiscal/analise/status/qualquer-job")
    assert res.status_code == 401
