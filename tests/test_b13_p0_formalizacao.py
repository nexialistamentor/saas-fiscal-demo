"""
Testes B13-P0 — bloqueadores Piloto 0 (formalização).
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual
from app.services.cnae_engine import recomendar_cnaes
from app.services.tax_engines.mei_constants import MEI_LIMITE_ANUAL_FATURAMENTO


@pytest.fixture
def client_auth():
    """Cliente autenticado com mock de auth — evita 401 nos endpoints."""
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "b13@test.local"

    app.dependency_overrides[get_usuario_atual] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# P1 — CNAE SaaS deve ser divisão 62 (não 5811/6110)
# ---------------------------------------------------------------------------
def test_p1_saas_cnae_divisao_62():
    r = recomendar_cnaes(
        "plataforma de software para ajudar empresas com impostos",
        "me",
    )
    assert r.cnae_principal_sugerido is not None
    codigo = r.cnae_principal_sugerido.codigo_subclasse
    assert codigo.startswith("62"), f"CNAE inesperado para SaaS: {codigo}"


# ---------------------------------------------------------------------------
# P2 — permite_mei coerente entre porte me e mei para mesma actividade
# ---------------------------------------------------------------------------
def test_p2_permite_mei_coerente_me_vs_mei():
    descricao = "desenvolvimento de software"
    r_me = recomendar_cnaes(descricao, "me")
    r_mei = recomendar_cnaes(descricao, "mei")
    assert r_me.permite_mei == r_mei.permite_mei


# ---------------------------------------------------------------------------
# P3 — endpoint recomendar-cnae responde 200 (auth mock)
# ---------------------------------------------------------------------------
def test_p3_endpoint_recomendar_cnae_200(client_auth):
    res = client_auth.post(
        "/formalizacao/recomendar-cnae",
        json={
            "descricao_actividade": "plataforma de software para impostos",
            "porte": "me",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["cnae_principal"]["codigo"].startswith("62")


# ---------------------------------------------------------------------------
# P4 — editora de livros → CNAE 58xx
# ---------------------------------------------------------------------------
def test_p4_editora_cnae_58xx():
    r = recomendar_cnaes("quero abrir uma editora de livros", "me")
    assert r.cnae_principal_sugerido is not None
    codigo = r.cnae_principal_sugerido.codigo_subclasse
    assert codigo.startswith("58"), f"CNAE inesperado para editora: {codigo}"


# ---------------------------------------------------------------------------
# P5 — endpoint simular-empresa responde 200 (auth mock)
# ---------------------------------------------------------------------------
def test_p5_endpoint_simular_empresa_200(client_auth):
    res = client_auth.post(
        "/formalizacao/simular-empresa",
        json={
            "descricao_actividade": "desenvolvimento de software",
            "porte": "me",
            "faturamento_anual": "120000",
            "folha_anual": "0",
            "atividade": "servicos",
        },
    )
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# P6 — MEI com faturamento acima do limite → permite_mei false + alerta
# ---------------------------------------------------------------------------
def test_p6_mei_faturamento_acima_limite(client_auth):
    acima = str(MEI_LIMITE_ANUAL_FATURAMENTO + 1)
    res = client_auth.post(
        "/formalizacao/simular-empresa",
        json={
            "descricao_actividade": "desenvolvimento de software",
            "porte": "mei",
            "faturamento_anual": acima,
            "folha_anual": "0",
            "atividade": "servicos",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["permite_mei"] is False
    assert len(data.get("alertas_mei", [])) > 0


def test_p6_mei_500k_sem_permite_mei_silencioso(client_auth):
    res = client_auth.post(
        "/formalizacao/simular-empresa",
        json={
            "descricao_actividade": "desenvolvimento de software",
            "porte": "mei",
            "faturamento_anual": "500000",
            "folha_anual": "0",
            "atividade": "servicos",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["permite_mei"] is False
    assert any("limite" in a.lower() for a in data.get("alertas_mei", []))


# ---------------------------------------------------------------------------
# P7 — faturamento zero/inválido → mensagem em português (não Pydantic cru)
# ---------------------------------------------------------------------------
def test_p7_faturamento_zero_mensagem_amigavel(client_auth):
    res = client_auth.post(
        "/formalizacao/simular-empresa",
        json={
            "descricao_actividade": "desenvolvimento de software",
            "porte": "me",
            "faturamento_anual": "0",
            "folha_anual": "0",
            "atividade": "servicos",
        },
    )
    assert res.status_code == 422, res.text
    corpo = res.text.lower()
    assert "input should be greater than 0" not in corpo
    assert "faturamento" in corpo


def test_mei_limite_constante_importavel():
    assert MEI_LIMITE_ANUAL_FATURAMENTO == Decimal("81000") or MEI_LIMITE_ANUAL_FATURAMENTO == 81_000
