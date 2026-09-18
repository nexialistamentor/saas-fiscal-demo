import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "frontend-dashboard" / "src" / "App.jsx"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")

SESSION_KEY = "solveris.taxReportAcquisitionContext.v1"
RESUME_FUNCTION_SHA256 = (
    "ff5d45ba526c444372d5c6ae4c0a49aeb73926ac35a27ba3f5f5e40033addf08"
)


def _balanced_block_after(source: str, marker: str) -> str:
    assert marker in source, f"source must contain {marker!r}"
    marker_start = source.index(marker)
    block_start = source.index("{", marker_start)
    depth = 0

    for position in range(block_start, len(source)):
        character = source[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[block_start : position + 1]

    raise AssertionError(f"Unclosed block after {marker!r}")


def _function_source(name: str) -> str:
    marker = f"async function {name}("
    start = APP_SOURCE.index(marker)
    block_start = APP_SOURCE.index("{", start)
    block = _balanced_block_after(APP_SOURCE, marker)
    return APP_SOURCE[start:block_start] + block


def _locked_report_section() -> str:
    start = APP_SOURCE.index("Diagnóstico completo bloqueado")
    end = APP_SOURCE.index("Diagnóstico completo disponível", start)
    expression_start = APP_SOURCE.rfind("{", 0, start)
    return APP_SOURCE[expression_start:end]


def test_reads_only_the_explicit_mercado_pago_return_query_marker() -> None:
    assert re.search(
        r"const\s+mercadoPagoReturn\s*=\s*"
        r"new\s+URLSearchParams\(window\.location\.search\)"
        r"\.get\([\"']mp_return[\"']\)",
        APP_SOURCE,
    ), "App must read mp_return explicitly from window.location.search"

    compared_values = set(
        re.findall(
            r"mercadoPagoReturn\s*={2,3}\s*[\"']([^\"']+)[\"']",
            APP_SOURCE,
        )
    )
    assert compared_values <= {"success", "pending", "failure"}, (
        "only success, pending, and failure may give mp_return semantic meaning"
    )


def test_processing_is_derived_only_from_return_ux_and_missing_acquisition() -> None:
    assert re.search(
        r"const\s+taxReportCheckoutProcessing\s*=\s*"
        r"\(\s*\(\s*mercadoPagoReturn\s*===\s*[\"']success[\"']\s*\|\|\s*"
        r"mercadoPagoReturn\s*===\s*[\"']pending[\"']\s*\)\s*\|\|\s*"
        r"taxReportRecoveredPaid\s*\)\s*&&\s*!\s*\(\s*"
        r"Number\.isInteger\(taxReportAcquisitionId\)\s*&&\s*"
        r"taxReportAcquisitionId\s*>\s*0\s*&&\s*"
        r"Number\.isInteger\(taxReportAcquisitionEmpresaId\)\s*&&\s*"
        r"taxReportAcquisitionEmpresaId\s*>\s*0\s*\)",
        APP_SOURCE,
        re.DOTALL,
    ), (
        "success/pending may only suppress another checkout while canonical "
        "acquisition identity is still absent"
    )


def test_processing_state_has_copy_and_does_not_render_checkout_button() -> None:
    section = _locked_report_section()
    processing_branch = re.search(
        r"taxReportCheckoutProcessing\s*\?\s*\("
        r"(?P<processing>[\s\S]*?)\)\s*:\s*\("
        r"(?P<checkout>[\s\S]*?)\)\s*\}",
        section,
    )
    assert processing_branch, (
        "the locked report must branch explicitly between processing and checkout"
    )

    processing = processing_branch.group("processing")
    checkout = processing_branch.group("checkout")
    assert "Pagamento em processamento" in processing
    assert "Estamos confirmando o pagamento e preparando seu relatório." in processing
    assert "Desbloquear diagnóstico completo" not in processing
    assert "iniciarCheckout" not in processing
    assert "Desbloquear diagnóstico completo" in checkout
    assert "onClick={iniciarCheckout}" in checkout


def test_checkout_handler_fails_closed_while_processing() -> None:
    checkout = _function_source("iniciarCheckout")
    prefix_before_fetch = checkout[: checkout.index("fetch(")]
    assert re.search(
        r"if\s*\(\s*taxReportCheckoutProcessing\s*\)\s*\{[^{}]*\breturn\b",
        prefix_before_fetch,
        re.DOTALL,
    ), "iniciarCheckout must return before fetch while processing is true"


def test_failure_and_unknown_markers_keep_normal_checkout_available() -> None:
    processing_assignment = re.search(
        r"const\s+taxReportCheckoutProcessing\s*=\s*(?P<expression>[\s\S]*?)\n\s*(?:const|let|useEffect|async\s+function)",
        APP_SOURCE,
    )
    assert processing_assignment, "processing derivation must be present"
    expression = processing_assignment.group("expression")
    assert 'mercadoPagoReturn === "failure"' not in expression
    assert "mercadoPagoReturn === 'failure'" not in expression

    section = _locked_report_section()
    assert re.search(
        r"taxReportCheckoutProcessing\s*\?[\s\S]*?:[\s\S]*?"
        r"onClick=\{iniciarCheckout\}",
        section,
    ), "false processing state, including failure/unknown, must offer checkout"


def test_return_marker_never_creates_browser_payment_or_acquisition_authority() -> None:
    marker_statements = "\n".join(
        line for line in APP_SOURCE.splitlines() if "mercadoPagoReturn" in line
    )
    for forbidden in (
        "consulta_paga",
        "relatorio.pago",
        "payment_id",
        "ordem_id",
        "grant",
        "acquisition_id",
        "setTaxReportAcquisitionId",
        "setTaxReportAcquisitionEmpresaId",
        "fetch(",
        'method: "POST"',
        "method: 'POST'",
        "MercadoPago",
    ):
        assert forbidden not in marker_statements, (
            f"mp_return is UX-only and must not feed authority term {forbidden!r}"
        )

    assert not re.search(
        r"if\s*\([^)]*mercadoPagoReturn\s*===\s*[\"']success[\"'][^)]*\)"
        r"\s*\{[\s\S]*?setTaxReportAcquisition(?:Id|EmpresaId)\s*\(",
        APP_SOURCE,
    ), "success must never synthesize canonical acquisition identity in the browser"


def test_resume_function_remains_the_unchanged_acquisition_authority() -> None:
    resume = _function_source("retomarAquisicaoTaxReport")
    assert hashlib.sha256(resume.encode("utf-8")).hexdigest() == RESUME_FUNCTION_SHA256, (
        "retomarAquisicaoTaxReport is GREEN/FROZEN and must remain unchanged in this gate"
    )
    assert "setTaxReportAcquisitionId(acquisition_id)" in resume
    assert "setTaxReportAcquisitionEmpresaId(context.empresa_id)" in resume
    assert SESSION_KEY in resume


def test_existing_resume_context_key_is_preserved() -> None:
    assert SESSION_KEY in APP_SOURCE
    assert APP_SOURCE.count(SESSION_KEY) >= 3, (
        "the canonical checkout/resume context lifecycle must remain present"
    )
