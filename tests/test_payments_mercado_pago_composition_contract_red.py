"""Contrato RED test-only da composicao raiz do Mercado Pago."""

import ast
import builtins
import gc
import inspect
import os
import socket
from importlib import import_module
from types import NoneType
from typing import get_args, get_type_hints

import pytest


_TARGET_MODULE = "app.services.mercado_pago_composition"


class _ForbiddenEnvironment(dict):
    def __getitem__(self, key):
        raise AssertionError("a composicao nao pode ler os.environ")

    def __iter__(self):
        raise AssertionError("a composicao nao pode iterar os.environ")

    def __contains__(self, key):
        raise AssertionError("a composicao nao pode consultar os.environ")

    def get(self, key, default=None):
        raise AssertionError("a composicao nao pode ler os.environ")


class _UntouchedCollaborator:
    __slots__ = ("_name",)

    def __init__(self, name):
        object.__setattr__(self, "_name", name)

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"colaborador tocado: {self._name}")

    def __getattr__(self, attribute):
        raise AssertionError(f"colaborador tocado: {self._name}.{attribute}")


class _ExplicitValues:
    """Objeto que so pode atravessar por identidade ate o resolvedor."""

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __getitem__(self, key):
        raise AssertionError("values deve ser delegado sem leitura paralela")

    def __iter__(self):
        raise AssertionError("values deve ser delegado sem iteracao paralela")

    def __getattr__(self, attribute):
        raise AssertionError("values deve ser delegado somente ao resolvedor")


class _ResolvedConfiguration:
    __slots__ = (
        "access_token",
        "webhook_secret",
        "notification_url",
        "back_urls",
        "timeout_seconds",
        "max_body_bytes",
    )

    def __init__(self):
        self.access_token = "mp-test-token-contract-marker"
        self.webhook_secret = "mp-test-webhook-secret-contract-marker"
        self.notification_url = (
            "https://payments.example.invalid/webhooks/mercado-pago"
        )
        self.back_urls = {
            "success": "https://app.example.invalid/checkout/success",
            "failure": "https://app.example.invalid/checkout/failure",
            "pending": "https://app.example.invalid/checkout/pending",
        }
        self.timeout_seconds = 7.25
        self.max_body_bytes = 16384


class _Constructed:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


def _constructor_double(name, events, instances):
    def construct(*args, **kwargs):
        instance = _Constructed(name)
        events.append((name, args, kwargs, instance))
        instances[name] = instance
        return instance

    return construct


def _assert_static_boundaries(module):
    tree = ast.parse(inspect.getsource(module))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden_modules = (
        "app.routers",
        "dotenv",
        "fastapi",
        "http",
        "httpx",
        "importlib",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    )
    assert not any(
        imported_name == forbidden
        or imported_name.startswith(f"{forbidden}.")
        for imported_name in imported
        for forbidden in forbidden_modules
    )
    assert not any(
        isinstance(node, ast.Name) and node.id == "open"
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"__import__", "import_module"}
        for node in ast.walk(tree)
    )


def _assert_private(rendering, *markers):
    normalized = rendering.lower()
    for marker in markers:
        if isinstance(marker, str) and marker.strip():
            assert marker.lower() not in normalized


def test_payments_mercado_pago_composition_contract_red(monkeypatch):
    composition = import_module(_TARGET_MODULE)

    signature = inspect.signature(composition.compor_mercado_pago)
    assert list(signature.parameters) == [
        "values",
        "session_factory",
        "http_client",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    return_type = get_type_hints(composition.compor_mercado_pago)["return"]
    assert set(get_args(return_type)) == {
        composition.MercadoPagoComposition,
        NoneType,
    }
    _assert_static_boundaries(composition)

    disabled_values = _ExplicitValues("disabled")
    enabled_values = _ExplicitValues("enabled")
    session_factory = _UntouchedCollaborator("session_factory")
    http_client = _UntouchedCollaborator("http_client")
    configuration = _ResolvedConfiguration()
    events = []
    instances = {}

    def resolve_configuration(*args, **kwargs):
        assert args == ()
        assert set(kwargs) == {"values"}
        values = kwargs["values"]
        events.append(("resolver", args, kwargs, values))
        if values is disabled_values:
            return None
        assert values is enabled_values
        return configuration

    monkeypatch.setattr(
        composition,
        "resolver_mercado_pago_runtime_config",
        resolve_configuration,
    )
    constructor_names = (
        "MercadoPagoPaymentClient",
        "MercadoPagoPreferenceClient",
        "MercadoPagoCheckoutOfferOneTimeGateway",
        "CheckoutOfferOrderComposer",
        "CheckoutOfferOneTimeDispatcher",
        "CheckoutOfferOneTimeApplication",
        "criar_mercado_pago_webhook_orchestrator",
    )
    for name in constructor_names:
        monkeypatch.setattr(
            composition,
            name,
            _constructor_double(name, events, instances),
        )

    def forbidden_effect(*args, **kwargs):
        raise AssertionError("I/O, ambiente ou rede executado pela composicao")

    with monkeypatch.context() as boundary_guard:
        boundary_guard.setattr(os, "environ", _ForbiddenEnvironment())
        boundary_guard.setattr(os, "getenv", forbidden_effect)
        boundary_guard.setattr(builtins, "open", forbidden_effect)
        boundary_guard.setattr(socket, "create_connection", forbidden_effect)
        boundary_guard.setattr(socket, "socket", forbidden_effect)

        disabled = composition.compor_mercado_pago(
            values=disabled_values,
            session_factory=session_factory,
            http_client=http_client,
        )
        assert disabled is None
        assert [event[0] for event in events] == ["resolver"]

        events.clear()
        result = composition.compor_mercado_pago(
            values=enabled_values,
            session_factory=session_factory,
            http_client=http_client,
        )

    assert [event[0] for event in events] == ["resolver", *constructor_names]
    calls = {event[0]: event for event in events[1:]}

    payment_call = calls["MercadoPagoPaymentClient"]
    preference_call = calls["MercadoPagoPreferenceClient"]
    assert payment_call[1] == preference_call[1] == ()
    for call in (payment_call, preference_call):
        assert call[2] == {
            "http_client": http_client,
            "access_token": configuration.access_token,
            "timeout_seconds": configuration.timeout_seconds,
        }

    gateway_call = calls["MercadoPagoCheckoutOfferOneTimeGateway"]
    assert gateway_call[1][:2] == (
        instances["MercadoPagoPreferenceClient"],
        configuration.notification_url,
    )
    assert gateway_call[2] == {}
    copied_back_urls = gateway_call[1][2]
    assert type(copied_back_urls) is dict
    assert copied_back_urls == configuration.back_urls
    assert copied_back_urls is not configuration.back_urls

    composer_call = calls["CheckoutOfferOrderComposer"]
    assert composer_call[1] == (session_factory,)
    assert composer_call[2] == {}
    dispatcher_call = calls["CheckoutOfferOneTimeDispatcher"]
    assert dispatcher_call[1] == (
        session_factory,
        instances["MercadoPagoCheckoutOfferOneTimeGateway"],
    )
    assert dispatcher_call[2] == {}
    application_call = calls["CheckoutOfferOneTimeApplication"]
    assert application_call[1] == (
        instances["CheckoutOfferOrderComposer"],
        instances["CheckoutOfferOneTimeDispatcher"],
    )
    assert application_call[2] == {}

    webhook_call = calls["criar_mercado_pago_webhook_orchestrator"]
    assert webhook_call[1] == ()
    assert webhook_call[2] == {
        "session_factory": session_factory,
        "signature_validator": composition.validar_mercado_pago_webhook_hmac,
        "signature_secret": configuration.webhook_secret,
        "payment_client": instances["MercadoPagoPaymentClient"],
    }

    assert type(result) is composition.MercadoPagoComposition
    assert {
        name for name in dir(result) if not name.startswith("_")
    } == {
        "checkout_application",
        "webhook_orchestrator",
        "max_body_bytes",
    }
    assert result.checkout_application is instances["CheckoutOfferOneTimeApplication"]
    assert result.webhook_orchestrator is instances[
        "criar_mercado_pago_webhook_orchestrator"
    ]
    assert result.max_body_bytes == configuration.max_body_bytes
    assert not hasattr(result, "__dict__")
    assert http_client not in gc.get_referents(result)
    assert not any(
        fragment in name.lower()
        for name in dir(result)
        for fragment in ("access_token", "http_client", "secret")
    )

    rendering = f"{result!r} {result!s}"
    assert repr(result) == str(result) == "<MercadoPagoComposition opaque>"
    _assert_private(
        rendering,
        "",
        " \t\r\n ",
        configuration.access_token,
        configuration.webhook_secret,
        configuration.notification_url,
        *configuration.back_urls.values(),
    )
    for name in (
        "checkout_application",
        "webhook_orchestrator",
        "max_body_bytes",
    ):
        with pytest.raises((AttributeError, TypeError)):
            setattr(result, name, object())
        with pytest.raises((AttributeError, TypeError)):
            delattr(result, name)
    with pytest.raises((AttributeError, TypeError)):
        result.extra = object()
