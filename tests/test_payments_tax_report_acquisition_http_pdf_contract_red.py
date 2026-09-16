"""RED: download HTTP canonico de uma aquisicao tax.report existente."""

from inspect import getsource, signature
from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.routes import relatorio_router
from app.security import get_usuario_atual
from app.services.tax_report_acquisition_pdf import TaxReportAcquisitionPdfError
from app.services.tax_report_acquisition_reader import TaxReportAcquisitionReadError


ROUTE_PATH = "/empresas/{empresa_id}/acquisitions/{acquisition_id}/pdf"
REQUEST_PATH = "/relatorio/empresas/21/acquisitions/601/pdf"


def _endpoint():
    matches = [
        route
        for route in relatorio_router.router.routes
        if getattr(route, "path", None) == ROUTE_PATH
        and "GET" in getattr(route, "methods", set())
    ]
    assert len(matches) == 1, (
        "rota canonica GET /relatorio/empresas/{empresa_id}/"
        "acquisitions/{acquisition_id}/pdf ainda nao existe"
    )
    return matches[0].endpoint


def _client():
    app = FastAPI()
    app.include_router(relatorio_router.router, prefix="/relatorio")
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(id=11)
    return TestClient(app)


def test_tax_report_acquisition_http_pdf_positive_contract_red(monkeypatch):
    _endpoint()
    acquisition = object()
    calls = []

    class FakeReader:
        def __init__(self, db):
            calls.append(("reader_init", db))

        def read(self, *, user_id, empresa_id, acquisition_id):
            calls.append(("read", user_id, empresa_id, acquisition_id))
            return acquisition

    class FakeRenderer:
        def render(self, *, acquisition, empresa_id):
            calls.append(("render", acquisition, empresa_id))
            return BytesIO(b"%PDF-http-contract")

    monkeypatch.setattr(relatorio_router, "TaxReportAcquisitionReader", FakeReader)
    monkeypatch.setattr(relatorio_router, "TaxReportAcquisitionPdfRenderer", FakeRenderer)

    with _client() as client:
        response = client.get(REQUEST_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"] == (
        "attachment; filename=relatorio-fiscal-601.pdf"
    )
    assert response.content.startswith(b"%PDF")
    assert calls[1:] == [
        ("read", 11, 21, 601),
        ("render", acquisition, 21),
    ]


def test_tax_report_acquisition_http_pdf_read_failure_is_closed_and_ordered_red(
    monkeypatch,
):
    _endpoint()
    renderer_calls = []

    class FakeReader:
        def __init__(self, db):
            pass

        def read(self, *, user_id, empresa_id, acquisition_id):
            raise TaxReportAcquisitionReadError(
                "binding existe, grant revoked, order=777, fingerprint=segredo"
            )

    class FakeRenderer:
        def render(self, *, acquisition, empresa_id):
            renderer_calls.append((acquisition, empresa_id))
            return BytesIO(b"%PDF-nao-deve-ser-gerado")

    monkeypatch.setattr(relatorio_router, "TaxReportAcquisitionReader", FakeReader)
    monkeypatch.setattr(relatorio_router, "TaxReportAcquisitionPdfRenderer", FakeRenderer)

    with _client() as client:
        response = client.get(REQUEST_PATH)

    assert response.status_code == 404
    assert response.json() == {"detail": "Aquisição indisponível."}
    assert renderer_calls == []
    for secret in ("binding", "revoked", "grant", "order", "fingerprint", "777"):
        assert secret not in response.text


def test_tax_report_acquisition_http_pdf_render_failure_is_closed_red(monkeypatch):
    _endpoint()

    class FakeReader:
        def __init__(self, db):
            pass

        def read(self, *, user_id, empresa_id, acquisition_id):
            return object()

    class FakeRenderer:
        def render(self, *, acquisition, empresa_id):
            raise TaxReportAcquisitionPdfError("renderer interno: segredo")

    monkeypatch.setattr(relatorio_router, "TaxReportAcquisitionReader", FakeReader)
    monkeypatch.setattr(relatorio_router, "TaxReportAcquisitionPdfRenderer", FakeRenderer)

    with _client() as client:
        response = client.get(REQUEST_PATH)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Aquisição indisponível para renderização."
    }
    assert "renderer interno" not in response.text
    assert "segredo" not in response.text


def test_tax_report_acquisition_http_pdf_path_validation_contract_red():
    endpoint = _endpoint()
    endpoint_signature = signature(endpoint)
    assert endpoint_signature.parameters["empresa_id"].annotation is int
    assert endpoint_signature.parameters["acquisition_id"].annotation is int

    with _client() as client:
        invalid_empresa = client.get(
            "/relatorio/empresas/nao-inteiro/acquisitions/601/pdf"
        )
        invalid_acquisition = client.get(
            "/relatorio/empresas/21/acquisitions/nao-inteiro/pdf"
        )

    assert invalid_empresa.status_code == 422
    assert invalid_acquisition.status_code == 422


def test_tax_report_acquisition_http_pdf_endpoint_authority_is_isolated_red():
    endpoint = _endpoint()
    source = getsource(endpoint)
    assert "TaxReportAcquisitionReader" in source
    assert "TaxReportAcquisitionPdfRenderer" in source
    for forbidden in (
        "_pagamento_confirmado",
        "consulta_paga",
        "relatorio.pago",
        ".pago",
        "Entitlement",
        "verificar_empresa_do_usuario",
        "RelatorioAnalise",
        "_gerar_pdf_relatorio_completo",
        "gerar_pdf_relatorio",
        "executar_analise",
        "executar_e_registrar_analise_xml",
    ):
        assert forbidden not in source

