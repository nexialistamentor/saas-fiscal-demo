import re
from pathlib import Path


APP_SOURCE = (
    Path(__file__).resolve().parents[1] / "frontend-dashboard" / "src" / "App.jsx"
).read_text(encoding="utf-8")

SESSION_KEY = "solveris.taxReportAcquisitionContext.v1"
FUNCTION_MARKER = "async function retomarAquisicaoTaxReport()"


def _balanced_block_after(source: str, marker: str) -> str:
    assert marker in source, f"App.jsx must declare {marker}"
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


def _acquisition_function() -> str:
    return _balanced_block_after(APP_SOURCE, FUNCTION_MARKER)


def _object_passed_to(call: str, source: str) -> str:
    call_start = source.index(call)
    object_start = source.index("{", call_start)
    depth = 0

    for position in range(object_start, len(source)):
        character = source[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[object_start : position + 1]

    raise AssertionError(f"Unclosed object passed to {call!r}")


def _fetch_options(source: str) -> str:
    fetch_start = source.index("fetch(")
    url_end = source.index("`,", fetch_start)
    options_start = source.index("{", url_end)
    return _object_passed_to("{", source[options_start:])


def test_app_has_canonical_acquisition_state_and_mount_resume_effect() -> None:
    assert re.search(
        r"const\s*\[\s*taxReportAcquisitionId\s*,\s*setTaxReportAcquisitionId\s*\]"
        r"\s*=\s*useState\(null\)",
        APP_SOURCE,
    ), "App must keep the canonical acquisition_id in dedicated React state"
    assert FUNCTION_MARKER in APP_SOURCE, (
        "App must declare the dedicated async post-checkout acquisition resume function"
    )
    assert re.search(
        r"useEffect\(\s*\(\)\s*=>\s*\{(?=[\s\S]*?"
        r"(?:void\s+)?retomarAquisicaoTaxReport\(\))"
        r"[\s\S]*?\}\s*,\s*\[\s*\]\s*\)",
        APP_SOURCE,
    ), "an empty-dependency useEffect must resume acquisition once after App mounts"


def test_resume_reads_only_canonical_session_context_and_fails_closed() -> None:
    function = _acquisition_function()
    read_match = re.search(
        rf"sessionStorage\.getItem\(\s*[\"']{re.escape(SESSION_KEY)}[\"']\s*\)",
        function,
    )
    assert read_match, "resume must read the exact canonical sessionStorage key"

    prefix_before_fetch = function[: function.index("fetch(")]
    assert re.search(
        r"if\s*\(\s*!\s*[A-Za-z_$][\w$]*\s*\)\s*\{[^{}]*\breturn\b",
        prefix_before_fetch,
    ), "missing session context must return before any fetch"
    assert "JSON.parse(" in prefix_before_fetch, "session context must be parsed as JSON"
    assert re.search(
        rf"(?:catch\s*\([^)]*\)|catch)\s*\{{[\s\S]*?"
        rf"sessionStorage\.removeItem\(\s*[\"']{re.escape(SESSION_KEY)}[\"']\s*\)"
        rf"[\s\S]*?\breturn\b",
        prefix_before_fetch,
    ), "corrupt JSON must remove the invalid key and return without fetching"


def test_resume_validates_exact_backend_identity_and_rejects_invalid_context() -> None:
    function = _acquisition_function()
    prefix_before_fetch = function[: function.index("fetch(")]

    for validation in (
        r"Number\.isInteger\(context\.empresa_id\)",
        r"context\.empresa_id\s*>\s*0",
        r"Number\.isInteger\(context\.relatorio_id\)",
        r"context\.relatorio_id\s*>\s*0",
        r"typeof\s+context\.request_fingerprint\s*===\s*[\"']string[\"']",
        r"/\^\[0-9a-f\]\{64\}\$/\.test\(context\.request_fingerprint\)",
    ):
        assert re.search(validation, prefix_before_fetch), (
            f"canonical context validation is missing {validation!r}"
        )

    invalid_branch = re.search(
        rf"if\s*\([\s\S]*?\)\s*\{{(?P<body>[\s\S]*?"
        rf"sessionStorage\.removeItem\(\s*[\"']{re.escape(SESSION_KEY)}[\"']\s*\)"
        rf"[\s\S]*?\breturn\b[\s\S]*?)\}}",
        prefix_before_fetch,
    )
    assert invalid_branch, (
        "invalid context must remove the canonical key and return before fetch"
    )


def test_acquisition_uses_deterministic_idempotency_key_without_new_persistence() -> None:
    function = _acquisition_function()
    prefix_before_fetch = function[: function.index("fetch(")]
    assert re.search(
        r"const\s+acquisitionIdempotencyKey\s*=\s*"
        r"`tax-report-acquisition:\$\{context\.empresa_id\}:"
        r"\$\{context\.relatorio_id\}:\$\{context\.request_fingerprint\}`",
        prefix_before_fetch,
    ), "acquisition retry identity must be derived deterministically from canonical context"
    assert "randomUUID" not in function, "post-checkout acquisition must not use randomUUID"
    assert "sessionStorage.setItem" not in function, (
        "deterministic acquisition retries must not require new persistence"
    )


def test_acquisition_posts_exact_canonical_request() -> None:
    function = _acquisition_function()
    assert re.search(
        r"fetch\(\s*`\$\{API_BASE\}/relatorio/empresas/"
        r"\$\{context\.empresa_id\}/acquisitions`\s*,",
        function,
    ), "resume must POST to the canonical empresa acquisition endpoint"

    options = _fetch_options(function)
    assert re.search(r"\bmethod\s*:\s*[\"']POST[\"']", options)
    assert re.search(
        r"[\"']Content-Type[\"']\s*:\s*[\"']application/json[\"']", options
    )
    assert re.search(r"Authorization\s*:\s*`Bearer \$\{getToken\(\)\}`", options)
    assert re.search(
        r"[\"']Idempotency-Key[\"']\s*:\s*acquisitionIdempotencyKey", options
    )

    body = _object_passed_to("JSON.stringify(", options)
    properties = re.findall(r"\b([A-Za-z_$][\w$]*)\s*:", body)
    assert properties == ["relatorio_id", "request_fingerprint"], (
        "acquisition body must contain only relatorio_id and request_fingerprint"
    )
    assert re.search(r"\brelatorio_id\s*:\s*context\.relatorio_id\b", body)
    assert re.search(
        r"\brequest_fingerprint\s*:\s*context\.request_fingerprint\b", body
    )


def test_retry_is_bounded_to_six_attempts_for_only_409_and_503() -> None:
    function = _acquisition_function()
    assert re.search(
        r"(?:for\s*\([^;]*;[^;]*(?:<\s*6|<=\s*6)[^;]*;[^)]*\)|"
        r"while\s*\([^)]*(?:<\s*6|<=\s*6)[^)]*\))",
        function,
    ), "acquisition retry loop must be explicitly bounded to at most six attempts"
    assert re.search(r"res\.status\s*===\s*409", function)
    assert re.search(r"res\.status\s*===\s*503", function)
    compared_statuses = set(
        re.findall(r"res\.status\s*===\s*(\d{3})", function)
    )
    assert compared_statuses == {"409", "503"}, (
        "only the exact HTTP statuses 409 and 503 may be transient"
    )
    assert re.search(
        r"setTimeout\s*\([^,]+,\s*(?:1000|[1-9]\d{3,})\s*\)", function
    ), "there must be a wait of at least 1000 ms between transient retries"


def test_non_transient_failure_stops_without_clearing_or_fabricating_identity() -> None:
    function = _acquisition_function()
    assert re.search(r"if\s*\(\s*!res\.ok\s*\)\s*\{[^{}]*\breturn\b", function), (
        "every non-2xx response other than retryable 409/503 must stop"
    )
    assert "sessionStorage.removeItem" not in function[function.index("fetch(") :], (
        "HTTP responses, including 409/503, must not clear the resume context"
    )
    assert not re.search(
        r"setTaxReportAcquisitionId\(\s*(?!acquisition_id\b)[^)]+\)", function
    ), "the frontend must not fabricate an acquisition_id"


def test_success_accepts_only_positive_integer_acquisition_id_and_keeps_context() -> None:
    function = _acquisition_function()
    response_match = re.search(
        r"const\s*\{\s*acquisition_id\s*\}\s*=\s*await\s+res\.json\(\)",
        function,
    )
    assert response_match, "successful acquisition response must read acquisition_id"
    suffix = function[response_match.end() :]
    assert re.search(r"Number\.isInteger\(acquisition_id\)", suffix)
    assert re.search(r"acquisition_id\s*>\s*0", suffix)
    setter = re.search(r"setTaxReportAcquisitionId\(\s*acquisition_id\s*\)", suffix)
    assert setter, "only the validated backend acquisition_id may enter React state"
    integer_check = suffix.index("Number.isInteger(acquisition_id)")
    positive_check = re.search(r"acquisition_id\s*>\s*0", suffix)
    assert positive_check
    assert integer_check < setter.start() and positive_check.start() < setter.start(), (
        "acquisition_id must be validated before it enters React state"
    )
    assert "sessionStorage.removeItem" not in suffix[: setter.end()], (
        "successful acquisition must retain context for the future acquired-PDF gate"
    )


def test_resume_has_no_browser_payment_authority_and_no_pdf_gate() -> None:
    function = _acquisition_function()
    for forbidden in (
        "localStorage",
        "URLSearchParams",
        "window.location.search",
        "consulta_paga",
        "relatorio.pago",
        "payment_id",
        "ordem_id",
        "offer_code",
        "preco",
        "moeda",
        "perfil_id",
        "tipo_perfil",
        "RelatorioPDFButton",
        ".pdf",
        "/pdf",
    ):
        assert forbidden not in function, (
            f"post-checkout acquisition gate must not use forbidden authority/PDF term {forbidden!r}"
        )
