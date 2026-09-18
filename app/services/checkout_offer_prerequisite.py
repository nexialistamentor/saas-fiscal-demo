from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import TaxReportCheckoutIntent as _IntentModel


class CheckoutOfferPrerequisiteError(Exception):
    pass


class CheckoutOfferPrerequisite:
    def __init__(self, db):
        self._db = db

    def require(
        self,
        *,
        authenticated_user_id,
        empresa_id,
        offer_code,
        idempotency_key,
    ):
        if offer_code != "tax-report-one-time-company":
            return

        if (
            type(authenticated_user_id) is not int
            or authenticated_user_id <= 0
            or type(empresa_id) is not int
            or empresa_id <= 0
            or type(offer_code) is not str
            or type(idempotency_key) is not str
            or not 1 <= len(idempotency_key) <= 255
            or any(not 0x21 <= ord(character) <= 0x7E for character in idempotency_key)
        ):
            raise CheckoutOfferPrerequisiteError()

        try:
            intent = self._db.scalar(
                select(_IntentModel).where(
                    _IntentModel.checkout_idempotency_key == idempotency_key,
                    _IntentModel.user_id == authenticated_user_id,
                    _IntentModel.empresa_id == empresa_id,
                    _IntentModel.offer_code == offer_code,
                )
            )
        except SQLAlchemyError:
            raise CheckoutOfferPrerequisiteError() from None

        if intent is None:
            raise CheckoutOfferPrerequisiteError()


__all__ = [
    "CheckoutOfferPrerequisite",
    "CheckoutOfferPrerequisiteError",
]
