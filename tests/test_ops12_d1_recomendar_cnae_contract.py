"""D1 — contrato HTTP para POST /formalizacao/recomendar-cnae."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.formalizacao_router as formalizacao_router
from app.main import app
from app.models import User
from app.security import get_usuario_atual

# ---------------------------------------------------------------------------
# Fake de retorno do serviço recomendar_cnaes
# ---------------------------------------------------------------------------

def _fake_cnae(codigo="6201500"):
    return SimpleNamespace(
        codigo_subclasse=codigo,
        descricao="Desenvolvimento de programas de computador sob encomenda",
        secao="J",
        codigo_classe="6201",
        versao_cnae="2.3",
    )


def _fake_resultado():
    return SimpleNamespace(
        cnae_principal_sugerido=_fake_cnae("6201500"),
        cnaes_secundarios_sugeridos=[_fake_cnae("6202300")],
        score_confianca=0.87,
        permite_mei=False,
        motivo_nao_mei="Atividade vedada ao MEI",
        regimes_compativeis=["simples", "lucro_presumido"],
        palavras_detectadas=["software", "desenvolvimento"],
        justificativa="Alta correspondência com CNAE 62.01-5",
    )


_BODY_ESPERADO = {
    "cnae_principal": {
        "codigo": "6201500",
        "descricao": "Desenvolvimento de programas de computador sob encomenda",
        "secao": "J",
        "codigo_classe": "6201",
        "versao_cnae": "2.3",
    },
    "cnaes_secundarios": [
        {
            "codigo": "6202300",
            "descricao": "Desenvolvimento de programas de computador sob encomenda",
            "secao": "J",
            "codigo_classe": "6201",
            "versao_cnae": "2.3",
        }
    ],
    "score_confianca": 0.87,
    "permite_mei": False,
    "motivo_nao_mei": "Atividade vedada ao MEI",
    "regimes_compativeis": ["simples", "lucro_presumido"],
    "palavras_detectadas": ["software", "desenvolvimento"],
    "justificativa": "Alta correspondência com CNAE 62.01-5",
}


def _mock_user():
    u = MagicMock(spec=User)
    u.id = 1
    return u


# ---------------------------------------------------------------------------
# D1.1 — 200 sucesso com valores default
# ---------------------------------------------------------------------------

def test_d1_recomendar_cnae_sucesso_default_retorna_200(monkeypatch):
    calls = []

    def fake_recomendar(descricao_actividade, porte, max_resultados):
        calls.append((descricao_actividade, porte, max_resultados))
        return _fake_resultado()

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fake_recomendar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/recomendar-cnae", json={
                "descricao_actividade": "desenvolvimento de software",
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == _BODY_ESPERADO
    assert len(calls) == 1
    assert calls[0][0] == "desenvolvimento de software"
    assert calls[0][1] == "me"   # default
    assert calls[0][2] == 5      # default


# ---------------------------------------------------------------------------
# D1.2 — 200 sucesso com max_resultados explícito
# ---------------------------------------------------------------------------

def test_d1_recomendar_cnae_max_resultados_explicito_retorna_200(monkeypatch):
    calls = []

    def fake_recomendar(descricao_actividade, porte, max_resultados):
        calls.append((descricao_actividade, porte, max_resultados))
        return _fake_resultado()

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fake_recomendar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/recomendar-cnae", json={
                "descricao_actividade": "consultoria empresarial",
                "porte": "epp",
                "max_resultados": 10,
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == _BODY_ESPERADO
    assert len(calls) == 1
    assert calls[0][0] == "consultoria empresarial"
    assert calls[0][1] == "epp"
    assert calls[0][2] == 10


# ---------------------------------------------------------------------------
# D1.3 — 422 sem descricao_actividade
# ---------------------------------------------------------------------------

def test_d1_recomendar_cnae_sem_descricao_retorna_422(monkeypatch):
    def fail_recomendar(*_a, **_k):
        raise AssertionError("recomendar_cnaes não deve ser chamado sem descricao_actividade")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fail_recomendar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/recomendar-cnae", json={
                "porte": "me",
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422


# ---------------------------------------------------------------------------
# D1.4 — 422 porte inválido
# ---------------------------------------------------------------------------

def test_d1_recomendar_cnae_porte_invalido_retorna_422(monkeypatch):
    def fail_recomendar(*_a, **_k):
        raise AssertionError("recomendar_cnaes não deve ser chamado com porte inválido")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fail_recomendar)
    app.dependency_overrides[get_usuario_atual] = lambda: _mock_user()

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/recomendar-cnae", json={
                "descricao_actividade": "comercio varejista",
                "porte": "invalido",
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422


# ---------------------------------------------------------------------------
# D1.5 — 401 sem autenticação
# ---------------------------------------------------------------------------

def test_d1_recomendar_cnae_sem_auth_retorna_401(monkeypatch):
    def fail_recomendar(*_a, **_k):
        raise AssertionError("recomendar_cnaes não deve ser chamado sem auth")

    monkeypatch.setattr(formalizacao_router, "recomendar_cnaes", fail_recomendar)

    def _user_401():
        raise HTTPException(status_code=401, detail="Não autenticado")

    app.dependency_overrides[get_usuario_atual] = _user_401

    try:
        with TestClient(app) as c:
            res = c.post("/formalizacao/recomendar-cnae", json={
                "descricao_actividade": "comercio varejista",
            })
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 401
    assert res.json() == {"detail": "Não autenticado"}
