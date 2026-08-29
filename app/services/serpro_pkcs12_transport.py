"""Closed HTTPS transport that delegates PKCS#12 handling to requests-pkcs12."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from numbers import Real
from typing import Any
from urllib.parse import urlsplit


class SerproPkcs12TransportError(RuntimeError):
    """Sanitized public failure exposed by the PKCS#12 transport."""


@dataclass(frozen=True, repr=False)
class Pkcs12Identity:
    """Opaque PKCS#12 arguments accepted by requests-pkcs12."""

    pkcs12_password: str
    pkcs12_data: bytes | None = None
    pkcs12_filename: str | bytes | None = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"

    __str__ = __repr__


_MISSING = object()


class SerproPkcs12Transport:
    """Validate a SERPRO HTTPS call and delegate its mTLS boundary unchanged."""

    def __init__(
        self,
        *,
        mtls_identity: object,
        request: Callable[..., Any] | None = None,
    ) -> None:
        if not isinstance(mtls_identity, Pkcs12Identity) or not self._valid_identity(
            mtls_identity
        ):
            raise SerproPkcs12TransportError("configuracao mTLS invalida")
        if request is not None and not callable(request):
            raise SerproPkcs12TransportError("configuracao mTLS invalida")
        self._mtls_identity = mtls_identity
        self._request = request if request is not None else self._default_request()

    @staticmethod
    def _default_request() -> Callable[..., Any]:
        try:
            from requests_pkcs12 import request
        except Exception as exc:
            raise SerproPkcs12TransportError("configuracao mTLS invalida") from exc
        return request

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(mtls_identity=<redacted>, "
            "request=<redacted>)"
        )

    __str__ = __repr__

    def __call__(
        self,
        *,
        url: Any,
        headers: Any,
        timeout: Any,
        method: Any = "POST",
        json: Any = _MISSING,
        data: Any = _MISSING,
        mtls_identity: object | None = None,
    ) -> Any:
        identity = self._resolve_identity(mtls_identity)
        if not self._valid_method(method) or not self._valid_url(url):
            raise SerproPkcs12TransportError("requisicao SERPRO invalida")
        if not self._valid_timeout(timeout) or not self._valid_headers(headers):
            raise SerproPkcs12TransportError("requisicao SERPRO invalida")
        if json is not _MISSING and data is not _MISSING:
            raise SerproPkcs12TransportError("requisicao SERPRO invalida")

        kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": timeout,
            "pkcs12_password": identity.pkcs12_password,
        }
        if json is not _MISSING:
            kwargs["json"] = json
        if data is not _MISSING:
            kwargs["data"] = data
        if identity.pkcs12_data is not None:
            kwargs["pkcs12_data"] = identity.pkcs12_data
        else:
            kwargs["pkcs12_filename"] = identity.pkcs12_filename

        try:
            return self._request(method, url, **kwargs)
        except Exception as exc:
            raise SerproPkcs12TransportError("falha no transporte SERPRO") from exc

    def _resolve_identity(self, supplied: object | None) -> Pkcs12Identity:
        if supplied is not None and supplied is not self._mtls_identity:
            raise SerproPkcs12TransportError("configuracao mTLS invalida")
        identity = self._mtls_identity if supplied is None else supplied
        if not isinstance(identity, Pkcs12Identity) or not self._valid_identity(identity):
            raise SerproPkcs12TransportError("configuracao mTLS invalida")
        return identity

    @staticmethod
    def _valid_identity(identity: Pkcs12Identity) -> bool:
        if not isinstance(identity.pkcs12_password, str) or not identity.pkcs12_password:
            return False
        has_data = isinstance(identity.pkcs12_data, bytes) and bool(identity.pkcs12_data)
        has_filename = (
            isinstance(identity.pkcs12_filename, (str, bytes))
            and bool(identity.pkcs12_filename.strip())
        )
        return has_data != has_filename

    @staticmethod
    def _valid_method(method: object) -> bool:
        return isinstance(method, str) and method == "POST"

    @staticmethod
    def _valid_url(url: object) -> bool:
        if not isinstance(url, str) or any(character.isspace() for character in url):
            return False
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.fragment == ""
            and (port is None or 0 < port <= 65535)
        )

    @staticmethod
    def _valid_timeout(timeout: object) -> bool:
        return (
            not isinstance(timeout, bool)
            and isinstance(timeout, Real)
            and math.isfinite(timeout)
            and timeout > 0
        )

    @staticmethod
    def _valid_headers(headers: object) -> bool:
        if not isinstance(headers, Mapping):
            return False
        names: set[str] = set()
        for name, value in headers.items():
            if (
                not isinstance(name, str)
                or not isinstance(value, str)
                or not name.strip()
                or "\r" in name
                or "\n" in name
                or "\r" in value
                or "\n" in value
            ):
                return False
            lowered = name.lower()
            if lowered in names:
                return False
            names.add(lowered)
        return True
