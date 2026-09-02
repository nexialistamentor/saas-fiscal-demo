"""Resolve explicit Mercado Pago runtime configuration."""

from collections.abc import Mapping as _Mapping
from ipaddress import ip_address as _ip_address
from types import MappingProxyType as _MappingProxyType
from urllib.parse import urlsplit as _urlsplit


__all__ = (
    "MercadoPagoRuntimeConfigurationError",
    "MercadoPagoRuntimeConfiguration",
    "resolver_mercado_pago_runtime_config",
)


_ENABLED = "MERCADO_PAGO_ENABLED"
_ENVIRONMENT = "ENVIRONMENT"
_MODE = "MERCADO_PAGO_MODE"
_TEST_TOKEN = "MERCADO_PAGO_TEST_ACCESS_TOKEN"
_TEST_SECRET = "MERCADO_PAGO_TEST_WEBHOOK_SECRET"
_PRODUCTION_TOKEN = "MERCADO_PAGO_PRODUCTION_ACCESS_TOKEN"
_PRODUCTION_SECRET = "MERCADO_PAGO_PRODUCTION_WEBHOOK_SECRET"
_NOTIFICATION_URL = "MERCADO_PAGO_NOTIFICATION_URL"
_BACK_URL_SUCCESS = "MERCADO_PAGO_BACK_URL_SUCCESS"
_BACK_URL_FAILURE = "MERCADO_PAGO_BACK_URL_FAILURE"
_BACK_URL_PENDING = "MERCADO_PAGO_BACK_URL_PENDING"
_TIMEOUT_SECONDS = "MERCADO_PAGO_TIMEOUT_SECONDS"
_MAX_BODY_BYTES = "MERCADO_PAGO_MAX_BODY_BYTES"
_NOTIFICATION_PATH = "/webhooks/mercado-pago"
_ERROR_MESSAGE = "invalid Mercado Pago runtime configuration"


class MercadoPagoRuntimeConfigurationError(Exception):
    """Raised when explicit runtime values do not satisfy the contract."""

    __slots__ = ()


class MercadoPagoRuntimeConfiguration:
    """Immutable resolved values with opaque rendering and identity semantics."""

    __slots__ = (
        "_mode",
        "_access_token",
        "_webhook_secret",
        "_notification_url",
        "_back_urls",
        "_timeout_seconds",
        "_max_body_bytes",
    )

    def __init__(
        self,
        *,
        mode,
        access_token,
        webhook_secret,
        notification_url,
        back_urls,
        timeout_seconds,
        max_body_bytes,
    ):
        object.__setattr__(self, "_mode", mode)
        object.__setattr__(self, "_access_token", access_token)
        object.__setattr__(self, "_webhook_secret", webhook_secret)
        object.__setattr__(self, "_notification_url", notification_url)
        object.__setattr__(
            self, "_back_urls", _MappingProxyType(dict(back_urls))
        )
        object.__setattr__(self, "_timeout_seconds", timeout_seconds)
        object.__setattr__(self, "_max_body_bytes", max_body_bytes)

    @property
    def mode(self):
        return self._mode

    @property
    def access_token(self):
        return self._access_token

    @property
    def webhook_secret(self):
        return self._webhook_secret

    @property
    def notification_url(self):
        return self._notification_url

    @property
    def back_urls(self):
        return self._back_urls

    @property
    def timeout_seconds(self):
        return self._timeout_seconds

    @property
    def max_body_bytes(self):
        return self._max_body_bytes

    def __setattr__(self, name, value):
        raise AttributeError("runtime configuration is immutable")

    def __delattr__(self, name):
        raise AttributeError("runtime configuration is immutable")

    def __repr__(self):
        return "<MercadoPagoRuntimeConfiguration opaque>"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("runtime configuration serialization is disabled")

    def __reduce_ex__(self, protocol):
        raise TypeError("runtime configuration serialization is disabled")

    def __getstate__(self):
        raise TypeError("runtime configuration serialization is disabled")


def _fail():
    raise MercadoPagoRuntimeConfigurationError(_ERROR_MESSAGE) from None


def _required(values, key):
    try:
        return values[key]
    except KeyError:
        _fail()


def _visible_ascii(value):
    return (
        type(value) is str
        and bool(value)
        and all(0x21 <= ord(character) <= 0x7E for character in value)
    )


def _valid_hostname(hostname):
    try:
        _ip_address(hostname)
        return True
    except ValueError:
        pass

    if all(character == "." or character.isdigit() for character in hostname):
        return False
    candidate = hostname[:-1] if hostname.endswith(".") else hostname
    if not candidate or len(candidate) > 253:
        return False
    labels = candidate.split(".")
    return all(
        label
        and len(label) <= 63
        and label[0] != "-"
        and label[-1] != "-"
        and all(character.isalnum() or character == "-" for character in label)
        for label in labels
    )


def _https_url(value, *, notification=False):
    if not _visible_ascii(value) or "#" in value:
        _fail()
    try:
        parsed = _urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        _fail()
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or not _valid_hostname(hostname)
        or port == 0
    ):
        _fail()
    if notification and (
        not parsed.path.endswith(_NOTIFICATION_PATH)
        or parsed.query
        or "?" in value
    ):
        _fail()
    return value


def _timeout(value):
    if type(value) is not str or not value or value != value.strip():
        _fail()
    try:
        parsed = float(value)
    except ValueError:
        _fail()
    if not 0.0 < parsed <= 60.0:
        _fail()
    return parsed


def _max_body(value):
    if (
        type(value) is not str
        or not value
        or not all("0" <= character <= "9" for character in value)
    ):
        _fail()
    parsed = int(value)
    if not 1 <= parsed <= 65536:
        _fail()
    return parsed


def resolver_mercado_pago_runtime_config(*, values):
    """Resolve only the supplied mapping, returning None when disabled."""

    if not isinstance(values, _Mapping):
        _fail()

    try:
        enabled = values[_ENABLED]
    except KeyError:
        return None
    if enabled == "false" and type(enabled) is str:
        return None
    if enabled != "true" or type(enabled) is not str:
        _fail()

    environment = _required(values, _ENVIRONMENT)
    mode = _required(values, _MODE)
    if type(environment) is not str or type(mode) is not str:
        _fail()
    if mode == "test":
        if environment not in {"development", "test", "staging"}:
            _fail()
        token_key = _TEST_TOKEN
        secret_key = _TEST_SECRET
    elif mode == "production":
        if environment != "production":
            _fail()
        token_key = _PRODUCTION_TOKEN
        secret_key = _PRODUCTION_SECRET
    else:
        _fail()

    access_token = _required(values, token_key)
    webhook_secret = _required(values, secret_key)
    if not _visible_ascii(access_token) or not _visible_ascii(webhook_secret):
        _fail()

    notification_url = _https_url(
        _required(values, _NOTIFICATION_URL), notification=True
    )
    back_urls = {
        "success": _https_url(_required(values, _BACK_URL_SUCCESS)),
        "failure": _https_url(_required(values, _BACK_URL_FAILURE)),
        "pending": _https_url(_required(values, _BACK_URL_PENDING)),
    }
    timeout_seconds = _timeout(_required(values, _TIMEOUT_SECONDS))
    max_body_bytes = _max_body(_required(values, _MAX_BODY_BYTES))

    return MercadoPagoRuntimeConfiguration(
        mode=mode,
        access_token=access_token,
        webhook_secret=webhook_secret,
        notification_url=notification_url,
        back_urls=back_urls,
        timeout_seconds=timeout_seconds,
        max_body_bytes=max_body_bytes,
    )
