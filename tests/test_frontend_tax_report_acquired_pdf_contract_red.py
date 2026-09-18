import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "frontend-dashboard" / "src" / "App.jsx").read_text(
    encoding="utf-8"
)
PDF_BUTTON_SOURCE = (
    ROOT / "frontend-dashboard" / "src" / "components" / "RelatorioPDFButton.jsx"
).read_text(encoding="utf-8")

SESSION_KEY = "solveris.taxReportAcquisitionContext.v1"


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


def _jsx_expression_before(source: str, marker: str) -> str:
    marker_start = source.index(marker)
    expression_start = source.rfind("{", 0, marker_start)
    assert expression_start >= 0, f"no JSX expression found before {marker!r}"
    return source[expression_start:marker_start]


def _available_report_block() -> str:
    marker = "Diagnóstico completo disponível"
    marker_start = APP_SOURCE.index(marker)
    block_start = APP_SOURCE.rfind("<div", 0, marker_start)
    block_end = APP_SOURCE.index("</div>", marker_start) + len("</div>")
    return APP_SOURCE[block_start:block_end]


def test_app_keeps_acquired_empresa_identity_in_dedicated_state() -> None:
    assert re.search(
        r"const\s*\[\s*taxReportAcquisitionEmpresaId\s*,\s*"
        r"setTaxReportAcquisitionEmpresaId\s*\]\s*=\s*useState\(null\)",
        APP_SOURCE,
    ), "App must keep the acquired empresa_id in dedicated React state"


def test_resume_sets_empresa_from_context_only_after_valid_acquisition_id() -> None:
    function = _balanced_block_after(
        APP_SOURCE, "async function retomarAquisicaoTaxReport()"
    )
    response_match = re.search(
        r"const\s*\{\s*acquisition_id\s*\}\s*=\s*await\s+res\.json\(\)",
        function,
    )
    assert response_match, "resume must read acquisition_id from the backend response"

    suffix = function[response_match.end() :]
    integer_check = suffix.index("Number.isInteger(acquisition_id)")
    positive_check = re.search(r"acquisition_id\s*>\s*0", suffix)
    acquisition_setter = re.search(
        r"setTaxReportAcquisitionId\(\s*acquisition_id\s*\)", suffix
    )
    empresa_setter = re.search(
        r"setTaxReportAcquisitionEmpresaId\(\s*context\.empresa_id\s*\)", suffix
    )
    assert positive_check and acquisition_setter and empresa_setter, (
        "validated acquisition success must retain context.empresa_id beside acquisition_id"
    )
    assert integer_check < empresa_setter.start()
    assert positive_check.start() < empresa_setter.start()


def test_available_report_uses_only_positive_canonical_acquisition_identity() -> None:
    condition = _jsx_expression_before(
        APP_SOURCE, "Diagnóstico completo disponível"
    )
    for required in (
        r"Number\.isInteger\(taxReportAcquisitionId\)",
        r"taxReportAcquisitionId\s*>\s*0",
        r"Number\.isInteger\(taxReportAcquisitionEmpresaId\)",
        r"taxReportAcquisitionEmpresaId\s*>\s*0",
    ):
        assert re.search(required, condition), (
            f"available report gate is missing canonical condition {required!r}"
        )

    for forbidden in ("consulta_paga", "relatorio.pago"):
        assert forbidden not in condition, (
            f"available report gate must not use legacy authority {forbidden!r}"
        )


def test_available_report_passes_exact_acquired_identity_and_excludes_memorial() -> None:
    block = _available_report_block()
    button = re.search(r"<RelatorioPDFButton\b(?P<props>[\s\S]*?)/>", block)
    assert button, "available report block must render RelatorioPDFButton"
    props = button.group("props")
    assert re.search(
        r"empresaId\s*=\s*\{\s*taxReportAcquisitionEmpresaId\s*\}", props
    )
    assert re.search(
        r"acquisitionId\s*=\s*\{\s*taxReportAcquisitionId\s*\}", props
    )
    assert "idPerfil" not in props, "PDF identity must not come from selected profile"
    assert "MemorialButton" not in block, (
        "the acquired canonical report block must not expose legacy MemorialButton"
    )


def test_checkout_remains_blocked_until_canonical_acquisition_exists() -> None:
    condition = _jsx_expression_before(APP_SOURCE, "Diagnóstico completo bloqueado")
    assert re.search(
        r"!\s*Number\.isInteger\(taxReportAcquisitionId\)", condition
    ) or re.search(r"taxReportAcquisitionId\s*<=\s*0", condition), (
        "checkout must remain blocked while canonical acquisition_id is absent or invalid"
    )
    assert "consulta_paga" not in condition, (
        "checkout completion must not be decided by legacy consulta_paga"
    )


def test_pdf_button_signature_accepts_only_canonical_identity() -> None:
    assert re.search(
        r"export\s+default\s+function\s+RelatorioPDFButton\(\s*\{\s*"
        r"empresaId\s*,\s*acquisitionId\s*,?\s*\}\s*\)",
        PDF_BUTTON_SOURCE,
    ), "RelatorioPDFButton must accept only empresaId and acquisitionId"


def test_pdf_download_fails_closed_before_fetch_for_invalid_identity() -> None:
    function = _balanced_block_after(PDF_BUTTON_SOURCE, "async function baixarPDF()")
    prefix_before_fetch = function[: function.index("fetch(")]
    for required in (
        r"!\s*Number\.isInteger\(empresaId\)",
        r"empresaId\s*<=\s*0",
        r"!\s*Number\.isInteger\(acquisitionId\)",
        r"acquisitionId\s*<=\s*0",
    ):
        assert re.search(required, prefix_before_fetch), (
            f"PDF download validation is missing {required!r} before fetch"
        )
    assert re.search(r"\breturn\b", prefix_before_fetch), (
        "invalid canonical identity must return before fetch"
    )


def test_pdf_download_uses_exact_authenticated_get_without_body() -> None:
    function = _balanced_block_after(PDF_BUTTON_SOURCE, "async function baixarPDF()")
    assert re.search(
        r"fetch\(\s*`\$\{API_BASE\}/relatorio/empresas/"
        r"\$\{empresaId\}/acquisitions/\$\{acquisitionId\}/pdf`\s*,",
        function,
    ), "PDF download must use the exact acquired-PDF endpoint"
    assert re.search(r"\bmethod\s*:\s*[\"']GET[\"']", function)
    assert re.search(
        r"Authorization\s*:\s*`Bearer\s+\$\{getToken\(\)\}`", function
    )
    assert not re.search(r"\bbody\s*:", function), "GET PDF request must not send a body"


def test_pdf_button_has_no_legacy_or_payment_authority() -> None:
    for forbidden in (
        "/relatorio/gerar",
        "perfil_id",
        "idPerfil",
        "consulta_paga",
        "relatorio.pago",
        'method: "POST"',
        "method: 'POST'",
        "payment_id",
        "ordem_id",
        "offer_code",
    ):
        assert forbidden not in PDF_BUTTON_SOURCE, (
            f"RelatorioPDFButton must not contain forbidden term {forbidden!r}"
        )


def test_pdf_response_keeps_local_error_and_download_lifecycle() -> None:
    function = _balanced_block_after(PDF_BUTTON_SOURCE, "async function baixarPDF()")
    failure_body = _balanced_block_after(function, "if (!res.ok)")
    assert "setErro(" in failure_body and re.search(r"\breturn\b", failure_body)
    assert "res.blob()" not in failure_body

    for required in (
        r"await\s+res\.blob\(\)",
        r"URL\.createObjectURL\(blob\)",
        r"\.download\s*=\s*[\"']relatorio-fiscal\.pdf[\"']",
        r"\.click\(\)",
        r"URL\.revokeObjectURL\(url\)",
    ):
        assert re.search(required, function), (
            f"successful PDF download lifecycle is missing {required!r}"
        )


def test_pdf_download_never_owns_or_clears_resume_context() -> None:
    assert SESSION_KEY not in PDF_BUTTON_SOURCE
    assert "sessionStorage" not in PDF_BUTTON_SOURCE, (
        "App alone must own acquisition replay continuity"
    )
    assert SESSION_KEY in APP_SOURCE, "App must retain the canonical replay context key"
    function = _balanced_block_after(PDF_BUTTON_SOURCE, "async function baixarPDF()")
    assert "removeItem" not in function, (
        "successful or failed PDF download must not clear replay context"
    )
