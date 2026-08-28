"""D2 — contrato HTTP para POST /formalizacao/comparar-regimes."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.formalizacao_router as formalizacao_router
from app.main import app
from app.models import User
from app.security import get_usuario_atual
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError

# ---------------------------------------------------------------------------
# Fake de retorno do serviço comparar_regimes
# ---------------------------------------------------------------------------

def _fake_resultado_regime(regime="simples"):
    return SimpleNamespace(
        regime=regime,
        carga_anual=Decimal("12000.00"),
        carga_mensal=Decimal("1000.00"),
        aliquota_efetiva_pct=6.0,
        anexo_simples="III",
        fator_r=0.28,
        alertas=[],
    )


def _fake_resultado():
    return SimpleNamespace(
        regime_recomendado="simples",
        economia_anual_vs_pior=Decimal("8000.00"),
        justificativa="Simples Nacional é o mais vantajoso para este perfil.",
        regimes_inelegiveis=[],
        regimes_nao_avaliados={},
        resultados={
            "simples": _fake_resultado_regime("simples"),
            "lucro_presumido": _fake_resultado_regime("lucro_presumido"),
        },
    )


_BODY_ESPERADO = {
    "regime_recomendado": "simples",
    "economia_anual_vs_pior": "8000.00",
    "justificativa": "Simples Nacional é o mais vantajoso para este perfil.",
    "regimes_inelegiveis": [],
    "regimes_nao_avaliados": {},
    "resultados": {
        "simples": {
            "regime": "simples",
            "carga_anual": "12000.00",
            "carga_mensal": "1000.00",
            "aliquota_efetiva_pct": 6.0,
            "anexo_simples": "III",
            "fator_r": 0.28,
            "alertas": [],
        },
        "lucro_presumido": {
            "regime": "lucro_presumido",
            "carga_anual": "12000.00",
            "carga_mensal": "1000.00",
            "aliquota_efetiva_pct": 6.0,
            "anexo_simples": "III",
            "fator_r": 0.28,
            "alertas": [],
        },
    },
}

_BODY_REQUEST_BASE = {
    "faturamento_anual": "180000.00",
    "folha_anual": "36000.00",
    "lucro_contabil": None,
    "secao_cnae": "J",
    "atividade": "servicos",
    "regimes_permitidos": None,
}


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    return u


# ---------------------------------------------------------------------------
# Fake BaseTaxEngine
# ---------------------------------------------------------------------------

class _FakeEngine:
    def __init__(self):
        self.ctx_recebido = None

    def resolver_ano_referencia(self, ctx):
        self.ctx_recebido = ctx
        if "ano_referencia" in ctx:
            return ctx["ano_referencia"]
        if "data_referencia" in ctx:
            return ctx["data_referencia"].year
        raise TempoNormativoAusenteError("Ano normativo ausente")


# ---------------------------------------------------------------------------
# D2.1 — 200 sucesso com ano_referencia
# ---------------------------------------------------------------------------

def test_d2_comparar_regimes_com_ano_referencia_retorna_200(monkeypatch):
    calls = []
    engine_instance = _FakeEngine()

    def fake_comparar(**kwargs):
        calls.append(kwargs)
        return _fake_resultado()

    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fake_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", lambda: engine_instance)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/comparar-regimes", json={
                **_BODY_REQUEST_BASE,
                "ano_referencia": 2025,
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == _BODY_ESPERADO
    assert engine_instance.ctx_recebido == {"ano_referencia": 2025}
    assert len(calls) == 1
    assert calls[0]["faturamento_anual"] == Decimal("180000.00")
    assert calls[0]["folha_anual"] == Decimal("36000.00")
    assert calls[0]["lucro_contabil"] is None
    assert calls[0]["secao_cnae"] == "J"
    assert calls[0]["atividade"] == "servicos"
    assert calls[0]["regimes_permitidos"] is None
    assert calls[0]["ano_referencia"] == 2025


# ---------------------------------------------------------------------------
# D2.2 — 200 sucesso com data_referencia
# ---------------------------------------------------------------------------

def test_d2_comparar_regimes_com_data_referencia_retorna_200(monkeypatch):
    calls = []
    engine_instance = _FakeEngine()

    def fake_comparar(**kwargs):
        calls.append(kwargs)
        return _fake_resultado()

    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fake_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", lambda: engine_instance)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/comparar-regimes", json={
                **_BODY_REQUEST_BASE,
                "data_referencia": "2025-06-15",
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == _BODY_ESPERADO
    assert len(calls) == 1
    # provar que data_referencia foi passada ao engine e o ano resolvido
    assert engine_instance.ctx_recebido is not None
    assert engine_instance.ctx_recebido.get("data_referencia") == date(2025, 6, 15)
    assert calls[0]["ano_referencia"] == 2025


# ---------------------------------------------------------------------------
# D2.3 — 422 TempoNormativoAusenteError (sem ano nem data)
# ---------------------------------------------------------------------------

def test_d2_comparar_regimes_sem_tempo_normativo_retorna_422(monkeypatch):
    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado sem tempo normativo")

    engine_instance = _FakeEngine()

    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", lambda: engine_instance)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/comparar-regimes", json=_BODY_REQUEST_BASE)
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


# ---------------------------------------------------------------------------
# D2.4 — 422 schema inválido: faturamento_anual ausente
# ---------------------------------------------------------------------------

def test_d2_comparar_regimes_sem_faturamento_retorna_422(monkeypatch):
    def fail_engine():
        raise AssertionError("BaseTaxEngine não deve ser instanciado com schema inválido")

    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado com schema inválido")

    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", fail_engine)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/comparar-regimes", json={
                "ano_referencia": 2025,
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422


# ---------------------------------------------------------------------------
# D2.5 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_d2_comparar_regimes_sem_auth_retorna_401(monkeypatch):
    def fail_engine():
        raise AssertionError("BaseTaxEngine não deve ser instanciado sem auth")

    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado sem auth")

    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", fail_engine)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/comparar-regimes", json={
                **_BODY_REQUEST_BASE,
                "ano_referencia": 2025,
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
