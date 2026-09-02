"""Contrato RED test-only do lifecycle de runtime do Mercado Pago."""

import ast
import builtins
import gc
import inspect
import os
import socket
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from types import NoneType
from typing import get_args, get_type_hints

import pytest


_TARGET_MODULE = "app.services.mercado_pago_runtime_lifecycle"
_CLIENT_PRIVATE_MARKER = "mp-client-private-marker-7c1"
_CONFIG_PRIVATE_MARKER = "mp-config-private-marker-7c1"
_INVALID_PRIVATE_MARKER = "mp-invalid-private-marker-7c1"
_PARTIAL_PRIVATE_MARKER = "mp-partial-private-marker-7c1"
_ROOT = Path(__file__).resolve().parents[1]


def _assert_clean_import_boundary():
    code = f"""
import builtins
import socket
import sys

sys.path.insert(0, {str(_ROOT)!r})

def forbidden_effect(*args, **kwargs):
    raise AssertionError("isolated import touched I/O or network")

def forbid_network(event, args):
    if event in {{
        "socket.bind",
        "socket.connect",
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
    }}:
        raise AssertionError("isolated import touched network")

builtins.open = forbidden_effect
socket.create_connection = forbidden_effect
sys.addaudithook(forbid_network)

import app.services.mercado_pago_runtime_lifecycle as lifecycle

for forbidden_module in (
    "app.services.mercado_pago_composition",
    "app.models",
    "app.database",
    "app.main",
    "tests.conftest",
):
    assert forbidden_module not in sys.modules, forbidden_module

assert callable(lifecycle.compor_mercado_pago)

def replacement(*args, **kwargs):
    raise AssertionError("composition must not run during import")

lifecycle.compor_mercado_pago = replacement
assert lifecycle.compor_mercado_pago is replacement
assert callable(lifecycle.compor_mercado_pago)
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


class _ForbiddenEnvironment(dict):
    def __getitem__(self, key):
        raise AssertionError("o lifecycle nao pode ler os.environ")

    def __iter__(self):
        raise AssertionError("o lifecycle nao pode iterar os.environ")

    def __contains__(self, key):
        raise AssertionError("o lifecycle nao pode consultar os.environ")

    def get(self, key, default=None):
        raise AssertionError("o lifecycle nao pode ler os.environ")


class _ExplicitValues:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __getitem__(self, key):
        raise AssertionError("values deve chegar intacto ao resolvedor")

    def __iter__(self):
        raise AssertionError("values nao pode ser iterado pelo lifecycle")

    def __getattr__(self, attribute):
        raise AssertionError("values so pode ser delegado por identidade")


class _ResolvedConfiguration:
    __slots__ = ("private_marker",)

    def __init__(self):
        self.private_marker = _CONFIG_PRIVATE_MARKER


class _Composition:
    __slots__ = ()


class _HttpClient:
    __slots__ = ("private_marker", "close_calls", "events")

    def __init__(self, events):
        self.private_marker = _CLIENT_PRIVATE_MARKER
        self.close_calls = 0
        self.events = events

    def close(self):
        self.close_calls += 1
        self.events.append(("close", self))

    def __repr__(self):
        return f"<_HttpClient {_CLIENT_PRIVATE_MARKER}>"


class _OpaqueFailure(Exception):
    __slots__ = ()

    def __repr__(self):
        return "<_OpaqueFailure opaque>"

    __str__ = __repr__


def _assert_static_boundaries(module):
    tree = ast.parse(inspect.getsource(module))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden_modules = (
        "builtins",
        "dotenv",
        "fastapi",
        "http",
        "httpx",
        "io",
        "os",
        "pathlib",
        "requests",
        "socket",
        "starlette",
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
        isinstance(node, ast.Name)
        and node.id in {"input", "open", "print"}
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"__import__", "import_module"}
        for node in ast.walk(tree)
    )
    lowered_source = inspect.getsource(module).lower()
    for marker in (
        "os.environ",
        "os.getenv",
        "getenv(",
        "load_dotenv",
        "httpx.",
        "requests.",
    ):
        assert marker not in lowered_source


def _assert_opaque(value, *private_markers):
    rendering = f"{value!s} {value!r}".lower()
    for marker in (
        "access_token",
        "webhook_secret",
        "traceback",
        "http://",
        "https://",
        *private_markers,
    ):
        if isinstance(marker, str) and marker.strip():
            assert marker.lower() not in rendering


def test_payments_mercado_pago_runtime_lifecycle_contract_red(monkeypatch):
    _assert_clean_import_boundary()
    lifecycle = import_module(_TARGET_MODULE)

    assert set(lifecycle.__all__) == {
        "MercadoPagoRuntimeActivation",
        "ativar_mercado_pago",
    }
    parameters = inspect.signature(
        lifecycle.ativar_mercado_pago
    ).parameters
    assert tuple(parameters) == (
        "values",
        "session_factory",
        "http_client_factory",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is inspect.Parameter.empty
        for parameter in parameters.values()
    )
    return_type = get_type_hints(lifecycle.ativar_mercado_pago)["return"]
    assert set(get_args(return_type)) == {
        lifecycle.MercadoPagoRuntimeActivation,
        NoneType,
    }
    _assert_static_boundaries(lifecycle)

    disabled_values = _ExplicitValues("disabled")
    invalid_values = _ExplicitValues("invalid")
    enabled_values = _ExplicitValues("enabled")
    partial_values = _ExplicitValues("partial")
    session_factory = object()
    configuration = _ResolvedConfiguration()
    composition = _Composition()
    invalid_failure = _OpaqueFailure(_INVALID_PRIVATE_MARKER)
    partial_failure = _OpaqueFailure(_PARTIAL_PRIVATE_MARKER)
    events = []
    clients = []

    def resolve_configuration(*args, **kwargs):
        assert args == ()
        assert tuple(kwargs) == ("values",)
        values = kwargs["values"]
        events.append(("resolver", values))
        if values is disabled_values:
            return None
        if values is invalid_values:
            raise invalid_failure
        assert values is enabled_values or values is partial_values
        return configuration

    def create_http_client(*args, **kwargs):
        assert args == ()
        assert kwargs == {}
        client = _HttpClient(events)
        clients.append(client)
        events.append(("factory", client))
        return client

    def compose_canonically(*args, **kwargs):
        assert args == ()
        assert tuple(kwargs) == (
            "values",
            "session_factory",
            "http_client",
        )
        assert kwargs["session_factory"] is session_factory
        assert kwargs["http_client"] is clients[-1]
        values = kwargs["values"]
        assert values is enabled_values or values is partial_values
        events.append(("composition", values, kwargs["http_client"]))
        if values is partial_values:
            raise partial_failure
        return composition

    monkeypatch.setattr(
        lifecycle,
        "resolver_mercado_pago_runtime_config",
        resolve_configuration,
    )
    monkeypatch.setattr(lifecycle, "compor_mercado_pago", compose_canonically)

    def forbidden_effect(*args, **kwargs):
        raise AssertionError("ambiente, I/O ou rede tocado pelo lifecycle")

    with monkeypatch.context() as boundary_guard:
        boundary_guard.setattr(os, "environ", _ForbiddenEnvironment())
        boundary_guard.setattr(os, "getenv", forbidden_effect)
        boundary_guard.setattr(builtins, "open", forbidden_effect)
        boundary_guard.setattr(socket, "create_connection", forbidden_effect)
        boundary_guard.setattr(socket, "socket", forbidden_effect)

        result = lifecycle.ativar_mercado_pago(
            values=disabled_values,
            session_factory=session_factory,
            http_client_factory=create_http_client,
        )
        assert result is None
        assert events == [("resolver", disabled_values)]
        assert clients == []

        events.clear()
        with pytest.raises(_OpaqueFailure) as invalid_captured:
            lifecycle.ativar_mercado_pago(
                values=invalid_values,
                session_factory=session_factory,
                http_client_factory=create_http_client,
            )
        assert invalid_captured.value is invalid_failure
        assert events == [("resolver", invalid_values)]
        assert clients == []

        events.clear()
        activation = lifecycle.ativar_mercado_pago(
            values=enabled_values,
            session_factory=session_factory,
            http_client_factory=create_http_client,
        )
        assert [event[0] for event in events] == [
            "resolver",
            "factory",
            "composition",
        ]
        assert events[0][1] is enabled_values
        assert events[2][1] is enabled_values
        assert events[2][2] is clients[0]
        assert len(clients) == 1

        enabled_client = clients[0]
        activation.close()
        activation.close()
        assert enabled_client.close_calls == 1

        events.clear()
        with pytest.raises(_OpaqueFailure) as partial_captured:
            lifecycle.ativar_mercado_pago(
                values=partial_values,
                session_factory=session_factory,
                http_client_factory=create_http_client,
            )

    assert partial_captured.value is partial_failure
    assert [event[0] for event in events] == [
        "resolver",
        "factory",
        "composition",
        "close",
    ]
    assert len(clients) == 2
    assert clients[1].close_calls == 1

    assert type(activation) is lifecycle.MercadoPagoRuntimeActivation
    assert {
        name for name in dir(activation) if not name.startswith("_")
    } == {"close", "composition"}
    assert activation.composition is composition
    assert not hasattr(activation, "__dict__")
    for hidden_name in (
        "client",
        "configuration",
        "http_client",
        "runtime_configuration",
    ):
        assert not hasattr(activation, hidden_name)
    assert configuration not in gc.get_referents(activation)

    assert repr(activation) == str(activation) == (
        "<MercadoPagoRuntimeActivation opaque>"
    )
    _assert_opaque(
        activation,
        "",
        " \t\r\n ",
        _CLIENT_PRIVATE_MARKER,
        _CONFIG_PRIVATE_MARKER,
    )
    _assert_opaque(
        invalid_captured.value,
        "",
        " \t\r\n ",
        _INVALID_PRIVATE_MARKER,
    )
    _assert_opaque(partial_captured.value, _PARTIAL_PRIVATE_MARKER)
