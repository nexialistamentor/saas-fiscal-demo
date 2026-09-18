import re
from pathlib import Path


APP_SOURCE = (
    Path(__file__).resolve().parents[1] / "frontend-dashboard" / "src" / "App.jsx"
).read_text(encoding="utf-8")


def _balanced_block_after(source: str, marker: str) -> str:
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


CHECKOUT_FUNCTION = _balanced_block_after(
    APP_SOURCE, "async function iniciarCheckout("
)
SESSION_KEY = "solveris.taxReportAcquisitionContext.v1"


def test_checkout_requires_valid_report_resume_identity_before_fetch() -> None:
    prefix_before_fetch = CHECKOUT_FUNCTION[: CHECKOUT_FUNCTION.index("fetch(")]

    assert re.search(
        r"const\s+relatorioId\s*=\s*resultadoXML\?\.relatorio_id\b",
        prefix_before_fetch,
    ), "iniciarCheckout must read relatorioId from resultadoXML?.relatorio_id before fetch"
    assert re.search(
        r"const\s+requestFingerprint\s*=\s*resultadoXML\?\.request_fingerprint\b",
        prefix_before_fetch,
    ), "iniciarCheckout must read requestFingerprint from resultadoXML?.request_fingerprint before fetch"
    assert re.search(
        r"if\s*\("
        r"(?=[\s\S]*?!Number\.isInteger\(relatorioId\))"
        r"(?=[\s\S]*?relatorioId\s*<=\s*0)"
        r"(?=[\s\S]*?typeof\s+requestFingerprint\s*!==\s*[\"']string[\"'])"
        r"(?=[\s\S]*?/\^\[0-9a-f\]\{64\}\$/\.test\(requestFingerprint\))"
        r"[\s\S]*?\)\s*\{[^{}]*\breturn\b",
        prefix_before_fetch,
    ), (
        "iniciarCheckout must fail closed before fetch unless relatorioId is a "
        "positive integer and requestFingerprint is a lowercase 64-hex string"
    )


def test_checkout_persists_exact_canonical_context_between_response_and_redirect() -> None:
    response_match = re.search(
        r"const\s*\{\s*checkout_url\s*\}\s*=\s*await\s+res\.json\(\)",
        CHECKOUT_FUNCTION,
    )
    redirect_match = re.search(
        r"window\.location\.href\s*=\s*checkout_url\b", CHECKOUT_FUNCTION
    )
    assert response_match and redirect_match

    between_response_and_redirect = CHECKOUT_FUNCTION[
        response_match.end() : redirect_match.start()
    ]
    storage_match = re.search(
        rf"sessionStorage\.setItem\(\s*[\"']{re.escape(SESSION_KEY)}[\"']\s*,"
        r"\s*JSON\.stringify\(\s*\{(?P<object>[\s\S]*?)\}\s*\)\s*\)",
        between_response_and_redirect,
    )
    assert storage_match, (
        "the canonical session context must be stored after checkout_url is read "
        "and before redirect"
    )

    stored_object = storage_match.group("object")
    properties = re.findall(r"\b([A-Za-z_$][\w$]*)\s*:", stored_object)
    assert properties == ["empresa_id", "relatorio_id", "request_fingerprint"], (
        "stored context must contain exactly empresa_id, relatorio_id, and "
        "request_fingerprint"
    )
    assert re.search(r"\bempresa_id\s*:\s*idPerfil\b", stored_object)
    assert re.search(r"\brelatorio_id\s*:\s*relatorioId\b", stored_object)
    assert re.search(
        r"\brequest_fingerprint\s*:\s*requestFingerprint\b", stored_object
    )


def test_checkout_resume_context_uses_no_persistent_or_url_channel() -> None:
    assert "localStorage" not in CHECKOUT_FUNCTION, (
        "tax report acquisition context must not use localStorage"
    )
    assert "URLSearchParams" not in CHECKOUT_FUNCTION, (
        "tax report acquisition context must not use URLSearchParams"
    )
    assert not re.search(r"[?&][^\s`\"']*(?:fingerprint|request_fingerprint)=", CHECKOUT_FUNCTION), (
        "request fingerprint must not be placed in a query string or URL"
    )


def test_checkout_resume_context_does_not_persist_sensitive_or_payment_data() -> None:
    storage_calls = re.findall(
        r"sessionStorage\.setItem\([\s\S]*?\)\s*\)", CHECKOUT_FUNCTION
    )
    assert storage_calls, "iniciarCheckout must persist the canonical session context"
    persisted_source = "\n".join(storage_calls)

    for forbidden in (
        "token",
        "Authorization",
        "Idempotency-Key",
        "checkout_url",
        "offer_code",
        "price",
        "preco",
        "preço",
        "currency",
        "moeda",
        "payment_status",
        "estado_pagamento",
        "acquisition_id",
    ):
        assert forbidden not in persisted_source, (
            f"session context must not persist forbidden field {forbidden!r}"
        )
