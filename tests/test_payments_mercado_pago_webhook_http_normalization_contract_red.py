"""Contrato RED offline do normalizador HTTP do webhook Mercado Pago."""

import ast
import inspect

import pytest


PRIVATE_VALUES = (
    "ts=1700000000,v1=assinatura-privada-9931",
    "request-privado-9931",
    "4719",
    "8128",
    "corpo-privado-9931",
    "consulta-privada-9931",
    "cabecalho-privado-9931",
    "segredo-privado-9931",
)


def _valid_input():
    return {
        "method": "POST",
        "content_type": "application/json",
        "headers": (
            ("Content-Language", "pt-BR"),
            ("X-Signature", PRIVATE_VALUES[0]),
            ("x-request-id", PRIVATE_VALUES[1]),
        ),
        "query_params": (("data.id", PRIVATE_VALUES[2]), ("type", "payment")),
        "body": (
            b'{"id":8128,"type":"payment","action":"payment.created",'
            b'"data":{"id":"4719"},"api_version":"v1",'
            b'"application_id":123,"date_created":"2026-09-01T00:00:00Z",'
            b'"live_mode":true,"user_id":456}'
        ),
    }


def _assert_private_error(error, *extra_private):
    assert type(error) is webhook_http.MercadoPagoWebhookHttpNormalizationError
    prohibited = (
        "signature",
        "request id",
        "request_id",
        "payment id",
        "payment_id",
        "notification id",
        "notification_id",
        "body",
        "query",
        "header",
        "json",
        "sql",
        "token",
        "secret",
        "segredo",
        "payload",
        *PRIVATE_VALUES,
        *extra_private,
    )
    for representation in (str(error), repr(error)):
        lowered = representation.lower()
        for value in prohibited:
            assert str(value).lower() not in lowered


def _assert_rejected(changes=None, *, cause_is_none=False, private=()):
    request = _valid_input()
    request.update(changes or {})
    with pytest.raises(
        webhook_http.MercadoPagoWebhookHttpNormalizationError
    ) as captured:
        webhook_http.normalizar_mercado_pago_webhook_http(**request)
    _assert_private_error(captured.value, *private)
    if cause_is_none:
        assert captured.value.__cause__ is None
        assert captured.value.__suppress_context__ is True


def test_payments_mercado_pago_webhook_http_normalization_contract_red():
    import app.services.mercado_pago_webhook_http as webhook_http

    globals()["webhook_http"] = webhook_http
    function = webhook_http.normalizar_mercado_pago_webhook_http
    signature = inspect.signature(function)
    assert tuple(signature.parameters) == (
        "method",
        "content_type",
        "headers",
        "query_params",
        "body",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )

    expected = {
        "notification_id": PRIVATE_VALUES[3],
        "payment_id": PRIVATE_VALUES[2],
        "request_id": PRIVATE_VALUES[1],
    }
    first_envelope, first_signature = function(**_valid_input())
    second_request = _valid_input()
    second_request["body"] = second_request["body"].replace(
        b"payment.created", b"payment.updated"
    )
    second_envelope, second_signature = function(**second_request)
    assert type(first_envelope) is dict
    assert first_envelope == expected
    assert second_envelope == expected
    assert first_envelope is not second_envelope
    assert first_signature == second_signature == PRIVATE_VALUES[0]
    first_envelope["payment_id"] = "9999"
    assert second_envelope == expected
    assert set(second_envelope) == {
        "notification_id",
        "payment_id",
        "request_id",
    }

    for method in ("GET", "post", " POST", "POST ", None, 1):
        _assert_rejected({"method": method})
    for content_type in (
        "text/plain",
        "Application/JSON",
        "application/json; charset=utf-8",
        " application/json",
        None,
    ):
        _assert_rejected({"content_type": content_type})
    for body in ("{}", bytearray(b"{}"), memoryview(b"{}"), None):
        _assert_rejected({"body": body})
    for body in (b"\xff", b'{"id":'):
        _assert_rejected({"body": body}, cause_is_none=True, private=(body,))
    for body in (b"[]", b"null", b"true", b"1", b'"scalar"'):
        _assert_rejected({"body": body})

    malformed_collections = (
        {},
        "x-signature=value",
        b"x-signature=value",
        None,
        ("x-signature", "value"),
        (("x-signature",),),
        (("x-signature", "value", "extra"),),
    )
    for malformed in malformed_collections:
        _assert_rejected({"headers": malformed})
        _assert_rejected({"query_params": malformed})

    valid = _valid_input()
    signature_header = ("x-signature", PRIVATE_VALUES[0])
    request_header = ("x-request-id", PRIVATE_VALUES[1])
    for headers in (
        (request_header,),
        (signature_header,),
        (signature_header, request_header, ("X-SIGNATURE", "duplicate")),
        (signature_header, request_header, ("X-Request-ID", "duplicate")),
    ):
        _assert_rejected({"headers": headers}, private=("duplicate",))
    for query in (
        (("type", "payment"),),
        (("data.id", PRIVATE_VALUES[2]),),
        (("data.id", PRIVATE_VALUES[2]), ("type", "payment"), ("extra", "x")),
        (("data.id", PRIVATE_VALUES[2]), ("data.id", PRIVATE_VALUES[2]), ("type", "payment")),
        (("data.id", PRIVATE_VALUES[2]), ("type", "payment"), ("type", "payment")),
    ):
        _assert_rejected({"query_params": query})

    duplicate_json = (
        b'{"id":8128,"id":8129,"type":"payment","action":"payment.created","data":{"id":"4719"}}',
        b'{"id":8128,"type":"payment","action":"payment.created","data":{"id":"4719","id":"4720"}}',
    )
    for body in duplicate_json:
        _assert_rejected({"body": body}, cause_is_none=True, private=(body,))

    invalid_bodies = (
        b'{"type":"payment","action":"payment.created","data":{"id":"4719"}}',
        b'{"id":8128,"action":"payment.created","data":{"id":"4719"}}',
        b'{"id":8128,"type":"payment","data":{"id":"4719"}}',
        b'{"id":8128,"type":"payment","action":"payment.created"}',
        b'{"id":8128,"type":"payment","action":"payment.created","data":{"id":"4719"},"extra":true}',
        b'{"id":8128,"type":"payment","action":"payment.created","data":{"id":"4719","extra":true}}',
        b'{"id":8128,"type":"payment","action":"payment.created","data":[]}',
    )
    for body in invalid_bodies:
        _assert_rejected({"body": body}, private=(body,))

    invalid_payment_ids = (
        None,
        True,
        4719,
        4719.0,
        "",
        "0",
        "-1",
        "04719",
        " 4719",
        "4719 ",
        "47 19",
        "\u0664\u0667\u0661\u0669",
    )
    for invalid in invalid_payment_ids:
        query = (("data.id", invalid), ("type", "payment"))
        _assert_rejected({"query_params": query}, private=(invalid,))
        body_value = (
            ("null" if invalid is None else str(invalid).lower()).encode("ascii")
            if not isinstance(invalid, str)
            else ('"' + invalid + '"').encode("utf-8")
        )
        body = (
            b'{"id":8128,"type":"payment","action":"payment.created",'
            b'"data":{"id":' + body_value + b"}}"
        )
        _assert_rejected({"body": body}, private=(invalid, body))
    divergent_body = valid["body"].replace(b'"4719"', b'"4720"')
    _assert_rejected({"body": divergent_body}, private=(divergent_body,))

    for invalid in (None, True, "8128", 8128.0, 0, -1):
        value = (
            b"null" if invalid is None else
            b"true" if invalid is True else
            ('"' + invalid + '"').encode() if isinstance(invalid, str) else
            str(invalid).encode()
        )
        body = valid["body"].replace(b"8128", value, 1)
        _assert_rejected({"body": body}, private=(invalid, body))

    invalid_request_ids = (None, 9931, "", " request", "request ", "request\t1", "request\r1", "request\n1", "request\x001")
    for invalid in invalid_request_ids:
        headers = (signature_header, ("x-request-id", invalid))
        _assert_rejected({"headers": headers}, private=(invalid,))
    invalid_signatures = (None, 9931, "", " signature", "signature ", "signature\t1", "signature\r1", "signature\n1")
    for invalid in invalid_signatures:
        headers = (("x-signature", invalid), request_header)
        _assert_rejected({"headers": headers}, private=(invalid,))

    for query_type, body_type in (("refund", "payment"), ("payment", "refund"), ("refund", "refund")):
        query = (("data.id", PRIVATE_VALUES[2]), ("type", query_type))
        body = valid["body"].replace(b'"type":"payment"', ('"type":"' + body_type + '"').encode())
        _assert_rejected({"query_params": query, "body": body}, private=(query_type, body_type))
    unknown_action = valid["body"].replace(b"payment.created", b"payment.cancelled")
    _assert_rejected({"body": unknown_action}, private=(unknown_action,))

    source = inspect.getsource(webhook_http)
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert "fastapi" not in imported_roots
    assert imported_roots.isdisjoint({"requests", "httpx", "urllib", "socket", "sqlalchemy"})
    lowered_source = source.lower()
    for forbidden in (
        "mercadopagowebhookorchestrator",
        "resolver_pagamento",
        "sessionmaker",
        "create_engine",
        "os.getenv",
        "os.environ",
        "environ.get",
        "access_token",
        "payment.created\" in",
        "ts=",
        "v1=",
    ):
        assert forbidden not in lowered_source
    assert "secret" not in signature.parameters
    assert "access_token" not in signature.parameters
