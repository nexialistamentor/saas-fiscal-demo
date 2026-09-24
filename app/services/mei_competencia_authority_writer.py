"""Materializacao fail-closed da autoridade economica por competencia MEI."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models


_CAPABILITY = "mei.das"
_PUBLIC_ERROR = "autoridade economica MEI recusada"


class MeiCompetenciaAuthorityWriterError(Exception):
    """Erro publico deliberadamente opaco."""


@dataclass(frozen=True)
class MeiCompetenciaAuthorityWriterResult:
    binding_id: int
    ordem_id: int
    empresa_id: int
    competencia: str
    capability: str
    created_at: datetime


class MeiCompetenciaAuthorityWriter:
    def __init__(self, db: Session):
        self._db = db

    def materialize(self, ordem_id):
        if type(ordem_id) is not int or ordem_id <= 0:
            self._fail()

        try:
            ordem = self._db.get(models.OrdemCheckout, ordem_id)
            if ordem is None:
                self._fail()

            self._validate_order(ordem)

            intent = self._db.scalar(
                select(models.MeiCompetenciaCheckoutIntent).where(
                    models.MeiCompetenciaCheckoutIntent.checkout_idempotency_key
                    == ordem.idempotency_key,
                    models.MeiCompetenciaCheckoutIntent.user_id
                    == ordem.user_id,
                    models.MeiCompetenciaCheckoutIntent.empresa_id
                    == ordem.empresa_id,
                    models.MeiCompetenciaCheckoutIntent.offer_code
                    == ordem.offer_code,
                    models.MeiCompetenciaCheckoutIntent.capability
                    == _CAPABILITY,
                )
            )
            if intent is None:
                self._fail()

            self._validate_intent(intent, ordem)
            self._validate_payment(ordem)
            self._validate_not_revoked(ordem)

            existing = tuple(
                self._db.scalars(
                    select(models.MeiCompetenciaAuthorityBinding).where(
                        models.MeiCompetenciaAuthorityBinding.ordem_id
                        == ordem.id
                    )
                ).all()
            )

            if existing:
                if len(existing) != 1:
                    self._fail()

                binding = existing[0]
                if (
                    binding.empresa_id != ordem.empresa_id
                    or binding.competencia != intent.competencia
                    or binding.capability != _CAPABILITY
                ):
                    self._fail()

                return self._project(binding)

            binding = models.MeiCompetenciaAuthorityBinding(
                ordem_id=ordem.id,
                empresa_id=ordem.empresa_id,
                competencia=intent.competencia,
                capability=_CAPABILITY,
            )
            self._db.add(binding)
            self._db.flush()

            if (
                type(binding.id) is not int
                or binding.id <= 0
                or binding.created_at is None
            ):
                self._fail()

            return self._project(binding)

        except MeiCompetenciaAuthorityWriterError:
            raise
        except SQLAlchemyError:
            raise MeiCompetenciaAuthorityWriterError(
                _PUBLIC_ERROR
            ) from None

    @classmethod
    def _validate_order(cls, ordem):
        if (
            ordem.estado != "paid"
            or type(ordem.user_id) is not int
            or ordem.user_id <= 0
            or type(ordem.empresa_id) is not int
            or ordem.empresa_id <= 0
            or ordem.plano_id is not None
            or type(ordem.offer_id) is not int
            or ordem.offer_id <= 0
            or type(ordem.contract_version) is not int
            or ordem.contract_version <= 0
            or type(ordem.offer_code) is not str
            or not ordem.offer_code
            or ordem.vertical != "tax"
            or ordem.subject_type != "company"
            or ordem.subject_id != ordem.empresa_id
            or ordem.moeda != "BRL"
            or ordem.valor is None
            or ordem.valor <= 0
            or type(ordem.idempotency_key) is not str
            or not ordem.idempotency_key
            or type(ordem.payment_id) is not str
            or not ordem.payment_id
        ):
            cls._fail()

        capabilities = tuple(
            capability.codigo for capability in ordem.capabilities
        )
        if _CAPABILITY not in capabilities:
            cls._fail()

    @classmethod
    def _validate_intent(cls, intent, ordem):
        competencia = intent.competencia
        if (
            intent.user_id != ordem.user_id
            or intent.empresa_id != ordem.empresa_id
            or intent.checkout_idempotency_key != ordem.idempotency_key
            or intent.offer_code != ordem.offer_code
            or intent.capability != _CAPABILITY
            or type(competencia) is not str
            or len(competencia) != 6
            or not competencia.isascii()
            or not competencia.isdigit()
            or not 1 <= int(competencia[4:]) <= 12
        ):
            cls._fail()

    def _validate_payment(self, ordem):
        payments = tuple(
            self._db.scalars(
                select(models.Pagamento).where(
                    models.Pagamento.ordem_checkout_id == ordem.id
                )
            ).all()
        )

        if len(payments) != 1:
            self._fail()

        payment = payments[0]
        if (
            payment.user_id != ordem.user_id
            or payment.plano_id is not None
            or payment.status != "approved"
            or payment.valor != ordem.valor
            or payment.confirmado_em is None
            or payment.mp_payment_id != ordem.payment_id
        ):
            self._fail()

    def _validate_not_revoked(self, ordem):
        revoked = self._db.scalar(
            select(models.CheckoutOfferGrant.id)
            .where(
                models.CheckoutOfferGrant.ordem_id == ordem.id,
                models.CheckoutOfferGrant.estado == "revoked",
            )
            .limit(1)
        )
        if revoked is not None:
            self._fail()

    @staticmethod
    def _project(binding):
        return MeiCompetenciaAuthorityWriterResult(
            binding_id=binding.id,
            ordem_id=binding.ordem_id,
            empresa_id=binding.empresa_id,
            competencia=binding.competencia,
            capability=binding.capability,
            created_at=binding.created_at,
        )

    @staticmethod
    def _fail():
        raise MeiCompetenciaAuthorityWriterError(_PUBLIC_ERROR)


__all__ = [
    "MeiCompetenciaAuthorityWriter",
    "MeiCompetenciaAuthorityWriterError",
    "MeiCompetenciaAuthorityWriterResult",
]
