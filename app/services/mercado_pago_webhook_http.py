"""Normalizacao HTTP estrita do webhook do Mercado Pago."""

import json
from collections.abc import Sequence


class MercadoPagoWebhookHttpNormalizationError(Exception):
    """Erro publico opaco da normalizacao HTTP."""

    def __init__(self, *_args, **_kwargs):
        super().__init__("Entrada invalida")


class _InvalidInput(Exception):
    pass


def _pairs(value):
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray, memoryview))
    ):
        raise _InvalidInput

    result = []
    for pair in value:
        if (
            not isinstance(pair, Sequence)
            or isinstance(pair, (str, bytes, bytearray, memoryview))
            or len(pair) != 2
        ):
            raise _InvalidInput
        result.append((pair[0], pair[1]))
    return result


def _opaque_text(value):
    return (
        isinstance(value, str)
        and bool(value)
        and not any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _positive_canonical_ascii_decimal(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value.isascii()
        and value.isdecimal()
        and value[0] != "0"
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidInput
        result[key] = value
    return result


def _reject_json_constant(_value):
    raise _InvalidInput


def _normalize(*, method, content_type, headers, query_params, body):
    if method != "POST" or type(method) is not str:
        raise _InvalidInput
    if content_type != "application/json" or type(content_type) is not str:
        raise _InvalidInput
    if type(body) is not bytes:
        raise _InvalidInput

    normalized_headers = {}
    for name, value in _pairs(headers):
        if not isinstance(name, str):
            raise _InvalidInput
        lowered_name = name.lower()
        if lowered_name in ("x-signature", "x-request-id"):
            if lowered_name in normalized_headers or not _opaque_text(value):
                raise _InvalidInput
            normalized_headers[lowered_name] = value
    if set(normalized_headers) != {"x-signature", "x-request-id"}:
        raise _InvalidInput

    query = {}
    for name, value in _pairs(query_params):
        if not isinstance(name, str) or name in query:
            raise _InvalidInput
        query[name] = value
    if set(query) != {"data.id", "type"}:
        raise _InvalidInput
    if not _positive_canonical_ascii_decimal(query["data.id"]):
        raise _InvalidInput
    if query["type"] != "payment" or type(query["type"]) is not str:
        raise _InvalidInput

    decoded_body = body.decode("utf-8", errors="strict")
    document = json.loads(
        decoded_body,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_json_constant,
    )
    if type(document) is not dict:
        raise _InvalidInput

    required = {"id", "type", "action", "data"}
    optional = {
        "api_version",
        "application_id",
        "date_created",
        "live_mode",
        "user_id",
    }
    if not required.issubset(document) or not set(document).issubset(required | optional):
        raise _InvalidInput

    notification_id = document["id"]
    if isinstance(notification_id, bool) or not isinstance(notification_id, int) or notification_id <= 0:
        raise _InvalidInput

    data = document["data"]
    if type(data) is not dict or set(data) != {"id"}:
        raise _InvalidInput
    payment_id = data["id"]
    if not _positive_canonical_ascii_decimal(payment_id) or payment_id != query["data.id"]:
        raise _InvalidInput

    if document["type"] != "payment" or type(document["type"]) is not str:
        raise _InvalidInput
    if document["type"] != query["type"]:
        raise _InvalidInput
    if document["action"] not in ("payment.created", "payment.updated") or type(document["action"]) is not str:
        raise _InvalidInput

    return (
        {
            "notification_id": str(notification_id),
            "payment_id": payment_id,
            "request_id": normalized_headers["x-request-id"],
        },
        normalized_headers["x-signature"],
    )


def normalizar_mercado_pago_webhook_http(
    *,
    method,
    content_type,
    headers,
    query_params,
    body,
):
    """Valida e reduz uma requisicao HTTP ao envelope canonico do orquestrador."""

    try:
        return _normalize(
            method=method,
            content_type=content_type,
            headers=headers,
            query_params=query_params,
            body=body,
        )
    except (_InvalidInput, UnicodeDecodeError, json.JSONDecodeError):
        raise MercadoPagoWebhookHttpNormalizationError() from None
