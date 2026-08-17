"""
B13-OPS-13A — Testes de bloqueio de tempo normativo nos endpoints HTTP.

Prova que os endpoints fiscais MEI bloqueiam com 422 estruturado
quando ano_referencia/data_referencia está ausente, e calculam
normalmente quando presente.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import get_usuario_atual


@pytest.fixture
def client_auth():
    """Cliente autenticado com mock de auth e paywall liberado."""
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.email = "b13ops13a@test.local"
    mock_user.consulta_paga = True
    app.dependency_overrides[get_usuario_atual] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _payload_bloqueio_valido(detail: dict) -> None:
    assert detail.get("bloqueado") is True
    assert detail.get("tipo_bloqueio") == "TEMPO_NORMATIVO_AUSENTE"
    assert detail.get("estado_l3") == "bloqueado"


# ---------------------------------------------------------------------------
# 1 e 2 — /imposto/calcular (MEI)
# ---------------------------------------------------------------------------

def test_imposto_calcular_mei_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_imposto_calcular_mei_com_ano_sem_atividade_bloqueia(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
            "ano_referencia": 2026,
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["tipo_bloqueio"] == "ATIVIDADE_MEI_AUSENTE"


# ---------------------------------------------------------------------------
# 3 — /relatorio/mei_tax
# ---------------------------------------------------------------------------

def test_relatorio_mei_tax_sem_autoridade_oficial_bloqueia(client_auth):
    res = client_auth.post(
        "/relatorio/mei_tax",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 503
    assert (
        res.json()["detail"]["tipo_bloqueio"]
        == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    )


# ---------------------------------------------------------------------------
# 4 — /relatorio/imposto-pdf
# ---------------------------------------------------------------------------

def test_relatorio_imposto_pdf_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/relatorio/imposto-pdf",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 503
    assert (
        res.json()["detail"]["tipo_bloqueio"]
        == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    )
    assert res.headers.get("content-type") != "application/pdf"
    assert not res.content.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# 5 — assistente_service fluxo MEI sem ano
# ---------------------------------------------------------------------------

def test_assistente_mei_sem_ano_pede_ano_referencia():
    from app.services.assistente_service import _resposta_assistente_mei

    resultado = _resposta_assistente_mei("quanto eu pago de MEI com faturamento de 5000")

    assert resultado.get("bloqueado") is True
    assert resultado.get("tipo_bloqueio") == "TEMPO_NORMATIVO_AUSENTE"
    assert resultado.get("estado_l3") == "bloqueado"
    assert "ano" in resultado.get("resposta", "").lower()


def test_simples_nacional_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I"},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_simples_nacional_com_ano_referencia_calcula(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "anexo": "I", "ano_referencia": 2026},
    )
    assert res.status_code == 200
    assert res.json()["_ano_referencia"] == 2026

def test_simples_nacional_com_ano_sem_anexo_bloqueia_na_borda(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={"rbt12": 360000.0, "ano_referencia": 2026},
    )

    assert res.status_code == 422
    erros = res.json().get("detail", [])
    assert any(
        erro.get("loc") == ["body", "anexo"]
        and erro.get("type") == "missing"
        for erro in erros
    )


def test_simples_nacional_acima_limite_bloqueia_http(client_auth):
    res = client_auth.post(
        "/imposto/simples-nacional",
        json={
            "rbt12": 4_800_001.0,
            "receita_mes": 400_000.0,
            "anexo": "I",
            "ano_referencia": 2026,
        },
    )

    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail.get("bloqueado") is True
    assert detail.get("tipo_bloqueio") == "LIMITE_SIMPLES_NACIONAL_EXCEDIDO"
    assert detail.get("estado_l3") == "bloqueado"
    assert "das_mensal" not in detail


def test_calcular_imposto_simples_nacional_sem_ano_bloqueia():
    from app.services.imposto_service import calcular_imposto_simples_nacional
    from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError
    import pytest as _pytest

    with _pytest.raises(TempoNormativoAusenteError):
        calcular_imposto_simples_nacional(rbt12=360000.0, anexo="I")


def test_calcular_imposto_simples_nacional_com_ano_retorna_metadados():
    from app.services.imposto_service import calcular_imposto_simples_nacional

    resultado = calcular_imposto_simples_nacional(rbt12=360000.0, anexo="I", ano_referencia=2026)
    assert resultado["_ano_referencia"] == 2026
    assert resultado["_estado_temporal"] == "resolvido"

def test_calcular_imposto_simples_nacional_com_ano_sem_anexo_bloqueia():
    from app.services.imposto_service import calcular_imposto_simples_nacional
    from app.services.tax_engines.base_tax_engine import (
        AnexoSimplesNaoDeterminadoError,
    )
    import pytest as _pytest

    with _pytest.raises(AnexoSimplesNaoDeterminadoError):
        calcular_imposto_simples_nacional(
            rbt12=360000.0,
            ano_referencia=2026,
        )


def test_calcular_imposto_simples_nacional_anexo_vazio_bloqueia():
    from app.services.imposto_service import calcular_imposto_simples_nacional
    from app.services.tax_engines.base_tax_engine import (
        AnexoSimplesNaoDeterminadoError,
    )
    import pytest as _pytest

    with _pytest.raises(AnexoSimplesNaoDeterminadoError):
        calcular_imposto_simples_nacional(
            rbt12=360000.0,
            anexo="   ",
            ano_referencia=2026,
        )

def test_calcular_imposto_simples_nacional_anexo_invalido_bloqueia():
    from app.services.imposto_service import calcular_imposto_simples_nacional
    import pytest as _pytest

    with _pytest.raises(ValueError, match="Anexo do Simples Nacional invalido"):
        calcular_imposto_simples_nacional(
            rbt12=360000.0,
            anexo="VI",
            ano_referencia=2026,
        )

def test_responder_empresa_acima_limite_bloqueia():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.services.assistente_service import responder_empresa

    resultado = responder_empresa(
        "simples nacional Anexo I com faturamento de 500 mil por mes em 2026",
        SimpleNamespace(empresas=[]),
        MagicMock(),
    )

    assert resultado.get("bloqueado") is True
    assert resultado.get("tipo_bloqueio") == "LIMITE_SIMPLES_NACIONAL_EXCEDIDO"
    assert resultado.get("estado_l3") == "bloqueado"
    assert resultado.get("requires_payment") is False
    assert resultado.get("analysis_type") == "simples_nacional"


def test_calcular_imposto_simples_nacional_no_limite_calcula():
    from app.services.imposto_service import calcular_imposto_simples_nacional

    resultado = calcular_imposto_simples_nacional(
        rbt12=4_800_000.0,
        receita_mes=400_000.0,
        anexo="I",
        ano_referencia=2026,
    )

    assert resultado["rbt12"] == 4_800_000.0
    assert resultado["faixa_simples_max"] == 4_800_000
    assert "das_mensal" in resultado


def test_calcular_imposto_simples_nacional_acima_limite_bloqueia():
    from app.services.imposto_service import calcular_imposto_simples_nacional
    from app.services.tax_engines.base_tax_engine import (
        LimiteSimplesNacionalExcedidoError,
    )
    import pytest as _pytest

    with _pytest.raises(
        LimiteSimplesNacionalExcedidoError,
        match=r"O faturamento informado excede o limite suportado por esta simulação do Simples Nacional\.",
    ):
        calcular_imposto_simples_nacional(
            rbt12=4_800_001.0,
            receita_mes=400_000.0,
            anexo="I",
            ano_referencia=2026,
        )


# ---------------------------------------------------------------------------
# CPF — tempo normativo (B13-OPS-13D)
# ---------------------------------------------------------------------------

def test_cpf_dashboard_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/cpf/dashboard",
        json={"faturamento_mensal": 5000.0, "despesas": 0},
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_cpf_dashboard_com_ano_referencia_calcula(client_auth):
    res = client_auth.post(
        "/cpf/dashboard",
        json={"faturamento_mensal": 5000.0, "despesas": 0, "ano_referencia": 2026},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["_ano_referencia"] == 2026
    assert body["_estado_temporal"] == "resolvido"


def test_imposto_calcular_cpf_sem_ano_referencia_bloqueia(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "CPF",
            "faturamento_mensal": 5000.0,
        },
    )
    assert res.status_code == 422
    _payload_bloqueio_valido(res.json()["detail"])


def test_imposto_calcular_cpf_com_ano_referencia_calcula(client_auth):
    res = client_auth.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "CPF",
            "faturamento_mensal": 5000.0,
            "ano_referencia": 2026,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tipo"] == "cpf"
    assert body["_ano_referencia"] == 2026


def test_assistente_cpf_sem_ano_pede_ano_referencia():
    from app.services.assistente_service import responder_cpf

    resultado = responder_cpf("quanto pago de imposto como autonomo com faturamento de 5000")

    assert resultado.get("bloqueado") is True
    assert resultado.get("tipo_bloqueio") == "TEMPO_NORMATIVO_AUSENTE"
    assert resultado.get("estado_l3") == "bloqueado"
    assert "ano" in resultado.get("resposta", "").lower()


def test_assistente_cpf_com_ano_calcula():
    from app.services.assistente_service import responder_cpf

    resultado = responder_cpf(
        "quanto pago de imposto como autonomo cpf com faturamento de 5000 em 2026"
    )

    assert resultado.get("bloqueado") is not True
    assert resultado.get("payload", {}).get("_ano_referencia") == 2026
