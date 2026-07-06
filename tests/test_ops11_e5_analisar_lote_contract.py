"""E5 — contrato HTTP para POST /lote/analisar-lote."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.routes.lote_router as lote_router
from app.main import app
from app.models import User
from app.security import get_usuario_atual

_XML_BYTES = b"<NFeProc><NFe></NFe></NFeProc>"


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


async def _fake_validar_upload_xml(file):
    return _XML_BYTES


def _xml_file(nome="nota.xml"):
    return ("files", (nome, _XML_BYTES, "application/xml"))


def test_e5_analisar_lote_xml_valido_retorna_200(monkeypatch):
    captured = []

    def fake_add_task(self, func, *args, **kwargs):
        captured.append((func, args, kwargs))

    monkeypatch.setattr(lote_router, "validar_upload_xml", _fake_validar_upload_xml)
    monkeypatch.setattr(lote_router.BackgroundTasks, "add_task", fake_add_task)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    try:
        with TestClient(app) as c:
            res = c.post("/lote/analisar-lote", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()

    # UUID válido
    job_id = body["job_id"]
    uuid.UUID(job_id)

    # body exacto — sem campos extra
    assert body == {
        "job_id": job_id,
        "status": "pending",
        "total_arquivos": 1,
    }

    # job em memória
    assert job_id in lote_router.jobs
    j = lote_router.jobs[job_id]
    assert j["owner_id"] == 1
    assert j["status"] == "pending"
    assert j["progress"] == 0
    assert j["processed_files"] == 0
    assert j["total_files"] == 1
    assert j["resultados"] is None
    assert j["error"] is None

    # background task com argumentos exactos
    assert len(captured) == 1
    func, args, kwargs = captured[0]
    assert func is lote_router.processar_lote
    assert len(args) == 2
    assert args[0] == job_id
    assert args[1] == [_XML_BYTES]
    assert kwargs == {}


def test_e5_analisar_lote_21_ficheiros_retorna_400(monkeypatch):
    monkeypatch.setattr(lote_router, "validar_upload_xml", _fake_validar_upload_xml)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    try:
        with TestClient(app) as c:
            res = c.post(
                "/lote/analisar-lote",
                files=[_xml_file(f"nota{i}.xml") for i in range(21)],
            )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 400
    assert res.json() == {"detail": "Máximo de 20 arquivos por lote."}
    assert len(lote_router.jobs) == 0


def test_e5_analisar_lote_servidor_ocupado_retorna_503(monkeypatch):
    import time
    for i in range(100):
        lote_router.jobs[str(i)] = {"created_at": time.time(), "owner_id": 1}

    captured = []

    def fake_add_task(self, func, *args, **kwargs):
        captured.append(True)

    monkeypatch.setattr(lote_router, "validar_upload_xml", _fake_validar_upload_xml)
    monkeypatch.setattr(lote_router.BackgroundTasks, "add_task", fake_add_task)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)

    try:
        with TestClient(app) as c:
            res = c.post("/lote/analisar-lote", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 503
    assert res.json() == {"detail": "Servidor ocupado, tente novamente em alguns minutos."}
    assert len(captured) == 0


def test_e5_analisar_lote_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.post("/lote/analisar-lote", files=[_xml_file()])
    assert res.status_code == 401


def test_e5_analisar_lote_sem_ficheiros_retorna_422():
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    try:
        with TestClient(app) as c:
            res = c.post("/lote/analisar-lote")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422
