"""Minimal, transport-agnostic adapter for SERPRO PGMEI trial calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping


_SUPPORTED_SERVICES = frozenset({"GERARDASPDF21", "GERARDASCODBARRA22"})


class PgmeiClientError(RuntimeError):
    """Closed, deliberately sanitized failure exposed by the adapter."""


@dataclass(frozen=True)
class PgmeiResult:
    status: int
    messages: Any
    data: Any
    raw_envelope: Mapping[str, Any]


class SerproPgmeiClient:
    """Build and validate the narrow PGMEI 1.0 trial request contract."""

    def __init__(
        self,
        *,
        endpoint: str,
        authentication: Mapping[str, str],
        timeout: float,
        transport: Callable[..., Any],
        contratante: str,
    ) -> None:
        self._endpoint = endpoint
        self._authentication = dict(authentication)
        self._timeout = timeout
        self._transport = transport
        self._contratante = contratante

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(endpoint={self._endpoint!r}, "
            f"timeout={self._timeout!r}, contratante={self._contratante!r}, "
            "authentication=<redacted>)"
        )

    def request(
        self,
        service: str,
        contribuinte: str,
        periodo_apuracao: str,
    ) -> PgmeiResult:
        if service not in _SUPPORTED_SERVICES:
            raise PgmeiClientError("servico nao suportado")
        if not self._valid_period(periodo_apuracao):
            raise PgmeiClientError("periodo_apuracao invalido")
        if not isinstance(contribuinte, str) or not contribuinte:
            raise PgmeiClientError("contribuinte invalido")

        payload = {
            "contratante": {"numero": self._contratante, "tipo": 2},
            "autorPedidoDados": {"numero": self._contratante, "tipo": 2},
            "contribuinte": {"numero": contribuinte, "tipo": 2},
            "pedidoDados": {
                "idSistema": "PGMEI",
                "idServico": service,
                "versaoSistema": "1.0",
                "dados": json.dumps(
                    {"periodoApuracao": periodo_apuracao}, separators=(",", ":")
                ),
            },
        }

        try:
            response = self._transport(
                url=self._endpoint,
                json=payload,
                headers=dict(self._authentication),
                timeout=self._timeout,
            )
        except Exception as exc:
            raise PgmeiClientError("falha de transporte") from exc

        if getattr(response, "status_code", None) != 200:
            raise PgmeiClientError("http status invalido")
        try:
            envelope = response.json()
        except Exception as exc:
            raise PgmeiClientError("json invalido") from exc
        if not isinstance(envelope, dict):
            raise PgmeiClientError("json invalido")
        if envelope.get("status") != 200:
            raise PgmeiClientError("status interno invalido")
        if envelope.get("sistema") != "PGMEI":
            raise PgmeiClientError("sistema divergente")
        if envelope.get("servico") != service:
            raise PgmeiClientError("servico divergente")
        if "dados" not in envelope or envelope["dados"] is None:
            raise PgmeiClientError("dados ausentes")

        return PgmeiResult(
            status=envelope["status"],
            messages=envelope.get("mensagens"),
            data=envelope["dados"],
            raw_envelope=envelope,
        )

    @staticmethod
    def _valid_period(value: object) -> bool:
        if not isinstance(value, str) or len(value) != 6:
            return False
        year, month = value[:4], value[4:]
        return year.isascii() and month.isascii() and year.isdigit() and month.isdigit() and 1 <= int(month) <= 12
