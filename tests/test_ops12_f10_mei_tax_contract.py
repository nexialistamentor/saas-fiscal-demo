"""F10/F11 — contratos HTTP para POST e GET de /relatorio/mei_tax."""

import copy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
from app.database import get_db
from app.main import app
from app.models import RelatorioAnalise, User
from app.security import get_usuario_atual
from app.services.resultado_provenance_service import (
    fingerprint_resultado_json,
    selar_resultado_nao_mei,
)


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
# F10.1 — 503 MEI sem autoridade operacional oficial
# ---------------------------------------------------------------------------

def test_f10_mei_tax_sem_autoridade_retorna_503_sem_resultado(monkeypatch):
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

    assert res.status_code == 503
    assert (
        res.json()["detail"]["tipo_bloqueio"]
        == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    )
    assert "id" not in res.json()
    assert calls == []
    assert _db_state.committed is False
    assert _db_state.added == []
    assert _db_state.refreshed == []


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
# F10.3 — autoridade oficial indisponivel precede o motor interno
# ---------------------------------------------------------------------------

def test_f10_mei_tax_sem_ano_retorna_503_sem_resultado(monkeypatch):
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

    assert res.status_code == 503
    assert (
        res.json()["detail"]["tipo_bloqueio"]
        == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    )
    assert "id" not in res.json()
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


class _ReadOnlyQuery:
    def __init__(self, db):
        self._db = db
        self._matches = list(db.registros)

    def filter(self, *expressoes):
        self._db.eventos.append("F")
        self._db.expressoes.extend(expressoes)
        criterios = _criterios_das_expressoes(expressoes)
        self._db.avaliacoes += len(self._db.registros)
        self._matches = [
            rel
            for rel in self._db.registros
            if all(getattr(rel, coluna) == valor for coluna, valor in criterios.items())
        ]
        return self

    def first(self):
        self._db.eventos.append("R")
        resultado = self._matches[0] if self._matches else None
        self._db.first_results.append(resultado)
        return resultado

    def __getattr__(self, nome):
        raise AssertionError(f"operação de query não autorizada: {nome}")


class _ReadOnlyDB:
    def __init__(self):
        resultado_101 = selar_resultado_nao_mei(
            {"registro": "A", "valor": 101},
            producer_id="app.services.imposto_service.calcular_imposto_simples",
        )
        self.registros = [
            SimpleNamespace(
                id=101,
                user_id=1,
                analysis_type=relatorio_router.ANALYSIS_TYPE_MEI_TAX,
                resultado_json=resultado_101,
                fingerprint=fingerprint_resultado_json(resultado_101),
            ),
            SimpleNamespace(
                id=102,
                user_id=2,
                analysis_type=relatorio_router.ANALYSIS_TYPE_MEI_TAX,
                resultado_json={"registro": "B", "valor": 102},
            ),
            SimpleNamespace(
                id=103,
                user_id=1,
                analysis_type="tax_planning",
                resultado_json={"registro": "C", "valor": 103},
            ),
        ]
        self.eventos = []
        self.expressoes = []
        self.first_results = []
        self.query_calls = 0
        self.avaliacoes = 0

    def query(self, modelo):
        assert modelo is RelatorioAnalise
        self.query_calls += 1
        self.eventos.append("Q")
        return _ReadOnlyQuery(self)

    def __getattr__(self, nome):
        raise AssertionError(f"operação de sessão não autorizada: {nome}")


_readonly_db_state = None


def _override_readonly_db():
    global _readonly_db_state
    if _readonly_db_state is None:
        _readonly_db_state = _ReadOnlyDB()
    yield _readonly_db_state


def _criterios_das_expressoes(expressoes):
    return {
        expressao.left.key: expressao.right.value
        for expressao in expressoes
    }


def _criterios_registrados(db):
    criterios = _criterios_das_expressoes(db.expressoes)
    assert len(db.expressoes) == 3
    return criterios


def _criterios_esperados(relatorio_id):
    return {
        "id": relatorio_id,
        "user_id": 1,
        "analysis_type": relatorio_router.ANALYSIS_TYPE_MEI_TAX,
    }


def _get_mei_tax(
    relatorio_id,
    monkeypatch,
    *,
    pago=True,
    gerador=None,
    raise_server_exceptions=True,
    db=None,
):
    global _readonly_db_state
    _readonly_db_state = db or _ReadOnlyDB()
    if gerador is None:
        gerador = lambda _resultado: BytesIO(b"%PDF-1.4\nfake")
    monkeypatch.setattr(relatorio_router, "gerar_pdf_imposto", gerador)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(
        consulta_paga=pago
    )
    app.dependency_overrides[get_db] = _override_readonly_db
    try:
        with TestClient(
            app, raise_server_exceptions=raise_server_exceptions
        ) as cliente:
            return cliente.get(f"/relatorio/mei_tax/{relatorio_id}")
    finally:
        app.dependency_overrides.clear()


def test_f11_get_mei_tax_sem_auth_retorna_401_sem_consulta(monkeypatch):
    global _readonly_db_state
    _readonly_db_state = _ReadOnlyDB()
    gerador_chamado = False

    def fail_gerador(_resultado):
        nonlocal gerador_chamado
        gerador_chamado = True
        raise AssertionError("gerador não devia ser chamado sem autenticação")

    monkeypatch.setattr(relatorio_router, "gerar_pdf_imposto", fail_gerador)
    app.dependency_overrides[get_db] = _override_readonly_db
    try:
        with TestClient(app) as cliente:
            response = cliente.get("/relatorio/mei_tax/101")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert _readonly_db_state.query_calls == 0
    assert gerador_chamado is False
    assert _readonly_db_state.eventos == []


def test_f11_get_mei_tax_sem_pagamento_retorna_402_sem_consulta(monkeypatch):
    gerador_chamado = False

    def fail_gerador(_resultado):
        nonlocal gerador_chamado
        gerador_chamado = True
        raise AssertionError("gerador não devia ser chamado sem pagamento")

    response = _get_mei_tax(101, monkeypatch, pago=False, gerador=fail_gerador)

    assert response.status_code == 402
    assert response.json() == {
        "detail": "Libere a análise fiscal para acessar o relatório."
    }
    assert _readonly_db_state.query_calls == 0
    assert gerador_chamado is False
    assert _readonly_db_state.eventos == []


def test_f11_post_get_tem_paridade_financeira(monkeypatch):
    global _readonly_db_state
    _readonly_db_state = _ReadOnlyDB()

    def fail_motor(**_kwargs):
        raise AssertionError("motor não devia ser chamado sem pagamento")

    def fail_gerador(_resultado):
        raise AssertionError("gerador não devia ser chamado sem pagamento")

    monkeypatch.setattr(relatorio_router, "calcular_imposto_simples", fail_motor)
    monkeypatch.setattr(relatorio_router, "gerar_pdf_imposto", fail_gerador)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user(
        consulta_paga=False
    )
    app.dependency_overrides[get_db] = _override_readonly_db
    try:
        with TestClient(app) as cliente:
            post_response = cliente.post("/relatorio/mei_tax", json=_payload_valido)
            get_response = cliente.get("/relatorio/mei_tax/101")
    finally:
        app.dependency_overrides.clear()

    assert get_response.status_code == 402
    assert post_response.status_code == 402
    assert get_response.json()["detail"] == post_response.json()["detail"]
    assert _readonly_db_state.query_calls == 0
    assert _readonly_db_state.eventos == []


def test_f11_get_mei_tax_inexistente_retorna_404(monkeypatch):
    gerador_chamado = False

    def fail_gerador(_resultado):
        nonlocal gerador_chamado
        gerador_chamado = True

    response = _get_mei_tax(999, monkeypatch, gerador=fail_gerador)

    assert response.status_code == 404
    assert _criterios_registrados(_readonly_db_state) == _criterios_esperados(999)
    assert _readonly_db_state.avaliacoes == 3
    assert _readonly_db_state.first_results == [None]
    assert gerador_chamado is False
    assert _readonly_db_state.eventos == ["Q", "F", "R"]


def test_f11_get_mei_tax_de_outro_utilizador_retorna_404(monkeypatch):
    gerador_chamado = False

    def fail_gerador(_resultado):
        nonlocal gerador_chamado
        gerador_chamado = True

    response = _get_mei_tax(102, monkeypatch, gerador=fail_gerador)

    assert response.status_code == 404
    assert _criterios_registrados(_readonly_db_state) == _criterios_esperados(102)
    assert _readonly_db_state.avaliacoes == 3
    assert _readonly_db_state.first_results == [None]
    assert gerador_chamado is False
    assert _readonly_db_state.eventos == ["Q", "F", "R"]


def test_f11_get_mei_tax_de_outro_tipo_retorna_404(monkeypatch):
    gerador_chamado = False

    def fail_gerador(_resultado):
        nonlocal gerador_chamado
        gerador_chamado = True

    response = _get_mei_tax(103, monkeypatch, gerador=fail_gerador)

    assert response.status_code == 404
    assert _criterios_registrados(_readonly_db_state) == _criterios_esperados(103)
    assert _readonly_db_state.avaliacoes == 3
    assert _readonly_db_state.first_results == [None]
    assert gerador_chamado is False
    assert _readonly_db_state.eventos == ["Q", "F", "R"]


def test_f11_get_mei_tax_v1_sem_autoridade_retorna_409_read_only(monkeypatch):
    argumentos_gerador = []
    global _readonly_db_state
    _readonly_db_state = _ReadOnlyDB()
    rel = _readonly_db_state.registros[0]
    estado_antes = copy.deepcopy(vars(rel))

    def fail_gerador(resultado):
        argumentos_gerador.append(resultado)
        raise AssertionError("gerar_pdf_imposto nao devia ser chamado")

    response = _get_mei_tax(
        101, monkeypatch, gerador=fail_gerador, db=_readonly_db_state
    )

    assert response.status_code == 409
    assert response.json()["detail"]["tipo_bloqueio"] == (
        "RESULTADO_PERSISTIDO_PROVENIENCIA_NAO_COMPROVADA"
    )
    assert response.json()["detail"]["estado_l3"] == "bloqueado"
    assert argumentos_gerador == []
    assert vars(rel) == estado_antes
    assert _criterios_registrados(_readonly_db_state) == _criterios_esperados(101)
    assert _readonly_db_state.eventos == ["Q", "F", "R"]
    assert _readonly_db_state.query_calls == 1
    assert _readonly_db_state.first_results == [rel]


def test_f11_get_mei_tax_v1_bloqueia_antes_do_gerador_sem_mutacao(monkeypatch):
    global _readonly_db_state
    _readonly_db_state = _ReadOnlyDB()
    rel = _readonly_db_state.registros[0]
    estado_antes = copy.deepcopy(vars(rel))

    def gerador_com_falha(_resultado):
        raise AssertionError("gerar_pdf_imposto foi alcancado")

    response = _get_mei_tax(
        101,
        monkeypatch,
        gerador=gerador_com_falha,
        db=_readonly_db_state,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["tipo_bloqueio"] == (
        "RESULTADO_PERSISTIDO_PROVENIENCIA_NAO_COMPROVADA"
    )
    assert response.json()["detail"]["estado_l3"] == "bloqueado"
    assert _readonly_db_state.eventos == ["Q", "F", "R"]
    assert _readonly_db_state.query_calls == 1
    assert _readonly_db_state.first_results == [rel]
    assert vars(rel) == estado_antes
    assert _criterios_registrados(_readonly_db_state) == _criterios_esperados(101)
