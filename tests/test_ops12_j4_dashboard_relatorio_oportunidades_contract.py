"""J4 — contrato HTTP para GET /dashboard/relatorio/{id}/oportunidades."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.dashboard_router as dashboard_router
from app.database import get_db
from app.main import app
from app.models import EngineResultado, RelatorioAnalise, User
from app.security import get_usuario_atual

_oportunidade = {"tipo": "RESTITUICAO_ST", "valor_estimado": 500.0}
_credito = {"tipo": "CREDITO_ST_ESTIMADO", "valor_estimado": 200.0}
_engine_op = {"tipo": "OPORTUNIDADE_ENGINE", "valor_estimado": 100.0}


class _QueryFake:
    def __init__(self, rows):
        self._rows = rows
        self.filter_called = False
        self.filter_args = None
        self.all_called = False
        self.first_called = False

    def filter(self, *args, **_k):
        self.filter_called = True
        self.filter_args = args
        return self

    def first(self):
        self.first_called = True
        return self._rows[0] if self._rows else None

    def all(self):
        self.all_called = True
        return self._rows


class _DBFake:
    def __init__(self, rel=None, engines=None):
        self._rel = [rel] if rel else []
        self._engines = engines or []
        self.query_instances = []
        self.query_models = []

    def query(self, *args, **_k):
        model = args[0] if args else None
        self.query_models.append(model)
        rows = self._rel if model is RelatorioAnalise else self._engines
        q = _QueryFake(rows)
        self.query_instances.append(q)
        return q


_db_state = None


def _override_db(rel=None, engines=None):
    def _inner():
        global _db_state
        _db_state = _DBFake(rel, engines)
        yield _db_state
    return _inner


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    u.role = "user"
    return u


def _rel_with_json():
    return SimpleNamespace(
        id=1, empresa_id=1, tempo_execucao=2.0,
        resultado_json={"oportunidades": [_oportunidade], "creditos_detectados": [_credito]}
    )


def _rel_empty_json():
    return SimpleNamespace(id=1, empresa_id=1, tempo_execucao=2.0, resultado_json=None)


def _engine_with_op():
    return SimpleNamespace(resultado={"oportunidades": [_engine_op]})


def test_j4_oportunidades_com_resultado_json_retorna_200(monkeypatch):
    global _db_state
    _db_state = None
    access_calls = []

    monkeypatch.setattr(
        dashboard_router, "verificar_acesso_relatorio",
        lambda rel, u, db: access_calls.append((rel, u, db))
    )
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel=_rel_with_json(), engines=[])

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1/oportunidades")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "relatorio_id": 1,
        "tempo_processamento_segundos": 2.0,
        "oportunidades": [_oportunidade],
        "creditos_detectados": [_credito],
        "total_oportunidades": 2,
    }
    assert _db_state is not None
    assert len(_db_state.query_instances) == 2
    assert _db_state.query_models[0] is RelatorioAnalise
    assert _db_state.query_models[1] is EngineResultado
    rel_q = _db_state.query_instances[0]
    assert rel_q.filter_called is True
    assert rel_q.first_called is True
    assert len(rel_q.filter_args) == 1
    eng_q = _db_state.query_instances[1]
    assert eng_q.filter_called is True
    assert eng_q.all_called is True
    assert len(eng_q.filter_args) == 1
    assert len(access_calls) == 1
    assert access_calls[0][0].id == 1
    assert access_calls[0][1].id == 1
    assert access_calls[0][2] is _db_state


def test_j4_oportunidades_fallback_engine_retorna_200(monkeypatch):
    global _db_state
    _db_state = None

    monkeypatch.setattr(dashboard_router, "verificar_acesso_relatorio", lambda *_a: None)
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel=_rel_empty_json(), engines=[_engine_with_op()])

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1/oportunidades")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "relatorio_id": 1,
        "tempo_processamento_segundos": 2.0,
        "oportunidades": [_engine_op],
        "creditos_detectados": [],
        "total_oportunidades": 1,
    }
    assert _db_state is not None
    assert len(_db_state.query_instances) == 2
    assert _db_state.query_models[0] is RelatorioAnalise
    assert _db_state.query_models[1] is EngineResultado
    rel_q = _db_state.query_instances[0]
    assert rel_q.filter_called is True
    assert rel_q.first_called is True
    assert len(rel_q.filter_args) == 1
    eng_q = _db_state.query_instances[1]
    assert eng_q.filter_called is True
    assert eng_q.all_called is True
    assert len(eng_q.filter_args) == 1


def test_j4_oportunidades_relatorio_inexistente_retorna_404(monkeypatch):
    global _db_state
    _db_state = None
    access_calls = []

    monkeypatch.setattr(
        dashboard_router, "verificar_acesso_relatorio",
        lambda rel, u, db: access_calls.append((rel, u, db))
    )
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel=None)

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/999/oportunidades")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 404
    assert res.json() == {"detail": "Relatório não encontrado"}
    assert access_calls == []
    assert _db_state is not None
    assert len(_db_state.query_instances) == 1
    assert _db_state.query_models[0] is RelatorioAnalise


def test_j4_oportunidades_acesso_negado_retorna_403(monkeypatch):
    global _db_state
    _db_state = None

    monkeypatch.setattr(
        dashboard_router, "verificar_acesso_relatorio",
        lambda *_a, **_k: (_ for _ in ()).throw(HTTPException(status_code=403, detail="Acesso negado"))
    )
    app.dependency_overrides[get_usuario_atual] = _mock_user
    app.dependency_overrides[get_db] = _override_db(rel=_rel_with_json())

    try:
        with TestClient(app) as c:
            res = c.get("/dashboard/relatorio/1/oportunidades")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res.json() == {"detail": "Acesso negado"}
    assert _db_state is not None
    assert len(_db_state.query_instances) == 1
    assert _db_state.query_models[0] is RelatorioAnalise
    rel_q = _db_state.query_instances[0]
    assert rel_q.filter_called is True
    assert rel_q.first_called is True
    assert len(rel_q.filter_args) == 1


def test_j4_oportunidades_sem_auth_retorna_401():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        res = c.get("/dashboard/relatorio/1/oportunidades")
    assert res.status_code == 401
