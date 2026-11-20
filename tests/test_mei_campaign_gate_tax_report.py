"""Controles adicionais: a oferta visivel no MEI tambem fecha a catraca."""

import json
from unittest.mock import patch
from urllib.request import Request

from scripts.mei_campaign_gate import evaluate
from scripts import mei_campaign_gate as gate


LANDING = "https://solveris.ia.br/mei"
API = "https://saas-fiscal-demo-production.up.railway.app"
DAS_URL = "https://checkout.example.invalid/mei-das"
REPORT_URL = "https://checkout.example.invalid/mei-report"
REPORT_RECOVERY = API + "/relatorio/empresas/76/checkout-recovery"


def _data(obj):
    return json.dumps(obj).encode("utf-8")


def _run(overrides=None, config_overrides=None, post_json=None):
    responses = {
        LANDING: (200, b'<title>SOLVERIS | MEI</title><div id="root"></div>'),
        API + "/health": (200, b'{"status":"ok"}'),
        API + "/auth/me": (200, _data({"email": "smoke@example.invalid"})),
        API + "/empresas/": (200, _data([{"id": 76, "regime_tributario": "mei"}])),
        API + "/checkout/offers": (200, _data([
            {"offer_code": "mei-das-one-time-company", "preco": "39.90",
             "moeda": "BRL", "vertical": "tax", "commercial_model": "one_time",
             "subject_type": "company", "usage_unit": "competence",
             "usage_limit": 1, "checkout_mode": "automatic"},
            {"offer_code": "tax-report-one-time-company", "preco": "39.90",
             "moeda": "BRL", "commercial_model": "one_time",
             "subject_type": "company"},
        ])),
        API + "/imposto/mei/76/checkout-recovery?competencia=202611": (200, _data({
            "estado": "pending", "competencia": "202611", "autorizado": False,
            "checkout_idempotency_key": "existing-das", "checkout_url": DAS_URL,
        })),
        REPORT_RECOVERY: (200, _data({
            "estado": "pending", "relatorio_id": 18,
            "request_fingerprint": "a" * 64,
            "checkout_idempotency_key": "existing-report", "checkout_url": REPORT_URL,
        })),
        DAS_URL: (200, b"<html>DAS sem pagamento</html>"),
        REPORT_URL: (200, b"<html>Relatorio sem pagamento</html>"),
    }
    responses.update(overrides or {})
    calls = []

    def get(url, token=None):
        calls.append((url, bool(token)))
        return responses.get(url, (404, b""))

    def login(url, email, password):
        assert url == API + "/auth/login"
        assert email == "smoke@example.invalid"
        assert password == "TEST_PASSWORD"
        return 200, _data({"access_token": "SENSITIVE"})

    config = {
        "landing": LANDING, "api": API, "email": "smoke@example.invalid",
        "password": "TEST_PASSWORD", "empresa_id": 76, "competencia": "202611",
        "exclusive_test_account": True, "phase": "during",
        "require_tax_report": True,
    }
    config.update(config_overrides or {})
    kwargs = {"get": get, "login": login}
    if post_json is not None:
        kwargs["post_json"] = post_json
    receipt = evaluate(config, **kwargs)
    return receipt, calls


def test_das_and_diagnosis_both_pass_without_payment_or_write():
    receipt, calls = _run()
    assert receipt["resultado"] == "CAMPANHA_APTA"
    assert len(receipt["testes"]) == 5
    assert any(row["teste"] == "checkout_relatorio" and row["resultado"] == "APROVADO"
               for row in receipt["testes"])
    assert (REPORT_URL, False) in calls
    assert (DAS_URL, False) in calls
    assert all("checkout-intents" not in url and "checkout/one-time" not in url
               for url, _ in calls)
    assert "SENSITIVE" not in repr(receipt)
    assert REPORT_URL not in repr(receipt)


def test_preflight_read_only_reuses_both_pending_checkouts_without_post():
    def forbidden_post(*_args):
        raise AssertionError("Preflight read-only chamou POST")

    receipt, calls = _run(
        config_overrides={"phase": "preflight", "preflight_read_only": True},
        post_json=forbidden_post,
    )
    assert receipt["resultado"] == "CAMPANHA_APTA"
    assert len(receipt["testes"]) == 5
    assert (REPORT_RECOVERY, True) in calls


def test_missing_diagnosis_checkout_blocks_even_when_das_passes():
    receipt, _ = _run({REPORT_RECOVERY: (404, b"")})
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert receipt["testes"][-1]["teste"] == "checkout_relatorio"
    assert receipt["testes"][-1]["motivo"] == "CHECKOUT_RELATORIO_NAO_RECUPERAVEL"


def test_invalid_diagnosis_checkout_url_blocks():
    receipt, _ = _run({REPORT_RECOVERY: (200, _data({
        "estado": "pending", "relatorio_id": 18,
        "request_fingerprint": "a" * 64,
        "checkout_idempotency_key": "existing-report",
        "checkout_url": "http://unsafe.invalid/checkout",
    }))})
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"


def test_diagnosis_catalog_price_change_blocks():
    receipt, calls = _run({API + "/checkout/offers": (200, _data([
        {"offer_code": "mei-das-one-time-company", "preco": "39.90",
         "moeda": "BRL", "vertical": "tax", "commercial_model": "one_time",
         "subject_type": "company", "usage_unit": "competence",
         "usage_limit": 1, "checkout_mode": "automatic"},
        {"offer_code": "tax-report-one-time-company", "preco": "49.90",
         "moeda": "BRL", "commercial_model": "one_time",
         "subject_type": "company"},
    ]))})
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert receipt["testes"][-1]["motivo"] == "OFERTA_RELATORIO_NAO_DISPONIVEL"
    assert not any(url == REPORT_RECOVERY for url, _ in calls)


def test_only_mercado_pago_checkout_get_can_follow_redirects():
    checkout = "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=synthetic"
    with patch.object(gate, "_send", return_value=(200, b"<html>checkout</html>")) as send:
        assert gate._get(checkout) == (200, b"<html>checkout</html>")
        opener = send.call_args.kwargs["opener"]
        assert any(isinstance(handler, gate._TrustedCheckoutRedirect)
                   for handler in opener.handlers)

        gate._get(API + "/health")
        assert "opener" not in send.call_args.kwargs

        gate._get(checkout, "SYNTHETIC_TOKEN")
        assert "opener" not in send.call_args.kwargs


def test_checkout_redirect_restricted_to_https_mercado_pago_and_four_hops():
    start = Request("https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=test")
    allowed = "https://www.mercadopago.com.br/checkout/v1/payment?pref_id=test"
    redirect = gate._TrustedCheckoutRedirect()
    for _ in range(4):
        next_request = redirect.redirect_request(start, None, 302, "Found", {}, allowed)
        assert next_request is not None and next_request.full_url == allowed
    assert redirect.redirect_request(start, None, 302, "Found", {}, allowed) is None

    for blocked in (
        "http://www.mercadopago.com.br/checkout",
        "https://mercadopago.com.br.evil.example/checkout",
        "https://www.mercadopago.com.br:8443/checkout",
        "https://example.com/checkout",
        "https://user@www.mercadopago.com.br/checkout",
    ):
        assert gate._TrustedCheckoutRedirect().redirect_request(
            start, None, 302, "Found", {}, blocked
        ) is None
