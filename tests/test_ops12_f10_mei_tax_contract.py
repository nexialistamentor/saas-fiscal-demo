"""F10 — contrato HTTP para POST /relatorio/mei_tax."""

from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
from app.database import get_db
from app.main import app
from app.models import RelatorioAnalise, User
from app.security import get_usuario_atual


class _DBFake:
    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)
        obj.id = 42

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)
        obj.id = 42


_db_state = None


def _override_db():
    global _db_state
    _db_state = _DBFake()
    yield _db_state


def _mock_user(consulta_paga=True):
    u = MagicMock(spec=User)
    u.id = 1
    u.consulta_paga = consulta_paga
    return u


_payload_valido = {
    "faturamento_mensal": 5000.0,
    "despesas": 0.0,
    "tipo_usuario": "MEI",
    "atividade": "comercio",
    "ano_referencia": 2026,
}

_resultado_motor = {"das": 71.60, "tributos": {"das": 71.60}}


# ---------------------------------------------------------------------------
# F10.1 — 200 MEI com pagamento e ano_referencia
# ---------------------------------------------------------------------------

def test_f10_mei_tax_retorna_200_com_id(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_calcular(**kwargs):
        calls.append(kwargs)
        return _resultado_motor

    monkeypatch.setattr(relatorio_router, "calcular_imposto_simples", fake_calcular)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(consulta_paga=True)
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/mei_tax", json=_payload_valido)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {"id": 42}
    assert calls == [{
        "faturamento": 5000.0,
        "despesas": 0.0,
        "tipo": "MEI",
        "atividade": "comercio",
        "ano_referencia": 2026,
    }]
    assert _db_state.committed is True
    assert len(_db_state.added) == 1
    assert isinstance(_db_state.added[0], RelatorioAnalise)
    assert _db_state.added[0].analysis_type == relatorio_router.ANALYSIS_TYPE_MEI_TAX
    assert _db_state.added[0].status == "ok"
    assert _db_state.added[0].resultado_json == _resultado_motor
    assert _db_state.refreshed == [_db_state.added[0]]


# ---------------------------------------------------------------------------
# F10.2 — 402 sem consulta_paga
# ---------------------------------------------------------------------------

def test_f10_mei_tax_sem_pagamento_retorna_402(monkeypatch):
    global _db_state
    _db_state = None
    calls = []

    def fake_calcular(**kw):
        calls.append(kw)
        return _resultado_motor

    monkeypatch.setattr(relatorio_router, "calcular_imposto_simples", fake_calcular)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(consulta_paga=False)
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/mei_tax", json=_payload_valido)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 402
    assert res.json() == {"detail": "Libere a análise fiscal para acessar o relatório."}
    assert calls == []
    assert _db_state.added == []
    assert _db_state.committed is False
    assert _db_state.refreshed == []


# ---------------------------------------------------------------------------
# F10.3 — 422 TempoNormativoAusenteError
# ---------------------------------------------------------------------------

def test_f10_mei_tax_sem_ano_retorna_422_bloqueado(monkeypatch):
    global _db_state
    _db_state = None

    from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError

    def fake_calcular_bloqueado(**kwargs):
        raise TempoNormativoAusenteError("Ano normativo ausente")

    monkeypatch.setattr(relatorio_router, "calcular_imposto_simples", fake_calcular_bloqueado)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(consulta_paga=True)
    app.dependency_overrides[get_db] = _override_db

    payload_sem_ano = {**_payload_valido, "ano_referencia": None}

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/mei_tax", json=payload_sem_ano)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json() == {
        "detail": {
            "bloqueado": True,
            "tipo_bloqueio": "TEMPO_NORMATIVO_AUSENTE",
            "estado_l3": "bloqueado",
            "erro": "Ano normativo ausente",
        }
    }
    assert _db_state.added == []
    assert _db_state.committed is False
    assert _db_state.refreshed == []


# ---------------------------------------------------------------------------
# F10.4 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_f10_mei_tax_sem_auth_retorna_401(monkeypatch):
    def fail_calcular(**_kw):
        raise AssertionError("calcular_imposto_simples não devia ser chamado sem auth")

    monkeypatch.setattr(relatorio_router, "calcular_imposto_simples", fail_calcular)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401
    app.dependency_overrides[get_db] = _override_db

    try:
        with TestClient(app) as c:
            res = c.post("/relatorio/mei_tax", json=_payload_valido)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
