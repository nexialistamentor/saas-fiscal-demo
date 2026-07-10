"""E2 — contrato HTTP para POST /fiscal/analisar-xml."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.fiscal_router as fiscal_router
from app.database import get_db
from app.main import app
from app.models import Empresa, User
from app.security import get_usuario_atual

_XML_BYTES = b"<NFeProc><NFe></NFe></NFeProc>"
_ANALISE_FAKE = {"insights": [], "score": 80.0}


class _QueryFake:
    def __init__(self, empresa):
        self._empresa = empresa
        self.filter_called = False
        self.first_called = False

    def filter(self, *_a, **_k):
        self.filter_called = True
        return self

    def first(self):
        self.first_called = True
        return self._empresa


class _DBFake:
    def __init__(self, empresa=None):
        self._empresa = empresa
        self.query_model = None
        self.query_instance = None

    def query(self, model):
        self.query_model = model
        self.query_instance = _QueryFake(self._empresa)
        return self.query_instance


_db_state = None


def _override_db(empresa=None):
    def _inner():
        global _db_state
        _db_state = _DBFake(empresa)
        yield _db_state
    return _inner


def _mock_user(user_id=1):
    u = MagicMock(spec=User)
    u.id = user_id
    return u


def _xml_file():
    return ("file", ("nota.xml", _XML_BYTES, "application/xml"))


# ---------------------------------------------------------------------------
# E2.1 — 200 com empresa_id → _enqueue_or_run_sync
# ---------------------------------------------------------------------------

def test_e2_analisar_xml_com_empresa_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    validar_calls = []
    verificar_calls = []
    enqueue_calls = []

    async def fake_validar(file):
        validar_calls.append(file)
        return _XML_BYTES

    def fake_verificar(empresa_id, usuario_atual, db):
        verificar_calls.append((empresa_id, usuario_atual, db))

    def fake_enqueue(conteudo, empresa_id, owner_id):
        enqueue_calls.append((conteudo, empresa_id, owner_id))
        return {"job_id": "job-abc-123"}

    def fail_executar(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado com empresa_id")

    emp = SimpleNamespace(id=10, user_id=10)
    monkeypatch.setattr(fiscal_router, "validar_upload_xml", fake_validar)
    monkeypatch.setattr(fiscal_router, "verificar_empresa_do_usuario", fake_verificar)
    monkeypatch.setattr(fiscal_router, "_enqueue_or_run_sync", fake_enqueue)
    monkeypatch.setattr(fiscal_router, "executar_analise_xml", fail_executar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db(empresa=emp)

    try:
        with TestClient(app) as c:
            res = c.post("/fiscal/analisar-xml?empresa_id=10", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"job_id": "job-abc-123"}
    assert len(validar_calls) == 1
    assert len(verificar_calls) == 1
    assert verificar_calls[0][0] == 10
    assert verificar_calls[0][1].id == 1
    assert verificar_calls[0][2] is _db_state
    assert len(enqueue_calls) == 1
    assert enqueue_calls[0][0] == _XML_BYTES
    assert enqueue_calls[0][1] == 10
    assert enqueue_calls[0][2] == 1
    assert _db_state.query_model is Empresa
    assert _db_state.query_instance.filter_called is True
    assert _db_state.query_instance.first_called is True


# ---------------------------------------------------------------------------
# E2.2 — 200 sem empresa_id → executar_analise_xml
# ---------------------------------------------------------------------------

def test_e2_analisar_xml_sem_empresa_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    validar_calls = []
    executar_calls = []

    async def fake_validar(file):
        validar_calls.append(file)
        return _XML_BYTES

    def fake_executar(conteudo):
        executar_calls.append(conteudo)
        return _ANALISE_FAKE

    def fail_enqueue(*_a, **_k):
        raise AssertionError("_enqueue_or_run_sync não deve ser chamado sem empresa_id")

    def fail_verificar(*_a, **_k):
        raise AssertionError("verificar_empresa_do_usuario não deve ser chamado sem empresa_id")

    monkeypatch.setattr(fiscal_router, "validar_upload_xml", fake_validar)
    monkeypatch.setattr(fiscal_router, "verificar_empresa_do_usuario", fail_verificar)
    monkeypatch.setattr(fiscal_router, "executar_analise_xml", fake_executar)
    monkeypatch.setattr(fiscal_router, "_enqueue_or_run_sync", fail_enqueue)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/fiscal/analisar-xml", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"status": "XML analisado", "resultado": _ANALISE_FAKE}
    assert len(validar_calls) == 1
    assert len(executar_calls) == 1
    assert executar_calls[0] == _XML_BYTES
    assert _db_state.query_model is None


# ---------------------------------------------------------------------------
# E2.3 — 403 empresa de outro utilizador
# ---------------------------------------------------------------------------

def test_e2_analisar_xml_empresa_de_outro_utilizador_retorna_403(monkeypatch):
    global _db_state
    _db_state = None
    validar_calls = []

    async def fake_validar(file):
        validar_calls.append(file)
        return _XML_BYTES

    def fake_verificar(empresa_id, usuario_atual, db):
        assert empresa_id == 10
        assert usuario_atual.id == 1
        assert db is _db_state
        raise HTTPException(status_code=403, detail="Acesso negado")

    def fail_enqueue(*_a, **_k):
        raise AssertionError("_enqueue_or_run_sync não deve ser chamado quando acesso é negado")

    def fail_executar(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado quando acesso é negado")

    monkeypatch.setattr(fiscal_router, "validar_upload_xml", fake_validar)
    monkeypatch.setattr(fiscal_router, "verificar_empresa_do_usuario", fake_verificar)
    monkeypatch.setattr(fiscal_router, "_enqueue_or_run_sync", fail_enqueue)
    monkeypatch.setattr(fiscal_router, "executar_analise_xml", fail_executar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/fiscal/analisar-xml?empresa_id=10", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
    assert len(validar_calls) == 1
    assert _db_state.query_model is None


# ---------------------------------------------------------------------------
# E2.4 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_e2_analisar_xml_sem_auth_retorna_401(monkeypatch):
    async def fail_validar(*_a, **_k):
        raise AssertionError("validar_upload_xml não deve ser chamado sem auth")

    def fail_verificar(*_a, **_k):
        raise AssertionError("verificar_empresa_do_usuario não deve ser chamado sem auth")

    def fail_enqueue(*_a, **_k):
        raise AssertionError("_enqueue_or_run_sync não deve ser chamado sem auth")

    def fail_executar(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado sem auth")

    monkeypatch.setattr(fiscal_router, "validar_upload_xml", fail_validar)
    monkeypatch.setattr(fiscal_router, "verificar_empresa_do_usuario", fail_verificar)
    monkeypatch.setattr(fiscal_router, "_enqueue_or_run_sync", fail_enqueue)
    monkeypatch.setattr(fiscal_router, "executar_analise_xml", fail_executar)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/fiscal/analisar-xml", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}


# ---------------------------------------------------------------------------
# E2.5 — 422 sem ficheiro multipart
# ---------------------------------------------------------------------------

def test_e2_analisar_xml_sem_ficheiro_retorna_422(monkeypatch):
    async def fail_validar(*_a, **_k):
        raise AssertionError("validar_upload_xml não deve ser chamado sem ficheiro")

    def fail_verificar(*_a, **_k):
        raise AssertionError("verificar_empresa_do_usuario não deve ser chamado sem ficheiro")

    def fail_enqueue(*_a, **_k):
        raise AssertionError("_enqueue_or_run_sync não deve ser chamado sem ficheiro")

    def fail_executar(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado sem ficheiro")

    monkeypatch.setattr(fiscal_router, "validar_upload_xml", fail_validar)
    monkeypatch.setattr(fiscal_router, "verificar_empresa_do_usuario", fail_verificar)
    monkeypatch.setattr(fiscal_router, "_enqueue_or_run_sync", fail_enqueue)
    monkeypatch.setattr(fiscal_router, "executar_analise_xml", fail_executar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/fiscal/analisar-xml")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
