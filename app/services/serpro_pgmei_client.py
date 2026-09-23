"""Minimal, transport-agnostic adapter for SERPRO PGMEI trial calls."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping


logger = logging.getLogger(__name__)
_LOG_EVENT = "serpro_pgmei_failure"


def _log_failure(stage: str, provider_status_code: int | None = None) -> None:
    if (
        isinstance(provider_status_code, int)
        and not isinstance(provider_status_code, bool)
    ):
        logger.warning(
            "%s stage=%s provider_status=%d",
            _LOG_EVENT,
            stage,
            provider_status_code,
        )
        return
    logger.warning(
        "%s stage=%s provider_status=unknown",
        _LOG_EVENT,
        stage,
    )


_SUPPORTED_SERVICES = frozenset({"GERARDASPDF21", "GERARDASCODBARRA22"})


class PgmeiClientError(RuntimeError):
    """Closed, deliberately sanitized failure exposed by the adapter."""

    def __init__(
        self,
        message: str,
        *,
        provider_status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_status_code = provider_status_code


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
            _log_failure("pgmei_transport")
            raise PgmeiClientError("falha de transporte") from exc

        status_code = getattr(response, "status_code", None)
        if status_code != 200:
            provider_status_code = (
                int(status_code)
                if isinstance(status_code, int) and not isinstance(status_code, bool)
                else None
            )
            _log_failure("pgmei_http", provider_status_code)
            raise PgmeiClientError(
                "http status invalido",
                provider_status_code=provider_status_code,
            )
        try:
            envelope = response.json()
        except Exception as exc:
            _log_failure("pgmei_response_json")
            raise PgmeiClientError("json invalido") from exc
        if not isinstance(envelope, dict):
            _log_failure("pgmei_response_shape")
            raise PgmeiClientError("json invalido")
        if envelope.get("status") != 200:
            _log_failure("pgmei_response_contract")
            raise PgmeiClientError("status interno invalido")
        pedido_dados = envelope.get("pedidoDados")
        if not isinstance(pedido_dados, Mapping):
            _log_failure("pgmei_response_contract")
            raise PgmeiClientError("sistema divergente")
        if pedido_dados.get("idSistema") != "PGMEI":
            _log_failure("pgmei_response_contract")
            raise PgmeiClientError("sistema divergente")
        if pedido_dados.get("idServico") != service:
            _log_failure("pgmei_response_contract")
            raise PgmeiClientError("servico divergente")
        if "dados" not in envelope or envelope["dados"] is None:
            _log_failure("pgmei_response_contract")
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
