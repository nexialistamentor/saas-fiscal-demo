"""RED: ligacao soberana da intencao duravel ao checkout tax.report.

Este contrato nao autoriza pagamento, grant, acquisition ou acesso ao PDF.
"""

import inspect
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.routes import relatorio_router
from app.services import checkout_offer_order_composition as composition


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend-dashboard/src/App.jsx"
INTENT_SERVICE = ROOT / "app/services/tax_report_checkout_intent.py"
PREREQUISITE_SERVICE = ROOT / "app/services/checkout_offer_prerequisite.py"
OFFER_CODE = "tax-report-one-time-company"
ROUTE_PATH = "/empresas/{empresa_id}/checkout-intents"


def _route():
    return next(
        (
            route
            for route in relatorio_router.router.routes
            if isinstance(route, APIRoute)
            and route.path == ROUTE_PATH
            and route.methods == {"POST"}
        ),
        None,
    )


def _block_after(source: str, marker: str) -> str:
    assert marker in source, f"ausente bloco frontend {marker!r}"
    start = source.index(marker)
    signature_start = source.index("(", start)

    paren_depth = 0
    signature_end = None

    for position in range(signature_start, len(source)):
        character = source[position]
        if character == "(":
            paren_depth += 1
        elif character == ")":
            paren_depth -= 1
            if paren_depth == 0:
                signature_end = position
                break

    assert signature_end is not None, (
        f"assinatura sem fechamento depois de {marker!r}"
    )

    brace = source.index("{", signature_end)
    depth = 0

    for position in range(brace, len(source)):
        character = source[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]

    raise AssertionError(f"bloco sem fechamento depois de {marker!r}")


def test_http_intent_endpoint_exists_authenticated_and_has_exact_input_red():
    route = _route()
    assert route is not None, f"ausente POST {ROUTE_PATH} no router de relatorio"
    assert route.status_code == 204
    assert any(
        dependency.call is relatorio_router.get_usuario_atual
        for dependency in route.dependant.dependencies
    ), "endpoint de intencao deve exigir usuario autenticado"

    fields = route.body_field.type_.model_fields
    assert tuple(fields) == ("relatorio_id", "request_fingerprint")
    assert route.body_field.type_.model_config.get("extra") == "forbid"
    schema = route.body_field.type_.model_json_schema()
    assert schema["properties"]["relatorio_id"]["exclusiveMinimum"] == 0
    assert schema["properties"]["request_fingerprint"]["pattern"] == "^[0-9a-f]{64}$"

    headers = [parameter for parameter in route.dependant.header_params]
    assert len(headers) == 1
    assert headers[0].alias == "Idempotency-Key"

    app = FastAPI()
    app.include_router(relatorio_router.router)
    operation = app.openapi()["paths"][ROUTE_PATH]["post"]
    header_schema = next(
        parameter["schema"]
        for parameter in operation["parameters"]
        if parameter["name"] == "Idempotency-Key" and parameter["in"] == "header"
    )
    assert header_schema["type"] == "string"
    assert header_schema["minLength"] == 1
    assert header_schema["maxLength"] == 255
    assert header_schema["pattern"] == r"^[\x21-\x7e]+$"


def test_http_intent_calls_durable_service_and_owns_transaction_red():
    route = _route()
    assert route is not None, f"ausente POST {ROUTE_PATH} no router de relatorio"
    source = inspect.getsource(route.endpoint)
    assert "TaxReportCheckoutIntent" in source and ".persist(" in source
    for required in (
        "usuario_atual.id",
        "empresa_id",
        "relatorio_id",
        OFFER_CODE,
        "idempotency",
        "request_fingerprint",
        ".commit(",
        ".rollback(",
        "TaxReportCheckoutIntentError",
        "SQLAlchemyError",
        "status_code=409",
        "status_code=503",
    ):
        assert required in source, f"handler de intencao nao prova {required!r}"


def _prerequisite_source() -> str:
    assert PREREQUISITE_SERVICE.is_file(), (
        "ausente fronteira app/services/checkout_offer_prerequisite.py"
    )
    return PREREQUISITE_SERVICE.read_text(encoding="utf-8")


def test_checkout_prerequisite_exposes_minimum_future_api_red():
    source = _prerequisite_source()
    assert "class CheckoutOfferPrerequisiteError(Exception)" in source
    assert "class CheckoutOfferPrerequisite" in source
    assert re.search(r"def\s+__init__\(self,\s*db\s*\)", source)
    require = re.search(
        r"def\s+require\(\s*self\s*,\s*\*\s*,"
        r"\s*authenticated_user_id\s*,\s*empresa_id\s*,"
        r"\s*offer_code\s*,\s*idempotency_key\s*,?\s*\)",
        source,
    )
    assert require, "prerequisite deve expor require com a API keyword-only canonica"


def test_checkout_prerequisite_requires_exact_intent_only_for_tax_report_red():
    source = _prerequisite_source()
    assert "TaxReportCheckoutIntent" in source
    assert OFFER_CODE in source
    assert re.search(
        rf"offer_code\s*!=\s*['\"]{re.escape(OFFER_CODE)}['\"]",
        source,
    ), "ofertas diferentes de tax.report devem retornar sem exigir intent"
    for predicate in (
        r"checkout_idempotency_key\s*==\s*idempotency_key",
        r"user_id\s*==\s*authenticated_user_id",
        r"empresa_id\s*==\s*empresa_id",
        r"offer_code\s*==\s*offer_code",
    ):
        assert re.search(predicate, source), (
            f"prerequisite nao prova o predicado exato {predicate!r}"
        )
    assert "CheckoutOfferPrerequisiteError" in source
    for forbidden in (".commit(", ".rollback(", "MercadoPago", "OrdemCheckout("):
        assert forbidden not in source, (
            f"prerequisite ganhou efeito colateral proibido: {forbidden}"
        )


def test_composer_stays_generic_and_calls_prerequisite_before_new_order_red():
    source = inspect.getsource(composition.CheckoutOfferOrderComposer)
    module_source = inspect.getsource(composition)
    assert "TaxReportCheckoutIntent" not in module_source
    assert "tax_report_checkout_intents" not in module_source
    assert OFFER_CODE not in module_source
    assert "CheckoutOfferPrerequisite" in module_source
    for argument in (
        "authenticated_user_id=authenticated_user_id",
        "empresa_id=empresa_id",
        "offer_code=offer_code",
        "idempotency_key=idempotency_key",
    ):
        assert argument in source, f"composer nao encaminha {argument!r}"
    guard = source.index(".require(")
    creation = source.index("OrdemCheckout(")
    assert guard < creation, "prerequisite deve ser exigido antes de criar OrdemCheckout"


def test_existing_order_replay_calls_prerequisite_before_acceptance_red():
    retry = inspect.getsource(composition.CheckoutOfferOrderComposer._retry)
    assert "CheckoutOfferPrerequisite" in retry
    assert ".require(" in retry
    for value in ("user_id", "empresa_id", "offer_code", "ordem.idempotency_key"):
        assert value in retry, f"replay nao encaminha {value!r} ao prerequisite"
    assert retry.index(".require(") < retry.index("return cls._snapshot(ordem)")


def test_frontend_persists_intent_in_dedicated_helper_before_checkout_red():
    source = APP.read_text(encoding="utf-8")
    helper = _block_after(source, "async function persistirTaxReportCheckoutIntent(")
    checkout = _block_after(source, "async function iniciarCheckout(")
    assert f"${{API_BASE}}/relatorio/empresas/${{empresaId}}/checkout-intents" in helper
    assert helper.count("Idempotency-Key") == 1
    assert re.search(r"Idempotency-Key['\"]?\s*:\s*idempotencyKey", helper)
    assert re.search(
        r"JSON\.stringify\(\s*\{\s*relatorio_id\s*:\s*relatorioId\s*,"
        r"\s*request_fingerprint\s*:\s*requestFingerprint\s*,?\s*\}\s*\)",
        helper,
        re.DOTALL,
    )
    helper_call = checkout.index("persistirTaxReportCheckoutIntent(")
    checkout_call = checkout.index("/checkout/one-time")
    assert helper_call < checkout_call
    assert "setCheckoutErro(err.message)" in checkout


def test_frontend_reuses_same_key_and_keeps_canonical_checkout_body_red():
    checkout = _block_after(
        APP.read_text(encoding="utf-8"), "async function iniciarCheckout("
    )
    key = re.search(
        r"(?:const|let)\s+(\w+)\s*=\s*"
        r"taxReportRecoveredIdempotencyKey\s*\|\|\s*"
        r"(?:crypto\.)?randomUUID\(\)",
        checkout,
    )
    assert key, (
        "iniciarCheckout deve reutilizar a chave recuperada "
        "ou criar uma nova por tentativa"
    )
    variable = key.group(1)
    explicit = re.search(
        rf"idempotencyKey\s*:\s*{re.escape(variable)}\b",
        checkout,
    )
    shorthand = re.search(
        rf"persistirTaxReportCheckoutIntent\(\s*\{{[\s\S]*?"
        rf"\b{re.escape(variable)}\s*,?\s*\}}\s*\)",
        checkout,
    )
    assert explicit or shorthand
    assert len(re.findall(rf"Idempotency-Key['\"]?\s*:\s*{variable}\b", checkout)) == 1
    canonical = checkout[checkout.index("/checkout/one-time") :]
    body = re.search(r"JSON\.stringify\(\s*\{([\s\S]*?)\}\s*\)", canonical)
    assert body
    assert re.findall(r"\b([A-Za-z_$][\w$]*)\s*:", body.group(1)) == [
        "empresa_id",
        "offer_code",
    ]


def test_intent_marker_never_becomes_commercial_or_access_authority_red():
    prerequisite = (
        PREREQUISITE_SERVICE.read_text(encoding="utf-8")
        if PREREQUISITE_SERVICE.is_file()
        else ""
    )
    sources = "\n".join(
        (
            INTENT_SERVICE.read_text(encoding="utf-8"),
            prerequisite,
            inspect.getsource(composition.CheckoutOfferOrderComposer),
        )
    )
    for forbidden in (
        "CheckoutOfferGrant(",
        "TaxReportAcquisitionBinding(",
        "payment_id =",
        "consulta_paga =",
        ".pago =",
        "gerar_pdf",
    ):
        assert forbidden not in sources, f"intencao ganhou autoridade proibida: {forbidden}"
