"""In-memory OAuth session for SERPRO, independent of certificate formats."""

from __future__ import annotations

import base64
import math
import threading
import time
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Callable


DEFAULT_ENDPOINT = "https://autenticacao.sapi.serpro.gov.br/authenticate"


class OAuthSessionError(RuntimeError):
    """Sanitized public failure raised by the OAuth session."""


@dataclass(frozen=True)
class _Token:
    access_token: str = field(repr=False)
    jwt_token: str = field(repr=False)
    expires_at: float


class SerproOAuthSession:
    """Acquire, cache and invalidate SERPRO OAuth credentials in memory."""

    def __init__(
        self,
        *,
        consumer_key: str,
        consumer_secret: str,
        mtls_identity: object,
        transport: Callable[..., Any],
        clock: Callable[[], float] = time.monotonic,
        safe_window: float = 30.0,
        timeout: float = 30.0,
        endpoint: str = DEFAULT_ENDPOINT,
    ) -> None:
        if not self._valid_number(safe_window, minimum=0, inclusive=True):
            raise OAuthSessionError("configuracao OAuth SERPRO invalida")
        if not self._valid_number(timeout, minimum=0, inclusive=False):
            raise OAuthSessionError("configuracao OAuth SERPRO invalida")
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._mtls_identity = mtls_identity
        self._transport = transport
        self._clock = clock
        self._safe_window = safe_window
        self._timeout = timeout
        self._endpoint = endpoint
        self._token: _Token | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _valid_number(value: object, *, minimum: float, inclusive: bool) -> bool:
        if isinstance(value, bool) or not isinstance(value, Real):
            return False
        if not math.isfinite(value):
            return False
        return value >= minimum if inclusive else value > minimum

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(endpoint={self._endpoint!r}, "
            f"safe_window={self._safe_window!r}, credentials=<redacted>, "
            "mtls_identity=<redacted>)"
        )

    def get_headers(self) -> dict[str, str]:
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token.access_token}",
            "jwt_token": token.jwt_token,
        }

    def invalidate(self) -> None:
        with self._lock:
            self._token = None

    def _get_token(self) -> _Token:
        with self._lock:
            now = self._clock()
            if self._token is not None and now < self._token.expires_at:
                return self._token
            token = self._authenticate(now)
            self._token = token
            return token

    def _authenticate(self, now: float) -> _Token:
        basic_source = f"{self._consumer_key}:{self._consumer_secret}".encode("utf-8")
        basic = base64.b64encode(basic_source).decode("ascii")
        try:
            response = self._transport(
                url=self._endpoint,
                method="POST",
                headers={
                    "Authorization": f"Basic {basic}",
                    "role-type": "TERCEIROS",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data="grant_type=client_credentials",
                mtls_identity=self._mtls_identity,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise OAuthSessionError("falha na autenticacao SERPRO") from exc

        if getattr(response, "status_code", None) != 200:
            raise OAuthSessionError("resposta de autenticacao invalida")
        try:
            payload = response.json()
        except Exception as exc:
            raise OAuthSessionError("resposta de autenticacao invalida") from exc
        if not isinstance(payload, dict):
            raise OAuthSessionError("resposta de autenticacao invalida")

        access_token = payload.get("access_token")
        jwt_token = payload.get("jwt_token")
        expires_in = payload.get("expires_in")
        valid = (
            payload.get("token_type") == "Bearer"
            and isinstance(access_token, str)
            and bool(access_token.strip())
            and isinstance(jwt_token, str)
            and bool(jwt_token.strip())
            and isinstance(expires_in, int)
            and not isinstance(expires_in, bool)
            and expires_in > 0
        )
        if not valid:
            raise OAuthSessionError("resposta de autenticacao invalida")

        return _Token(
            access_token=access_token,
            jwt_token=jwt_token,
            expires_at=now + max(0.0, expires_in - self._safe_window),
        )
