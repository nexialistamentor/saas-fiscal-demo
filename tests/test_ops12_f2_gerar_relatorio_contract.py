"""F2 — contrato HTTP para POST /relatorio/gerar-relatorio."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
from app.database import get_db
from app.main import app
from app.models import Empresa, User
from app.security import get_usuario_atual
from app.services.usage_service import LimiteAnalisesAtingidoError

_XML_BYTES = b"<NFeProc><NFe></NFe></NFeProc>"
_MENSAGEM = "Análise concluída. Desbloqueie o relatório completo para visualizar os detalhes."
_ANALISE_FAKE = {"insights": [], "context_flags": {}}


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


def _mock_user(user_id=1, plano=None):
    u = MagicMock(spec=User)
    u.id = user_id
    u.plano = plano
    return u


def _xml_file():
    return ("file", ("nota.xml", _XML_BYTES, "application/xml"))


# ---------------------------------------------------------------------------
# F2.1 — 200 sem empresa_id
# ---------------------------------------------------------------------------

def test_f2_gerar_relatorio_sem_empresa_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    validar_calls = []
    executar_calls = []
    montar_calls = []

    async def fake_validar(file):
        validar_calls.append(file)
        return _XML_BYTES

    def fake_executar(db, xml_bytes, user_id, empresa_id, limite_analises=100):
        executar_calls.append((db, xml_bytes, user_id, empresa_id, limite_analises))
        return SimpleNamespace(id=42), _ANALISE_FAKE

    def fake_montar(analise, empresa_id, db):
        montar_calls.append((analise, empresa_id, db))
        return {"empresa_id": None, "insights": [], "score_global": None}

    def fail_analise_xml(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado no fluxo autenticado")

    plano = SimpleNamespace(limite_analises=7)
    monkeypatch.setattr(relatorio_router, "validar_upload_xml", fake_validar)
    monkeypatch.setattr(relatorio_router, "executar_e_registrar_analise_xml", fake_executar)
    monkeypatch.setattr(relatorio_router, "executar_analise_xml", fail_analise_xml)
    monkeypatch.setattr(relatorio_router, "_montar_relatorio", fake_montar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(user_id=1, plano=plano)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar-relatorio", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "status": "processado",
        "mensagem": _MENSAGEM,
        "relatorio_id": 42,
    }
    assert len(validar_calls) == 1
    assert len(executar_calls) == 1
    assert executar_calls[0][0] is _db_state
    assert executar_calls[0][1] == _XML_BYTES
    assert executar_calls[0][2] == 1
    assert executar_calls[0][3] is None
    assert executar_calls[0][4] == 7
    assert montar_calls == [(_ANALISE_FAKE, None, _db_state)]
    assert _db_state.query_model is None  # não consultou Empresa


# ---------------------------------------------------------------------------
# F2.2 — 200 com empresa_id=10
# ---------------------------------------------------------------------------

def test_f2_gerar_relatorio_com_empresa_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    verificar_calls = []
    executar_calls = []

    async def fake_validar(file):
        return _XML_BYTES

    def fake_verificar(empresa_id, usuario_atual, db):
        verificar_calls.append((empresa_id, usuario_atual, db))

    def fake_executar(db, xml_bytes, user_id, empresa_id, limite_analises=100):
        executar_calls.append((db, xml_bytes, user_id, empresa_id, limite_analises))
        return SimpleNamespace(id=99), _ANALISE_FAKE

    def fake_montar(analise, empresa_id, db):
        return {"empresa_id": empresa_id, "insights": [], "score_global": None}

    def fail_analise_xml(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado no fluxo autenticado")

    emp = SimpleNamespace(id=10, user_id=55)
    monkeypatch.setattr(relatorio_router, "validar_upload_xml", fake_validar)
    monkeypatch.setattr(relatorio_router, "verificar_empresa_do_usuario", fake_verificar)
    monkeypatch.setattr(relatorio_router, "executar_e_registrar_analise_xml", fake_executar)
    monkeypatch.setattr(relatorio_router, "executar_analise_xml", fail_analise_xml)
    monkeypatch.setattr(relatorio_router, "_montar_relatorio", fake_montar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(user_id=1)
    app.dependency_overrides[get_db] = _override_db(empresa=emp)

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar-relatorio?empresa_id=10", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "status": "processado",
        "mensagem": _MENSAGEM,
        "relatorio_id": 99,
    }
    assert len(verificar_calls) == 1
    assert verificar_calls[0][0] == 10
    assert verificar_calls[0][1].id == 1
    assert verificar_calls[0][2] is _db_state
    assert len(executar_calls) == 1
    assert executar_calls[0][0] is _db_state
    assert executar_calls[0][1] == _XML_BYTES
    assert executar_calls[0][2] == 55  # user_id vem de emp.user_id
    assert executar_calls[0][3] == 10
    assert executar_calls[0][4] == 100
    assert _db_state.query_model is Empresa
    assert _db_state.query_instance.filter_called is True
    assert _db_state.query_instance.first_called is True


# ---------------------------------------------------------------------------
# F2.3 — 429 LimiteAnalisesAtingidoError
# ---------------------------------------------------------------------------

def test_f2_gerar_relatorio_limite_atingido_retorna_429(monkeypatch):
    montar_calls = []

    async def fake_validar(file):
        return _XML_BYTES

    def fake_executar(*_a, **_k):
        raise LimiteAnalisesAtingidoError("Limite atingido")

    def fail_montar(*_a, **_k):
        montar_calls.append(True)

    def fail_analise_xml(*_a, **_k):
        raise AssertionError("executar_analise_xml não deve ser chamado no fluxo autenticado")

    monkeypatch.setattr(relatorio_router, "validar_upload_xml", fake_validar)
    monkeypatch.setattr(relatorio_router, "executar_e_registrar_analise_xml", fake_executar)
    monkeypatch.setattr(relatorio_router, "executar_analise_xml", fail_analise_xml)
    monkeypatch.setattr(relatorio_router, "_montar_relatorio", fail_montar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar-relatorio", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 429
    assert res.json() == {"detail": "Limite atingido"}
    assert montar_calls == []


# ---------------------------------------------------------------------------
# F2.4 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_f2_gerar_relatorio_sem_auth_retorna_401(monkeypatch):
    async def fail_validar(*_a, **_k):
        raise AssertionError("validar_upload_xml não deve ser chamado sem auth")

    monkeypatch.setattr(relatorio_router, "validar_upload_xml", fail_validar)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar-relatorio", files=[_xml_file()])
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}


# ---------------------------------------------------------------------------
# F2.5 — 422 sem ficheiro multipart
# ---------------------------------------------------------------------------

def test_f2_gerar_relatorio_sem_ficheiro_retorna_422(monkeypatch):
    async def fail_validar(*_a, **_k):
        raise AssertionError("validar_upload_xml não deve ser chamado sem ficheiro")

    monkeypatch.setattr(relatorio_router, "validar_upload_xml", fail_validar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db()

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/gerar-relatorio")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
