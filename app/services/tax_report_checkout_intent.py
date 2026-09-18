"""Persistencia da intencao duravel do checkout de relatorio fiscal."""

from dataclasses import dataclass
from datetime import datetime
import hmac
import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    RelatorioAnalise as _RelatorioAnalise,
    TaxReportCheckoutIntent as _IntentModel,
)
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    verificar_resultado_persistido,
)


_OFFER_CODE = "tax-report-one-time-company"
_FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}")


class TaxReportCheckoutIntentError(Exception):
    """Falha opaca ao persistir ou recuperar a intencao de checkout."""


@dataclass(frozen=True)
class TaxReportCheckoutIntentResult:
    intent_id: int
    checkout_idempotency_key: str
    user_id: int
    empresa_id: int
    relatorio_analise_id: int
    offer_code: str
    request_fingerprint: str
    created_at: datetime


class TaxReportCheckoutIntent:
    def __init__(self, db: Session):
        self._db = db

    def persist(
        self,
        *,
        user_id,
        empresa_id,
        relatorio_id,
        offer_code,
        checkout_idempotency_key,
        request_fingerprint,
    ):
        self._validate_input(
            user_id=user_id,
            empresa_id=empresa_id,
            relatorio_id=relatorio_id,
            offer_code=offer_code,
            checkout_idempotency_key=checkout_idempotency_key,
            request_fingerprint=request_fingerprint,
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
                    or existing.relatorio_analise_id != relatorio_id
                    or existing.offer_code != offer_code
                    or existing.request_fingerprint != request_fingerprint
                ):
                    raise TaxReportCheckoutIntentError(
                        "intencao de checkout divergente"
                    )
                return self._project(existing)

            relatorio = self._db.get(_RelatorioAnalise, relatorio_id)
            if (
                relatorio is None
                or relatorio.id != relatorio_id
                or relatorio.user_id != user_id
                or relatorio.empresa_id != empresa_id
                or relatorio.status != "ok"
                or not self._valid_fingerprint(relatorio.fingerprint)
            ):
                raise TaxReportCheckoutIntentError(
                    "relatorio inexistente ou inelegivel"
                )

            try:
                verificar_resultado_persistido(relatorio)
            except ResultadoProvenanceError as exc:
                raise TaxReportCheckoutIntentError(
                    "resultado persistido invalido"
                ) from exc

            if not hmac.compare_digest(
                relatorio.fingerprint, request_fingerprint
            ):
                raise TaxReportCheckoutIntentError(
                    "fingerprint solicitado divergente"
                )

            intent = _IntentModel(
                checkout_idempotency_key=checkout_idempotency_key,
                user_id=user_id,
                empresa_id=empresa_id,
                relatorio_analise_id=relatorio_id,
                offer_code=offer_code,
                request_fingerprint=request_fingerprint,
            )
            self._db.add(intent)
            self._db.flush()
            if type(intent.id) is not int or intent.id <= 0 or intent.created_at is None:
                raise TaxReportCheckoutIntentError(
                    "intencao persistida invalida"
                )
            return self._project(intent)
        except SQLAlchemyError as exc:
            raise TaxReportCheckoutIntentError(
                "falha ao persistir intencao de checkout"
            ) from exc

    @staticmethod
    def _valid_fingerprint(value):
        return type(value) is str and _FINGERPRINT_PATTERN.fullmatch(value) is not None

    @classmethod
    def _validate_input(
        cls,
        *,
        user_id,
        empresa_id,
        relatorio_id,
        offer_code,
        checkout_idempotency_key,
        request_fingerprint,
    ):
        if any(
            type(value) is not int or value <= 0
            for value in (user_id, empresa_id, relatorio_id)
        ):
            raise TaxReportCheckoutIntentError("identificadores invalidos")
        if offer_code != _OFFER_CODE or type(offer_code) is not str:
            raise TaxReportCheckoutIntentError("offer_code invalido")
        if (
            type(checkout_idempotency_key) is not str
            or not 1 <= len(checkout_idempotency_key) <= 255
            or any(
                not 0x21 <= ord(char) <= 0x7E
                for char in checkout_idempotency_key
            )
        ):
            raise TaxReportCheckoutIntentError(
                "checkout_idempotency_key invalida"
            )
        if not cls._valid_fingerprint(request_fingerprint):
            raise TaxReportCheckoutIntentError("request_fingerprint invalido")

    @staticmethod
    def _project(intent):
        return TaxReportCheckoutIntentResult(
            intent_id=intent.id,
            checkout_idempotency_key=intent.checkout_idempotency_key,
            user_id=intent.user_id,
            empresa_id=intent.empresa_id,
            relatorio_analise_id=intent.relatorio_analise_id,
            offer_code=intent.offer_code,
            request_fingerprint=intent.request_fingerprint,
            created_at=intent.created_at,
        )


__all__ = [
    "TaxReportCheckoutIntent",
    "TaxReportCheckoutIntentError",
    "TaxReportCheckoutIntentResult",
]
