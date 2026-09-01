"""Contrato RED offline do HMAC oficial do webhook Mercado Pago."""

import ast
import hashlib
import hmac
import inspect
import os
import textwrap

import pytest


SECRET = "segredo-ficticio-mp2-2026"
DATA_ID = "4719001"
REQUEST_ID = "request-ficticio-mp2-8128"
TIMESTAMP = "1700000000"
MANIFEST = (
    "id:4719001;"
    "request-id:request-ficticio-mp2-8128;"
    "ts:1700000000;"
)
EXPECTED_DIGEST = (
    "ab179adec5c57e9dd94cfc7f0d11f57d"
    "85839c7e0026b3dbe639dae6efd5efc1"
)
VALID_SIGNATURE = f"ts={TIMESTAMP},v1={EXPECTED_DIGEST}"


class _ForbiddenEnvironment(dict):
    def __getitem__(self, key):
        raise AssertionError("o validador HMAC nao pode ler o ambiente")

    def get(self, key, default=None):
        raise AssertionError("o validador HMAC nao pode ler o ambiente")


class _StringCoercionTrap:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


def test_payments_mercado_pago_webhook_hmac_contract_red(
    monkeypatch,
    caplog,
):
    from app.services.mercado_pago_webhook import (
        MercadoPagoWebhookSignatureVerifier,
    )
    from app.services.mercado_pago_webhook_hmac import (
        validar_mercado_pago_webhook_hmac,
    )

    signature = inspect.signature(validar_mercado_pago_webhook_hmac)
    assert tuple(signature.parameters) == (
        "x_signature",
        "x_request_id",
        "data_id",
        "secret",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )

    prepared_digest = hmac.new(
        SECRET.encode("utf-8"),
        MANIFEST.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert prepared_digest == EXPECTED_DIGEST
    source = textwrap.dedent(
        inspect.getsource(validar_mercado_pago_webhook_hmac)
    )

    module = inspect.getmodule(validar_mercado_pago_webhook_hmac)
    assert module is not None
    module_tree = ast.parse(inspect.getsource(module))
    imported_roots = set()
    for node in ast.walk(module_tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(
        {
            "aiohttp",
            "datetime",
            "http",
            "httpx",
            "mercadopago",
            "os",
            "requests",
            "socket",
            "time",
            "urllib",
            "urllib3",
            "websockets",
        }
    )
    lowered_source = source.lower()
    for forbidden in (
        "getenv",
        "environ",
        "tolerance",
        "replay",
        "nonce",
        "cache",
        "expires",
        "expiry",
    ):
        assert forbidden not in lowered_source

    def forbidden_getenv(*args, **kwargs):
        raise AssertionError("o validador HMAC nao pode ler o ambiente")

    monkeypatch.setattr(os, "getenv", forbidden_getenv)
    monkeypatch.setattr(os, "environ", _ForbiddenEnvironment())
    caplog.set_level(1)

    original_compare_digest = hmac.compare_digest
    compare_digest_calls = []

    def compare_digest_spy(left, right):
        compare_digest_calls.append((left, right))
        return original_compare_digest(left, right)

    monkeypatch.setattr(hmac, "compare_digest", compare_digest_spy)

    base = {
        "x_signature": VALID_SIGNATURE,
        "x_request_id": REQUEST_ID,
        "data_id": DATA_ID,
        "secret": SECRET,
    }

    def call(expected, **changes):
        arguments = {**base, **changes}
        try:
            result = validar_mercado_pago_webhook_hmac(**arguments)
        except Exception as error:
            for representation in (str(error), repr(error)):
                assert SECRET not in representation
                assert MANIFEST not in representation
            pytest.fail(
                "o validador deve falhar fechado com retorno bool",
                pytrace=False,
            )
        assert type(result) is bool
        assert result is expected

    calls_before = len(compare_digest_calls)
    call(True)
    assert compare_digest_calls[calls_before:] == [
        (EXPECTED_DIGEST, EXPECTED_DIGEST)
    ]

    calls_before = len(compare_digest_calls)
    call(
        True,
        x_signature=f"v1={EXPECTED_DIGEST},ts={TIMESTAMP}",
    )
    assert compare_digest_calls[calls_before:] == [
        (EXPECTED_DIGEST, EXPECTED_DIGEST)
    ]

    divergent_digest = f"0{EXPECTED_DIGEST[1:]}"
    calls_before = len(compare_digest_calls)
    call(
        False,
        x_signature=f"ts={TIMESTAMP},v1={divergent_digest}",
    )
    divergent_calls = compare_digest_calls[calls_before:]
    assert len(divergent_calls) == 1
    assert set(divergent_calls[0]) == {EXPECTED_DIGEST, divergent_digest}

    call(False, secret="outro-segredo-ficticio")
    call(False, data_id="4719002")
    call(False, x_request_id="request-ficticio-mp2-8129")
    call(
        False,
        x_signature=f"ts=1700000001,v1={EXPECTED_DIGEST}",
    )

    invalid_signatures = (
        f"ts={TIMESTAMP}",
        f"v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},ts={TIMESTAMP}",
        f"v1={EXPECTED_DIGEST},v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},unknown={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},={EXPECTED_DIGEST}",
        f"ts=,v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},v1=",
        f"ts:{TIMESTAMP},v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP};v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},v1:{EXPECTED_DIGEST}",
        f"ts={TIMESTAMP}=1,v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST},extra=value",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST},",
        f",ts={TIMESTAMP},v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},,v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP}\r,v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST}\n",
        f" ts={TIMESTAMP},v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST} ",
        f"ts ={TIMESTAMP},v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP}, v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP}\t,v1={EXPECTED_DIGEST}",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST.upper()}",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST[:-1]}",
        f"ts={TIMESTAMP},v1={EXPECTED_DIGEST}0",
        f"ts={TIMESTAMP},v1={'g' * 64}",
        f"ts={TIMESTAMP},v1={'ａ' * 64}",
        f"ts=0,v1={EXPECTED_DIGEST}",
        f"ts=00,v1={EXPECTED_DIGEST}",
        f"ts=01,v1={EXPECTED_DIGEST}",
        f"ts=-1,v1={EXPECTED_DIGEST}",
        f"ts=+1,v1={EXPECTED_DIGEST}",
        f"ts=1.0,v1={EXPECTED_DIGEST}",
        f"ts=1e3,v1={EXPECTED_DIGEST}",
        f"ts=abc,v1={EXPECTED_DIGEST}",
        f"ts=١٧٠٠٠٠٠٠٠٠,v1={EXPECTED_DIGEST}",
    )
    for invalid_signature in invalid_signatures:
        call(False, x_signature=invalid_signature)

    for invalid_signature in (
        None,
        True,
        1,
        b"ts=1700000000,v1=digest",
        [],
        {},
        _StringCoercionTrap(VALID_SIGNATURE),
    ):
        call(False, x_signature=invalid_signature)

    invalid_decimal_values = (
        None,
        True,
        4719001,
        b"4719001",
        "",
        "0",
        "00",
        "04719001",
        "+4719001",
        "-4719001",
        "4719.001",
        "47 19001",
        "٤٧١٩٠٠١",
        _StringCoercionTrap(DATA_ID),
    )
    for invalid_data_id in invalid_decimal_values:
        call(False, data_id=invalid_data_id)

    invalid_request_ids = (
        None,
        True,
        8128,
        b"request-ficticio-mp2-8128",
        "",
        " request",
        "request ",
        "request\tid",
        "request\rid",
        "request\nid",
        "request\u00a0id",
        "request\u2003id",
        "request\u2028id",
        _StringCoercionTrap(REQUEST_ID),
    )
    for invalid_request_id in invalid_request_ids:
        call(False, x_request_id=invalid_request_id)
    for control_code in (*range(0x20), *range(0x7F, 0xA0)):
        call(False, x_request_id=f"request{chr(control_code)}id")

    for invalid_secret in (
        "",
        None,
        True,
        1,
        b"segredo-ficticio-mp2-2026",
        _StringCoercionTrap(SECRET),
    ):
        call(False, secret=invalid_secret)

    verifier = MercadoPagoWebhookSignatureVerifier(
        validador=validar_mercado_pago_webhook_hmac,
        secret=SECRET,
    )
    event = {
        "notification_id": "8128",
        "payment_id": DATA_ID,
        "request_id": REQUEST_ID,
    }
    assert verifier.verificar(event, VALID_SIGNATURE) is True
    invalid_signature = f"ts={TIMESTAMP},v1={divergent_digest}"
    assert verifier.verificar(event, invalid_signature) is False

    for record in caplog.records:
        public_log = f"{record.getMessage()} {record.args!r}"
        assert SECRET not in public_log
        assert MANIFEST not in public_log
        assert VALID_SIGNATURE not in public_log
        assert EXPECTED_DIGEST not in public_log
        assert DATA_ID not in public_log
        assert REQUEST_ID not in public_log
        assert TIMESTAMP not in public_log
