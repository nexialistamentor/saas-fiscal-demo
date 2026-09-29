"""Persistencia fail-closed da intencao de checkout por competencia MEI."""

from dataclasses import dataclass
from datetime import datetime
import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    CheckoutOffer,
    CheckoutOfferCapability,
    Empresa,
    MeiCompetenciaCheckoutIntent as _IntentModel,
)


_CAPABILITY = "mei.das"
_CANONICAL = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*\Z")
_PUBLIC_ERROR = "intencao de checkout MEI recusada"


class MeiCompetenciaCheckoutIntentError(Exception):
    """Erro de dominio deliberadamente opaco."""


@dataclass(frozen=True)
class MeiCompetenciaCheckoutIntentResult:
    intent_id: int
    checkout_idempotency_key: str
    user_id: int
    empresa_id: int
    competencia: str
    capability: str
    offer_code: str
    created_at: datetime


class MeiCompetenciaCheckoutIntent:
    def __init__(self, db: Session):
        self._db = db

    def persist(
        self,
        *,
        user_id,
        empresa_id,
        competencia,
        offer_code,
        checkout_idempotency_key,
    ):
        self._validate_input(
            user_id=user_id,
            empresa_id=empresa_id,
            competencia=competencia,
            offer_code=offer_code,
            checkout_idempotency_key=checkout_idempotency_key,
        )

        try:
            existing = self._db.scalar(
                select(_IntentModel).where(
                    _IntentModel.checkout_idempotency_key
                    == checkout_idempotency_key
                )
            )

            if existing is not None:
                if (
                    existing.user_id != user_id
                    or existing.empresa_id != empresa_id
                    or existing.competencia != competencia
                    or existing.capability != _CAPABILITY
                    or existing.offer_code != offer_code
                ):
                    self._fail()

                return self._project(existing)

            empresa = self._db.get(Empresa, empresa_id)
            if (
                empresa is None
                or empresa.user_id != user_id
                or empresa.status_empresa != "ativa"
                or empresa.regime_tributario != "mei"
            ):
                self._fail()

            oferta = self._db.scalar(
                select(CheckoutOffer)
                .join(
                    CheckoutOfferCapability,
                    CheckoutOfferCapability.offer_id == CheckoutOffer.id,
                )
                .where(
                    CheckoutOffer.codigo == offer_code,
                    CheckoutOffer.estado == "published",
                    CheckoutOffer.vertical == "tax",
                    CheckoutOffer.subject_type == "company",
                    CheckoutOffer.commercial_model.in_(("monthly", "one_time")),
                    CheckoutOfferCapability.codigo == _CAPABILITY,
                )
                .limit(1)
            )

            if oferta is None:
                self._fail()

            intent = _IntentModel(
                checkout_idempotency_key=checkout_idempotency_key,
                user_id=user_id,
                empresa_id=empresa_id,
                competencia=competencia,
                capability=_CAPABILITY,
                offer_code=offer_code,
            )
            self._db.add(intent)
            self._db.flush()

            if (
                type(intent.id) is not int
                or intent.id <= 0
                or intent.created_at is None
            ):
                self._fail()

            return self._project(intent)

        except MeiCompetenciaCheckoutIntentError:
            raise
        except SQLAlchemyError:
            raise MeiCompetenciaCheckoutIntentError(
                _PUBLIC_ERROR
            ) from None

    @classmethod
    def _validate_input(
        cls,
        *,
        user_id,
        empresa_id,
        competencia,
        offer_code,
        checkout_idempotency_key,
    ):
        if (
            type(user_id) is not int
            or user_id <= 0
            or type(empresa_id) is not int
            or empresa_id <= 0
        ):
            cls._fail()

        if (
            type(competencia) is not str
            or len(competencia) != 6
            or not competencia.isascii()
            or not competencia.isdigit()
            or not 1 <= int(competencia[4:]) <= 12
        ):
            cls._fail()

        if (
            type(offer_code) is not str
            or len(offer_code) > 120
            or _CANONICAL.fullmatch(offer_code) is None
            or "--" in offer_code
        ):
            cls._fail()

        if (
            type(checkout_idempotency_key) is not str
            or not 1 <= len(checkout_idempotency_key) <= 255
            or any(
                not 0x21 <= ord(char) <= 0x7E
                for char in checkout_idempotency_key
            )
        ):
            cls._fail()

    @staticmethod
    def _project(intent):
        return MeiCompetenciaCheckoutIntentResult(
            intent_id=intent.id,
            checkout_idempotency_key=intent.checkout_idempotency_key,
            user_id=intent.user_id,
            empresa_id=intent.empresa_id,
            competencia=intent.competencia,
            capability=intent.capability,
            offer_code=intent.offer_code,
            created_at=intent.created_at,
        )

    @staticmethod
    def _fail():
        raise MeiCompetenciaCheckoutIntentError(_PUBLIC_ERROR)


__all__ = [
    "MeiCompetenciaCheckoutIntent",
    "MeiCompetenciaCheckoutIntentError",
    "MeiCompetenciaCheckoutIntentResult",
]
