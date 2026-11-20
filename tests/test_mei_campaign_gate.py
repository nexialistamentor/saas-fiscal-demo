"""Contratos da catraca comercial; transporte inteiramente sintetico."""

import json

from scripts.mei_campaign_gate import evaluate


LANDING = "https://solveris.ia.br/mei"
API = "https://saas-fiscal-demo-production.up.railway.app"


def _config(**updates):
    cfg = {
        "landing": LANDING,
        "api": API,
        "landing_text": "SOLVERIS | MEI",
        "email": "commercial-smoke@example.com",
        "password": "SEGREDO_NAO_REVELAR",
        "empresa_id": 77,
        "competencia": "202611",
        "exclusive_test_account": True,
        "phase": "during",
    }
    cfg.update(updates)
    return cfg


def _body(value):
    return json.dumps(value).encode("utf-8")


def _fake_transport(overrides=None):
    calls = []
    data = {
        LANDING: (200, b'<title>SOLVERIS | MEI</title><div id="root"></div>'),
        API + "/health": (200, b'{"status":"ok"}'),
        API + "/auth/me": (200, _body({"email": "commercial-smoke@example.com"})),
        API + "/empresas/": (200, _body([{"id": 77, "regime_tributario": "mei"}])),
        API + "/checkout/offers": (200, _body([{
            "offer_code": "mei-das-one-time-company", "preco": "39.90", "moeda": "BRL",
            "vertical": "tax", "commercial_model": "one_time", "subject_type": "company",
            "usage_unit": "competence", "usage_limit": 1, "checkout_mode": "automatic",
        }])),
        API + "/imposto/mei/77/checkout-recovery?competencia=202611": (200, _body({
            "estado": "pending", "competencia": "202611", "autorizado": False,
            "checkout_idempotency_key": "synthetic-existing",
            "checkout_url": "https://checkout.example.invalid/pending",
        })),
        "https://checkout.example.invalid/pending": (200, b"<html>Checkout de teste</html>"),
    }
    data.update(overrides or {})

    def get(url, token=None):
        calls.append(("GET", url, bool(token)))
        return data.get(url, (404, b""))

    def login(url, email, password):
        calls.append(("POST_LOGIN", url, bool(password)))
        return (200, _body({"access_token": "SENSITIVE_TOKEN", "token_type": "bearer"}))

    return get, login, calls


def test_commercial_gate_green_only_with_synthetic_pending_checkout():
    get, login, calls = _fake_transport()
    receipt = evaluate(_config(), get=get, login=login)
    assert receipt["resultado"] == "CAMPANHA_APTA"
    assert all(row["resultado"] == "APROVADO" for row in receipt["testes"])
    assert sum(action == "POST_LOGIN" for action, *_ in calls) == 1
    assert all(action in ("GET", "POST_LOGIN") for action, *_ in calls)
    assert "SEGREDO_NAO_REVELAR" not in repr(receipt)
    assert "SENSITIVE_TOKEN" not in repr(receipt)
    assert "checkout.example.invalid" not in repr(receipt)


def test_health_200_login_500_blocks_campaign():
    get, _, calls = _fake_transport()
    def broken_login(*_args):
        return (500, b"psycopg secret")
    receipt = evaluate(_config(), get=get, login=broken_login)
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert any(row["teste"] == "backend" and row["resultado"] == "APROVADO"
               for row in receipt["testes"])
    assert any(row["teste"] == "login_sintetico" and row.get("http") == 500
               for row in receipt["testes"])
    assert not any("checkout/offers" in url for _, url, _ in calls)


def test_credentials_missing_does_not_call_login():
    get, login, calls = _fake_transport()
    receipt = evaluate(_config(password=""), get=get, login=login)
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert all(action == "GET" for action, *_ in calls)


def test_no_pending_checkout_blocks_campaign():
    url = API + "/imposto/mei/77/checkout-recovery?competencia=202611"
    get, login, _ = _fake_transport({url: (404, b"")})
    receipt = evaluate(_config(), get=get, login=login)
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert receipt["testes"][-1]["motivo"] == "CHECKOUT_PENDENTE_NAO_RECUPERAVEL"


def test_http_checkout_url_and_changed_price_block_campaign():
    url = API + "/imposto/mei/77/checkout-recovery?competencia=202611"
    get, login, _ = _fake_transport({url: (200, _body({
        "estado": "pending", "competencia": "202611", "autorizado": False,
        "checkout_idempotency_key": "test", "checkout_url": "http://unsafe.example/",
    }))})
    assert evaluate(_config(), get=get, login=login)["resultado"] == "CAMPANHA_BLOQUEADA"

    offer_url = API + "/checkout/offers"
    get, login, _ = _fake_transport({offer_url: (200, _body([{
        "offer_code": "mei-das-one-time-company", "preco": "99.99",
    }]))})
    receipt = evaluate(_config(), get=get, login=login)
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert receipt["testes"][-1]["motivo"] == "OFERTA_MEI_NAO_DISPONIVEL"


def test_invalid_endpoint_blocks_before_any_connection():
    get, login, calls = _fake_transport()
    receipt = evaluate(_config(api="http://not-local.example"), get=get, login=login)
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert calls == []


def test_preflight_requires_explicit_write_authorization_and_stable_key():
    get, login, calls = _fake_transport()
    receipt = evaluate(_config(phase="preflight"), get=get, login=login)
    assert receipt["resultado"] == "CAMPANHA_BLOQUEADA"
    assert receipt["testes"][-1]["motivo"] == "CRIACAO_SINTETICA_SEM_AUTORIZACAO"
    assert not any(action.startswith("POST_CHECKOUT") for action, *_ in calls)


def test_preflight_authorized_creates_one_synthetic_intent_without_payment():
    get, login, calls = _fake_transport()
    def post_json(url, token, key, payload):
        calls.append(("POST_CHECKOUT", url, True))
        assert token == "SENSITIVE_TOKEN"
        assert key == "stable-synthetic-key"
        if url.endswith("/checkout-intents"):
            assert payload == {"competencia": "202611", "offer_code": "mei-das-one-time-company"}
            return (204, b"")
        assert url.endswith("/checkout/one-time")
        assert payload == {"empresa_id": 77, "offer_code": "mei-das-one-time-company"}
        return (200, _body({"checkout_url": "https://checkout.example.invalid/pending"}))

    receipt = evaluate(_config(phase="preflight", approved_test_write=True,
                               synthetic_idempotency_key="stable-synthetic-key"),
                       get=get, login=login, post_json=post_json)
    assert receipt["resultado"] == "CAMPANHA_APTA"
    assert sum(action == "POST_CHECKOUT" for action, *_ in calls) == 2
    assert "stable-synthetic-key" not in repr(receipt)
