"""Contrato RED offline do futuro cliente de preferencias Mercado Pago."""

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

from app.services.mercado_pago_checkout_offer_one_time import (
    MercadoPagoCheckoutOfferOneTimeGateway,
)


_ACCESS_TOKEN = "APP_USR-mp4-private-token-74e2"
_IDEMPOTENCY_KEY = "mp4-order-91-preference-5cb8"
_TIMEOUT_SECONDS = 4.25
_URL = "https://api.mercadopago.com/checkout/preferences"
_PAYLOAD_MARKER = "mp4-payload-private-a81d"
_RESPONSE_MARKER = "mp4-response-private-c39f"
_CHECKOUT_URL = "https://www.mercadopago.com.br/checkout/v1/redirect"


class _ResponseDouble:
    def __init__(self, *, status_code=201, payload=None, json_error=None):
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
    def __init__(
        self,
        *,
        response=None,
        transport_error=None,
        mutate_payload=None,
    ):
        self.response = response
        self.transport_error = transport_error
        self.mutate_payload = mutate_payload
        self.calls = []

    def post(self, **kwargs):
        self.calls.append(kwargs)
        if self.mutate_payload is not None:
            self.mutate_payload(kwargs["json"])
        if self.transport_error is not None:
            raise self.transport_error
        return self.response


class _DictSubclass(dict):
    pass


class _StringSubclass(str):
    pass


class _IntegerSubclass(int):
    pass


class _FloatSubclass(float):
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
    raise AssertionError("o contrato deve permanecer offline e injetado")


def _assert_exact_post(
    http_client,
    *,
    payload,
    idempotency_key=_IDEMPOTENCY_KEY,
    timeout_seconds=_TIMEOUT_SECONDS,
):
    assert http_client.calls == [
        {
            "url": _URL,
            "headers": {
                "Accept": "application/json",
                "Authorization": f"Bearer {_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": idempotency_key,
            },
            "json": payload,
            "timeout": timeout_seconds,
            "follow_redirects": False,
        }
    ]


def _assert_not_exposed(texts, private_values=()):
    lowered_texts = tuple(text.lower() for text in texts)
    for private_value in (
        _ACCESS_TOKEN,
        _IDEMPOTENCY_KEY,
        _URL,
        _PAYLOAD_MARKER,
        _RESPONSE_MARKER,
        *private_values,
    ):
        rendered = str(private_value)
        assert rendered
        if rendered.isspace():
            continue
        assert all(rendered.lower() not in text for text in lowered_texts)


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
    assert type(error) is error_type
    representations = (
        str(error),
        repr(error),
        repr(error.args),
        repr(vars(error)),
    )
    assert all(representations[:3])
    if constant_representations:
        assert representations == constant_representations[0]
    else:
        constant_representations.append(representations)

    observable_texts = [*representations, caplog.text]
    if client is not None:
        observable_texts.extend((str(client), repr(client)))
    _assert_not_exposed(observable_texts, private_values)
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
    return {"unknown-except"}


def _assert_narrow_source_contract(module):
    tree = ast.parse(inspect.getsource(module))
    forbidden_import_roots = {
        "logging",
        "mercadopago",
        "requests",
        "socket",
        "urllib",
    }
    forbidden_httpx_members = {
        "AsyncClient",
        "Client",
        "delete",
        "get",
        "patch",
        "post",
        "put",
        "request",
        "stream",
    }
    forbidden_identifiers = {"logging", "print", "retry", "sleep"}
    allowed_catches = {
        "HTTPError",
        "JSONDecodeError",
        "UnicodeDecodeError",
    }
    forbidden_imports = []
    forbidden_environment_accesses = []
    forbidden_global_http = []
    forbidden_runtime_names = []
    invalid_handlers = []
    imported_environment_names = set()
    os_aliases = {"os"}
    httpx_aliases = {"httpx"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.partition(".")[0]
                if root in forbidden_import_roots:
                    forbidden_imports.append(alias.name)
                if alias.name == "os":
                    os_aliases.add(alias.asname or alias.name)
                if alias.name == "httpx":
                    httpx_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").partition(".")[0]
            if root in forbidden_import_roots:
                forbidden_imports.append(node.module or "")
            if node.module == "os":
                for alias in node.names:
                    if alias.name in {"environ", "getenv"}:
                        imported_environment_names.add(
                            alias.asname or alias.name
                        )
            if node.module == "httpx":
                for alias in node.names:
                    if alias.name in forbidden_httpx_members:
                        forbidden_global_http.append(alias.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id in os_aliases
                and node.attr in {"environ", "getenv"}
            ):
                forbidden_environment_accesses.append(node.attr)
            if (
                isinstance(node.value, ast.Name)
                and node.value.id in httpx_aliases
                and node.attr in forbidden_httpx_members
            ):
                forbidden_global_http.append(node.attr)
            if node.attr in {"retry", "sleep"}:
                forbidden_runtime_names.append(node.attr)
        elif isinstance(node, ast.Name):
            if node.id in imported_environment_names:
                forbidden_environment_accesses.append(node.id)
            if node.id in forbidden_identifiers:
                forbidden_runtime_names.append(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in forbidden_identifiers:
                forbidden_runtime_names.append(node.name)
        elif isinstance(node, ast.ExceptHandler):
            caught = _caught_exception_names(node.type)
            if not caught or not caught <= allowed_catches:
                invalid_handlers.append(caught)

    assert forbidden_imports == []
    assert forbidden_environment_accesses == []
    assert forbidden_global_http == []
    assert forbidden_runtime_names == []
    assert invalid_handlers == []


def test_mercado_pago_preference_client_contract_red(monkeypatch, caplog):
    original_import = builtins.__import__
    original_httpx_client_types = (httpx.Client, httpx.AsyncClient)
    forbidden_roots = {
        "logging",
        "mercadopago",
        "requests",
        "socket",
        "urllib",
    }

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.partition(".")[0] in forbidden_roots:
            raise AssertionError(f"import proibido: {name}")
        return original_import(name, globals, locals, fromlist, level)

    caplog.set_level(logging.DEBUG)
    with monkeypatch.context() as runtime_guard:
        runtime_guard.setattr(builtins, "__import__", guarded_import)
        runtime_guard.setattr(builtins, "print", _forbidden_external_access)
        runtime_guard.setattr(os, "getenv", _forbidden_external_access)
        runtime_guard.setattr(os, "environ", _ForbiddenEnvironment())
        runtime_guard.setattr(
            socket,
            "create_connection",
            _forbidden_external_access,
        )
        runtime_guard.setattr(httpx, "get", _forbidden_external_access)
        runtime_guard.setattr(httpx, "post", _forbidden_external_access)
        runtime_guard.setattr(httpx, "request", _forbidden_external_access)
        runtime_guard.setattr(httpx, "stream", _forbidden_external_access)
        runtime_guard.setattr(httpx, "Client", _forbidden_external_access)
        runtime_guard.setattr(
            httpx,
            "AsyncClient",
            _forbidden_external_access,
        )

        preference_module = import_module(
            "app.services.mercado_pago_preference_client"
        )
        client_type = preference_module.MercadoPagoPreferenceClient
        error_type = preference_module.MercadoPagoPreferenceClientError

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
            inspect.signature(client_type.criar_preferencia).parameters.values()
        )
        assert [parameter.name for parameter in method_parameters] == [
            "self",
            "payload",
            "idempotency_key",
        ]
        assert method_parameters[0].kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in method_parameters[1:]
        )
        assert all(
            parameter.default is inspect.Parameter.empty
            for parameter in method_parameters[1:]
        )

        _assert_narrow_source_contract(preference_module)
        assert not any(
            isinstance(value, original_httpx_client_types)
            for value in vars(preference_module).values()
        )
        assert _ACCESS_TOKEN not in inspect.getsource(preference_module)
        assert _IDEMPOTENCY_KEY not in inspect.getsource(preference_module)

        constant_representations = []
        untouched_response = _ResponseDouble(payload={"ready": True})
        untouched_http_client = _HttpClientDouble(response=untouched_response)
        client = client_type(
            http_client=untouched_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        assert untouched_http_client.calls == []
        _assert_not_exposed((str(client), repr(client), caplog.text))

        with pytest.raises(TypeError):
            client_type(
                untouched_http_client,
                _ACCESS_TOKEN,
                _TIMEOUT_SECONDS,
            )
        with pytest.raises(TypeError):
            client.criar_preferencia(
                {"provider_data": True},
                _IDEMPOTENCY_KEY,
            )
        assert untouched_http_client.calls == []

        invalid_tokens = (
            None,
            True,
            123,
            _ACCESS_TOKEN.encode("ascii"),
            _StringSubclass(_ACCESS_TOKEN),
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
            fresh_http_client = _HttpClientDouble(
                response=untouched_response
            )
            _capture_client_error(
                error_type,
                lambda value=invalid_token, transport=fresh_http_client: client_type(
                    http_client=transport,
                    access_token=value,
                    timeout_seconds=_TIMEOUT_SECONDS,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                private_values=(
                    invalid_token
                    if isinstance(invalid_token, (str, bytes))
                    and bool(invalid_token)
                    else "mp4-invalid-token"
                ,),
            )
            assert fresh_http_client.calls == []

        invalid_timeouts = (
            None,
            True,
            False,
            "4.25",
            0,
            0.0,
            -1,
            -0.1,
            math.inf,
            -math.inf,
            math.nan,
            1 + 0j,
            _IntegerSubclass(2),
            _FloatSubclass(2.5),
        )
        for invalid_timeout in invalid_timeouts:
            fresh_http_client = _HttpClientDouble(
                response=untouched_response
            )
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
            SimpleNamespace(post=None),
            SimpleNamespace(post="not-callable"),
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

        integer_timeout_response = _ResponseDouble(
            payload={"integer_timeout": True}
        )
        integer_timeout_http_client = _HttpClientDouble(
            response=integer_timeout_response
        )
        integer_timeout_client = client_type(
            http_client=integer_timeout_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=3,
        )
        assert integer_timeout_client.criar_preferencia(
            payload={"provider_data": True},
            idempotency_key=_IDEMPOTENCY_KEY,
        ) == {"integer_timeout": True}
        _assert_exact_post(
            integer_timeout_http_client,
            payload={"provider_data": True},
            timeout_seconds=3,
        )
        assert integer_timeout_response.json_calls == 1

        invalid_payload_marker = "mp4-invalid-payload-private-d082"
        cyclic_payload = {"marker": invalid_payload_marker}
        cyclic_payload["cycle"] = cyclic_payload
        invalid_payloads = (
            None,
            True,
            1,
            "",
            [],
            (),
            {},
            _DictSubclass(provider_data=True),
            {"value": b"mp4-private-bytes"},
            {"value": object()},
            {"value": Decimal("1.00")},
            {"value": 1 + 2j},
            {"value": {1, 2}},
            {"value": math.nan},
            {"value": math.inf},
            {"value": -math.inf},
            {("tuple", "key"): "not-json"},
            cyclic_payload,
        )
        validation_http_client = _HttpClientDouble(
            response=untouched_response
        )
        validation_client = client_type(
            http_client=validation_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        for invalid_payload in invalid_payloads:
            _capture_client_error(
                error_type,
                lambda value=invalid_payload: validation_client.criar_preferencia(
                    payload=value,
                    idempotency_key=_IDEMPOTENCY_KEY,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=validation_client,
                private_values=(invalid_payload_marker,),
            )
            assert validation_http_client.calls == []

        invalid_idempotency_keys = (
            None,
            True,
            91,
            _IDEMPOTENCY_KEY.encode("ascii"),
            _StringSubclass(_IDEMPOTENCY_KEY),
            "",
            " ",
            "\t",
            "\r",
            "\n",
            f"{_IDEMPOTENCY_KEY} with-space",
            f" {_IDEMPOTENCY_KEY}",
            f"{_IDEMPOTENCY_KEY} ",
            f"{_IDEMPOTENCY_KEY}\rprivate",
            f"{_IDEMPOTENCY_KEY}\nprivate",
            f"{_IDEMPOTENCY_KEY}\x00private",
            f"{_IDEMPOTENCY_KEY}\x1fprivate",
            f"{_IDEMPOTENCY_KEY}\x7fprivate",
            f"{_IDEMPOTENCY_KEY}\u200bprivate",
        )
        for invalid_key in invalid_idempotency_keys:
            fresh_http_client = _HttpClientDouble(
                response=untouched_response
            )
            key_client = client_type(
                http_client=fresh_http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda value=invalid_key, current=key_client: current.criar_preferencia(
                    payload={"provider_data": True},
                    idempotency_key=value,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=key_client,
                private_values=(
                    invalid_key
                    if isinstance(invalid_key, (str, bytes))
                    and bool(invalid_key)
                    else "mp4-invalid-key"
                ,),
            )
            assert fresh_http_client.calls == []

        caller_payload = {
            "provider_extension": {
                "marker": _PAYLOAD_MARKER,
                "items": [{"opaque": [1, 2, 3]}],
            }
        }
        response_payload = {
            "provider_extension": {
                "marker": _RESPONSE_MARKER,
                "values": [{"opaque": True}],
            }
        }
        success_response = _ResponseDouble(payload=response_payload)
        success_http_client = _HttpClientDouble(response=success_response)
        success_client = client_type(
            http_client=success_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        caplog.clear()
        returned_payload = success_client.criar_preferencia(
            payload=caller_payload,
            idempotency_key=_IDEMPOTENCY_KEY,
        )
        _assert_exact_post(success_http_client, payload=caller_payload)
        sent_payload = success_http_client.calls[0]["json"]
        assert sent_payload is not caller_payload
        assert sent_payload["provider_extension"] is not (
            caller_payload["provider_extension"]
        )
        assert sent_payload["provider_extension"]["items"] is not (
            caller_payload["provider_extension"]["items"]
        )
        assert returned_payload == response_payload
        assert returned_payload is not response_payload
        assert returned_payload["provider_extension"] is not (
            response_payload["provider_extension"]
        )
        assert returned_payload["provider_extension"]["values"] is not (
            response_payload["provider_extension"]["values"]
        )
        assert success_response.json_calls == 1

        caller_payload["provider_extension"]["items"][0]["opaque"].append(4)
        assert sent_payload["provider_extension"]["items"][0]["opaque"] == [
            1,
            2,
            3,
        ]
        returned_payload["provider_extension"]["values"][0][
            "opaque"
        ] = False
        assert response_payload["provider_extension"]["values"][0] == {
            "opaque": True
        }
        _assert_not_exposed(
            (str(success_client), repr(success_client), caplog.text)
        )

        exact_call = success_http_client.calls[0]
        assert _ACCESS_TOKEN not in exact_call["url"]
        assert _ACCESS_TOKEN not in repr(exact_call["json"])
        assert _IDEMPOTENCY_KEY not in exact_call["url"]
        assert _IDEMPOTENCY_KEY not in repr(exact_call["json"])
        assert list(exact_call["headers"]).count("X-Idempotency-Key") == 1
        assert exact_call["headers"]["X-Idempotency-Key"] == (
            _IDEMPOTENCY_KEY
        )
        assert all(
            _IDEMPOTENCY_KEY not in str(value)
            for name, value in exact_call["headers"].items()
            if name != "X-Idempotency-Key"
        )

        mutation_original = {
            "provider_extension": {
                "marker": "caller-owned",
                "items": [{"value": 10}],
            }
        }

        def mutate_sent_payload(payload):
            payload["provider_extension"]["marker"] = "transport-mutated"
            payload["provider_extension"]["items"][0]["value"] = 999
            payload["provider_extension"]["items"].append({"value": 1000})

        mutation_response = _ResponseDouble(payload={})
        mutation_http_client = _HttpClientDouble(
            response=mutation_response,
            mutate_payload=mutate_sent_payload,
        )
        mutation_client = client_type(
            http_client=mutation_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        assert mutation_client.criar_preferencia(
            payload=mutation_original,
            idempotency_key=_IDEMPOTENCY_KEY,
        ) == {}
        assert mutation_original == {
            "provider_extension": {
                "marker": "caller-owned",
                "items": [{"value": 10}],
            }
        }
        _assert_exact_post(
            mutation_http_client,
            payload={
                "provider_extension": {
                    "marker": "transport-mutated",
                    "items": [{"value": 999}, {"value": 1000}],
                }
            },
        )
        assert mutation_response.json_calls == 1

        empty_response = _ResponseDouble(payload={})
        transparent_http_client = _HttpClientDouble(response=empty_response)
        transparent_client = client_type(
            http_client=transparent_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        transparent_payload = {
            "provider_owned_field": {"opaque": "uninterpreted"}
        }
        assert transparent_client.criar_preferencia(
            payload=transparent_payload,
            idempotency_key=_IDEMPOTENCY_KEY,
        ) == {}
        _assert_exact_post(
            transparent_http_client,
            payload=transparent_payload,
        )
        assert empty_response.json_calls == 1

        gateway_response_payload = {
            "id": "mp-pref-one-time-91",
            "init_point": _CHECKOUT_URL,
        }
        gateway_response = _ResponseDouble(payload=gateway_response_payload)
        gateway_http_client = _HttpClientDouble(response=gateway_response)
        gateway_client = client_type(
            http_client=gateway_http_client,
            access_token=_ACCESS_TOKEN,
            timeout_seconds=_TIMEOUT_SECONDS,
        )
        notification_url = "https://fisco.example/webhooks/mercado-pago"
        back_urls = {
            "success": "https://fisco.example/checkout/sucesso",
            "failure": "https://fisco.example/checkout/falha",
            "pending": "https://fisco.example/checkout/pendente",
        }
        gateway = MercadoPagoCheckoutOfferOneTimeGateway(
            cliente_preferencias=gateway_client,
            notification_url=notification_url,
            back_urls=back_urls,
        )
        gateway_result = gateway.criar_cobranca(
            ordem_id=91,
            user_id=41,
            empresa_id=301,
            offer_code="document-one-time-company",
            valor=Decimal("79.50"),
            moeda="BRL",
            idempotency_key=_IDEMPOTENCY_KEY,
        )
        canonical_gateway_payload = {
            "external_reference": "91",
            "items": [
                {
                    "id": "document-one-time-company",
                    "title": "document-one-time-company",
                    "quantity": 1,
                    "unit_price": 79.5,
                    "currency_id": "BRL",
                }
            ],
            "notification_url": notification_url,
            "back_urls": back_urls,
        }
        _assert_exact_post(
            gateway_http_client,
            payload=canonical_gateway_payload,
        )
        assert gateway_result == {
            "provider_order_id": "mp-pref-one-time-91",
            "checkout_url": _CHECKOUT_URL,
        }
        assert gateway_response.json_calls == 1
        assert gateway_response_payload == {
            "id": "mp-pref-one-time-91",
            "init_point": _CHECKOUT_URL,
        }

        private_status_marker = "mp4-status-private-205f"
        non_success_statuses = (
            200,
            202,
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
            201.0,
            _PrivateStatus(201, private_status_marker),
            None,
        )
        for status_code in non_success_statuses:
            response = _ResponseDouble(
                status_code=status_code,
                payload={"marker": _RESPONSE_MARKER},
            )
            http_client = _HttpClientDouble(response=response)
            status_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=status_client: current.criar_preferencia(
                    payload={"marker": _PAYLOAD_MARKER},
                    idempotency_key=_IDEMPOTENCY_KEY,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=status_client,
                private_values=(private_status_marker,),
            )
            _assert_exact_post(
                http_client,
                payload={"marker": _PAYLOAD_MARKER},
            )
            assert response.json_calls == 0

        transport_private_marker = "mp4-transport-private-75b1"
        request = httpx.Request("POST", _URL)
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
            http_client = _HttpClientDouble(
                transport_error=transport_error
            )
            transport_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=transport_client: current.criar_preferencia(
                    payload={"marker": _PAYLOAD_MARKER},
                    idempotency_key=_IDEMPOTENCY_KEY,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=transport_client,
                private_values=(transport_private_marker,),
            )
            _assert_exact_post(
                http_client,
                payload={"marker": _PAYLOAD_MARKER},
            )

        unexpected_transport_error = ValueError(
            "mp4-unexpected-transport-private-f931"
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
            unexpected_client.criar_preferencia(
                payload={"marker": _PAYLOAD_MARKER},
                idempotency_key=_IDEMPOTENCY_KEY,
            )
        assert unexpected_transport_captured.value is (
            unexpected_transport_error
        )
        _assert_exact_post(
            unexpected_http_client,
            payload={"marker": _PAYLOAD_MARKER},
        )

        json_private_marker = "mp4-json-private-6b12"
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
            lambda: invalid_json_client.criar_preferencia(
                payload={"marker": _PAYLOAD_MARKER},
                idempotency_key=_IDEMPOTENCY_KEY,
            ),
            caplog=caplog,
            constant_representations=constant_representations,
            client=invalid_json_client,
            private_values=(json_private_marker,),
        )
        _assert_exact_post(
            invalid_json_http_client,
            payload={"marker": _PAYLOAD_MARKER},
        )
        assert invalid_json_response.json_calls == 1

        unicode_private_marker = "mp4-unicode-private-590c"
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
            lambda: invalid_unicode_client.criar_preferencia(
                payload={"marker": _PAYLOAD_MARKER},
                idempotency_key=_IDEMPOTENCY_KEY,
            ),
            caplog=caplog,
            constant_representations=constant_representations,
            client=invalid_unicode_client,
            private_values=(unicode_private_marker,),
        )
        _assert_exact_post(
            invalid_unicode_http_client,
            payload={"marker": _PAYLOAD_MARKER},
        )
        assert invalid_unicode_response.json_calls == 1

        unexpected_json_error = ValueError(
            "mp4-unexpected-json-private-16df"
        )
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
            unexpected_json_client.criar_preferencia(
                payload={"marker": _PAYLOAD_MARKER},
                idempotency_key=_IDEMPOTENCY_KEY,
            )
        assert unexpected_json_captured.value is unexpected_json_error
        _assert_exact_post(
            unexpected_json_http_client,
            payload={"marker": _PAYLOAD_MARKER},
        )
        assert unexpected_json_response.json_calls == 1

        for response_without_json in (
            SimpleNamespace(status_code=201),
            SimpleNamespace(status_code=201, json=None),
            SimpleNamespace(status_code=201, json="not-callable"),
        ):
            http_client = _HttpClientDouble(response=response_without_json)
            response_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=response_client: current.criar_preferencia(
                    payload={"marker": _PAYLOAD_MARKER},
                    idempotency_key=_IDEMPOTENCY_KEY,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=response_client,
            )
            _assert_exact_post(
                http_client,
                payload={"marker": _PAYLOAD_MARKER},
            )

        invalid_response_marker = "mp4-invalid-response-private-7a20"
        invalid_response_payloads = (
            [],
            (),
            None,
            invalid_response_marker,
            _DictSubclass(marker=_RESPONSE_MARKER),
        )
        for invalid_response_payload in invalid_response_payloads:
            response = _ResponseDouble(payload=invalid_response_payload)
            http_client = _HttpClientDouble(response=response)
            response_client = client_type(
                http_client=http_client,
                access_token=_ACCESS_TOKEN,
                timeout_seconds=_TIMEOUT_SECONDS,
            )
            _capture_client_error(
                error_type,
                lambda current=response_client: current.criar_preferencia(
                    payload={"marker": _PAYLOAD_MARKER},
                    idempotency_key=_IDEMPOTENCY_KEY,
                ),
                caplog=caplog,
                constant_representations=constant_representations,
                client=response_client,
                private_values=(invalid_response_marker,),
            )
            _assert_exact_post(
                http_client,
                payload={"marker": _PAYLOAD_MARKER},
            )
            assert response.json_calls == 1

        assert len(constant_representations) == 1
