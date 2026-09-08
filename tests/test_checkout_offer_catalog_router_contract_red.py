"""Contrato RED offline do futuro router read-only do catalogo de ofertas."""

import ast
import inspect
import sys
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import fastapi
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest


_PRIVATE_MARKERS = (
    "catalog-private-sql-7711",
    "catalog-private-capability-7711",
    "catalog-private-traceback-7711",
)
_PUBLIC_FIELDS = {
    "offer_code",
    "nome_publico",
    "vertical",
    "commercial_model",
    "subject_type",
    "moeda",
    "preco",
    "billing_period",
    "usage_unit",
    "usage_limit",
    "checkout_mode",
}


def _offer(code, **overrides):
    values = {
        "id": 701,
        "codigo": code,
        "nome_publico": "Assistencia fiscal mensal",
        "vertical": "tax",
        "commercial_model": "monthly",
        "subject_type": "company",
        "estado": "published",
        "moeda": "BRL",
        "preco": Decimal("39.90"),
        "billing_period": "month",
        "usage_unit": None,
        "usage_limit": None,
        "contract_version": 9,
        "criado_em": _PRIVATE_MARKERS[0],
        "atualizado_em": _PRIVATE_MARKERS[2],
        "capabilities": (_PRIVATE_MARKERS[1],),
        "checkout_mode": "automatic",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _CatalogServiceSpy:
    def __init__(self, result=(), error=None):
        self.result = result
        self.error = error
        self.calls = []

    def listar_ofertas_publicadas(self):
        self.calls.append(())
        if self.error is not None:
            raise self.error
        return self.result

    def reset(self, *, result=(), error=None):
        self.result = result
        self.error = error
        self.calls.clear()


class _CurrentUserDependency:
    def __init__(self, result):
        self.result = result
        self.error = None
        self.calls = []

    def __call__(self):
        self.calls.append(())
        if self.error is not None:
            raise self.error
        return self.result

    def reset(self, *, result=None, error=None):
        self.result = result
        self.error = error
        self.calls.clear()


class _UserMustRemainOpaque:
    def __getattribute__(self, name):
        raise AssertionError(f"router tentou ler atributo do usuario: {name}")


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


def test_checkout_offer_catalog_router_contract_red():
    router_module = import_module("app.routers.checkout_offer_catalog_router")

    assert set(router_module.__all__) == {
        "CheckoutOfferCatalogRouterConfigurationError",
        "criar_checkout_offer_catalog_router",
    }
    error_type = router_module.CheckoutOfferCatalogRouterConfigurationError
    factory = router_module.criar_checkout_offer_catalog_router
    assert issubclass(error_type, Exception)
    parameters = inspect.signature(factory).parameters
    assert tuple(parameters) == (
        "catalog_service",
        "current_user_dependency",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is inspect.Parameter.empty
        for parameter in parameters.values()
    )

    service = _CatalogServiceSpy()
    dependency = _CurrentUserDependency(_UserMustRemainOpaque())
    guard = _RouterConstructorGuard()
    configuration_errors = []
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fastapi, "APIRouter", guard)
        if hasattr(router_module, "APIRouter"):
            patch.setattr(router_module, "APIRouter", guard)
        for invalid_service in (
            None,
            object(),
            SimpleNamespace(listar_ofertas_publicadas="not-callable"),
        ):
            with pytest.raises(error_type) as captured:
                factory(
                    catalog_service=invalid_service,
                    current_user_dependency=dependency,
                )
            configuration_errors.append(captured.value)
        for invalid_dependency in (None, object(), "not-callable"):
            with pytest.raises(error_type) as captured:
                factory(
                    catalog_service=service,
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
    assert all(type(error) is error_type for error in configuration_errors)

    router = factory(
        catalog_service=service,
        current_user_dependency=dependency,
    )
    assert isinstance(router, APIRouter)
    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == "/checkout/offers"
    assert route.methods == {"GET"}
    assert len(route.dependant.dependencies) == 1
    auth_dependency = route.dependant.dependencies[0]
    assert auth_dependency.call is dependency
    assert auth_dependency.dependencies == []
    assert not any(
        (
            route.dependant.body_params,
            route.dependant.query_params,
            route.dependant.path_params,
            route.dependant.header_params,
            route.dependant.cookie_params,
        )
    )
    assert service.calls == []
    assert dependency.calls == []

    app = FastAPI()
    app.include_router(router)
    operation = app.openapi()["paths"]["/checkout/offers"]["get"]
    assert operation.get("parameters", []) == []
    assert "requestBody" not in operation

    monthly = _offer("tax-monthly-company")
    one_time = _offer(
        "document-one-time-company",
        id=702,
        nome_publico="Processamento documental",
        vertical="document",
        commercial_model="one_time",
        subject_type="cpf",
        preco=Decimal("79.50"),
        billing_period=None,
        usage_unit="document",
        usage_limit=5,
    )
    negotiated = _offer(
        "tax-negotiated-institution",
        id=703,
        nome_publico="Programa fiscal institucional",
        commercial_model="negotiated",
        subject_type="institution",
        moeda=None,
        preco=None,
        billing_period=None,
        checkout_mode="proposal",
    )
    service.reset(result=(monthly, negotiated, one_time))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/checkout/offers")
        assert response.status_code == 200
        assert response.json() == [
            {
                "offer_code": "document-one-time-company",
                "nome_publico": "Processamento documental",
                "vertical": "document",
                "commercial_model": "one_time",
                "subject_type": "cpf",
                "moeda": "BRL",
                "preco": "79.50",
                "billing_period": None,
                "usage_unit": "document",
                "usage_limit": 5,
                "checkout_mode": "automatic",
            },
            {
                "offer_code": "tax-monthly-company",
                "nome_publico": "Assistencia fiscal mensal",
                "vertical": "tax",
                "commercial_model": "monthly",
                "subject_type": "company",
                "moeda": "BRL",
                "preco": "39.90",
                "billing_period": "month",
                "usage_unit": None,
                "usage_limit": None,
                "checkout_mode": "automatic",
            },
            {
                "offer_code": "tax-negotiated-institution",
                "nome_publico": "Programa fiscal institucional",
                "vertical": "tax",
                "commercial_model": "negotiated",
                "subject_type": "institution",
                "moeda": None,
                "preco": None,
                "billing_period": None,
                "usage_unit": None,
                "usage_limit": None,
                "checkout_mode": "proposal",
            },
        ]
        assert all(set(item) == _PUBLIC_FIELDS for item in response.json())
        rendered = response.content.lower()
        for forbidden in (
            b'"id"',
            b"contract_version",
            b"capabilities",
            b"criado_em",
            b"atualizado_em",
            b"select ",
        ):
            assert forbidden not in rendered
        for marker in _PRIVATE_MARKERS:
            assert marker.encode() not in response.content
        assert service.calls == [()]
        assert dependency.calls == [()]

        # Query strings do not become authority or arguments of the service.
        service.reset(result=(monthly,))
        dependency.reset(result=_UserMustRemainOpaque())
        injected = client.get(
            "/checkout/offers",
            params={
                "user_id": "999",
                "preco": "0.01",
                "moeda": "USD",
                "contract_version": "999",
                "capabilities": "browser.injected",
            },
        )
        assert injected.status_code == 200
        assert injected.json()[0]["preco"] == "39.90"
        assert service.calls == [()]
        assert dependency.calls == [()]

        service.reset(result=())
        dependency.reset(result=_UserMustRemainOpaque())
        empty = client.get("/checkout/offers")
        assert empty.status_code == 200
        assert empty.json() == []
        assert service.calls == [()]
        assert dependency.calls == [()]

        service.reset(result=(monthly,))
        dependency.reset(
            error=HTTPException(status_code=401, detail="not authenticated")
        )
        unauthenticated = client.get("/checkout/offers")
        assert unauthenticated.status_code == 401
        assert service.calls == []

        dependency.reset(result=_UserMustRemainOpaque())
        invalid_results = (
            None,
            [monthly],
            (object(),),
            (_offer("tax-invalid-state", estado="draft"),),
            (_offer("Tax-invalid-code"),),
            (_offer("tax-invalid-name", nome_publico=""),),
            (_offer("tax-invalid-vertical", vertical="payments"),),
            (_offer("tax-invalid-model", commercial_model="lifetime"),),
            (_offer("tax-invalid-subject", subject_type="browser"),),
            (_offer("tax-invalid-currency", moeda="USD"),),
            (_offer("tax-invalid-period", billing_period="year"),),
            (_offer("tax-invalid-unit", usage_unit="document"),),
            (_offer("tax-invalid-limit", usage_limit=True),),
            (_offer("tax-invalid-price-type", preco="39.90"),),
            (_offer("tax-invalid-price-scale", preco=Decimal("39.900")),),
            (_offer("tax-invalid-price-zero", preco=Decimal("0.00")),),
            (_offer("tax-invalid-price-nan", preco=Decimal("NaN")),),
            (_offer("tax-invalid-mode", checkout_mode="browser"),),
            (
                _offer("tax-duplicate-company"),
                _offer("tax-duplicate-company", id=999),
            ),
            (
                monthly,
                _offer(
                    "tax-invalid-second",
                    checkout_mode=_PRIVATE_MARKERS[2],
                ),
            ),
        )
        for invalid_result in invalid_results:
            service.reset(result=invalid_result)
            divergent = client.get("/checkout/offers")
            _assert_empty_500(divergent)
            assert service.calls == [()]

        service.reset(error=RuntimeError(_PRIVATE_MARKERS[0]))
        failed = client.get("/checkout/offers")
        _assert_empty_500(failed)
        assert service.calls == [()]

    source = inspect.getsource(router_module)
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.level))
    blocked_roots = {
        "sqlalchemy",
        "sqlite3",
        "database",
        "databases",
        "os",
        "dotenv",
        "requests",
        "httpx",
        "socket",
        "mercadopago",
        "stripe",
    }
    assert not {name.split(".")[0] for name, _ in imports} & blocked_roots
    assert not any(
        name == "app.main"
        or name.startswith("app.main.")
        or name == "app.models"
        or name.startswith("app.models.")
        or name == "app.services"
        or name.startswith("app.services.")
        for name, _ in imports
    )
    for name, level in imports:
        if level == 0 and name.split(".")[0] in {
            "fastapi",
            "starlette",
            "pydantic",
        }:
            continue
        assert level == 0
        assert name.split(".")[0] in sys.stdlib_module_names

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    service_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "listar_ofertas_publicadas"
    ]
    assert len(service_calls) == 1
    assert service_calls[0].args == []
    assert service_calls[0].keywords == []
    depends_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "Depends"
    ]
    assert len(depends_calls) == 1
    assert len(depends_calls[0].args) == 1
    assert isinstance(depends_calls[0].args[0], ast.Name)
    assert depends_calls[0].args[0].id == "current_user_dependency"
    assert depends_calls[0].keywords == []

    lowered_source = source.lower()
    for forbidden_fragment in (
        "app.main",
        "get_usuario_atual",
        "get_current_user",
        "sessionmaker",
        "create_engine",
        "select(",
        "insert(",
        "update(",
        "delete(",
        "commit(",
        "flush(",
        "rollback(",
        "mercado_pago",
        "mercadopago",
        "webhook",
        "print(",
        "traceback",
    ):
        assert forbidden_fragment not in lowered_source
