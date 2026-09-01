"""Aplicacao do fluxo de checkout one-time baseado em oferta."""

from decimal import Decimal as _Decimal
import re as _re
from urllib.parse import urlsplit as _urlsplit

from app.services.checkout_offer_one_time_dispatch import (
    CheckoutOfferOneTimeDispatchProjection as _DispatchProjection,
)
from app.services.checkout_offer_order_composition import (
    CheckoutOfferOrderSnapshot as _OrderSnapshot,
)


_PUBLIC_MESSAGE = "Nao foi possivel iniciar o checkout"
_OFFER_CODE = _re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", _re.ASCII)
_CAPABILITY = _re.compile(
    r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+", _re.ASCII
)


class CheckoutOfferOneTimeApplicationError(Exception):
    """Falha publica deliberadamente opaca da aplicacao."""

    def __init__(self):
        super().__init__(_PUBLIC_MESSAGE)


class CheckoutOfferOneTimeApplication:
    def __init__(self, order_composer, dispatcher):
        try:
            compose = getattr(order_composer, "iniciar_checkout_empresa", None)
            dispatch = getattr(dispatcher, "despachar", None)
        except Exception:
            raise CheckoutOfferOneTimeApplicationError() from None
        if not callable(compose) or not callable(dispatch):
            raise CheckoutOfferOneTimeApplicationError()
        self._compose = compose
        self._dispatch = dispatch

    def iniciar_checkout(
        self, *, authenticated_user_id, empresa_id, offer_code, idempotency_key
    ):
        try:
            order = self._compose(
                authenticated_user_id=authenticated_user_id,
                empresa_id=empresa_id,
                offer_code=offer_code,
                idempotency_key=idempotency_key,
            )
            self._validate_order(
                order,
                authenticated_user_id,
                empresa_id,
                offer_code,
                idempotency_key,
            )
            projection = self._dispatch(
                authenticated_user_id=authenticated_user_id,
                empresa_id=empresa_id,
                ordem_id=order.id,
            )
            self._validate_projection(projection, order.id)
            return {"checkout_url": projection.checkout_url}
        except CheckoutOfferOneTimeApplicationError:
            raise
        except Exception:
            raise CheckoutOfferOneTimeApplicationError() from None

    @classmethod
    def _validate_order(cls, order, user_id, empresa_id, offer_code, key):
        if type(order) is not _OrderSnapshot:
            raise CheckoutOfferOneTimeApplicationError()
        if not all(
            cls._positive_id(value)
            for value in (
                order.id,
                order.offer_id,
                order.contract_version,
                order.subject_id,
                order.user_id,
                order.usage_limit,
            )
        ):
            raise CheckoutOfferOneTimeApplicationError()
        if (
            type(user_id) is not int
            or type(empresa_id) is not int
            or type(offer_code) is not str
            or type(key) is not str
            or order.user_id != user_id
            or order.subject_id != empresa_id
            or order.offer_code != offer_code
            or order.idempotency_key != key
            or _OFFER_CODE.fullmatch(order.offer_code) is None
            or order.vertical not in {"tax", "document"}
            or order.commercial_model != "one_time"
            or order.subject_type != "company"
            or order.estado != "pending"
            or order.moeda != "BRL"
            or order.billing_period is not None
            or order.plano_id is not None
            or not cls._amount(order.valor)
            or not cls._canonical_text(order.usage_unit, 50)
            or not cls._canonical_text(order.idempotency_key, 255)
            or not cls._capabilities(order.capabilities)
        ):
            raise CheckoutOfferOneTimeApplicationError()

    @staticmethod
    def _positive_id(value):
        return type(value) is int and value > 0

    @staticmethod
    def _amount(value):
        return (
            isinstance(value, _Decimal)
            and value.is_finite()
            and value > _Decimal("0")
            and value == value.quantize(_Decimal("0.01"))
        )

    @staticmethod
    def _canonical_text(value, limit):
        return (
            type(value) is str
            and bool(value)
            and value == value.strip()
            and len(value) <= limit
            and "\r" not in value
            and "\n" not in value
        )

    @classmethod
    def _capabilities(cls, values):
        return (
            type(values) is tuple
            and bool(values)
            and values == tuple(sorted(values))
            and len(values) == len(set(values))
            and all(
                type(value) is str and _CAPABILITY.fullmatch(value) is not None
                for value in values
            )
        )

    @classmethod
    def _validate_projection(cls, projection, order_id):
        if (
            type(projection) is not _DispatchProjection
            or not cls._positive_id(projection.ordem_id)
            or projection.ordem_id != order_id
            or not cls._canonical_text(projection.provider_order_id, 255)
            or not cls._checkout_url(projection.checkout_url)
        ):
            raise CheckoutOfferOneTimeApplicationError()

    @classmethod
    def _checkout_url(cls, value):
        if not cls._canonical_text(value, 2000):
            return False
        try:
            parsed = _urlsplit(value)
            return (
                parsed.scheme == "https"
                and bool(parsed.netloc)
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
            )
        except (TypeError, ValueError):
            return False


__all__ = [
    "CheckoutOfferOneTimeApplicationError",
    "CheckoutOfferOneTimeApplication",
]
