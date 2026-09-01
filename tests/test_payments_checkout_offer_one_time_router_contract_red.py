"""Contrato RED offline do futuro router autenticado de checkout one-time."""

import ast
import inspect
import sys
from importlib import import_module
from types import SimpleNamespace
import fastapi
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

_USER_ID = 41
_EMPRESA_ID = 301
_OFFER_CODE = "document-one-time-company"
_IDEMPOTENCY_KEY = "router-one-time-company-301"
_CHECKOUT_URL = "https://checkout.example.invalid/one-time/order-701"
_PRIVATE_MARKERS = (
    "router-private-token-8811", "router-private-credential-8811",
    "router-private-traceback-8811", "owner-private-password-8811",
)

class _ApplicationServiceSpy:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def iniciar_checkout(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result

    def reset(self, *, result=None, error=None):
        self.result = result
        self.error = error
        self.calls.clear()

class _CurrentUserDependency:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self):
        self.calls.append(())
        return self.result

    def reset(self, result):
        self.result = result
        self.calls.clear()

class _UserProbe:
    def __init__(self, user_id):
        object.__setattr__(self, "_user_id", user_id)
        object.__setattr__(self, "_accesses", [])

    def __getattribute__(self, name):
        if name == "id":
            accesses = object.__getattribute__(self, "_accesses")
            accesses.append(name)
            return object.__getattribute__(self, "_user_id")
        raise AssertionError(f"atributo de usuario indevido: {name}")

class _DerivedInt(int):
    pass

class _RouterConstructorGuard:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("router criado antes de validar dependencias")

def _assert_empty_500(response):
    assert response.status_code == 500
    assert response.content == b""
    lowered = response.content.lower()
    assert b"traceback" not in lowered
    for marker in _PRIVATE_MARKERS:
        assert marker.encode() not in response.content

def _post(client, *, body=None, key=_IDEMPOTENCY_KEY, query=""):
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post(
        f"/checkout/one-time{query}",
        headers=headers,
        json=(
            {"empresa_id": _EMPRESA_ID, "offer_code": _OFFER_CODE}
            if body is None
            else body
        ),
    )

def test_payments_checkout_offer_one_time_router_contract_red():
    router_module = import_module(
        "app.routers.checkout_offer_one_time_router"
    )
    assert set(router_module.__all__) == {
        "CheckoutOfferOneTimeRouterConfigurationError",
        "criar_checkout_offer_one_time_router",
    }
    error_type = router_module.CheckoutOfferOneTimeRouterConfigurationError
    factory = router_module.criar_checkout_offer_one_time_router
    assert issubclass(error_type, Exception)
    parameters = inspect.signature(factory).parameters
    assert tuple(parameters) == (
        "application_service",
        "current_user_dependency",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is inspect.Parameter.empty
        for parameter in parameters.values()
    )

    service = _ApplicationServiceSpy({"checkout_url": _CHECKOUT_URL})
    dependency = _CurrentUserDependency(SimpleNamespace(id=_USER_ID))
    guard = _RouterConstructorGuard()
    configuration_errors = []
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fastapi, "APIRouter", guard)
        if hasattr(router_module, "APIRouter"):
            patch.setattr(router_module, "APIRouter", guard)
        for invalid_service in (
            None,
            object(),
            SimpleNamespace(iniciar_checkout=_PRIVATE_MARKERS[0]),
        ):
            with pytest.raises(error_type) as captured:
                factory(
                    application_service=invalid_service,
                    current_user_dependency=dependency,
                )
            configuration_errors.append(captured.value)
        for invalid_dependency in (
            None,
            object(),
            _PRIVATE_MARKERS[1],
        ):
            with pytest.raises(error_type) as captured:
                factory(
                    application_service=service,
                    current_user_dependency=invalid_dependency,
                )
            configuration_errors.append(captured.value)
        with pytest.raises(TypeError):
            factory(service, dependency)
        assert guard.calls == []
        assert service.calls == []
        assert dependency.calls == []
    assert len({str(error) for error in configuration_errors}) == 1
    assert len({repr(error) for error in configuration_errors}) == 1
    for error in configuration_errors:
        assert type(error) is error_type
        rendered = f"{error!s} {error!r}".lower()
        assert all(marker not in rendered for marker in _PRIVATE_MARKERS)

    user = _UserProbe(_USER_ID)
    dependency.reset(user)
    router = factory(
        application_service=service,
        current_user_dependency=dependency,
    )
    assert isinstance(router, APIRouter)
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == "/checkout/one-time"
    assert route.methods == {"POST"}
    assert len(route.dependant.dependencies) == 1
    auth_dependency = route.dependant.dependencies[0]
    assert auth_dependency.call is dependency
    assert auth_dependency.dependencies == []
    assert len(route.dependant.body_params) == 1
    assert len(route.dependant.header_params) == 1
    assert not any((
        route.dependant.query_params, route.dependant.path_params,
        route.dependant.cookie_params,
    ))
    header = route.dependant.header_params[0]
    assert header.alias == "Idempotency-Key"
    assert header.required is True
    body_model = route.dependant.body_params[0].type_
    assert set(body_model.model_fields) == {"empresa_id", "offer_code"}
    assert body_model.model_config.get("extra") == "forbid"
    offer_schema = body_model.model_json_schema()["properties"]["offer_code"]
    assert offer_schema["type"] == "string"
    assert offer_schema["maxLength"] == 120
    assert offer_schema["pattern"] == r"^[a-z0-9]+(?:-[a-z0-9]+)+$"
    assert service.calls == []
    assert dependency.calls == []

    app = FastAPI()
    app.include_router(router)
    header_schema = next(
        parameter["schema"]
        for parameter in app.openapi()["paths"]["/checkout/one-time"]["post"]["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert header_schema["type"] == "string"
    assert header_schema["minLength"] == 1
    assert header_schema["maxLength"] == 255
    assert header_schema["pattern"] == r"^[\x21-\x7e]+$"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = _post(client)
        assert response.status_code == 200
        assert response.json() == {"checkout_url": _CHECKOUT_URL}
        assert set(response.json()) == {"checkout_url"}
        expected_call = {
            "authenticated_user_id": _USER_ID,
            "empresa_id": _EMPRESA_ID,
            "offer_code": _OFFER_CODE,
            "idempotency_key": _IDEMPOTENCY_KEY,
        }
        assert service.calls == [expected_call]
        assert dependency.calls == [()]
        assert object.__getattribute__(user, "_accesses") == ["id"]

        service.reset({"checkout_url": _CHECKOUT_URL})
        dependency.reset(_UserProbe(_USER_ID))
        query_response = _post(
            client,
            query="?idempotency_key=router-query-must-be-ignored",
        )
        assert query_response.status_code == 200
        assert service.calls == [expected_call]

        service.reset({"checkout_url": _CHECKOUT_URL})
        dependency.reset(SimpleNamespace(id=_USER_ID))
        missing_header = _post(
            client,
            key=None,
            query="?idempotency_key=router-query-is-not-header",
        )
        assert missing_header.status_code == 422
        assert service.calls == []

        forbidden_fields = {
            "user_id": 99, "authenticated_user_id": 99, "preco": "79.50",
            "moeda": "BRL", "modelo": "one_time",
            "capabilities": ["document.extract"],
            "idempotency_key": "body-key-is-forbidden",
        }
        for field, value in forbidden_fields.items():
            service.reset({"checkout_url": _CHECKOUT_URL})
            body = {
                "empresa_id": _EMPRESA_ID,
                "offer_code": _OFFER_CODE,
                field: value,
            }
            rejected = _post(client, body=body)
            assert rejected.status_code == 422
            assert service.calls == []
        for body in (
            {}, {"empresa_id": _EMPRESA_ID}, {"offer_code": _OFFER_CODE}, [],
        ):
            service.reset({"checkout_url": _CHECKOUT_URL})
            rejected = _post(client, body=body)
            assert rejected.status_code == 422
            assert service.calls == []
        for invalid_empresa_id in (None, True, False, 0, -1, 301.0, "301"):
            service.reset({"checkout_url": _CHECKOUT_URL})
            rejected = _post(client, body={
                "empresa_id": invalid_empresa_id, "offer_code": _OFFER_CODE,
            })
            assert rejected.status_code == 422
            assert service.calls == []
        for invalid_offer_code in (
            "", "DOCUMENT-one-time-company", " document-one-time-company",
            "document one-time-company", "document\r\none-time-company",
            "document", "a-" + "b" * 119,
        ):
            service.reset({"checkout_url": _CHECKOUT_URL})
            rejected = _post(client, body={
                "empresa_id": _EMPRESA_ID, "offer_code": invalid_offer_code,
            })
            assert rejected.status_code == 422
            assert service.calls == []
        for invalid_key in ("", " ", "\t", "a" * 256):
            service.reset({"checkout_url": _CHECKOUT_URL})
            rejected = _post(client, key=invalid_key)
            assert rejected.status_code == 422
            assert service.calls == []

        service.reset({"checkout_url": _CHECKOUT_URL})
        duplicate_header = client.post(
            "/checkout/one-time",
            headers=[("Idempotency-Key", "first-key"),
                     ("Idempotency-Key", "second-key")],
            json={"empresa_id": _EMPRESA_ID, "offer_code": _OFFER_CODE},
        )
        assert duplicate_header.status_code == 422
        assert service.calls == []

        exact_key = "!#$%&'*+-.^_`|~AZaz09"
        service.reset({"checkout_url": _CHECKOUT_URL})
        assert _post(client, key=exact_key).status_code == 200
        assert service.calls == [{**expected_call, "idempotency_key": exact_key}]

        for invalid_id in (
            None, True, False, 0, -1, "41", _DerivedInt(_USER_ID),
        ):
            service.reset({"checkout_url": _CHECKOUT_URL})
            dependency.reset(SimpleNamespace(id=invalid_id))
            invalid_user = _post(client)
            _assert_empty_500(invalid_user)
            assert service.calls == []
        service.reset({"checkout_url": _CHECKOUT_URL})
        dependency.reset(object())
        _assert_empty_500(_post(client))
        assert service.calls == []

        dependency.reset(SimpleNamespace(id=_USER_ID))
        service.reset(error=RuntimeError(_PRIVATE_MARKERS[2]))
        _assert_empty_500(_post(client))
        assert service.calls == [expected_call]

        invalid_results = (
            None, SimpleNamespace(checkout_url=_CHECKOUT_URL),
            {"checkout_url": _CHECKOUT_URL, "estado": "private"},
            {"checkout_url": 701}, {"checkout_url": "/checkout/order-701"},
            {"checkout_url": "http://checkout.example.invalid/pay"},
            {"checkout_url": "https:///checkout/order-701"},
            {"checkout_url": "https://checkout.example.invalid:bad/pay"},
            {
                "checkout_url": (
                    "https://owner:owner-private-password-8811@"
                    "checkout.example.invalid/pay"
                )
            },
        )
        for invalid_result in invalid_results:
            service.reset(invalid_result)
            divergent = _post(client)
            _assert_empty_500(divergent)
            assert service.calls == [expected_call]

    source = inspect.getsource(router_module)
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.level))
    blocked_roots = {
        "sqlalchemy", "sqlite3", "database", "databases", "os", "dotenv",
        "requests", "httpx", "socket", "mercadopago", "stripe", "logging",
        "time", "tenacity", "backoff",
    }
    assert not {name.split(".")[0] for name, _level in imports} & blocked_roots
    assert not any(name == "app.main" or name.startswith("app.main.") for name, _ in imports)
    assert not any("checkout_offer_one_time_application" in n for n, _ in imports)
    for name, level in imports:
        if level == 0 and name.split(".")[0] in {"fastapi", "starlette", "pydantic"}:
            continue
        assert level == 0
        assert name.split(".")[0] in sys.stdlib_module_names

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    service_calls = [
        node for node in calls
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "iniciar_checkout"
    ]
    assert len(service_calls) == 1
    assert service_calls[0].args == []
    assert [keyword.arg for keyword in service_calls[0].keywords] == [
        "authenticated_user_id", "empresa_id", "offer_code", "idempotency_key",
    ]
    depends_calls = [node for node in calls if (
        isinstance(node.func, ast.Name) and node.func.id == "Depends"
    )]
    assert len(depends_calls) == 1
    assert len(depends_calls[0].args) == 1
    assert isinstance(depends_calls[0].args[0], ast.Name)
    assert depends_calls[0].args[0].id == "current_user_dependency"
    assert depends_calls[0].keywords == []

    lowered_source = source.lower()
    for forbidden_fragment in (
        "app.main", "get_usuario_atual", "get_current_user", "sessionmaker",
        "create_engine", "os.getenv", "os.environ", "environ.get", "catalog",
        "preco", "price", "moeda", "currency", "capabilit", "print(",
        "traceback", "stacktrace",
    ):
        assert forbidden_fragment not in lowered_source
