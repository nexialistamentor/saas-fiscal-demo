"""Contrato RED offline do futuro router publico do webhook Mercado Pago."""

import ast
import asyncio
import inspect
import io
import sys
import tokenize
from importlib import import_module

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request


SIGNATURE = "ts=1700000000,v1=assinatura-router-privada-9931"
REQUEST_ID = "request-router-privado-9931"
PAYMENT_ID = "47199931"
NOTIFICATION_ID = "81289931"
PAYLOAD_MARKER = "payload-router-privado-9931"
TOKEN_MARKER = "token-router-privado-9931"
EXCEPTION_MARKER = "excecao-router-privada-9931"
CONFIGURATION_MARKER = "configuracao-router-privada-9931"
PRIVATE_MARKERS = (
    SIGNATURE,
    REQUEST_ID,
    PAYMENT_ID,
    NOTIFICATION_ID,
    PAYLOAD_MARKER,
    TOKEN_MARKER,
    EXCEPTION_MARKER,
    CONFIGURATION_MARKER,
)
VALID_BODY = (
    b'{"id":81289931,"type":"payment","action":"payment.created",'
    b'"data":{"id":"47199931"},'
    b'"date_created":"payload-router-privado-9931"}'
)
EXPECTED_ENVELOPE = {
    "notification_id": NOTIFICATION_ID,
    "payment_id": PAYMENT_ID,
    "request_id": REQUEST_ID,
}
VALID_QUERY = f"data.id={PAYMENT_ID}&type=payment"


class _OrchestratorDouble:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def processar(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result

    def reset(self, *, result=None, error=None):
        self.result = result
        self.error = error
        self.calls.clear()


class _InvalidOrchestrator:
    processar = CONFIGURATION_MARKER

    def __repr__(self):
        return CONFIGURATION_MARKER


class _DerivedInt(int):
    pass


class _RouterConstructorGuard:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("router criado antes da validacao")


class _NormalizerDouble:
    def __init__(self, delegate):
        self.delegate = delegate
        self.result = (EXPECTED_ENVELOPE, SIGNATURE)
        self.error = None
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        if self.delegate is not None:
            return self.delegate(*args, **kwargs)
        return self.result

    def reset(self, *, delegate=None, result=None, error=None):
        self.delegate = delegate
        self.result = (
            (EXPECTED_ENVELOPE, SIGNATURE)
            if result is None
            else result
        )
        self.error = error
        self.calls.clear()


def _headers(
    body,
    *,
    content_types=("application/json",),
    signatures=(SIGNATURE,),
    request_ids=(REQUEST_ID,),
):
    headers = [
        ("host", "router.test"),
        ("accept", "application/router-contract"),
        ("accept-encoding", "identity"),
        ("connection", "close"),
        ("user-agent", "router-contract-agent"),
    ]
    headers.extend(("content-type", value) for value in content_types)
    headers.append(("x-order-a", "primeiro-router-9931"))
    headers.extend(("x-signature", value) for value in signatures)
    headers.extend(("x-request-id", value) for value in request_ids)
    headers.extend(
        (
            ("x-order-b", "ultimo-router-9931"),
            ("content-length", str(len(body))),
        )
    )
    return headers


def _post(client, *, body=VALID_BODY, query=VALID_QUERY, headers=None):
    return client.post(
        f"/webhooks/mercado-pago?{query}",
        headers=_headers(body) if headers is None else headers,
        content=body,
    )


def _assert_no_private_data(response):
    for marker in PRIVATE_MARKERS:
        assert marker.encode("utf-8") not in response.content
    assert VALID_BODY not in response.content


def _assert_empty_response(response, status_code):
    assert response.status_code == status_code
    assert response.content == b""
    _assert_no_private_data(response)


def _assert_configuration_error(error, error_type):
    assert type(error) is error_type
    for representation in (str(error), repr(error)):
        lowered = representation.lower()
        for marker in PRIVATE_MARKERS:
            assert marker.lower() not in lowered


def _only_route(router):
    assert isinstance(router, APIRouter)
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == "/webhooks/mercado-pago"
    assert route.methods == {"POST"}
    assert "GET" not in route.methods
    return route


def _raw_request(*, headers, receive):
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/webhooks/mercado-pago",
            "raw_path": b"/webhooks/mercado-pago",
            "query_string": VALID_QUERY.encode("ascii"),
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 9931),
            "server": ("router.test", 443),
            "state": {},
        },
        receive=receive,
    )


async def _invoke_endpoint(route, request):
    return await route.endpoint(request)


def test_payments_mercado_pago_webhook_router_contract_red():
    router_module = import_module(
        "app.routers.mercado_pago_webhook_router"
    )
    http_module = import_module(
        "app.services.mercado_pago_webhook_http"
    )
    orchestration_module = import_module(
        "app.services.mercado_pago_webhook_orchestration"
    )

    factory = router_module.criar_mercado_pago_webhook_router
    configuration_error = (
        router_module.MercadoPagoWebhookRouterConfigurationError
    )
    signature = inspect.signature(factory)
    assert tuple(signature.parameters) == (
        "orchestrator",
        "max_body_bytes",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    assert issubclass(configuration_error, Exception)

    constructor_guard = _RouterConstructorGuard()
    valid_orchestrator = _OrchestratorDouble()
    configuration_errors = []
    fastapi_module = import_module("fastapi")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fastapi_module, "APIRouter", constructor_guard)
        if hasattr(router_module, "APIRouter"):
            patch.setattr(router_module, "APIRouter", constructor_guard)

        invalid_orchestrators = (
            None,
            object(),
            lambda: None,
            _InvalidOrchestrator(),
        )
        for invalid_orchestrator in invalid_orchestrators:
            with pytest.raises(configuration_error) as captured:
                factory(
                    orchestrator=invalid_orchestrator,
                    max_body_bytes=1,
                )
            configuration_errors.append(captured.value)
            _assert_configuration_error(
                captured.value,
                configuration_error,
            )

        invalid_limits = (
            None,
            True,
            False,
            0,
            -1,
            65_537,
            1.0,
            "1",
            _DerivedInt(1),
            _DerivedInt(65_536),
        )
        for invalid_limit in invalid_limits:
            with pytest.raises(configuration_error) as captured:
                factory(
                    orchestrator=valid_orchestrator,
                    max_body_bytes=invalid_limit,
                )
            configuration_errors.append(captured.value)
            _assert_configuration_error(
                captured.value,
                configuration_error,
            )

        with pytest.raises(TypeError):
            factory(valid_orchestrator, 1)
        assert constructor_guard.calls == []
        assert valid_orchestrator.calls == []

    assert len({str(error) for error in configuration_errors}) == 1
    assert len({repr(error) for error in configuration_errors}) == 1
    for valid_limit in (1, 65_536):
        boundary_orchestrator = _OrchestratorDouble()
        boundary_router = factory(
            orchestrator=boundary_orchestrator,
            max_body_bytes=valid_limit,
        )
        _only_route(boundary_router)
        assert boundary_orchestrator.calls == []

    real_normalizer = (
        http_module.normalizar_mercado_pago_webhook_http
    )
    normalizer = _NormalizerDouble(real_normalizer)
    orchestrator = _OrchestratorDouble()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            http_module,
            "normalizar_mercado_pago_webhook_http",
            normalizer,
        )
        patch.setattr(
            router_module,
            "normalizar_mercado_pago_webhook_http",
            normalizer,
            raising=False,
        )
        router = factory(
            orchestrator=orchestrator,
            max_body_bytes=len(VALID_BODY),
        )
        route = _only_route(router)
        assert inspect.iscoroutinefunction(route.endpoint)
        assert route.dependant.request_param_name is not None
        assert route.dependant.body_params == []
        assert route.dependant.dependencies == []
        assert orchestrator.calls == []

        app = FastAPI()
        app.include_router(router)
        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            response = _post(client)
            _assert_empty_response(response, 200)
            assert len(normalizer.calls) == 1
            normalizer_args, normalizer_kwargs = normalizer.calls[0]
            assert normalizer_args == ()
            assert set(normalizer_kwargs) == {
                "method",
                "content_type",
                "headers",
                "query_params",
                "body",
            }
            assert normalizer_kwargs["method"] == "POST"
            assert normalizer_kwargs["content_type"] == "application/json"
            assert tuple(normalizer_kwargs["headers"]) == tuple(
                _headers(VALID_BODY)
            )
            assert tuple(normalizer_kwargs["query_params"]) == (
                ("data.id", PAYMENT_ID),
                ("type", "payment"),
            )
            assert type(normalizer_kwargs["body"]) is bytes
            assert normalizer_kwargs["body"] == VALID_BODY
            assert all(
                type(name) is type(value) is str
                for name, value in normalizer_kwargs["headers"]
            )
            assert all(
                type(name) is type(value) is str
                for name, value in normalizer_kwargs["query_params"]
            )
            assert orchestrator.calls == [
                ((EXPECTED_ENVELOPE, SIGNATURE), {})
            ]

            processed_result = object()
            normalizer.reset(delegate=real_normalizer)
            orchestrator.reset(result=processed_result)
            first_repeat = _post(client)
            second_repeat = _post(client)
            _assert_empty_response(first_repeat, 200)
            _assert_empty_response(second_repeat, 200)
            assert len(normalizer.calls) == 2
            assert orchestrator.calls == [
                ((EXPECTED_ENVELOPE, SIGNATURE), {}),
                ((EXPECTED_ENVELOPE, SIGNATURE), {}),
            ]

            normalizer.reset(delegate=real_normalizer)
            orchestrator.reset()
            for method in ("get", "put", "patch", "delete"):
                method_response = getattr(client, method)(
                    f"/webhooks/mercado-pago?{VALID_QUERY}",
                    headers=_headers(VALID_BODY),
                )
                assert method_response.status_code == 405
                _assert_no_private_data(method_response)
            assert normalizer.calls == []
            assert orchestrator.calls == []

            malformed_content_types = (
                (),
                ("application/json", "application/json"),
                ("text/plain",),
                ("application/json; charset=utf-8",),
                ("Application/JSON",),
            )
            for content_types in malformed_content_types:
                normalizer.reset(delegate=real_normalizer)
                orchestrator.reset()
                response = _post(
                    client,
                    headers=_headers(
                        VALID_BODY,
                        content_types=content_types,
                    ),
                )
                _assert_empty_response(response, 400)
                assert normalizer.calls == []
                assert orchestrator.calls == []

            duplicate_header_cases = (
                {
                    "signatures": (
                        SIGNATURE,
                        "assinatura-duplicada-router-9931",
                    )
                },
                {
                    "request_ids": (
                        REQUEST_ID,
                        "request-duplicado-router-9931",
                    )
                },
            )
            for header_changes in duplicate_header_cases:
                normalizer.reset(delegate=real_normalizer)
                orchestrator.reset()
                response = _post(
                    client,
                    headers=_headers(VALID_BODY, **header_changes),
                )
                _assert_empty_response(response, 400)
                assert len(normalizer.calls) == 1
                captured_headers = tuple(
                    normalizer.calls[0][1]["headers"]
                )
                if "signatures" in header_changes:
                    assert [
                        value
                        for name, value in captured_headers
                        if name == "x-signature"
                    ] == list(header_changes["signatures"])
                else:
                    assert [
                        value
                        for name, value in captured_headers
                        if name == "x-request-id"
                    ] == list(header_changes["request_ids"])
                assert orchestrator.calls == []

            malformed_queries = (
                f"data.id={PAYMENT_ID}&data.id={PAYMENT_ID}&type=payment",
                f"data.id={PAYMENT_ID}&type=payment&type=payment",
                f"data.id={PAYMENT_ID}&type=payment&extra=extra-router-9931",
            )
            for malformed_query in malformed_queries:
                normalizer.reset(delegate=real_normalizer)
                orchestrator.reset()
                response = _post(client, query=malformed_query)
                _assert_empty_response(response, 400)
                assert len(normalizer.calls) == 1
                assert tuple(
                    normalizer.calls[0][1]["query_params"]
                ) == tuple(
                    tuple(pair.split("=", 1))
                    for pair in malformed_query.split("&")
                )
                assert orchestrator.calls == []

            for invalid_body in (b"", b'{"id":'):
                normalizer.reset(delegate=real_normalizer)
                orchestrator.reset()
                response = _post(client, body=invalid_body)
                _assert_empty_response(response, 400)
                assert len(normalizer.calls) == 1
                assert normalizer.calls[0][1]["body"] == invalid_body
                assert orchestrator.calls == []

            normalizer.reset(
                delegate=None,
                error=http_module.MercadoPagoWebhookHttpNormalizationError(
                    TOKEN_MARKER,
                    EXCEPTION_MARKER,
                ),
            )
            orchestrator.reset()
            response = _post(client)
            _assert_empty_response(response, 400)
            assert len(normalizer.calls) == 1
            assert orchestrator.calls == []

            normalizer.reset(delegate=None)
            orchestrator.reset(
                error=(
                    orchestration_module
                    .MercadoPagoWebhookAuthenticationError(
                        TOKEN_MARKER,
                        EXCEPTION_MARKER,
                    )
                )
            )
            response = _post(client)
            _assert_empty_response(response, 401)
            assert orchestrator.calls == [
                ((EXPECTED_ENVELOPE, SIGNATURE), {})
            ]

            normalizer.reset(delegate=None)
            orchestrator.reset(
                error=(
                    orchestration_module
                    .MercadoPagoWebhookOrchestrationError(
                        TOKEN_MARKER,
                        EXCEPTION_MARKER,
                    )
                )
            )
            response = _post(client)
            _assert_empty_response(response, 500)
            assert orchestrator.calls == [
                ((EXPECTED_ENVELOPE, SIGNATURE), {})
            ]

        early_orchestrator = _OrchestratorDouble()
        early_router = factory(
            orchestrator=early_orchestrator,
            max_body_bytes=8,
        )
        early_route = _only_route(early_router)
        normalizer.reset(delegate=real_normalizer)
        receive_calls = []

        async def receive_must_not_run():
            receive_calls.append("called")
            raise AssertionError("receive consumido para Content-Length excessivo")

        early_headers = (
            (b"content-type", b"application/json"),
            (b"x-signature", SIGNATURE.encode("ascii")),
            (b"x-request-id", REQUEST_ID.encode("ascii")),
            (b"content-length", b"9"),
        )
        early_request = _raw_request(
            headers=early_headers,
            receive=receive_must_not_run,
        )
        early_response = asyncio.run(
            _invoke_endpoint(early_route, early_request)
        )
        assert early_response.status_code == 400
        assert early_response.body == b""
        assert receive_calls == []
        assert normalizer.calls == []
        assert early_orchestrator.calls == []

        stream_orchestrator = _OrchestratorDouble()
        stream_router = factory(
            orchestrator=stream_orchestrator,
            max_body_bytes=8,
        )
        stream_route = _only_route(stream_router)
        normalizer.reset(delegate=real_normalizer)
        stream_messages = [
            {
                "type": "http.request",
                "body": b"12345",
                "more_body": True,
            },
            {
                "type": "http.request",
                "body": b"6789",
                "more_body": True,
            },
        ]
        stream_receive_calls = []

        async def receive_oversized_stream():
            index = len(stream_receive_calls)
            stream_receive_calls.append(index)
            if index >= len(stream_messages):
                raise AssertionError("stream continuou depois de exceder o limite")
            return stream_messages[index]

        stream_headers = (
            (b"content-type", b"application/json"),
            (b"x-signature", SIGNATURE.encode("ascii")),
            (b"x-request-id", REQUEST_ID.encode("ascii")),
        )
        stream_request = _raw_request(
            headers=stream_headers,
            receive=receive_oversized_stream,
        )
        stream_response = asyncio.run(
            _invoke_endpoint(stream_route, stream_request)
        )
        assert stream_response.status_code == 400
        assert stream_response.body == b""
        assert stream_receive_calls == [0, 1]
        assert normalizer.calls == []
        assert stream_orchestrator.calls == []

    source = inspect.getsource(router_module)
    tree = ast.parse(source)
    tokens = list(
        tokenize.generate_tokens(io.StringIO(source).readline)
    )
    assert tokens[-1].type == tokenize.ENDMARKER

    imported_modules = []
    canonical_internal_imports = set()
    allowed_internal_imports = {
        "app.services.mercado_pago_webhook_http",
        "app.services.mercado_pago_webhook_orchestration",
    }
    allowed_relative_imports = {
        "services.mercado_pago_webhook_http",
        "services.mercado_pago_webhook_orchestration",
    }
    allowed_standard_roots = {"__future__", "collections", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append((alias.name, 0))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append((node.module, node.level))

    for imported_module, level in imported_modules:
        root = imported_module.split(".")[0]
        if level == 0 and root in {"fastapi", "starlette"}:
            continue
        if level == 0 and imported_module in allowed_internal_imports:
            canonical_internal_imports.add(imported_module)
            continue
        if level == 2 and imported_module in allowed_relative_imports:
            canonical_internal_imports.add(f"app.{imported_module}")
            continue
        assert level == 0
        assert root in sys.stdlib_module_names
        assert root in allowed_standard_roots
    assert canonical_internal_imports == allowed_internal_imports

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    normalizer_calls = [
        node
        for node in calls
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "normalizar_mercado_pago_webhook_http"
        )
        or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "normalizar_mercado_pago_webhook_http"
        )
    ]
    assert len(normalizer_calls) == 1
    assert normalizer_calls[0].args == []
    assert [keyword.arg for keyword in normalizer_calls[0].keywords] == [
        "method",
        "content_type",
        "headers",
        "query_params",
        "body",
    ]
    direct_process_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "processar"
    ]
    threadpool_process_calls = [
        node
        for node in calls
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "run_in_threadpool"
            and node.args
            and (
                (
                    isinstance(node.args[0], ast.Name)
                    and node.args[0].id == "processar"
                )
                or (
                    isinstance(node.args[0], ast.Attribute)
                    and node.args[0].attr == "processar"
                )
            )
        )
    ]
    process_calls = direct_process_calls + threadpool_process_calls
    assert len(process_calls) == 1
    process_call = process_calls[0]
    if direct_process_calls:
        assert isinstance(process_call.func.value, ast.Name)
        assert process_call.func.value.id == "orchestrator"
        expected_process_args = ("evento", "assinatura")
    else:
        assert isinstance(
            next(
                parent
                for parent in ast.walk(tree)
                if process_call in ast.iter_child_nodes(parent)
            ),
            ast.Await,
        )
        expected_process_args = ("processar", "evento", "assinatura")
    assert tuple(
        argument.id
        for argument in process_call.args
        if isinstance(argument, ast.Name)
    ) == expected_process_args
    assert len(process_call.args) == len(expected_process_args)
    assert process_call.keywords == []
    stream_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "stream"
    ]
    assert len(stream_calls) == 1
    assert not any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr in {"body", "json"}
        for node in calls
    )
    assert not any(
        isinstance(node.func, ast.Name)
        and node.func.id == "dict"
        for node in calls
    )

    identifiers = {
        node.id.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    attributes = {
        node.attr.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    identifiers.update(attributes)
    assert "scope" in attributes
    assert attributes.isdisjoint({"headers", "query_params"})
    assert identifiers.isdisjoint(
        {
            "json",
            "loads",
            "print",
            "logging",
            "logger",
            "getenv",
            "environ",
            "backgroundtasks",
            "depends",
            "security",
            "session",
            "sessionmaker",
            "create_engine",
            "retry",
            "sleep",
            "get_current_user",
            "current_user",
        }
    )

    imported_roots = {
        imported_module.split(".")[0]
        for imported_module, _level in imported_modules
    }
    assert imported_roots.isdisjoint(
        {
            "database",
            "databases",
            "sqlalchemy",
            "requests",
            "httpx",
            "urllib",
            "socket",
            "mercadopago",
            "os",
            "logging",
            "json",
            "orjson",
            "ujson",
            "time",
            "tenacity",
        }
    )
    lowered_source = source.lower()
    for forbidden_fragment in (
        "app.main",
        "jsonresponse",
        "access_token",
        "client_secret",
        "authorization",
        "credentials",
        "notification_id",
        "payment_id",
        "request_id",
        "ordem_id",
        "checkout",
        "preco",
        "price",
        "moeda",
        "currency",
        "oferta",
        "offer",
        "capabilit",
        "payment.created",
        "payment.updated",
        "approved",
        "stacktrace",
        "traceback",
        "os.getenv",
        "os.environ",
        "environ.get",
    ):
        assert forbidden_fragment not in lowered_source
