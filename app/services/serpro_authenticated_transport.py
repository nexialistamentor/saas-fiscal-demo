"""Authenticated, token-rotating transport composition for SERPRO calls."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class AuthenticatedTransportError(RuntimeError):
    """Closed, sanitized failure exposed by the authenticated transport."""


class SerproAuthenticatedTransport:
    """Add current session credentials and retry one unauthenticated request."""

    def __init__(self, session: Any, downstream: Callable[..., Any]) -> None:
        self._session = session
        self._downstream = downstream

    def __repr__(self) -> str:
        return f"{type(self).__name__}(session=<redacted>, downstream=<redacted>)"

    def __call__(
        self,
        *,
        url: Any,
        json: Any,
        headers: Mapping[str, str],
        timeout: Any,
    ) -> Any:
        base_headers = self._validated_caller_headers(headers)
        response = self._send(
            url=url,
            json=json,
            headers=self._authenticated_headers(base_headers),
            timeout=timeout,
        )
        if getattr(response, "status_code", None) != 401:
            return response

        try:
            self._session.invalidate()
        except Exception:
            raise AuthenticatedTransportError("falha no transporte autenticado") from None
        return self._send(
            url=url,
            json=json,
            headers=self._authenticated_headers(base_headers),
            timeout=timeout,
        )

    @staticmethod
    def _validated_caller_headers(
        headers: Mapping[str, str],
    ) -> dict[str, str]:
        if not isinstance(headers, Mapping):
            raise AuthenticatedTransportError("headers da requisicao invalidos")

        normalized: dict[str, str] = {}
        copied: dict[str, str] = {}
        for key, value in headers.items():
            if (
                not isinstance(key, str)
                or not isinstance(value, str)
                or not key.strip()
                or "\r" in key
                or "\n" in key
                or "\r" in value
                or "\n" in value
            ):
                raise AuthenticatedTransportError("headers da requisicao invalidos")
            lowered = key.lower()
            if lowered in normalized:
                raise AuthenticatedTransportError("headers da requisicao invalidos")
            normalized[lowered] = key
            if lowered in {"authorization", "jwt_token"}:
                raise AuthenticatedTransportError("headers da requisicao invalidos")
            if lowered == "content-type":
                if value != "application/json":
                    raise AuthenticatedTransportError("headers da requisicao invalidos")
                continue
            copied[key] = value
        copied["Content-Type"] = "application/json"
        return copied

    def _authenticated_headers(self, base: Mapping[str, str]) -> dict[str, str]:
        try:
            session_headers = self._session.get_headers()
        except Exception:
            raise AuthenticatedTransportError("falha no transporte autenticado") from None

        if not isinstance(session_headers, Mapping):
            raise AuthenticatedTransportError("credenciais de sessao invalidas")
        keys = list(session_headers)
        if any(not isinstance(key, str) for key in keys):
            raise AuthenticatedTransportError("credenciais de sessao invalidas")
        lowered = [key.lower() for key in keys]
        if len(lowered) != len(set(lowered)) or set(keys) != {
            "Authorization",
            "jwt_token",
        }:
            raise AuthenticatedTransportError("credenciais de sessao invalidas")

        authorization = session_headers["Authorization"]
        jwt_token = session_headers["jwt_token"]
        if (
            not isinstance(authorization, str)
            or not isinstance(jwt_token, str)
            or not authorization.startswith("Bearer ")
            or not authorization.removeprefix("Bearer ")
            or any(character.isspace() for character in authorization.removeprefix("Bearer "))
            or not jwt_token
            or any(character.isspace() for character in jwt_token)
        ):
            raise AuthenticatedTransportError("credenciais de sessao invalidas")

        combined = dict(base)
        combined["Authorization"] = authorization
        combined["jwt_token"] = jwt_token
        return combined

    def _send(self, *, url: Any, json: Any, headers: dict[str, str], timeout: Any) -> Any:
        try:
            return self._downstream(
                url=url,
                json=json,
                headers=headers,
                timeout=timeout,
            )
        except Exception:
            raise AuthenticatedTransportError("falha no transporte autenticado") from None
