import base64
import copy
import json
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
PDF_BASE64 = base64.b64encode(b"%PDF-1.7\ncontract fixture\n%%EOF").decode("ascii")
BARCODE = [
    "858900000008",
    "860503282026",
    "608201234567",
    "890123456789",
]
PRIVATE_MARKERS = (
    "dados_oficiais",
    "raw_envelope",
    "mensagens",
    "transport-private",
    "private-official-text",
    "observacao1",
    "observacao2",
    "observacao3",
    "composicao",
    "consumer-secret-classified",
    "secret.pfx",
    "access-token-classified",
    "formula-interna-86.05",
)
BLOCKED_502 = {
    "bloqueado": True,
    "estado_l3": "bloqueado",
    "tipo_bloqueio": "AUTORIDADE_OFICIAL_MEI_FALHOU",
}


def _empresa(**overrides):
    values = {
        "id": 41,
        "status_empresa": "ativa",
        "regime_tributario": "mei",
        "cnpj": "12.345.678/0001-90",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _official_pdf_data(*, valor_total=86.05, detail_overrides=None, **document_overrides):
    detail = {
        "periodoApuracao": "202607",
        "numeroDocumento": "12345678901234567",
        "dataVencimento": "20260820",
        "dataLimiteAcolhimento": "20260820",
        "valores": {
            "principal": 86.05,
            "multa": 0.0,
            "juros": 0.0,
            "total": valor_total,
        },
        "observacao1": "private-official-text observacao1",
        "observacao2": "private-official-text observacao2",
        "observacao3": "private-official-text observacao3",
        "composicao": [
            {"codigo": "0151", "denominacao": "private-official-text"}
        ],
    }
    if detail_overrides:
        detail.update(detail_overrides)
    document = {
        "pdf": PDF_BASE64,
        "cnpjCompleto": "12345678000190",
        "detalhamento": detail,
        "resultadoFormulaInterna": "formula-interna-86.05",
    }
    document.update(document_overrides)
    return json.dumps([document], separators=(",", ":"))


def _official_barcode_data(
    *, valor_total=86.05, detail_overrides=None, **document_overrides
):
    detail = {
        "periodoApuracao": "202607",
        "numeroDocumento": "12345678901234567",
        "dataVencimento": "20260820",
        "dataLimiteAcolhimento": "20260820",
        "valores": {
            "principal": 86.05,
            "multa": 0.0,
            "juros": 0.0,
            "total": valor_total,
        },
        "codigoDeBarras": BARCODE,
        "observacao1": "private-official-text observacao1",
        "observacao2": "private-official-text observacao2",
        "observacao3": "private-official-text observacao3",
        "composicao": [
            {"codigo": "0151", "denominacao": "private-official-text"}
        ],
    }
    if detail_overrides:
        detail.update(detail_overrides)
    document = {
        "cnpjCompleto": "12345678000190",
        "razaoSocial": "private-official-text",
        "detalhamento": [detail],
        "resultadoFormulaInterna": "formula-interna-86.05",
    }
    document.update(document_overrides)
    return json.dumps([document], separators=(",", ":"))


def _mutated_data(data, mutation):
    payload = json.loads(data)
    mutation(payload[0])
    return json.dumps(payload, separators=(",", ":"))


class StubClient:
    def __init__(self, data=None, messages=None, error=None):
        self.data = _official_pdf_data() if data is None else data
        self.messages = (
            [{"codigo": "INFO", "texto": "private-official-text"}]
            if messages is None
            else messages
        )
        self.error = error
        self.calls = []

    def request(self, service, contribuinte, periodo_apuracao):
        self.calls.append((service, contribuinte, periodo_apuracao))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            data=self.data,
            messages=self.messages,
            raw_envelope={
                "raw_envelope": "private-official-text",
                "pfx": "/private/secret.pfx",
                "token": "access-token-classified",
            },
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


def _assert_private_data_absent(response):
    serialized = response.text
    for marker in PRIVATE_MARKERS:
        assert marker not in serialized


def _assert_sanitized_502(response):
    assert response.status_code == 502
    assert _detail(response) == BLOCKED_502
    _assert_private_data_absent(response)


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
def test_identity_and_service_are_derived_and_official_response_is_normalized(
    client, monkeypatch, isolated_route, stored_cnpj, formato, service, canonical
):
    app.dependency_overrides[tenant_empresa] = lambda: _empresa(cnpj=stored_cnpj)
    official_data = (
        _official_pdf_data(cnpjCompleto=canonical)
        if formato == "pdf"
        else _official_barcode_data(cnpjCompleto=canonical)
    )
    stub = StubClient(data=official_data)
    composed = _install_client(monkeypatch, isolated_route, stub)
    response = client.post(ROUTE, json={"periodo_apuracao": "202607", "formato": formato})
    assert response.status_code == 200
    assert composed == [True]
    assert stub.calls == [(service, canonical, "202607")]
    expected_document = {
        "cnpj": canonical,
        "periodo_apuracao": "202607",
        "numero_documento": "12345678901234567",
        "data_vencimento": "20260820",
        "data_limite_acolhimento": "20260820",
        "valor_total": 86.05,
        "pdf_base64": PDF_BASE64,
    }
    if formato == "codigo_barras":
        expected_document.pop("pdf_base64")
        expected_document["codigo_barras"] = BARCODE
    assert response.json() == {
        "empresa_id": 41,
        "periodo_apuracao": "202607",
        "formato": formato,
        "servico": service,
        "origem_oficial": "SERPRO_PGMEI",
        "estado_oficial": "emitido",
        "documento": expected_document,
    }
    _assert_private_data_absent(response)


def test_provider_composes_once_and_reuses_client(client, monkeypatch, isolated_route):
    stub = StubClient()
    composed = _install_client(monkeypatch, isolated_route, stub)
    client.post(ROUTE, json=VALID_BODY)
    client.post(ROUTE, json=VALID_BODY)
    assert composed == [True]
    assert len(stub.calls) == 2


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        ("[Aviso-PGMEI-MSG_13011]", "DEBITO_EM_DIVIDA_ATIVA"),
        ("[Aviso-PGMEI-MSG_23017]", "VALOR_INFERIOR_MINIMO"),
        ("[Aviso-PGMEI-MSG_23018]", "PERIODO_JA_PAGO"),
        ("[Aviso-PGMEI-MSG_23019]", "SEM_DAS_A_EMITIR"),
    ],
)
@pytest.mark.parametrize(
    ("formato", "service"),
    [("pdf", "GERARDASPDF21"), ("codigo_barras", "GERARDASCODBARRA22")],
)
def test_known_official_non_issuance_is_mapped_without_private_text(
    client, monkeypatch, isolated_route, code, reason, formato, service
):
    messages = [{"codigo": code, "texto": "private-official-text transport-private"}]
    stub = StubClient(data="", messages=messages)
    _install_client(monkeypatch, isolated_route, stub)
    response = client.post(
        ROUTE, json={"periodo_apuracao": "202607", "formato": formato}
    )
    assert response.status_code == 200
    assert response.json() == {
        "empresa_id": 41,
        "periodo_apuracao": "202607",
        "formato": formato,
        "servico": service,
        "origem_oficial": "SERPRO_PGMEI",
        "estado_oficial": "nao_emitido",
        "motivo_oficial": reason,
        "documento": None,
    }
    _assert_private_data_absent(response)


@pytest.mark.parametrize(
    ("case", "data"),
    [
        ("invalid_json", "not-json private-official-text"),
        ("root_object", json.dumps({"documento": json.loads(_official_pdf_data())[0]})),
        ("empty_without_known_notice", "[]"),
        (
            "multiple_documents",
            json.dumps(
                [json.loads(_official_pdf_data())[0], json.loads(_official_pdf_data())[0]]
            ),
        ),
        ("document_is_not_object", json.dumps(["private-official-text"])),
        ("pdf_detail_is_not_object", _official_pdf_data(detalhamento=[])),
    ],
)
def test_malformed_official_shapes_fail_closed_and_sanitized(
    client, monkeypatch, isolated_route, case, data
):
    messages = (
        [{"codigo": "INFO", "texto": "private-official-text"}]
        if case == "empty_without_known_notice"
        else None
    )
    stub = StubClient(data=data, messages=messages)
    _install_client(monkeypatch, isolated_route, stub)
    _assert_sanitized_502(client.post(ROUTE, json=VALID_BODY))


@pytest.mark.parametrize(
    ("formato", "data"),
    [
        (
            "pdf",
            _mutated_data(
                _official_pdf_data(),
                lambda document: document.update(
                    {"detalhamento": [document["detalhamento"]]}
                ),
            ),
        ),
        (
            "codigo_barras",
            _mutated_data(
                _official_barcode_data(),
                lambda document: document.update(
                    {"detalhamento": document["detalhamento"][0]}
                ),
            ),
        ),
        (
            "pdf",
            _mutated_data(
                _official_pdf_data(),
                lambda document: document["detalhamento"].pop("valores"),
            ),
        ),
        (
            "pdf",
            _official_pdf_data(detail_overrides={"valores": []}),
        ),
        (
            "pdf",
            _mutated_data(
                _official_pdf_data(),
                lambda document: document["detalhamento"]["valores"].pop("total"),
            ),
        ),
    ],
)
def test_service_specific_detail_and_values_shapes_fail_closed(
    client, monkeypatch, isolated_route, formato, data
):
    stub = StubClient(data=data)
    _install_client(monkeypatch, isolated_route, stub)
    response = client.post(
        ROUTE, json={"periodo_apuracao": "202607", "formato": formato}
    )
    _assert_sanitized_502(response)


@pytest.mark.parametrize(
    ("level", "field", "value"),
    [
        ("document", "cnpjCompleto", "99999999000199"),
        ("detail", "periodoApuracao", "202608"),
        ("detail", "numeroDocumento", "1234"),
        ("detail", "numeroDocumento", "１２３４５６７８９０１２３４５６７"),
        ("detail", "dataVencimento", "20260230"),
        ("detail", "dataVencimento", "2026-08-20"),
        ("detail", "dataLimiteAcolhimento", "20261301"),
        ("values", "total", True),
        ("values", "total", -0.01),
        ("values", "total", float("nan")),
        ("values", "total", float("inf")),
        ("values", "total", float("-inf")),
    ],
)
def test_divergent_official_metadata_fails_closed_and_sanitized(
    client, monkeypatch, isolated_route, level, field, value
):
    if level == "document":
        data = _official_pdf_data(**{field: value})
    elif level == "detail":
        data = _official_pdf_data(detail_overrides={field: value})
    else:
        assert field == "total"
        data = _official_pdf_data(valor_total=value)
    stub = StubClient(data=data)
    _install_client(monkeypatch, isolated_route, stub)
    _assert_sanitized_502(client.post(ROUTE, json=VALID_BODY))


@pytest.mark.parametrize(
    "pdf_value",
    [
        "%%%not-base64%%%",
        base64.b64encode(b"not a PDF").decode("ascii"),
    ],
)
def test_invalid_pdf_fails_closed_and_sanitized(
    client, monkeypatch, isolated_route, pdf_value
):
    stub = StubClient(data=_official_pdf_data(pdf=pdf_value))
    _install_client(monkeypatch, isolated_route, stub)
    _assert_sanitized_502(client.post(ROUTE, json=VALID_BODY))


@pytest.mark.parametrize(
    "barcode",
    [
        None,
        [],
        BARCODE[:3],
        [*BARCODE, "123"],
        [BARCODE[0] + " ", *BARCODE[1:]],
        [BARCODE[0] + "\t", *BARCODE[1:]],
        ["１２３４５６７８９０１２", *BARCODE[1:]],
        ["85890000000A", *BARCODE[1:]],
    ],
)
def test_invalid_barcode_fails_closed_and_sanitized(
    client, monkeypatch, isolated_route, barcode
):
    if barcode is None:
        data = _mutated_data(
            _official_barcode_data(),
            lambda document: document["detalhamento"][0].pop("codigoDeBarras"),
        )
        assert "codigoDeBarras" not in json.loads(data)[0]["detalhamento"][0]
    else:
        data = _official_barcode_data(
            detail_overrides={"codigoDeBarras": barcode}
        )
    stub = StubClient(data=data)
    _install_client(monkeypatch, isolated_route, stub)
    response = client.post(
        ROUTE, json={"periodo_apuracao": "202607", "formato": "codigo_barras"}
    )
    _assert_sanitized_502(response)


def test_unknown_notice_with_empty_data_fails_closed_and_sanitized(
    client, monkeypatch, isolated_route
):
    stub = StubClient(
        data="",
        messages=[{"codigo": "[Aviso-PGMEI-MSG_99999]", "texto": "private-official-text"}],
    )
    _install_client(monkeypatch, isolated_route, stub)
    _assert_sanitized_502(client.post(ROUTE, json=VALID_BODY))


@pytest.mark.parametrize(
    "messages",
    [
        None,
        "[Aviso-PGMEI-MSG_13011] private-official-text",
        {"codigo": "[Aviso-PGMEI-MSG_13011]"},
        [],
        [None],
        [{"texto": "private-official-text"}],
        [{"codigo": 13011, "texto": "private-official-text"}],
        [{"codigo": "[Aviso-PGMEI-MSG_13011] extra", "texto": "private-official-text"}],
    ],
)
def test_malformed_messages_with_empty_data_fail_closed_and_sanitized(
    client, monkeypatch, isolated_route, messages
):
    stub = StubClient(data="", messages=copy.deepcopy(messages))
    if messages is None:
        stub.messages = None
    _install_client(monkeypatch, isolated_route, stub)
    _assert_sanitized_502(client.post(ROUTE, json=VALID_BODY))


@pytest.mark.parametrize(
    "error",
    [PgmeiClientError("transport-private"), RuntimeError("pfx=/private/secret.pfx")],
)
def test_client_failures_are_sanitized(client, monkeypatch, isolated_route, error):
    stub = StubClient(error=error)
    _install_client(monkeypatch, isolated_route, stub)
    _assert_sanitized_502(client.post(ROUTE, json=VALID_BODY))


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
    _assert_private_data_absent(response)


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
    client.post(ROUTE, json=VALID_BODY)
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
