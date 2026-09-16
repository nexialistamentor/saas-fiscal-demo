"""Aquisicao canonica de snapshots persistidos para ``tax.report``."""

from copy import deepcopy
import hmac
import string

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from app.models import (
    CheckoutOfferGrant,
    CheckoutOfferGrantCapability,
    CheckoutOfferGrantConsumption,
    OrdemCheckout,
    RelatorioAnalise,
    TaxReportAcquisitionBinding,
)
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    fingerprint_resultado_json,
    verificar_resultado_persistido,
)


_CAPABILITY = "tax.report"
_UNITS = 1


class TaxReportAcquisitionError(Exception):
    """Inconsistencia previsivel durante uma aquisicao de relatorio fiscal."""


class TaxReportAcquisition:
    def __init__(self, db: Session) -> None:
        self._db = db

    def acquire(
        self,
        *,
        user_id: int,
        empresa_id: int,
        relatorio_id: int,
        idempotency_key: str,
        request_fingerprint: str,
    ):
        self._validar_entrada(
            user_id=user_id,
            empresa_id=empresa_id,
            relatorio_id=relatorio_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )

        existing = self._consumo_por_idempotency_key(idempotency_key)
        if existing is not None:
            return self._validar_replay(
                existing, user_id=user_id, empresa_id=empresa_id,
                relatorio_id=relatorio_id,
                request_fingerprint=request_fingerprint,
            )

        relatorio = self._db.get(RelatorioAnalise, relatorio_id)
        if (
            relatorio is None
            or relatorio.user_id != user_id
            or relatorio.empresa_id != empresa_id
            or relatorio.status != "ok"
        ):
            raise TaxReportAcquisitionError("relatorio inexistente ou inelegivel")
        try:
            verificar_resultado_persistido(relatorio)
        except ResultadoProvenanceError as exc:
            raise TaxReportAcquisitionError("resultado persistido invalido") from exc
        if not hmac.compare_digest(relatorio.fingerprint, request_fingerprint):
            raise TaxReportAcquisitionError("fingerprint solicitado divergente")
        snapshot = deepcopy(relatorio.resultado_json)

        grant = self._selecionar_grant_com_lock(
            user_id=user_id, empresa_id=empresa_id
        )
        existing = self._consumo_por_idempotency_key(idempotency_key)
        if existing is not None:
            return self._validar_replay(
                existing, user_id=user_id, empresa_id=empresa_id,
                relatorio_id=relatorio_id,
                request_fingerprint=request_fingerprint,
            )
        if grant is None:
            raise TaxReportAcquisitionError("nenhum grant elegivel")

        usage_before = grant.usage_consumed
        usage_limit = grant.usage_limit
        if (
            not isinstance(usage_before, int) or isinstance(usage_before, bool)
            or not isinstance(usage_limit, int) or isinstance(usage_limit, bool)
            or usage_before < 0 or usage_limit <= 0
            or usage_before >= usage_limit or grant.estado != "active"
        ):
            raise TaxReportAcquisitionError("saldo ou estado do grant inconsistente")
        usage_after = usage_before + _UNITS
        grant.usage_consumed = usage_after
        grant.estado = "exhausted" if usage_after == usage_limit else "active"

        consumption = CheckoutOfferGrantConsumption(
            grant_id=grant.id, user_id=user_id, empresa_id=empresa_id,
            capability=_CAPABILITY, idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint, units=_UNITS,
            usage_before=usage_before, usage_after=usage_after,
        )
        self._db.add(consumption)
        self._db.flush()
        binding = TaxReportAcquisitionBinding(
            consumption_id=consumption.id,
            relatorio_analise_id=relatorio.id,
            fingerprint=request_fingerprint,
            resultado_json_snapshot=snapshot,
        )
        self._db.add(binding)
        return binding

    def _consumo_por_idempotency_key(self, key):
        return self._db.scalar(
            select(CheckoutOfferGrantConsumption).where(
                CheckoutOfferGrantConsumption.idempotency_key == key
            )
        )

    def _selecionar_grant_com_lock(self, *, user_id: int, empresa_id: int):
        statement = (
            select(CheckoutOfferGrant)
            .join(OrdemCheckout, OrdemCheckout.id == CheckoutOfferGrant.ordem_id)
            .join(
                CheckoutOfferGrantCapability,
                CheckoutOfferGrantCapability.grant_id == CheckoutOfferGrant.id,
            )
            .where(
                OrdemCheckout.estado == "paid",
                OrdemCheckout.user_id == user_id,
                OrdemCheckout.empresa_id == empresa_id,
                CheckoutOfferGrant.estado == "active",
                CheckoutOfferGrantCapability.codigo == _CAPABILITY,
                CheckoutOfferGrant.usage_consumed < CheckoutOfferGrant.usage_limit,
            )
            .order_by(
                CheckoutOfferGrant.created_at.asc(), CheckoutOfferGrant.id.asc()
            )
            .limit(1)
            .with_for_update(of=CheckoutOfferGrant)
            .execution_options(populate_existing=True)
        )
        return self._db.scalar(statement)

    def _validar_replay(
        self, consumption, *, user_id, empresa_id, relatorio_id,
        request_fingerprint,
    ):
        if (
            consumption.capability != _CAPABILITY
            or consumption.user_id != user_id
            or consumption.empresa_id != empresa_id
            or consumption.request_fingerprint != request_fingerprint
            or consumption.units != _UNITS
        ):
            raise TaxReportAcquisitionError("replay idempotente divergente")
        try:
            binding = self._db.scalars(
                select(TaxReportAcquisitionBinding).where(
                    TaxReportAcquisitionBinding.consumption_id == consumption.id
                )
            ).one()
        except (NoResultFound, MultipleResultsFound) as exc:
            raise TaxReportAcquisitionError("binding idempotente ausente ou ambiguo") from exc
        if (
            binding.relatorio_analise_id != relatorio_id
            or binding.fingerprint != request_fingerprint
        ):
            raise TaxReportAcquisitionError("binding idempotente divergente")
        try:
            snapshot_fingerprint = fingerprint_resultado_json(
                binding.resultado_json_snapshot
            )
        except ResultadoProvenanceError as exc:
            raise TaxReportAcquisitionError("snapshot adquirido invalido") from exc
        if not hmac.compare_digest(snapshot_fingerprint, binding.fingerprint):
            raise TaxReportAcquisitionError("snapshot adquirido adulterado")
        return binding

    @staticmethod
    def _validar_entrada(
        *, user_id, empresa_id, relatorio_id, idempotency_key,
        request_fingerprint,
    ):
        identifiers = (user_id, empresa_id, relatorio_id)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in identifiers
        ):
            raise TaxReportAcquisitionError("identificadores invalidos")
        if (
            not isinstance(idempotency_key, str) or not idempotency_key
            or len(idempotency_key) > 255
        ):
            raise TaxReportAcquisitionError("idempotency_key invalida")
        if (
            not isinstance(request_fingerprint, str)
            or len(request_fingerprint) != 64
            or request_fingerprint != request_fingerprint.lower()
            or any(char not in string.hexdigits.lower() for char in request_fingerprint)
        ):
            raise TaxReportAcquisitionError("request_fingerprint invalido")


__all__ = ["TaxReportAcquisition", "TaxReportAcquisitionError"]
