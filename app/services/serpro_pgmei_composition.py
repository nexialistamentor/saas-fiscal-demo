"""Fail-closed composition root for the SERPRO PGMEI client."""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping
from numbers import Real
from typing import Any
from urllib.parse import urlsplit

from app.services.serpro_authenticated_transport import SerproAuthenticatedTransport
from app.services.serpro_oauth_session import SerproOAuthSession
from app.services.serpro_pgmei_client import SerproPgmeiClient
from app.services.serpro_pkcs12_transport import (
    Pkcs12Identity,
    SerproPkcs12Transport,
)


DEFAULT_OAUTH_TIMEOUT = 30.0
DEFAULT_PGMEI_TIMEOUT = 30.0
DEFAULT_OAUTH_SAFE_WINDOW = 30.0

_REQUIRED = (
    "SERPRO_CONSUMER_KEY",
    "SERPRO_CONSUMER_SECRET",
    "SERPRO_PKCS12_FILE",
    "SERPRO_PKCS12_PASSWORD",
    "SERPRO_PGMEI_ENDPOINT",
    "SERPRO_CONTRATANTE",
)


class SerproPgmeiCompositionError(RuntimeError):
    """Sanitized public composition failure."""


class _ComposedSerproPgmeiClient(SerproPgmeiClient):
    def __repr__(self) -> str:
        return f"{SerproPgmeiClient.__name__}(<redacted>)"

    __str__ = __repr__


def compose_serpro_pgmei(
    config: Mapping[str, Any] | None = None,
    *,
    request: Callable[..., Any] | None = None,
) -> SerproPgmeiClient | None:
    """Build the sole PGMEI dependency graph when explicitly enabled."""
    source: Mapping[str, Any] = os.environ if config is None else config
    if not isinstance(source, Mapping):
        raise SerproPgmeiCompositionError("configuracao SERPRO invalida")

    gate = source.get("SERPRO_PGMEI_ENABLED", "false")
    if type(gate) is not str:
        raise SerproPgmeiCompositionError("configuracao SERPRO invalida")
    if gate == "false":
        return None
    if gate != "true":
        raise SerproPgmeiCompositionError("configuracao SERPRO invalida")

    try:
        values = {name: _required_string(source, name) for name in _REQUIRED}
        oauth_timeout = _number(
            source.get("SERPRO_OAUTH_TIMEOUT", DEFAULT_OAUTH_TIMEOUT),
            allow_zero=False,
        )
        pgmei_timeout = _number(
            source.get("SERPRO_PGMEI_TIMEOUT", DEFAULT_PGMEI_TIMEOUT),
            allow_zero=False,
        )
        safe_window = _number(
            source.get("SERPRO_OAUTH_SAFE_WINDOW", DEFAULT_OAUTH_SAFE_WINDOW),
            allow_zero=True,
        )
        if not _https_url(values["SERPRO_PGMEI_ENDPOINT"]):
            raise ValueError
        if request is not None and not callable(request):
            raise ValueError
    except Exception:
        raise SerproPgmeiCompositionError("configuracao SERPRO invalida") from None

    try:
        identity = Pkcs12Identity(
            pkcs12_filename=values["SERPRO_PKCS12_FILE"],
            pkcs12_password=values["SERPRO_PKCS12_PASSWORD"],
        )
        pkcs12_transport = SerproPkcs12Transport(
            mtls_identity=identity,
            request=request,
        )
        session = SerproOAuthSession(
            consumer_key=values["SERPRO_CONSUMER_KEY"],
            consumer_secret=values["SERPRO_CONSUMER_SECRET"],
            mtls_identity=identity,
            transport=pkcs12_transport,
            safe_window=safe_window,
            timeout=oauth_timeout,
        )
        authenticated_transport = SerproAuthenticatedTransport(
            session,
            pkcs12_transport,
        )
        return _ComposedSerproPgmeiClient(
            endpoint=values["SERPRO_PGMEI_ENDPOINT"],
            authentication={},
            timeout=pgmei_timeout,
            transport=authenticated_transport,
            contratante=values["SERPRO_CONTRATANTE"],
        )
    except Exception:
        raise SerproPgmeiCompositionError("falha na composicao SERPRO") from None


def _required_string(source: Mapping[str, Any], name: str) -> str:
    value = source.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    return value


def _number(value: Any, *, allow_zero: bool) -> float:
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, str):
        if not value.strip():
            raise ValueError
        parsed = float(value)
    elif isinstance(value, Real):
        parsed = float(value)
    else:
        raise ValueError
    if not math.isfinite(parsed) or parsed < 0 or (parsed == 0 and not allow_zero):
        raise ValueError
    return parsed


def _https_url(value: str) -> bool:
    if any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
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
