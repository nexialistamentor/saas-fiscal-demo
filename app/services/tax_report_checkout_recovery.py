from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    CheckoutOfferGrant,
    CheckoutOfferGrantCapability,
    OrdemCheckout,
    OrdemCheckoutCapability,
    TaxReportCheckoutIntent,
)


_OFFER_CODE = "tax-report-one-time-company"
_CAPABILITY = "tax.report"


class TaxReportCheckoutRecoveryError(Exception):
    pass


class TaxReportCheckoutRecoveryNotFoundError(
    TaxReportCheckoutRecoveryError
):
    pass


class TaxReportCheckoutRecoveryConflictError(
    TaxReportCheckoutRecoveryError
):
    pass


class TaxReportCheckoutRecoveryStorageError(
    TaxReportCheckoutRecoveryError
):
    pass


@dataclass(frozen=True)
class TaxReportCheckoutRecoveryResult:
    estado: str
    checkout_idempotency_key: str
    relatorio_id: int
    request_fingerprint: str
    checkout_url: str | None


def _is_positive_int(value):
    return type(value) is int and value > 0


def _is_visible_ascii(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 255
        and all(0x21 <= ord(character) <= 0x7E for character in value)
    )


def _is_https_url(value):
    if not isinstance(value, str) or not value or "\r" in value or "\n" in value:
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        return False


class TaxReportCheckoutRecovery:
    def __init__(self, db):
        self._db = db

    def resolve(
        self,
        *,
        user_id,
        empresa_id,
    ):
        if not _is_positive_int(user_id) or not _is_positive_int(empresa_id):
            raise TaxReportCheckoutRecoveryConflictError()

        try:
            selected = (
                self._db.query(TaxReportCheckoutIntent, OrdemCheckout)
                .join(
                    OrdemCheckout,
                    TaxReportCheckoutIntent.checkout_idempotency_key
                    == OrdemCheckout.idempotency_key,
                )
                .filter(
                    TaxReportCheckoutIntent.user_id == user_id,
                    TaxReportCheckoutIntent.empresa_id == empresa_id,
                    TaxReportCheckoutIntent.offer_code == _OFFER_CODE,
                    OrdemCheckout.user_id == user_id,
                    OrdemCheckout.empresa_id == empresa_id,
                    OrdemCheckout.offer_code == _OFFER_CODE,
                    OrdemCheckout.estado.in_(("paid", "pending")),
                )
                .order_by(
                    OrdemCheckout.criado_em.desc(),
                    OrdemCheckout.id.desc(),
                )
                .limit(1)
                .first()
            )

            if selected is None:
                raise TaxReportCheckoutRecoveryNotFoundError()

            intent, ordem = selected
            self._validate_identity(intent, ordem, user_id, empresa_id)

            order_capabilities = (
                self._db.query(OrdemCheckoutCapability)
                .filter(
                    OrdemCheckoutCapability.ordem_id == ordem.id,
                    OrdemCheckoutCapability.codigo == _CAPABILITY,
                )
                .all()
            )
            if len(order_capabilities) != 1:
                raise TaxReportCheckoutRecoveryConflictError()

            if ordem.estado == "pending":
                checkout_url = self._validate_pending(ordem)
            else:
                self._validate_paid(ordem)
                checkout_url = None

            return TaxReportCheckoutRecoveryResult(
                estado=ordem.estado,
                checkout_idempotency_key=intent.checkout_idempotency_key,
                relatorio_id=intent.relatorio_analise_id,
                request_fingerprint=intent.request_fingerprint,
                checkout_url=checkout_url,
            )
        except SQLAlchemyError:
            raise TaxReportCheckoutRecoveryStorageError() from None

    def _validate_identity(self, intent, ordem, user_id, empresa_id):
        if (
            not _is_visible_ascii(intent.checkout_idempotency_key)
            or intent.checkout_idempotency_key != ordem.idempotency_key
            or not _is_positive_int(intent.relatorio_analise_id)
            or not isinstance(intent.request_fingerprint, str)
            or len(intent.request_fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in intent.request_fingerprint)
            or intent.user_id != user_id
            or intent.empresa_id != empresa_id
            or intent.offer_code != _OFFER_CODE
            or not _is_positive_int(ordem.id)
            or not _is_positive_int(ordem.offer_id)
            or not _is_positive_int(ordem.contract_version)
            or ordem.plano_id is not None
            or ordem.vertical != "tax"
            or ordem.commercial_model != "one_time"
            or ordem.subject_type != "company"
            or ordem.subject_id != empresa_id
            or ordem.empresa_id != empresa_id
            or ordem.user_id != user_id
            or ordem.offer_code != _OFFER_CODE
            or ordem.estado not in {"paid", "pending"}
        ):
            raise TaxReportCheckoutRecoveryConflictError()

    def _validate_pending(self, ordem):
        grants = (
            self._db.query(CheckoutOfferGrant)
            .filter(CheckoutOfferGrant.ordem_id == ordem.id)
            .all()
        )
        if ordem.payment_id is not None or grants:
            raise TaxReportCheckoutRecoveryConflictError()

        has_provider_order_id = ordem.provider_order_id is not None
        has_checkout_url = ordem.checkout_url is not None
        if has_provider_order_id != has_checkout_url:
            raise TaxReportCheckoutRecoveryConflictError()
        if has_provider_order_id and (
            not isinstance(ordem.provider_order_id, str)
            or not ordem.provider_order_id.strip()
            or not _is_https_url(ordem.checkout_url)
        ):
            raise TaxReportCheckoutRecoveryConflictError()
        return ordem.checkout_url

    def _validate_paid(self, ordem):
        if (
            not isinstance(ordem.payment_id, str)
            or not ordem.payment_id.strip()
            or not isinstance(ordem.provider_order_id, str)
            or not ordem.provider_order_id.strip()
            or not _is_https_url(ordem.checkout_url)
        ):
            raise TaxReportCheckoutRecoveryConflictError()

        grants = (
            self._db.query(CheckoutOfferGrant)
            .join(
                CheckoutOfferGrantCapability,
                CheckoutOfferGrantCapability.grant_id == CheckoutOfferGrant.id,
            )
            .filter(
                CheckoutOfferGrant.ordem_id == ordem.id,
                CheckoutOfferGrantCapability.codigo == _CAPABILITY,
            )
            .all()
        )
        if len(grants) != 1:
            raise TaxReportCheckoutRecoveryConflictError()

        grant = grants[0]
        if (
            grant.ordem_id != ordem.id
            or not _is_positive_int(grant.usage_limit)
            or type(grant.usage_consumed) is not int
            or grant.usage_consumed < 0
            or grant.usage_consumed > grant.usage_limit
            or (
                grant.estado == "active"
                and grant.usage_consumed >= grant.usage_limit
            )
            or (
                grant.estado == "exhausted"
                and grant.usage_consumed != grant.usage_limit
            )
            or grant.estado not in {"active", "exhausted"}
        ):
            raise TaxReportCheckoutRecoveryConflictError()
