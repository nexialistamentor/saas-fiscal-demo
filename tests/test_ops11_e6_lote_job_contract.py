"""E6 — contrato HTTP para GET /lote/job/{job_id}."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.routes.lote_router as lote_router
from app.main import app
from app.models import User
from app.security import get_usuario_atual


def _mock_user(user_id=1):
    u = MagicMock(spec=User)
    u.id = user_id
    u.role = "user"
    return u


@pytest.fixture(autouse=True)
def _limpar_jobs():
    lote_router.jobs.clear()
    yield
    lote_router.jobs.clear()


def test_e6_consultar_job_inexistente_retorna_404():
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.get("/lote/job/job-que-nao-existe")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 404
    assert res.json() == {"detail": "Job não encontrado"}


def test_e6_consultar_job_outro_utilizador_retorna_403():
    lote_router.jobs["job-alheio"] = {
        "owner_id": 99, "status": "processing",
        "progress": 50, "processed_files": 1, "total_files": 2,
    }
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.get("/lote/job/job-alheio")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado a este job"}


def test_e6_consultar_job_processing_retorna_200_com_contrato():
    lote_router.jobs["job-proc"] = {
        "owner_id": 1, "status": "processing",
        "progress": 50, "processed_files": 1, "total_files": 2,
    }
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.get("/lote/job/job-proc")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {
        "status": "processing",
        "progress": 50,
        "processed_files": 1,
        "total_files": 2,
    }


def test_e6_consultar_job_completed_retorna_200_com_contrato():
    lote_router.jobs["job-done"] = {
        "owner_id": 1, "status": "completed", "progress": 100,
        "processed_files": 2, "total_files": 2,
        "resultados": [{"ok": True}, {"ok": True}],
        "duration_seconds": 3, "finished_at": 1700000000.0,
    }
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.get("/lote/job/job-done")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {
        "status": "completed",
        "progress": 100,
        "processed_files": 2,
        "total_files": 2,
        "resultados": [{"ok": True}, {"ok": True}],
        "duration_seconds": 3,
        "finished_at": 1700000000.0,
    }


def test_e6_consultar_job_failed_retorna_200_com_contrato():
    lote_router.jobs["job-fail"] = {
        "owner_id": 1, "status": "failed", "progress": 50,
        "processed_files": 1, "total_files": 2,
        "error": "XML inválido", "duration_seconds": 1, "finished_at": 1700000001.0,
    }
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.get("/lote/job/job-fail")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json() == {
        "status": "failed",
        "progress": 50,
        "processed_files": 1,
        "total_files": 2,
        "error": "XML inválido",
        "duration_seconds": 1,
        "finished_at": 1700000001.0,
    }


def test_e6_consultar_job_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/lote/job/qualquer-job")
    assert res.status_code == 401
