"""D3 — contrato HTTP para POST /formalizacao/simular-empresa."""

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
# Fakes reutilizáveis
# ---------------------------------------------------------------------------

def _fake_cnae_obj(codigo="6201500", secao="J"):
    return SimpleNamespace(
        codigo_subclasse=codigo,
        descricao="Desenvolvimento de programas de computador sob encomenda",
        secao=secao,
        codigo_classe="6201",
        versao_cnae="2.3",
    )


def _fake_resultado_cnae(com_cnae=True, porte="me"):
    return SimpleNamespace(
        cnae_principal_sugerido=_fake_cnae_obj() if com_cnae else None,
        cnaes_secundarios_sugeridos=[],
        score_confianca=0.87,
        permite_mei=False,
        motivo_nao_mei="Atividade vedada ao MEI",
        regimes_compativeis=["mei", "simples", "lucro_presumido"],
        palavras_detectadas=["software", "desenvolvimento"],
        justificativa="Alta correspondência com CNAE 62.01-5",
    )


def _fake_resultado_cnae_mei():
    return SimpleNamespace(
        cnae_principal_sugerido=_fake_cnae_obj("7319099", "M"),
        cnaes_secundarios_sugeridos=[],
        score_confianca=0.80,
        permite_mei=True,
        motivo_nao_mei=None,
        regimes_compativeis=["mei", "simples"],
        palavras_detectadas=["artesanato"],
        justificativa="Compatível com MEI.",
    )


def _fake_resultado_regime_obj(regime="simples"):
    return SimpleNamespace(
        regime=regime,
        carga_anual=Decimal("12000.00"),
        carga_mensal=Decimal("1000.00"),
        aliquota_efetiva_pct=6.0,
        anexo_simples="III",
        fator_r=0.28,
        alertas=[],
    )


def _fake_resultado_regime():
    return SimpleNamespace(
        regime_recomendado="simples",
        economia_anual_vs_pior=Decimal("8000.00"),
        justificativa="Simples Nacional é o mais vantajoso.",
        regimes_inelegiveis=[],
        resultados={
            "simples": _fake_resultado_regime_obj("simples"),
            "lucro_presumido": _fake_resultado_regime_obj("lucro_presumido"),
        },
    )


_CNAE_SERIALIZADO = {
    "codigo": "6201500",
    "descricao": "Desenvolvimento de programas de computador sob encomenda",
    "secao": "J",
    "codigo_classe": "6201",
    "versao_cnae": "2.3",
}

_REGIME_SERIALIZADO = {
    "regime": "simples",
    "carga_anual": "12000.00",
    "carga_mensal": "1000.00",
    "aliquota_efetiva_pct": 6.0,
    "anexo_simples": "III",
    "fator_r": 0.28,
    "alertas": [],
}

_BODY_ESPERADO_200 = {
    "cnae_recomendado": _CNAE_SERIALIZADO,
    "secao_cnae": "J",
    "permite_mei": False,
    "motivo_nao_mei": "Atividade vedada ao MEI",
    "alertas_mei": [],
    "regime_recomendado": "simples",
    "economia_anual_vs_pior": "8000.00",
    "regimes_compativeis": ["mei", "simples", "lucro_presumido"],
    "regimes_inelegiveis": [],
    "resultados_regime": {
        "simples": _REGIME_SERIALIZADO,
        "lucro_presumido": {**_REGIME_SERIALIZADO, "regime": "lucro_presumido"},
    },
    "justificativa_cnae": "Alta correspondência com CNAE 62.01-5",
    "justificativa_regime": "Simples Nacional é o mais vantajoso.",
    "palavras_detectadas": ["software", "desenvolvimento"],
}

_BODY_REQUEST_BASE = {
    "descricao_actividade": "desenvolvimento de software",
    "porte": "me",
    "faturamento_anual": "180000.00",
    "folha_anual": "36000.00",
    "lucro_contabil": None,
    "atividade": "servicos",
    "ano_referencia": 2025,
}


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    return u


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
# D3.1 — 200 sucesso com ano_referencia
# ---------------------------------------------------------------------------

def test_d3_simular_empresa_sucesso_retorna_200(monkeypatch):
    calls_cnae = []
    calls_regime = []
    engine = _FakeEngine()

    def fake_recomendar(descricao_actividade, porte, **_k):
        calls_cnae.append({"descricao_actividade": descricao_actividade, "porte": porte})
        return _fake_resultado_cnae()

    def fake_comparar(**kwargs):
        calls_regime.append(kwargs)
        return _fake_resultado_regime()

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fake_recomendar)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fake_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", lambda: engine)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/simular-empresa", json=_BODY_REQUEST_BASE)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == _BODY_ESPERADO_200

    # provar recomendar_cnaes chamado correctamente
    assert len(calls_cnae) == 1
    assert calls_cnae[0]["descricao_actividade"] == "desenvolvimento de software"
    assert calls_cnae[0]["porte"] == "me"

    # provar BaseTaxEngine resolveu ano
    assert engine.ctx_recebido == {"ano_referencia": 2025}

    # provar comparar_regimes chamado com todos os argumentos correctos
    assert calls_regime == [{
        "faturamento_anual": Decimal("180000.00"),
        "folha_anual": Decimal("36000.00"),
        "lucro_contabil": None,
        "secao_cnae": "J",
        "atividade": "servicos",
        "regimes_permitidos": ["simples", "lucro_presumido"],
        "ano_referencia": 2025,
    }]


# ---------------------------------------------------------------------------
# D3.2 — 422 CNAE não identificado
# ---------------------------------------------------------------------------

def test_d3_simular_empresa_cnae_nao_identificado_retorna_422(monkeypatch):
    calls_cnae = []

    def fake_recomendar(descricao_actividade, porte, **_k):
        calls_cnae.append(True)
        return _fake_resultado_cnae(com_cnae=False)

    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado sem CNAE")

    def fail_engine():
        raise AssertionError("BaseTaxEngine não deve ser instanciado sem CNAE")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fake_recomendar)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", fail_engine)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/simular-empresa", json=_BODY_REQUEST_BASE)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json() == {"detail": "Não foi possível identificar CNAE para a actividade descrita"}
    assert len(calls_cnae) == 1


# ---------------------------------------------------------------------------
# D3.3 — 422 TempoNormativoAusenteError
# ---------------------------------------------------------------------------

def test_d3_simular_empresa_sem_tempo_normativo_retorna_422(monkeypatch):
    calls_cnae = []

    def fake_recomendar(descricao_actividade, porte, **_k):
        calls_cnae.append(True)
        return _fake_resultado_cnae()

    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado sem tempo normativo")

    class _EngineAusente:
        def resolver_ano_referencia(self, ctx):
            raise TempoNormativoAusenteError("Ano normativo ausente")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fake_recomendar)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", lambda: _EngineAusente())
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    body = {k: v for k, v in _BODY_REQUEST_BASE.items() if k != "ano_referencia"}

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/simular-empresa", json=body)
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
    assert len(calls_cnae) == 1


# ---------------------------------------------------------------------------
# D3.4 — 422 schema inválido: descricao_actividade ausente
# ---------------------------------------------------------------------------

def test_d3_simular_empresa_sem_descricao_retorna_422(monkeypatch):
    def fail_recomendar(*_a, **_k):
        raise AssertionError("recomendar_cnaes não deve ser chamado com schema inválido")

    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado com schema inválido")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fail_recomendar)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/simular-empresa", json={
                "faturamento_anual": "180000.00",
                "ano_referencia": 2025,
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422


# ---------------------------------------------------------------------------
# D3.5 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_d3_simular_empresa_sem_auth_retorna_401(monkeypatch):
    def fail_recomendar(*_a, **_k):
        raise AssertionError("recomendar_cnaes não deve ser chamado sem auth")

    def fail_comparar(**_k):
        raise AssertionError("comparar_regimes não deve ser chamado sem auth")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fail_recomendar)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fail_comparar)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/simular-empresa", json=_BODY_REQUEST_BASE)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}


# ---------------------------------------------------------------------------
# D3.6 — 200 MEI com faturamento acima do limite
# ---------------------------------------------------------------------------

def test_d3_simular_empresa_mei_acima_limite_retorna_200(monkeypatch):
    engine = _FakeEngine()
    calls_regime = []

    def fake_recomendar(descricao_actividade, porte, **_k):
        return _fake_resultado_cnae_mei()

    def fake_comparar(**kwargs):
        calls_regime.append(kwargs)
        return _fake_resultado_regime()

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fake_recomendar)
    monkeypatch.setattr(formalizacao_router, "comparar_regimes", fake_comparar)
    monkeypatch.setattr(formalizacao_router, "BaseTaxEngine", lambda: engine)
    monkeypatch.setattr(formalizacao_router, "MEI_LIMITE_ANUAL_FATURAMENTO", Decimal("81000.00"))
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/simular-empresa", json={
                **_BODY_REQUEST_BASE,
                "descricao_actividade": "artesanato",
                "porte": "mei",
                "faturamento_anual": "120000.00",
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body["permite_mei"] is False
    assert body["motivo_nao_mei"] == "Faturamento acima do limite anual permitido para MEI"
    assert body["alertas_mei"] == [
        "Faturamento anual (R$ 120,000.00) ultrapassa o limite MEI de R$ 81,000.00"
    ]
    # provar comparar_regimes com regimes MEI filtrados
    assert len(calls_regime) == 1
    assert calls_regime[0]["regimes_permitidos"] == ["mei", "simples"]
    assert calls_regime[0]["secao_cnae"] == "M"
    assert calls_regime[0]["ano_referencia"] == 2025
