"""Contrato RED offline do futuro cliente de consulta Mercado Pago."""

import ast
import builtins
import inspect
import json
import logging
import math
import os
import socket
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import httpx
import pytest

from app.services.mercado_pago_payment_resolution import (
    MercadoPagoPaymentResolutionError,
    MercadoPagoPaymentResolver,
)


_PAYMENT_ID = "731947"
_ACCESS_TOKEN = "APP_USR-mp3-private-token-9f28"
_TIMEOUT_SECONDS = 4.75
_URL = f"https://api.mercadopago.com/v1/payments/{_PAYMENT_ID}"
_PAYLOAD_MARKER = "mp3-payload-private-6d51"


class _ResponseDouble:
    def __init__(self, *, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error
        self.json_calls = 0

    def json(self):
        self.json_calls += 1
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class _HttpClientDouble:
    def __init__(self, *, response=None, transport_error=None):
        self.response = response
        self.transport_error = transport_error
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if self.transport_error is not None:
            raise self.transport_error
        return self.response


class _DictSubclass(dict):
    pass


class _PrivateStatus(int):
    def __new__(cls, value, marker):
        instance = super().__new__(cls, value)
        instance.marker = marker
        return instance

    def __str__(self):
        return self.marker

    def __repr__(self):
        return self.marker


class _ForbiddenEnvironment(dict):
    @staticmethod
    def _deny(*_args, **_kwargs):
        raise AssertionError("o cliente nao pode ler variaveis de ambiente")

    __contains__ = _deny
    __getitem__ = _deny
    __iter__ = _deny
    __len__ = _deny
    copy = _deny
    get = _deny
    items = _deny
    keys = _deny
    values = _deny


def _forbidden_external_access(*_args, **_kwargs):
    raise AssertionError("o contrato deve permanecer offline e sem cliente global")


def _assert_exact_get(
    http_client,
    *,
    payment_id=_PAYMENT_ID,
    timeout_seconds=_TIMEOUT_SECONDS,
):
    assert http_client.calls == [
        {
            "url": f"https://api.mercadopago.com/v1/payments/{payment_id}",
            "headers": {
                "Accept": "application/json",
                "Authorization": f"Bearer {_ACCESS_TOKEN}",
            },
            "timeout": timeout_seconds,
            "follow_redirects": False,
        }
    ]


def _assert_not_exposed(texts, private_values):
    combined = "\n".join(texts).lower()
    for private_value in private_values:
        rendered = str(private_value)
        assert rendered
        assert rendered.lower() not in combined


def _capture_client_error(
    error_type,
    operation,
    *,
    caplog,
    constant_representations,
    client=None,
    private_values=(),
):
    caplog.clear()
    with pytest.raises(error_type) as captured:
        operation()

    error = captured.value
    representations = (str(error), repr(error))
    assert all(representations)
    if constant_representations:
        assert representations == constant_representations[0]
    else:
        constant_representations.append(representations)

    observable_texts = [*representations, caplog.text]
    if client is not None:
        observable_texts.append(repr(client))
    _assert_not_exposed(
        observable_texts,
        (
            "Authorization",
            _ACCESS_TOKEN,
            _PAYMENT_ID,
            _URL,
            _PAYLOAD_MARKER,
            *private_values,
        ),
    )
    return error


def _caught_exception_names(exception_type):
    if exception_type is None:
        return {"bare-except"}
    if isinstance(exception_type, ast.Name):
        return {exception_type.id}
    if isinstance(exception_type, ast.Attribute):
        return {exception_type.attr}
    if isinstance(exception_type, ast.Tuple):
        names = set()
        for element in exception_type.elts:
            names.update(_caught_exception_names(element))
        return names
    return set()


def _assert_narrow_source_contract(module):
    tree = ast.parse(inspect.getsource(module))
    forbidden_import_roots = {
        "dotenv",
        "mercadopago",
        "requests",
        "socket",
        "urllib",
    }
    forbidden_imports = []
    forbidden_environment_accesses = []
    broad_handlers = []
    imported_environment_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.partition(".")[0] in forbidden_import_roots:
                    forbidden_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").partition(".")[0]
            if root in forbidden_import_roots:
                forbidden_imports.append(node.module or "")
            if node.module == "os":
                for alias in node.names:
                    if alias.name in {"environ", "getenv"}:
                        imported_environment_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in {"environ", "getenv"}
            ):
                forbidden_environment_accesses.append(node.attr)
        elif isinstance(node, ast.Name):
            if node.id in imported_environment_names:
                forbidden_environment_accesses.append(node.id)
        elif isinstance(node, ast.ExceptHandler):
            caught = _caught_exception_names(node.type)
            if caught & {"Exception", "BaseException", "bare-except"}:
                broad_handlers.append(caught)

    assert forbidden_imports == []
    assert forbidden_environment_accesses == []
    assert broad_handlers == []


def test_mercado_pago_payment_client_contract_red(monkeypatch, caplog):
    original_import = builtins.__import__
    original_httpx_client_types = (httpx.Client, httpx.AsyncClient)
    forbidden_roots = {
        "dotenv",
        "mercadopago",
        "requests",
        "socket",
        "urllib",
    }

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.partition(".")[0] in forbidden_roots:
            raise AssertionError(f"import HTTP proibido: {name}")
        return original_import(name, globals, locals, fromlist, level)

    caplog.set_level(logging.DEBUG)
    with monkeypatch.context() as runtime_guard:
        runtime_guard.setattr(builtins, "__import__", guarded_import)
        runtime_guard.setattr(builtins, "print", _forbidden_external_access)
        runtime_guard.setattr(os, "getenv", _forbidden_external_access)
        runtime_guard.setattr(os, "environ", _ForbiddenEnvironment())
        runtime_guard.setattr(socket, "create_connection", _forbidden_external_access)
        runtime_guard.setattr(httpx, "get", _forbidden_external_access)
        runtime_guard.setattr(httpx, "request", _forbidden_external_access)
        runtime_guard.setattr(httpx, "Client", _forbidden_external_access)
        runtime_guard.setattr(httpx, "AsyncClient", _forbidden_external_access)

        payment_module = import_module(
            "app.services.mercado_pago_payment_client"
        )
        client_type = payment_module.MercadoPagoPaymentClient
        error_type = payment_module.MercadoPagoPaymentClientError

        assert inspect.isclass(client_type)
        assert inspect.isclass(error_type)
        assert issubclass(error_type, Exception)

        constructor_parameters = list(
            inspect.signature(client_type).parameters.values()
        )
        assert [parameter.name for parameter in constructor_parameters] == [
            "http_client",
            "access_token",
            "timeout_seconds",
        ]
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in constructor_parameters
        )
        assert all(
            parameter.default is inspect.Parameter.empty
            for parameter in constructor_parameters
        )

        method_parameters = list(
            inspect.signature(client_type.obter_pagamento).parameters.values()
        )
        assert [parameter.name for parameter in method_parameters] == [
            "self",
            "payment_id",
        ]
        assert method_parameters[0].kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
        assert method_parameters[1].kind is inspect.Parameter.KEYWORD_ONLY
        assert method_parameters[1].default is inspect.Parameter.empty

        _assert_narrow_source_contract(payment_module)
        assert not any(
            isinstance(value, original_httpx_client_types)
            for value in vars(payment_module).values()
        )

        constant_representations = []
        valid_response = _ResponseDouble(
            payload={
                "id": int(_PAYMENT_ID),
                "external_reference": "91",
                "status": "approved",
                "transaction_amount": "49.90",
                "currency_id": "BRL",
                "provider_extension": {"marker": _PAYLOAD_MARKER},
            }
        )
        valid_http_client = _HttpClientDouble(response=valid_response)
        client = client_type(
            http_client=valid_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        assert valid_http_client.calls == []
        _assert_not_exposed(
            (repr(client), caplog.text),
            ("Authorization", _ACCESS_TOKEN, _PAYMENT_ID, _URL, _PAYLOAD_MARKER),
        )

        integer_timeout_response = _ResponseDouble(payload={"integer": True})
        integer_timeout_http_client = _HttpClientDouble(
            response=integer_timeout_response
        )
        integer_timeout_client = client_type(
            http_client=integer_timeout_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=2,
        )
        assert integer_timeout_client.obter_pagamento(
            payment_id=_PAYMENT_ID
        ) == {"integer": True}
        _assert_exact_get(integer_timeout_http_client, timeout_seconds=2)
        assert integer_timeout_response.json_calls == 1
        _assert_not_exposed(
            (repr(integer_timeout_client), caplog.text),
            ("Authorization", _ACCESS_TOKEN, _PAYMENT_ID, _URL),
        )

        with pytest.raises(TypeError):
            client_type(valid_http_client, _ACCESS_TOKEN, _TIMEOUT_SECONDS)
        with pytest.raises(TypeError):
            client.obter_pagamento(_PAYMENT_ID)
        assert valid_http_client.calls == []

        caplog.clear()
        returned_payload = client.obter_pagamento(payment_id=_PAYMENT_ID)
        assert type(returned_payload) is dict
        assert returned_payload == valid_response.payload
        assert returned_payload is not valid_response.payload
        returned_payload["client_copy_probe"] = True
        assert "client_copy_probe" not in valid_response.payload
        assert valid_response.json_calls == 1
        _assert_exact_get(valid_http_client)
        _assert_not_exposed(
            (repr(client), caplog.text),
            ("Authorization", _ACCESS_TOKEN, _PAYMENT_ID, _URL, _PAYLOAD_MARKER),
        )

        resolver_payload = {
            "id": int(_PAYMENT_ID),
            "external_reference": "91",
            "status": "approved",
            "transaction_amount": "49.90",
            "currency_id": "BRL",
            "provider_extension": {"marker": _PAYLOAD_MARKER},
        }
        resolver_response = _ResponseDouble(payload=resolver_payload)
        resolver_http_client = _HttpClientDouble(response=resolver_response)
        resolver_client = client_type(
            http_client=resolver_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        resolver = MercadoPagoPaymentResolver(
            cliente_pagamentos=resolver_client
        )
        assert resolver.resolver_pagamento(_PAYMENT_ID, "8128") == {
            "ordem_id": 91,
            "event_id": "8128",
            "valor": Decimal("49.90"),
            "moeda": "BRL",
        }
        assert resolver_payload == {
            "id": int(_PAYMENT_ID),
            "external_reference": "91",
            "status": "approved",
            "transaction_amount": "49.90",
            "currency_id": "BRL",
            "provider_extension": {"marker": _PAYLOAD_MARKER},
        }
        assert resolver_response.json_calls == 1
        _assert_exact_get(resolver_http_client)

        business_payloads = (
            {
                "id": int(_PAYMENT_ID),
                "external_reference": "91",
                "status": "pending",
                "provider_extension": _PAYLOAD_MARKER,
            },
            {
                "id": int(_PAYMENT_ID),
                "external_reference": "not-an-order",
                "status": "provider-specific-status",
                "transaction_amount": "provider-specific-amount",
                "currency_id": "USD",
                "provider_extension": _PAYLOAD_MARKER,
            },
        )
        for business_payload in business_payloads:
            response = _ResponseDouble(payload=business_payload)
            http_client = _HttpClientDouble(response=response)
            transparent_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            transparent_result = transparent_client.obter_pagamento(
                payment_id=_PAYMENT_ID
            )
            assert type(transparent_result) is dict
            assert transparent_result == business_payload
            assert transparent_result is not business_payload
            assert response.json_calls == 1
            _assert_exact_get(http_client)

        pending_response = _ResponseDouble(payload=business_payloads[0])
        pending_http_client = _HttpClientDouble(response=pending_response)
        pending_resolver = MercadoPagoPaymentResolver(
            cliente_pagamentos=client_type(
                http_client=pending_http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        )
        assert pending_resolver.resolver_pagamento(_PAYMENT_ID, "8129") is None
        _assert_exact_get(pending_http_client)

        invalid_business_response = _ResponseDouble(payload=business_payloads[1])
        invalid_business_http_client = _HttpClientDouble(
            response=invalid_business_response
        )
        invalid_business_resolver = MercadoPagoPaymentResolver(
            cliente_pagamentos=client_type(
                http_client=invalid_business_http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
        )
        with pytest.raises(MercadoPagoPaymentResolutionError):
            invalid_business_resolver.resolver_pagamento(_PAYMENT_ID, "8130")
        _assert_exact_get(invalid_business_http_client)

        invalid_payment_http_client = _HttpClientDouble(
            response=_ResponseDouble(payload={})
        )
        invalid_payment_client = client_type(
            http_client=invalid_payment_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        for invalid_payment_id in (
            None,
            True,
            1,
            "",
            "0",
            "00",
            f"0{_PAYMENT_ID}",
            f"+{_PAYMENT_ID}",
            f"-{_PAYMENT_ID}",
            f"{_PAYMENT_ID}.0",
            f" {_PAYMENT_ID}",
            f"{_PAYMENT_ID} ",
            f"{_PAYMENT_ID[:3]} {_PAYMENT_ID[3:]}",
            f"{_PAYMENT_ID}\t",
            f"{_PAYMENT_ID}\r",
            f"{_PAYMENT_ID}\n",
            "١٢٣",
            "１２３",
        ):
            _capture_client_error(
                error_type,
                lambda value=invalid_payment_id: invalid_payment_client.obter_pagamento(
                    payment_id=value
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=invalid_payment_client,
                private_values=(
                    (invalid_payment_id,)
                    if invalid_payment_id in {"١٢٣", "１２３"}
                    else ()
                ),
            )
            assert invalid_payment_http_client.calls == []

        invalid_tokens = (
            None,
            True,
            123,
            _ACCESS_TOKEN.encode("ascii"),
            "",
            " ",
            "\t",
            "\r",
            "\n",
            f"{_ACCESS_TOKEN} with-space",
            f" {_ACCESS_TOKEN}",
            f"{_ACCESS_TOKEN} ",
            f"{_ACCESS_TOKEN}\rprivate",
            f"{_ACCESS_TOKEN}\nprivate",
            f"{_ACCESS_TOKEN}\x00private",
            f"{_ACCESS_TOKEN}\x1fprivate",
            f"{_ACCESS_TOKEN}\x7fprivate",
            f"{_ACCESS_TOKEN}\u200bprivate",
        )
        for invalid_token in invalid_tokens:
            fresh_http_client = _HttpClientDouble(response=valid_response)
            _capture_client_error(
                error_type,
                lambda value=invalid_token, transport=fresh_http_client: client_type(
                    http_client=transport,
                    access_token=value,
                    timeout_seconds=_TIMEOUT_SECONDS,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
            )
            assert fresh_http_client.calls == []

        for invalid_timeout in (
            None,
            True,
            False,
            "4.75",
            0,
            0.0,
            -1,
            -0.1,
            math.inf,
            -math.inf,
            math.nan,
            1 + 0j,
        ):
            fresh_http_client = _HttpClientDouble(response=valid_response)
            _capture_client_error(
                error_type,
                lambda value=invalid_timeout, transport=fresh_http_client: client_type(
                    http_client=transport,
                    access_token=_ACCESS_TOKEN,
                    timeout_seconds=value,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
            )
            assert fresh_http_client.calls == []

        for invalid_http_client in (
            None,
            object(),
            SimpleNamespace(get=None),
            SimpleNamespace(get="not-callable"),
        ):
            _capture_client_error(
                error_type,
                lambda value=invalid_http_client: client_type(
                    http_client=value,
                    access_token=_ACCESS_TOKEN,
                    timeout_seconds=_TIMEOUT_SECONDS,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
            )

        private_status_marker = "mp3-status-private-a814"
        non_success_statuses = (
            201,
            204,
            400,
            401,
            404,
            408,
            429,
            500,
            503,
            True,
            False,
            200.0,
            _PrivateStatus(200, private_status_marker),
            None,
        )
        for status_code in non_success_statuses:
            response = _ResponseDouble(
                status_code=status_code,
                payload={"marker": _PAYLOAD_MARKER},
            )
            http_client = _HttpClientDouble(response=response)
            status_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=status_client: current.obter_pagamento(
                    payment_id=_PAYMENT_ID
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=status_client,
                private_values=(private_status_marker,),
            )
            _assert_exact_get(http_client)
            assert response.json_calls == 0

        transport_private_marker = "mp3-transport-private-f52c"
        request = httpx.Request("GET", _URL)
        transport_errors = (
            httpx.TimeoutException(
                transport_private_marker,
                request=request,
            ),
            httpx.ConnectError(
                transport_private_marker,
                request=request,
            ),
        )
        for transport_error in transport_errors:
            http_client = _HttpClientDouble(transport_error=transport_error)
            transport_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=transport_client: current.obter_pagamento(
                    payment_id=_PAYMENT_ID
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=transport_client,
                private_values=(transport_private_marker,),
            )
            _assert_exact_get(http_client)

        unexpected_transport_error = ValueError(
            "mp3-unexpected-transport-private-58de"
        )
        unexpected_http_client = _HttpClientDouble(
            transport_error=unexpected_transport_error
        )
        unexpected_client = client_type(
            http_client=unexpected_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        with pytest.raises(ValueError) as unexpected_transport_captured:
            unexpected_client.obter_pagamento(payment_id=_PAYMENT_ID)
        assert unexpected_transport_captured.value is unexpected_transport_error
        _assert_exact_get(unexpected_http_client)

        json_private_marker = "mp3-json-private-c724"
        invalid_json_response = _ResponseDouble(
            json_error=json.JSONDecodeError(
                "invalid private JSON",
                json_private_marker,
                0,
            )
        )
        invalid_json_http_client = _HttpClientDouble(
            response=invalid_json_response
        )
        invalid_json_client = client_type(
            http_client=invalid_json_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        _capture_client_error(
            error_type,
            lambda: invalid_json_client.obter_pagamento(payment_id=_PAYMENT_ID),
            caplog=caplog,
            constant_representations=constant_representations,
            client=invalid_json_client,
            private_values=(json_private_marker,),
        )
        _assert_exact_get(invalid_json_http_client)
        assert invalid_json_response.json_calls == 1

        unicode_private_marker = "mp3-unicode-private-37af"
        unicode_private_bytes = unicode_private_marker.encode("ascii") + b"\xff"
        invalid_byte_index = len(unicode_private_bytes) - 1
        invalid_unicode_response = _ResponseDouble(
            json_error=UnicodeDecodeError(
                "utf-8",
                unicode_private_bytes,
                invalid_byte_index,
                invalid_byte_index + 1,
                unicode_private_marker,
            )
        )
        invalid_unicode_http_client = _HttpClientDouble(
            response=invalid_unicode_response
        )
        invalid_unicode_client = client_type(
            http_client=invalid_unicode_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        _capture_client_error(
            error_type,
            lambda: invalid_unicode_client.obter_pagamento(
                payment_id=_PAYMENT_ID
            ),
            caplog=caplog,
            constant_representations=constant_representations,
            client=invalid_unicode_client,
            private_values=(unicode_private_marker,),
        )
        _assert_exact_get(invalid_unicode_http_client)
        assert invalid_unicode_response.json_calls == 1

        unexpected_json_error = ValueError("mp3-unexpected-json-private-814a")
        unexpected_json_response = _ResponseDouble(
            json_error=unexpected_json_error
        )
        unexpected_json_http_client = _HttpClientDouble(
            response=unexpected_json_response
        )
        unexpected_json_client = client_type(
            http_client=unexpected_json_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        with pytest.raises(ValueError) as unexpected_json_captured:
            unexpected_json_client.obter_pagamento(payment_id=_PAYMENT_ID)
        assert unexpected_json_captured.value is unexpected_json_error
        _assert_exact_get(unexpected_json_http_client)
        assert unexpected_json_response.json_calls == 1

        invalid_payloads = (
            [],
            "mp3-string-payload-private-8cb1",
            None,
            _DictSubclass(marker=_PAYLOAD_MARKER),
        )
        for invalid_payload in invalid_payloads:
            response = _ResponseDouble(payload=invalid_payload)
            http_client = _HttpClientDouble(response=response)
            payload_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=payload_client: current.obter_pagamento(
                    payment_id=_PAYMENT_ID
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=payload_client,
                private_values=("mp3-string-payload-private-8cb1",),
            )
            _assert_exact_get(http_client)
            assert response.json_calls == 1

        for response_without_json in (
            SimpleNamespace(status_code=200),
            SimpleNamespace(status_code=200, json=None),
            SimpleNamespace(status_code=200, json="not-callable"),
        ):
            http_client = _HttpClientDouble(response=response_without_json)
            response_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=response_client: current.obter_pagamento(
                    payment_id=_PAYMENT_ID
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=response_client,
            )
            _assert_exact_get(http_client)

        assert len(constant_representations) == 1
