"""Controlled promotion keeps the frozen canary contract as the default."""

import pytest
from fastapi import HTTPException

from test_serpro_pgmei_official_route_contract import (
    ROUTE, VALID_BODY, StubClient, _empresa, _official_pdf_data,
    _install_client, _assert_private_data_absent, client, isolated_route,
)
from app.main import app
from app.security import tenant_empresa
from test_serpro_pgmei_tenant_binding_contract import (
    _register_login_and_accept_terms, _create_active_mei,
)


@pytest.fixture(autouse=True)
def access_mode(monkeypatch):
    monkeypatch.setenv("SERPRO_PGMEI_ACCESS_MODE", "tenant")


def test_tenant_mode_accepts_another_bound_company(client, isolated_route, monkeypatch):
    cnpj = "11222333000181"
    app.dependency_overrides[tenant_empresa] = lambda: _empresa(cnpj=cnpj)
    stub = StubClient(data=_official_pdf_data(cnpjCompleto=cnpj))
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 200
    assert composed == [True]
    assert stub.calls == [("GERARDASPDF21", cnpj, "202607")]
    _assert_private_data_absent(response)


def test_tenant_mode_rejects_real_cross_tenant_guard(client, isolated_route, monkeypatch):
    # Synthetic local accounts; use the actual security dependency, not a stub.
    app.dependency_overrides.pop(tenant_empresa)
    _, headers = _register_login_and_accept_terms(client, "promotion_a")
    other_email, _ = _register_login_and_accept_terms(client, "promotion_b")
    other_company = _create_active_mei(other_email, "promotion_b")
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(f"/imposto/mei/{other_company}/das", headers=headers, json=VALID_BODY)
    assert response.status_code == 403
    assert composed == []
    assert stub.calls == []


@pytest.mark.parametrize("mode", ["", "TENANT", "true", "*", "tenant "])
def test_unknown_mode_never_calls_provider(client, isolated_route, monkeypatch, mode):
    monkeypatch.setenv("SERPRO_PGMEI_ACCESS_MODE", mode)
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 403
    assert response.json()["detail"]["tipo_bloqueio"] == "SERPRO_PGMEI_MODO_ACESSO_INVALIDO"
    assert composed == []
    assert stub.calls == []


@pytest.mark.parametrize("mode", [None, "canary"])
def test_default_and_explicit_canary_still_reject_other_cnpj(
    client, isolated_route, monkeypatch, mode
):
    if mode is None:
        monkeypatch.delenv("SERPRO_PGMEI_ACCESS_MODE", raising=False)
    else:
        monkeypatch.setenv("SERPRO_PGMEI_ACCESS_MODE", mode)
    app.dependency_overrides[tenant_empresa] = lambda: _empresa(cnpj="11222333000181")
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 403
    assert response.json()["detail"]["tipo_bloqueio"] == "SERPRO_PGMEI_CANARY_NAO_AUTORIZADO"
    assert composed == []
    assert stub.calls == []


@pytest.mark.parametrize("failure", ["tenant", "economic", "economic_exception", "disabled"])
def test_tenant_mode_keeps_authority_boundaries(client, isolated_route, monkeypatch, failure):
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    if failure == "tenant":
        def denied():
            raise HTTPException(status_code=403)
        app.dependency_overrides[tenant_empresa] = denied
    elif failure == "economic":
        monkeypatch.setattr(isolated_route, "_tem_autoridade_economica_mei_competencia", lambda **kw: False)
    elif failure == "economic_exception":
        def failed(**kw):
            raise RuntimeError("storage unavailable")
        monkeypatch.setattr(isolated_route, "_tem_autoridade_economica_mei_competencia", failed)
    else:
        monkeypatch.setattr(isolated_route, "compose_serpro_pgmei", lambda: None)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == (503 if failure == "disabled" else 403)
    assert composed == []
    assert stub.calls == []


@pytest.mark.parametrize("fields", [
    {"status_empresa": "em_abertura"},
    {"regime_tributario": "simples"},
    {"cnpj": "invalid"},
])
def test_tenant_mode_keeps_company_eligibility(client, isolated_route, monkeypatch, fields):
    app.dependency_overrides[tenant_empresa] = lambda: _empresa(**fields)
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json=VALID_BODY)
    assert response.status_code == 422
    assert composed == []
    assert stub.calls == []
