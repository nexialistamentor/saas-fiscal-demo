from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import limiter
from app.security import tenant_empresa
from app.services.serpro_pgmei_client import PgmeiClientError


ROUTE = "/imposto/mei/41/das"
VALID_BODY = {"periodo_apuracao": "202607", "formato": "pdf"}


def _empresa(**overrides):
    values = {
        "id": 41,
        "status_empresa": "ativa",
        "regime_tributario": "mei",
        "cnpj": "12.345.678/0001-90",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StubClient:
    def __init__(self, data="DADOS-OFICIAIS", error=None):
        self.data = data
        self.error = error
        self.calls = []

    def request(self, service, contribuinte, periodo_apuracao):
        self.calls.append((service, contribuinte, periodo_apuracao))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            data=self.data,
            messages={"private": "message"},
            raw_envelope={"secret": "raw"},
        )


@pytest.fixture(autouse=True)
def isolated_route(monkeypatch):
    import app.routes.imposto_router as imposto_router

    app.dependency_overrides[tenant_empresa] = lambda: _empresa()
    monkeypatch.delenv("SERPRO_PGMEI_ENABLED", raising=False)
    limiter.enabled = False
    if hasattr(imposto_router, "_get_serpro_pgmei_client"):
        imposto_router._get_serpro_pgmei_client.cache_clear()
    yield imposto_router
    app.dependency_overrides.clear()
    if hasattr(imposto_router, "_get_serpro_pgmei_client"):
        imposto_router._get_serpro_pgmei_client.cache_clear()
    limiter.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _install_client(monkeypatch, imposto_router, stub):
    composed = []

    def compose():
        composed.append(True)
        return stub

    monkeypatch.setattr(imposto_router, "compose_serpro_pgmei", compose)
    imposto_router._get_serpro_pgmei_client.cache_clear()
    return composed


def _detail(response):
    return response.json()["detail"]


def test_route_exists_and_gate_is_default_off_without_transport(client):
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 503
    assert _detail(response) == {
        "bloqueado": True,
        "estado_l3": "bloqueado",
        "tipo_bloqueio": "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL",
    }


def test_tenant_denial_precedes_composition_and_client(client, monkeypatch, isolated_route):
    effects = []

    def denied():
        raise HTTPException(status_code=403, detail="empresa nao autorizada")

    app.dependency_overrides[tenant_empresa] = denied
    monkeypatch.setattr(isolated_route, "compose_serpro_pgmei", lambda: effects.append("compose"))
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 403
    assert effects == []


@pytest.mark.parametrize(
    ("empresa", "tipo"),
    [
        (_empresa(status_empresa="inativa"), "EMPRESA_MEI_INATIVA"),
        (_empresa(status_empresa="Ativa"), "EMPRESA_MEI_INATIVA"),
        (_empresa(regime_tributario="simples_nacional"), "EMPRESA_NAO_MEI"),
        (_empresa(regime_tributario="MEI"), "EMPRESA_NAO_MEI"),
        (_empresa(cnpj=None), "CNPJ_EMPRESA_INVALIDO"),
        (_empresa(cnpj="12.345.678/0001-AA"), "CNPJ_EMPRESA_INVALIDO"),
        (_empresa(cnpj="１２３４５６７８０００１９０"), "CNPJ_EMPRESA_INVALIDO"),
        (_empresa(cnpj="12 345678000190"), "CNPJ_EMPRESA_INVALIDO"),
    ],
)
def test_ineligible_company_never_composes(client, monkeypatch, isolated_route, empresa, tipo):
    effects = []
    app.dependency_overrides[tenant_empresa] = lambda: empresa
    monkeypatch.setattr(isolated_route, "compose_serpro_pgmei", lambda: effects.append("compose"))
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 422
    assert _detail(response) == {
        "bloqueado": True,
        "estado_l3": "bloqueado",
        "tipo_bloqueio": tipo,
    }
    assert effects == []


@pytest.mark.parametrize("field", ["empresa_id", "cnpj", "contribuinte", "servico", "credencial"])
def test_body_cannot_select_identity_service_or_credentials(
    client, monkeypatch, isolated_route, field
):
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json={**VALID_BODY, field: "attacker-controlled"})
    assert response.status_code == 422
    assert composed == []
    assert stub.calls == []


@pytest.mark.parametrize(
    ("periodo", "formato"),
    [("202600", "pdf"), ("202613", "pdf"), ("２０２６０７", "pdf"), ("2026 7", "pdf"), ("202607", "PDF")],
)
def test_body_period_and_format_are_strict(client, monkeypatch, isolated_route, periodo, formato):
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json={"periodo_apuracao": periodo, "formato": formato})
    assert response.status_code == 422
    assert composed == []
    assert stub.calls == []


@pytest.mark.parametrize(
    ("stored_cnpj", "formato", "service", "canonical"),
    [
        ("12.345.678/0001-90", "pdf", "GERARDASPDF21", "12345678000190"),
        ("ab.cde.f12/3456-78", "codigo_barras", "GERARDASCODBARRA22", "ABCDEF12345678"),
    ],
)
def test_cnpj_is_canonicalized_and_format_maps_exclusively(
    client, monkeypatch, isolated_route, stored_cnpj, formato, service, canonical
):
    app.dependency_overrides[tenant_empresa] = lambda: _empresa(cnpj=stored_cnpj)
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(
        ROUTE, json={"periodo_apuracao": "202607", "formato": formato}
    )
    assert response.status_code == 200
    assert composed == [True]
    assert stub.calls == [(service, canonical, "202607")]
    assert response.json() == {
        "empresa_id": 41,
        "periodo_apuracao": "202607",
        "formato": formato,
        "servico": service,
        "origem_oficial": "SERPRO_PGMEI",
        "dados_oficiais": "DADOS-OFICIAIS",
    }


def test_provider_composes_once_and_reuses_client(client, monkeypatch, isolated_route):
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    assert client.post(ROUTE, json=VALID_BODY).status_code == 200
    assert client.post(ROUTE, json=VALID_BODY).status_code == 200
    assert composed == [True]
    assert len(stub.calls) == 2


@pytest.mark.parametrize("data", ["", "   ", None, 7, {}, []])
def test_divergent_official_data_fails_closed(client, monkeypatch, isolated_route, data):
    stub = StubClient(data=data)
    _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 502
    assert _detail(response) == {
        "bloqueado": True,
        "estado_l3": "bloqueado",
        "tipo_bloqueio": "AUTORIDADE_OFICIAL_MEI_FALHOU",
    }


@pytest.mark.parametrize(
    "error",
    [PgmeiClientError("transport-private"), RuntimeError("pfx=/private/secret.pfx")],
)
def test_client_failures_are_sanitized(client, monkeypatch, isolated_route, error):
    stub = StubClient(error=error)
    _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 502
    serialized = response.text
    assert _detail(response) == {
        "bloqueado": True,
        "estado_l3": "bloqueado",
        "tipo_bloqueio": "AUTORIDADE_OFICIAL_MEI_FALHOU",
    }
    assert "transport-private" not in serialized
    assert "secret.pfx" not in serialized


def test_composition_failure_is_sanitized_503(client, monkeypatch, isolated_route):
    def fail():
        raise RuntimeError("consumer-secret-classified /private/client.pfx")

    monkeypatch.setattr(isolated_route, "compose_serpro_pgmei", fail)
    isolated_route._get_serpro_pgmei_client.cache_clear()
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 503
    assert _detail(response) == {
        "bloqueado": True,
        "estado_l3": "bloqueado",
        "tipo_bloqueio": "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL",
    }
    assert "consumer-secret-classified" not in response.text
    assert "client.pfx" not in response.text


def test_official_route_never_calls_internal_producers(client, monkeypatch, isolated_route):
    forbidden = []
    monkeypatch.setattr(isolated_route, "executar_analise", lambda *a, **k: forbidden.append("analysis"))
    monkeypatch.setattr(
        isolated_route,
        "calcular_imposto_simples",
        lambda *a, **k: forbidden.append("simples"),
    )
    monkeypatch.setattr(
        isolated_route,
        "calcular_imposto_simples_nacional",
        lambda *a, **k: forbidden.append("simples_nacional"),
    )
    stub = StubClient()
    _install_client(monkeypatch, isolated_route, stub)
    assert client.post(ROUTE, json=VALID_BODY).status_code == 200
    assert forbidden == []


def test_existing_calcular_mei_contract_remains_blocked(client):
    response = client.post(
        "/imposto/calcular",
        json={
            "tipo_usuario": "MEI",
            "faturamento_mensal": 5000,
            "atividade": "comercio",
            "ano_referencia": 2026,
        },
    )
    assert response.status_code == 503
    detail = _detail(response)
    assert detail["bloqueado"] is True
    assert detail["tipo_bloqueio"] == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    for forbidden in ("imposto_mensal", "imposto_anual", "das"):
        assert forbidden not in detail
