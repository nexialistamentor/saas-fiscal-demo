"""RED: recuperaÃ§Ã£o server-side do checkout tax.report sem sessionStorage."""

import inspect
import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.routes import relatorio_router


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend-dashboard/src/App.jsx"
SERVICE = ROOT / "app/services/tax_report_checkout_recovery.py"

ROUTE_PATH = "/empresas/{empresa_id}/checkout-recovery"
OFFER_CODE = "tax-report-one-time-company"
CAPABILITY = "tax.report"
CONTEXT_KEY = "solveris.taxReportAcquisitionContext.v1"


def _route():
    return next(
        (
            route
            for route in relatorio_router.router.routes
            if isinstance(route, APIRoute)
            and route.path == ROUTE_PATH
            and route.methods == {"GET"}
        ),
        None,
    )


def _function_block(source: str, marker: str) -> str:
    assert marker in source, f"ausente funcao {marker!r}"
    start = source.index(marker)
    signature_start = source.index("(", start)

    depth = 0
    signature_end = None
    for pos in range(signature_start, len(source)):
        if source[pos] == "(":
            depth += 1
        elif source[pos] == ")":
            depth -= 1
            if depth == 0:
                signature_end = pos
                break

    assert signature_end is not None

    brace = source.index("{", signature_end)
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]

    raise AssertionError(f"corpo sem fechamento depois de {marker!r}")


def _service_source():
    assert SERVICE.is_file(), (
        "ausente app/services/tax_report_checkout_recovery.py"
    )
    return SERVICE.read_text(encoding="utf-8")


def test_recovery_service_is_read_only_and_uses_durable_chain_red():
    source = _service_source()

    for required in (
        "TaxReportCheckoutIntent",
        "OrdemCheckout",
        "CheckoutOfferGrant",
        "CheckoutOfferGrantCapability",
        OFFER_CODE,
        CAPABILITY,
        "checkout_idempotency_key",
        "idempotency_key",
        "relatorio_analise_id",
        "request_fingerprint",
        "checkout_url",
    ):
        assert required in source, f"recovery nao prova {required!r}"

    for forbidden in (
        ".commit(",
        ".rollback(",
        "MercadoPago",
        "CheckoutOfferGrant(",
        "CheckoutOfferGrantConsumption(",
        "TaxReportAcquisitionBinding(",
        "consulta_paga =",
        ".pago =",
        "payment_id =",
        "gerar_pdf",
    ):
        assert forbidden not in source, (
            f"recovery ganhou autoridade proibida: {forbidden}"
        )


def test_recovery_selects_latest_durable_checkout_before_interpreting_state_red():
    source = _service_source()

    assert "TaxReportCheckoutRecoveryError" in source
    assert "TaxReportCheckoutRecoveryResult" in source
    assert "class TaxReportCheckoutRecovery" in source
    assert re.search(
        r"def\s+resolve\(\s*self\s*,\s*\*\s*,"
        r"\s*user_id\s*,\s*empresa_id\s*,?\s*\)",
        source,
    )

    # A recuperaÃ§Ã£o Ã© da tentativa durÃ¡vel mais recente, nÃ£o "qualquer paid".
    assert "OrdemCheckout.criado_em.desc()" in source
    assert "OrdemCheckout.id.desc()" in source
    assert ".limit(1)" in source

    # SÃ³ depois de resolver a ordem mais recente o estado Ã© interpretado.
    assert '"paid"' in source
    assert '"pending"' in source


def test_recovery_paid_requires_canonical_grant_capability_red():
    source = _service_source()

    for required in (
        "CheckoutOfferGrant.ordem_id",
        "CheckoutOfferGrantCapability.grant_id",
        "CheckoutOfferGrantCapability.codigo",
        CAPABILITY,
        '"active"',
        '"exhausted"',
    ):
        assert required in source, (
            f"paid recovery nao prova cadeia comercial {required!r}"
        )


def test_recovery_http_endpoint_is_authenticated_and_read_only_red():
    route = _route()

    assert route is not None, f"ausente GET {ROUTE_PATH}"
    assert any(
        dependency.call is relatorio_router.get_usuario_atual
        for dependency in route.dependant.dependencies
    )

    source = inspect.getsource(route.endpoint)
    assert "TaxReportCheckoutRecovery" in source
    assert ".resolve(" in source
    assert "usuario_atual.id" in source
    assert "empresa_id" in source
    assert "status_code=404" in source
    assert "status_code=409" in source
    assert "status_code=503" in source


def test_frontend_recovers_only_when_local_context_is_absent_red():
    source = APP.read_text(encoding="utf-8")
    helper = _function_block(
        source,
        "async function recuperarTaxReportCheckoutDoServidor(",
    )

    assert CONTEXT_KEY in helper
    assert "sessionStorage.getItem" in helper
    assert (
        "${API_BASE}/relatorio/empresas/${empresaId}/checkout-recovery"
        in helper
    )
    assert 'method: "GET"' in helper or "method: 'GET'" in helper
    assert "Authorization" in helper
    assert "crypto.randomUUID" not in helper
    assert "/checkout/one-time" not in helper


def test_paid_recovery_restores_canonical_acquisition_context_red():
    source = APP.read_text(encoding="utf-8")
    helper = _function_block(
        source,
        "async function recuperarTaxReportCheckoutDoServidor(",
    )

    assert '"paid"' in helper or "'paid'" in helper
    assert CONTEXT_KEY in helper
    assert "relatorio_id" in helper
    assert "request_fingerprint" in helper
    assert "sessionStorage.setItem" in helper
    assert "retomarAquisicaoTaxReport" in helper


def test_pending_recovery_reuses_original_checkout_identity_red():
    source = APP.read_text(encoding="utf-8")
    helper = _function_block(
        source,
        "async function recuperarTaxReportCheckoutDoServidor(",
    )
    checkout = _function_block(source, "async function iniciarCheckout(")

    assert '"pending"' in helper or "'pending'" in helper
    assert "checkout_url" in helper
    assert "checkout_idempotency_key" in helper
    assert "relatorio_id" in helper
    assert "request_fingerprint" in helper
    assert "setResultadoXML" in helper
    assert "setTaxReportRecoveredCheckoutUrl" in helper
    assert "setTaxReportRecoveredIdempotencyKey" in helper

    # Se jÃ¡ houver URL, reutiliza exatamente o checkout existente.
    assert "taxReportRecoveredCheckoutUrl" in checkout
    assert "window.location.href = taxReportRecoveredCheckoutUrl" in checkout

    # Se ainda nÃ£o houver URL persistida, reutiliza a chave original;
    # nunca cria uma segunda identidade comercial.
    assert re.search(
        r"const\s+idempotencyKey\s*=\s*"
        r"taxReportRecoveredIdempotencyKey\s*\|\|\s*"
        r"crypto\.randomUUID\(\)",
        checkout,
    )

    assert re.search(
        r'["\']Idempotency-Key["\']\s*:\s*idempotencyKey',
        checkout,
    )


def test_server_recovery_runs_when_company_identity_becomes_available_red():
    source = APP.read_text(encoding="utf-8")

    assert "recuperarTaxReportCheckoutDoServidor(idPerfil)" in source
    assert re.search(
        r"useEffect\(\s*\(\)\s*=>\s*\{[\s\S]*?"
        r"recuperarTaxReportCheckoutDoServidor\(idPerfil\)"
        r"[\s\S]*?\}\s*,\s*\[\s*tipoPerfil\s*,\s*idPerfil\s*\]\s*\)",
        source,
    )