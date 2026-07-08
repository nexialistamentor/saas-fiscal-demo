"""F8 — contrato HTTP para GET /relatorio/{relatorio_id}."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import RelatorioAnalise, User
from app.security import get_usuario_atual


class _QueryFake:
    def __init__(self, rel):
        self._rel = rel
        self.filter_called = False
        self.filter_args = None
        self.first_called = False

    def filter(self, *args, **_k):
        self.filter_called = True
        self.filter_args = args
        return self

    def first(self):
        self.first_called = True
        return self._rel


class _DBFake:
    def __init__(self, rel):
        self._rel = rel
        self.query_instance = None
        self.query_model = None

    def query(self, *args, **_k):
        self.query_model = args[0] if args else None
        self.query_instance = _QueryFake(self._rel)
        return self.query_instance


_db_state = None


def _override_db(rel):
    def _inner():
        global _db_state
        _db_state = _DBFake(rel)
        yield _db_state
    return _inner


def _mock_user(user_id=1, consulta_paga=True):
    u = MagicMock(spec=User)
    u.id = user_id
    u.consulta_paga = consulta_paga
    return u


def _make_rel(user_id=1, consulta_paga=None, resultado_json=None):
    return SimpleNamespace(
        id=1,
        user_id=user_id,
        empresa_id=10,
        status="ok",
        analysis_type="empresa_tax",
        score_resultante=85.0,
        total_alertas=2,
        pago=True,
        criado_em=datetime(2026, 1, 15, 10, 0, 0),
        consulta_paga=consulta_paga,
        resultado_json=resultado_json or {},
    )


def _assert_query(filter_args_len=1):
    assert _db_state is not None
    assert _db_state.query_model is RelatorioAnalise
    assert _db_state.query_instance.filter_called is True
    assert _db_state.query_instance.first_called is True
    assert len(_db_state.query_instance.filter_args) == filter_args_len


# ---------------------------------------------------------------------------
# F8.1 — 200 bloqueado por pagamento
# ---------------------------------------------------------------------------

def test_f8_relatorio_bloqueado_sem_pagamento():
    global _db_state
    _db_state = None
    rel = _make_rel(user_id=1, consulta_paga=None)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(user_id=1, consulta_paga=False)
    app.dependency_overrides[get_db] = _override_db(rel)

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "status": "bloqueado",
        "mensagem": "Pagamento necessário",
        "relatorio_id": 1,
    }
    _assert_query()


# ---------------------------------------------------------------------------
# F8.2 — 200 pago com payload completo
# ---------------------------------------------------------------------------

def test_f8_relatorio_pago_retorna_payload_completo():
    global _db_state
    _db_state = None
    rel = _make_rel(
        user_id=1,
        consulta_paga=True,
        resultado_json={"oportunidades": [{"ncm": "12345678"}]},
    )
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(user_id=1, consulta_paga=True)
    app.dependency_overrides[get_db] = _override_db(rel)

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "oportunidades": [{"ncm": "12345678"}],
        "relatorio_id": 1,
        "empresa_id": 10,
        "status": "ok",
        "analysis_type": "empresa_tax",
        "score_resultante": 85.0,
        "total_alertas": 2,
        "pago": True,
        "criado_em": "2026-01-15T10:00:00",
    }
    _assert_query()


# ---------------------------------------------------------------------------
# F8.3 — 404 relatório inexistente
# ---------------------------------------------------------------------------

def test_f8_relatorio_inexistente_retorna_404():
    global _db_state
    _db_state = None
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(1)
    app.dependency_overrides[get_db] = _override_db(None)

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/999")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json() == {"detail": "Relatório não encontrado"}
    _assert_query()


# ---------------------------------------------------------------------------
# F8.4 — 403 relatório de outro utilizador
# ---------------------------------------------------------------------------

def test_f8_relatorio_de_outro_utilizador_retorna_403():
    global _db_state
    _db_state = None
    rel = _make_rel(user_id=99)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(user_id=1)
    app.dependency_overrides[get_db] = _override_db(rel)

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
    _assert_query()


# ---------------------------------------------------------------------------
# F8.5 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_f8_relatorio_sem_auth_retorna_401():
    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db(None)

    try:
        with TestClient(app) as c:
            res = c.get("/relatorio/1")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
