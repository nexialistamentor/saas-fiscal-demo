"""E4 — contrato HTTP para DELETE /fiscal/analise/cancelar/{job_id}."""

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


def test_e4_cancelar_sync_job_retorna_200_nao_aplicavel():
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.delete(f"/fiscal/analise/cancelar/{fiscal_router._SYNC_JOB}")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "job_id": fiscal_router._SYNC_JOB,
        "status": "não aplicável (análise síncrona)",
    }


def test_e4_cancelar_job_inexistente_retorna_404():
    from rq.exceptions import NoSuchJobError

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.side_effect = NoSuchJobError("not found")
        try:
            with TestClient(app) as c:
                res = c.delete("/fiscal/analise/cancelar/job-inexistente-999")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json()["detail"] == "Job não encontrado"


def test_e4_cancelar_job_outro_utilizador_retorna_403():
    fake_job = SimpleNamespace(
        id="job-alheio-123",
        meta={"owner_id": 99},
        is_finished=False,
        cancel=lambda: None,
    )

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.return_value = fake_job
        try:
            with TestClient(app) as c:
                res = c.delete("/fiscal/analise/cancelar/job-alheio-123")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json()["detail"] == "Acesso negado a este job"


def test_e4_cancelar_job_proprio_retorna_200_cancelado():
    cancelled = []
    fake_job = SimpleNamespace(
        id="job-proprio-456",
        meta={"owner_id": 1},
        is_finished=False,
        cancel=lambda: cancelled.append(True),
    )

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.return_value = fake_job
        try:
            with TestClient(app) as c:
                res = c.delete("/fiscal/analise/cancelar/job-proprio-456")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"job_id": "job-proprio-456", "status": "cancelado"}
    assert cancelled == [True]


def test_e4_cancelar_job_proprio_ja_finalizado_retorna_200_sem_cancelar():
    cancelled = []
    fake_job = SimpleNamespace(
        id="job-finalizado-789",
        meta={"owner_id": 1},
        is_finished=True,
        cancel=lambda: cancelled.append(True),
    )

    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    with patch("app.routes.fiscal_router.Job") as mock_job_cls:
        mock_job_cls.fetch.return_value = fake_job
        try:
            with TestClient(app) as c:
                res = c.delete("/fiscal/analise/cancelar/job-finalizado-789")
        finally:
            app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"status": "job já finalizado"}
    assert cancelled == []


def test_e4_cancelar_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.delete("/fiscal/analise/cancelar/qualquer-job")
    assert res.status_code == 401
