"""Leitura fail-closed de uma aquisicao persistida de relatorio fiscal."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hmac
import re

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    CheckoutOfferGrant as Grant,
    CheckoutOfferGrantConsumption as Consumption,
    OrdemCheckout as Order,
    TaxReportAcquisitionBinding as Binding,
)
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    fingerprint_resultado_json,
)


_CAPABILITY = "tax.report"
_SHA256_LOWERCASE = re.compile(r"[0-9a-f]{64}\Z")


class TaxReportAcquisitionReadError(Exception):
    """A aquisicao nao pode ser lida com seguranca."""


@dataclass(frozen=True)
class TaxReportAcquisitionReadResult:
    acquisition_id: int
    relatorio_analise_id: int
    fingerprint: str
    resultado_json_snapshot: dict
    created_at: datetime


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _valid_fingerprint(value: object) -> bool:
    return isinstance(value, str) and _SHA256_LOWERCASE.fullmatch(value) is not None


class TaxReportAcquisitionReader:
    def __init__(self, db: Session):
        self._db = db

    def _get(self, model: type, identity: int):
        try:
            return self._db.get(model, identity)
        except SQLAlchemyError as exc:
            raise TaxReportAcquisitionReadError("falha ao ler aquisicao") from exc

    def read(
        self,
        *,
        user_id: int,
        empresa_id: int,
        acquisition_id: int,
    ):
        with self._db.no_autoflush:
            return self._read(
                user_id=user_id,
                empresa_id=empresa_id,
                acquisition_id=acquisition_id,
            )

    def _read(
        self,
        *,
        user_id: int,
        empresa_id: int,
        acquisition_id: int,
    ):
        if not all(_positive_int(value) for value in (user_id, empresa_id, acquisition_id)):
            raise TaxReportAcquisitionReadError("identificador invalido")

        binding = self._get(Binding, acquisition_id)
        if (
            binding is None
            or not _positive_int(binding.id)
            or binding.id != acquisition_id
            or not _positive_int(binding.consumption_id)
            or not _positive_int(binding.relatorio_analise_id)
            or not _valid_fingerprint(binding.fingerprint)
            or not isinstance(binding.resultado_json_snapshot, dict)
            or binding.created_at is None
        ):
            raise TaxReportAcquisitionReadError("binding invalido")

        try:
            calculated_fingerprint = fingerprint_resultado_json(
                binding.resultado_json_snapshot
            )
        except ResultadoProvenanceError as exc:
            raise TaxReportAcquisitionReadError("snapshot invalido") from exc
        if not hmac.compare_digest(calculated_fingerprint, binding.fingerprint):
            raise TaxReportAcquisitionReadError("fingerprint divergente")

        consumption = self._get(Consumption, binding.consumption_id)
        if (
            consumption is None
            or consumption.id != binding.consumption_id
            or not _positive_int(consumption.grant_id)
            or consumption.user_id != user_id
            or consumption.empresa_id != empresa_id
            or consumption.capability != _CAPABILITY
            or consumption.units != 1
            or not _valid_fingerprint(consumption.request_fingerprint)
            or not hmac.compare_digest(
                consumption.request_fingerprint, binding.fingerprint
            )
        ):
            raise TaxReportAcquisitionReadError("consumption invalido")

        grant = self._get(Grant, consumption.grant_id)
        if (
            grant is None
            or grant.id != consumption.grant_id
            or not _positive_int(grant.ordem_id)
            or not _positive_int(grant.usage_limit)
            or type(grant.usage_consumed) is not int
            or grant.usage_consumed < 0
            or grant.usage_consumed > grant.usage_limit
        ):
            raise TaxReportAcquisitionReadError("grant invalido")

        active = grant.estado == "active" and grant.usage_consumed < grant.usage_limit
        exhausted = (
            grant.estado == "exhausted"
            and grant.usage_consumed == grant.usage_limit
        )
        if not (active or exhausted):
            raise TaxReportAcquisitionReadError("estado do grant invalido")

        order = self._get(Order, grant.ordem_id)
        if (
            order is None
            or order.id != grant.ordem_id
            or order.estado != "paid"
            or order.user_id != user_id
            or order.empresa_id != empresa_id
        ):
            raise TaxReportAcquisitionReadError("ordem invalida")

        return TaxReportAcquisitionReadResult(
            acquisition_id=binding.id,
            relatorio_analise_id=binding.relatorio_analise_id,
            fingerprint=binding.fingerprint,
            resultado_json_snapshot=deepcopy(binding.resultado_json_snapshot),
            created_at=binding.created_at,
        )
