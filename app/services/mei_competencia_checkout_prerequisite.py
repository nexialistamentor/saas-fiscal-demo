"""Prerequisite soberano para checkout de competencia MEI."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    MeiCompetenciaCheckoutIntent as _IntentModel,
)


_CAPABILITY = "mei.das"
_PUBLIC_ERROR = "prerequisito de checkout MEI recusado"


class MeiCompetenciaCheckoutPrerequisiteError(Exception):
    """Erro publico deliberadamente opaco."""


class MeiCompetenciaCheckoutPrerequisite:
    def __init__(self, db):
        self._db = db

    def require(
        self,
        *,
        authenticated_user_id,
        empresa_id,
        offer_code,
        idempotency_key,
        capabilities=None,
    ):
        try:
            self._validate_capabilities(capabilities)

            if _CAPABILITY not in capabilities:
                return

            self._validate_identity(
                authenticated_user_id=authenticated_user_id,
                empresa_id=empresa_id,
                offer_code=offer_code,
                idempotency_key=idempotency_key,
            )

            intent = self._db.scalar(
                select(_IntentModel).where(
                    _IntentModel.checkout_idempotency_key
                    == idempotency_key,
                    _IntentModel.user_id == authenticated_user_id,
                    _IntentModel.empresa_id == empresa_id,
                    _IntentModel.offer_code == offer_code,
                    _IntentModel.capability == _CAPABILITY,
                )
            )

            if intent is None:
                self._fail()

        except MeiCompetenciaCheckoutPrerequisiteError:
            raise
        except SQLAlchemyError:
            raise MeiCompetenciaCheckoutPrerequisiteError(
                _PUBLIC_ERROR
            ) from None

    @classmethod
    def _validate_capabilities(cls, capabilities):
        if type(capabilities) is not tuple:
            cls._fail()

        if any(
            type(capability) is not str or not capability
            for capability in capabilities
        ):
            cls._fail()

    @classmethod
    def _validate_identity(
        cls,
        *,
        authenticated_user_id,
        empresa_id,
        offer_code,
        idempotency_key,
    ):
        if (
            type(authenticated_user_id) is not int
            or authenticated_user_id <= 0
            or type(empresa_id) is not int
            or empresa_id <= 0
            or type(offer_code) is not str
            or not offer_code
            or type(idempotency_key) is not str
            or not 1 <= len(idempotency_key) <= 255
            or any(
                not 0x21 <= ord(character) <= 0x7E
                for character in idempotency_key
            )
        ):
            cls._fail()

    @staticmethod
    def _fail():
        raise MeiCompetenciaCheckoutPrerequisiteError(_PUBLIC_ERROR)


__all__ = [
    "MeiCompetenciaCheckoutPrerequisite",
    "MeiCompetenciaCheckoutPrerequisiteError",
]
