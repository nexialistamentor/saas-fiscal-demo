"""Contrato RED da configuracao explicita de runtime do Mercado Pago."""

import ast
import json
import math
import pickle
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from importlib import import_module
from inspect import Parameter, getsource, signature
from types import MappingProxyType

import pytest


_ENABLED = "MERCADO_PAGO_ENABLED"
_ENVIRONMENT = "ENVIRONMENT"
_MODE = "MERCADO_PAGO_MODE"
_TEST_TOKEN = "TEST-token-visible-9x"
_TEST_SECRET = "TEST-secret-visible-8y"
_PRODUCTION_TOKEN = "PROD-token-visible-7z"
_PRODUCTION_SECRET = "PROD-secret-visible-6w"
_NOTIFICATION_URL = (
    "https://hooks.example.invalid/api/webhooks/mercado-pago"
)
_SUCCESS_URL = "https://app.example.invalid:8443/payment/success?source=mp"
_FAILURE_URL = "https://app.example.invalid/payment/failure"
_PENDING_URL = "https://app.example.invalid/payment/pending"
_SELECTED_KEYS = {
    "test": (
        "MERCADO_PAGO_TEST_ACCESS_TOKEN",
        "MERCADO_PAGO_TEST_WEBHOOK_SECRET",
    ),
    "production": (
        "MERCADO_PAGO_PRODUCTION_ACCESS_TOKEN",
        "MERCADO_PAGO_PRODUCTION_WEBHOOK_SECRET",
    ),
}
_COMMON_KEYS = {
    "notification_url": "MERCADO_PAGO_NOTIFICATION_URL",
    "success": "MERCADO_PAGO_BACK_URL_SUCCESS",
    "failure": "MERCADO_PAGO_BACK_URL_FAILURE",
    "pending": "MERCADO_PAGO_BACK_URL_PENDING",
    "timeout": "MERCADO_PAGO_TIMEOUT_SECONDS",
    "max_body": "MERCADO_PAGO_MAX_BODY_BYTES",
}
_PRIVATE_MARKERS = (
    _TEST_TOKEN,
    _TEST_SECRET,
    _PRODUCTION_TOKEN,
    _PRODUCTION_SECRET,
    _NOTIFICATION_URL,
    _SUCCESS_URL,
    _FAILURE_URL,
    _PENDING_URL,
)


class _GuardedMapping(Mapping):
    def __init__(self, values, forbidden=()):
        self._values = dict(values)
        self._forbidden = set(forbidden)
        self.accessed = []

    def __getitem__(self, key):
        self.accessed.append(key)
        if key in self._forbidden:
            raise AssertionError(f"chave proibida lida: {key}")
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class _ConstructionGuard:
    def __init__(self, *args, **kwargs):
        raise AssertionError("configuracao construida com gate desativado")


def _values(*, environment="test", mode="test"):
    return {
        _ENABLED: "true",
        _ENVIRONMENT: environment,
        _MODE: mode,
        _SELECTED_KEYS["test"][0]: _TEST_TOKEN,
        _SELECTED_KEYS["test"][1]: _TEST_SECRET,
        _SELECTED_KEYS["production"][0]: _PRODUCTION_TOKEN,
        _SELECTED_KEYS["production"][1]: _PRODUCTION_SECRET,
        _COMMON_KEYS["notification_url"]: _NOTIFICATION_URL,
        _COMMON_KEYS["success"]: _SUCCESS_URL,
        _COMMON_KEYS["failure"]: _FAILURE_URL,
        _COMMON_KEYS["pending"]: _PENDING_URL,
        _COMMON_KEYS["timeout"]: "4.25",
        _COMMON_KEYS["max_body"]: "32768",
    }


def _sensitive_values(values):
    if not isinstance(values, Mapping):
        return ()
    result = []
    for key in (*_SELECTED_KEYS["test"], *_SELECTED_KEYS["production"],
                *tuple(_COMMON_KEYS.values())[:4]):
        try:
            value = values[key]
        except (KeyError, AssertionError):
            continue
        if isinstance(value, str) and value and value.strip():
            result.append(value)
    return tuple(result)


def _assert_opaque(value, *private_values):
    rendered = f"{value!s} {value!r}".lower()
    for marker in (
        "access_token", "webhook_secret", "credential", "credencial",
        "traceback", "dotenv", "http://", "https://",
        *_PRIVATE_MARKERS, *private_values,
    ):
        marker_text = str(marker)
        if not marker_text.strip():
            continue
        assert marker_text.lower() not in rendered


def _reject(module, values, *private_values):
    before = dict(values) if isinstance(values, dict) else None
    with pytest.raises(
        module.MercadoPagoRuntimeConfigurationError
    ) as captured:
        module.resolver_mercado_pago_runtime_config(values=values)
    assert type(captured.value) is module.MercadoPagoRuntimeConfigurationError
    assert captured.value.args
    assert all(type(arg) is str and arg for arg in captured.value.args)
    assert captured.value.__cause__ is None
    if captured.value.__context__ is not None:
        assert captured.value.__suppress_context__ is True
    _assert_opaque(
        captured.value, *_sensitive_values(values), *private_values
    )
    if before is not None:
        assert values == before
    return captured.value.args


def _replace(values, key, value):
    changed = dict(values)
    if value is ...:
        changed.pop(key, None)
    else:
        changed[key] = value
    return changed


def test_payments_mercado_pago_runtime_config_contract_red(monkeypatch):
    module = import_module("app.services.mercado_pago_runtime_config")

    assert set(module.__all__) == {
        "MercadoPagoRuntimeConfigurationError",
        "MercadoPagoRuntimeConfiguration",
        "resolver_mercado_pago_runtime_config",
    }
    assert issubclass(module.MercadoPagoRuntimeConfigurationError, Exception)
    parameters = signature(
        module.resolver_mercado_pago_runtime_config
    ).parameters
    assert tuple(parameters) == ("values",)
    assert parameters["values"].kind is Parameter.KEYWORD_ONLY
    assert parameters["values"].default is Parameter.empty

    tree = ast.parse(getsource(module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    blocked = {
        "fastapi", "starlette", "httpx", "requests", "socket", "ssl",
        "sqlalchemy", "sqlite3", "dotenv", "os", "logging", "time",
        "datetime", "hmac", "hashlib", "secrets", "mercadopago",
    }
    assert not {name.split(".")[0] for name in imported} & blocked
    assert not any(name == "app.models" for name in imported)
    assert not any(
        name.startswith("urllib.") and name != "urllib.parse"
        for name in imported
    )
    lowered_source = getsource(module).lower()
    for marker in (
        "os.environ", "os.getenv", "getenv(", "load_dotenv",
        "create_engine", "requests.", "httpx.", "logging.", "hmac.",
    ):
        assert marker not in lowered_source

    for disabled in ({}, {_ENABLED: "false"}):
        before = dict(disabled)
        assert module.resolver_mercado_pago_runtime_config(
            values=disabled
        ) is None
        assert disabled == before

    disabled_values = _values()
    disabled_values[_ENABLED] = "false"
    disabled_probe = _GuardedMapping(
        disabled_values, set(disabled_values) - {_ENABLED}
    )
    with monkeypatch.context() as scoped:
        scoped.setattr(
            module, "MercadoPagoRuntimeConfiguration", _ConstructionGuard
        )
        assert module.resolver_mercado_pago_runtime_config(
            values=disabled_probe
        ) is None
    assert set(disabled_probe.accessed) <= {_ENABLED}

    invalid_mappings = (
        None, True, 1, "true", b"true", [], (), set(), object()
    )
    for invalid_mapping in invalid_mappings:
        _reject(module, invalid_mapping)
    for gate in (None, True, False, 0, 1, "", "False", "TRUE", " false",
                 "true ", "0", "1"):
        _reject(module, {_ENABLED: gate})

    base = _values()
    for environment in (
        ..., None, "", "Development", "qa", "production ", True
    ):
        _reject(module, _replace(base, _ENVIRONMENT, environment))
    for mode in (..., None, "", "Test", "sandbox", "production ", True):
        _reject(module, _replace(base, _MODE, mode))
    _reject(
        module,
        _replace(_values(environment="production"), _MODE, "test"),
    )
    for environment in ("development", "test", "staging"):
        _reject(
            module,
            _replace(_values(environment=environment), _MODE, "production"),
        )

    configurations = []
    for environment, mode in (
        ("development", "test"), ("test", "test"),
        ("staging", "test"), ("production", "production"),
    ):
        candidate = _values(environment=environment, mode=mode)
        selected = _SELECTED_KEYS[mode]
        opposite = _SELECTED_KEYS[
            "production" if mode == "test" else "test"
        ]
        probe = _GuardedMapping(candidate, opposite)
        config = module.resolver_mercado_pago_runtime_config(values=probe)
        assert type(config) is module.MercadoPagoRuntimeConfiguration
        assert config.mode == mode
        assert config.access_token == candidate[selected[0]]
        assert config.webhook_secret == candidate[selected[1]]
        assert config.notification_url == _NOTIFICATION_URL
        assert isinstance(config.back_urls, Mapping)
        assert dict(config.back_urls) == {
            "success": _SUCCESS_URL,
            "failure": _FAILURE_URL,
            "pending": _PENDING_URL,
        }
        assert config.timeout_seconds == 4.25
        assert type(config.timeout_seconds) is float
        assert config.max_body_bytes == 32768
        assert type(config.max_body_bytes) is int
        assert not set(probe.accessed) & set(opposite)
        configurations.append((config, candidate))

    config, valid_input = configurations[1]
    assert {
        name for name in dir(config) if not name.startswith("_")
    } == {
        "mode", "access_token", "webhook_secret", "notification_url",
        "back_urls", "timeout_seconds", "max_body_bytes",
    }
    for name in (
        "mode", "access_token", "webhook_secret", "notification_url",
        "back_urls", "timeout_seconds", "max_body_bytes",
    ):
        with pytest.raises((AttributeError, TypeError)):
            setattr(config, name, "changed")
    with pytest.raises((AttributeError, TypeError)):
        config.back_urls["success"] = "https://changed.example.invalid"
    _assert_opaque(config)

    twin = module.resolver_mercado_pago_runtime_config(
        values=MappingProxyType(dict(valid_input))
    )
    assert twin is not config
    assert twin != config
    with pytest.raises(TypeError):
        config < twin
    serializers = [pickle.dumps, lambda item: json.dumps(item, default=vars)]
    if is_dataclass(config):
        serializers.append(asdict)
    for serializer in serializers:
        try:
            serialized = serializer(config)
        except (AttributeError, TypeError, pickle.PickleError):
            continue
        _assert_opaque(serialized)

    for mode in ("test", "production"):
        selected = _SELECTED_KEYS[mode]
        opposite = _SELECTED_KEYS[
            "production" if mode == "test" else "test"
        ]
        environment = "production" if mode == "production" else "test"
        for key in selected:
            missing = _replace(
                _values(environment=environment, mode=mode), key, ...
            )
            missing[opposite[0]] = "opposite-token-must-not-fallback"
            missing[opposite[1]] = "opposite-secret-must-not-fallback"
            _reject(module, missing)
        for key in selected:
            for invalid in (
                None, "", " ", "has space", "tab\tvalue", "line\nvalue",
                "acentuado-ç", "delete-\x7f", 17, b"bytes", True,
            ):
                _reject(module, _replace(
                    _values(environment=environment, mode=mode), key, invalid
                ))

    url_keys = tuple(_COMMON_KEYS.values())[:4]
    invalid_urls = (
        None, "", "http://app.example.invalid/path", "/relative/path",
        "//app.example.invalid/path", "https:///missing-host",
        "https://user:password@app.example.invalid/path",
        "https://app.example.invalid/path#fragment",
        "https://app.example.invalid:abc/path",
        "https://app.example.invalid:99999/path",
        "https://-bad.example.invalid/path",
        "https://bad..example.invalid/path",
    )
    for key in url_keys:
        for invalid in invalid_urls:
            _reject(module, _replace(base, key, invalid), invalid)
    for valid_notification in (
        "https://hooks.example.invalid/webhooks/mercado-pago",
        "https://hooks.example.invalid/api/v1/webhooks/mercado-pago",
    ):
        candidate = _replace(
            base, _COMMON_KEYS["notification_url"], valid_notification
        )
        resolved = module.resolver_mercado_pago_runtime_config(
            values=candidate
        )
        assert resolved.notification_url == valid_notification
    for invalid_notification in (
        "https://hooks.example.invalid/webhooks/mercado-pago/",
        "https://hooks.example.invalid/webhooks/mercado-pago/extra",
        "https://hooks.example.invalid/webhooks/mercado-pago?source=mp",
        "https://hooks.example.invalid/mercado-pago",
    ):
        _reject(
            module,
            _replace(
                base, _COMMON_KEYS["notification_url"], invalid_notification
            ),
            invalid_notification,
        )

    for invalid_timeout in (
        ..., None, "", "0", "-0.1", "60.0001", "nan", "inf", "-inf",
        0, -1, 60.1, math.nan, math.inf, True,
    ):
        _reject(module, _replace(
            base, _COMMON_KEYS["timeout"], invalid_timeout
        ))
    for valid_timeout in ("0.001", "60"):
        candidate = _replace(base, _COMMON_KEYS["timeout"], valid_timeout)
        resolved = module.resolver_mercado_pago_runtime_config(
            values=candidate
        )
        assert resolved.timeout_seconds == float(valid_timeout)

    for invalid_max_body in (
        ..., None, "", "0", "65537", "1.0", "1e3", " 1", "+1",
        0, 65537, 1.5, True,
    ):
        _reject(module, _replace(
            base, _COMMON_KEYS["max_body"], invalid_max_body
        ))
    for valid_max_body in ("1", "65536"):
        candidate = _replace(base, _COMMON_KEYS["max_body"], valid_max_body)
        before = dict(candidate)
        resolved = module.resolver_mercado_pago_runtime_config(
            values=candidate
        )
        assert resolved.max_body_bytes == int(valid_max_body)
        assert candidate == before
