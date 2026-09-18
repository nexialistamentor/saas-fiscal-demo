import re
from pathlib import Path


APP_SOURCE = (
    Path(__file__).resolve().parents[1] / "frontend-dashboard" / "src" / "App.jsx"
).read_text(encoding="utf-8")


def _balanced_block_after(source: str, marker: str) -> str:
    marker_start = source.index(marker)
    block_start = source.index("{", marker_start)
    return _balanced_block_at(source, block_start)


def _balanced_block_at(source: str, block_start: int) -> str:
    depth = 0

    for position in range(block_start, len(source)):
        character = source[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[block_start : position + 1]

    raise AssertionError(f"Unclosed block starting at offset {block_start}")


CHECKOUT_FUNCTION = _balanced_block_after(
    APP_SOURCE, "async function iniciarCheckout("
)


def _fetch_options() -> str:
    fetch_start = CHECKOUT_FUNCTION.index("fetch(")
    url_end = CHECKOUT_FUNCTION.index("`,", fetch_start)
    options_start = CHECKOUT_FUNCTION.index("{", url_end)
    return _balanced_block_at(CHECKOUT_FUNCTION, options_start)


def _object_passed_to(call: str, source: str) -> str:
    call_start = source.index(call)
    object_start = source.index("{", call_start)
    return _balanced_block_at(source, object_start)


def test_empresa_checkout_uses_canonical_endpoint_and_fail_closed_guard() -> None:
    assert re.search(
        r'if\s*\(\s*tipoPerfil\s*!==\s*["\']empresa["\']\s*\|\|'
        r'\s*!Number\.isInteger\(idPerfil\)\s*\|\|\s*idPerfil\s*<=\s*0\s*\)'
        r'\s*\{[^{}]*return\b',
        CHECKOUT_FUNCTION,
        re.DOTALL,
    ), "iniciarCheckout must return before fetch unless the profile is a positive-integer empresa"

    assert re.search(
        r'fetch\(\s*`\$\{API_BASE\}/checkout/one-time`\s*,', CHECKOUT_FUNCTION
    ), "iniciarCheckout must POST to the canonical /checkout/one-time endpoint"


def test_canonical_checkout_headers_and_per_attempt_idempotency_key() -> None:
    options = _fetch_options()
    headers = _object_passed_to("headers:", options)

    assert len(re.findall(r'["\']Idempotency-Key["\']\s*:', headers)) == 1, (
        "canonical checkout must send exactly one Idempotency-Key header"
    )
    assert re.search(r'["\']Content-Type["\']\s*:\s*["\']application/json["\']', headers)
    assert re.search(r'Authorization\s*:\s*`Bearer \$\{getToken\(\)\}`', headers)

    key_value = re.search(
        r'["\']Idempotency-Key["\']\s*:\s*([A-Za-z_$][\w$]*)', headers
    )
    assert key_value, "Idempotency-Key must use a generated, non-empty value"
    variable = key_value.group(1)
    prefix_before_fetch = CHECKOUT_FUNCTION[: CHECKOUT_FUNCTION.index("fetch(")]
    assert re.search(
        rf'\b(?:const|let)\s+{re.escape(variable)}\s*=\s*'
        r'taxReportRecoveredIdempotencyKey\s*\|\|\s*(?:crypto\.)?randomUUID\(\)',
        prefix_before_fetch,
    ), (
        "checkout must reuse a recovered Idempotency-Key or generate "
        "a fresh one for a new attempt"
    )


def test_canonical_checkout_body_has_only_backend_authority_inputs() -> None:
    options = _fetch_options()
    body = _object_passed_to("JSON.stringify(", options)
    properties = re.findall(r'\b([A-Za-z_$][\w$]*)\s*:', body)

    assert properties == ["empresa_id", "offer_code"], (
        "checkout body must contain exactly empresa_id and offer_code"
    )
    assert re.search(r'\bempresa_id\s*:\s*idPerfil\b', body)
    assert re.search(
        r'\boffer_code\s*:\s*["\']tax-report-one-time-company["\']', body
    )


def test_canonical_checkout_uses_checkout_url_for_redirect() -> None:
    assert re.search(
        r'const\s*\{\s*checkout_url\s*\}\s*=\s*await\s+res\.json\(\)',
        CHECKOUT_FUNCTION,
    ), "canonical checkout response must be read from checkout_url"
    assert re.search(
        r'window\.location\.href\s*=\s*checkout_url\b', CHECKOUT_FUNCTION
    ), "the browser must redirect to checkout_url"


def test_legacy_checkout_contract_is_absent_from_iniciar_checkout() -> None:
    for legacy_term in (
        "/checkout/criar-pagamento",
        "link_checkout",
        "perfil_id",
        "tipo_perfil",
    ):
        assert legacy_term not in CHECKOUT_FUNCTION, (
            f"legacy checkout term {legacy_term!r} must be removed from iniciarCheckout"
        )
