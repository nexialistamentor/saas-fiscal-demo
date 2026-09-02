"""Consumo atomico de grants de ofertas avulsas de documentos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CheckoutOfferGrant,
    CheckoutOfferGrantCapability,
    CheckoutOfferGrantConsumption,
    OrdemCheckout,
)


_CAPABILITY = "document.extract"
_UNITS_PER_OPERATION = 1


class CheckoutOfferGrantUsageError(Exception):
    """Rejeicao previsivel do consumo de um checkout offer grant."""


class CheckoutOfferGrantUsage:
    """Consome uma unidade de grant sem finalizar a transacao do chamador."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def consumir(
        self,
        *,
        user_id: int,
        empresa_id: int,
        capability: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> CheckoutOfferGrantConsumption:
        self._validar_entrada(
            user_id=user_id,
            empresa_id=empresa_id,
            capability=capability,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )

        existing = self._consumo_por_idempotency_key(idempotency_key)
        if existing is not None:
            return self._validar_replay(
                existing,
                user_id=user_id,
                empresa_id=empresa_id,
                capability=capability,
                request_fingerprint=request_fingerprint,
            )

        grant = self._selecionar_grant_com_lock(
            user_id=user_id,
            empresa_id=empresa_id,
            capability=capability,
        )

        # A espera pelo row lock pode ter permitido que outra transacao
        # persistisse esta chave. A segunda leitura precede qualquer debito.
        existing = self._consumo_por_idempotency_key(idempotency_key)
        if existing is not None:
            return self._validar_replay(
                existing,
                user_id=user_id,
                empresa_id=empresa_id,
                capability=capability,
                request_fingerprint=request_fingerprint,
            )

        if grant is None:
            raise CheckoutOfferGrantUsageError("nenhum grant elegivel")

        usage_before = grant.usage_consumed
        usage_limit = grant.usage_limit
        if (
            not isinstance(usage_before, int)
            or not isinstance(usage_limit, int)
            or usage_before < 0
            or usage_limit <= 0
            or usage_before >= usage_limit
            or grant.estado != "active"
        ):
            raise CheckoutOfferGrantUsageError(
                "inconsistencia de saldo ou estado do grant"
            )

        usage_after = usage_before + _UNITS_PER_OPERATION
        if usage_after > usage_limit:
            raise CheckoutOfferGrantUsageError("saldo do grant excedido")

        grant.usage_consumed = usage_after
        grant.estado = "exhausted" if usage_after == usage_limit else "active"

        consumption = CheckoutOfferGrantConsumption(
            grant_id=grant.id,
            user_id=user_id,
            empresa_id=empresa_id,
            capability=capability,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            units=_UNITS_PER_OPERATION,
            usage_before=usage_before,
            usage_after=usage_after,
        )
        self._db.add(consumption)
        return consumption

    def _consumo_por_idempotency_key(
        self, idempotency_key: str
    ) -> CheckoutOfferGrantConsumption | None:
        return self._db.scalar(
            select(CheckoutOfferGrantConsumption).where(
                CheckoutOfferGrantConsumption.idempotency_key == idempotency_key
            )
        )

    def _selecionar_grant_com_lock(
        self, *, user_id: int, empresa_id: int, capability: str
    ) -> CheckoutOfferGrant | None:
        statement = (
            select(CheckoutOfferGrant)
            .join(
                OrdemCheckout,
                OrdemCheckout.id == CheckoutOfferGrant.ordem_id,
            )
            .join(
                CheckoutOfferGrantCapability,
                CheckoutOfferGrantCapability.grant_id == CheckoutOfferGrant.id,
            )
            .where(
                OrdemCheckout.estado == "paid",
                OrdemCheckout.user_id == user_id,
                OrdemCheckout.empresa_id == empresa_id,
                CheckoutOfferGrant.estado == "active",
                CheckoutOfferGrantCapability.codigo == capability,
                CheckoutOfferGrant.usage_consumed
                < CheckoutOfferGrant.usage_limit,
            )
            .order_by(
                CheckoutOfferGrant.created_at.asc(),
                CheckoutOfferGrant.id.asc(),
            )
            .limit(1)
            .with_for_update(of=CheckoutOfferGrant)
            .execution_options(populate_existing=True)
        )
        return self._db.scalar(statement)

    @staticmethod
    def _validar_replay(
        consumption: CheckoutOfferGrantConsumption,
        *,
        user_id: int,
        empresa_id: int,
        capability: str,
        request_fingerprint: str,
    ) -> CheckoutOfferGrantConsumption:
        same_operation = (
            consumption.user_id == user_id
            and consumption.empresa_id == empresa_id
            and consumption.capability == capability
            and consumption.request_fingerprint == request_fingerprint
            and consumption.units == _UNITS_PER_OPERATION
            and consumption.usage_before >= 0
            and consumption.usage_after
            == consumption.usage_before + _UNITS_PER_OPERATION
        )
        if not same_operation:
            raise CheckoutOfferGrantUsageError("replay idempotente divergente")
        return consumption

    @staticmethod
    def _validar_entrada(
        *,
        user_id: int,
        empresa_id: int,
        capability: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> None:
        if capability != _CAPABILITY:
            raise CheckoutOfferGrantUsageError("capability invalida")
        if (
            not isinstance(user_id, int)
            or isinstance(user_id, bool)
            or user_id <= 0
            or not isinstance(empresa_id, int)
            or isinstance(empresa_id, bool)
            or empresa_id <= 0
        ):
            raise CheckoutOfferGrantUsageError("escopo invalido")
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key
            or len(idempotency_key) > 255
            or not isinstance(request_fingerprint, str)
            or not request_fingerprint
            or len(request_fingerprint) > 255
        ):
            raise CheckoutOfferGrantUsageError("dados idempotentes invalidos")


__all__ = ["CheckoutOfferGrantUsage", "CheckoutOfferGrantUsageError"]
