"""Router autenticado e read-only do catalogo publico de ofertas."""

from decimal import Decimal
import re

from fastapi import APIRouter, Depends, Response

__all__ = (
    "CheckoutOfferCatalogRouterConfigurationError",
    "criar_checkout_offer_catalog_router",
)


_CODIGO = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.ASCII)
_VERTICAIS = frozenset({"tax", "document"})
_MODELOS = frozenset({"monthly", "one_time", "negotiated"})
_SUJEITOS = frozenset({"cpf", "company", "institution"})


class CheckoutOfferCatalogRouterConfigurationError(Exception):
    """Indica colaboradores ausentes ou incompatíveis."""


def _configuration_error():
    return CheckoutOfferCatalogRouterConfigurationError(
        "invalid checkout offer catalog router configuration"
    )


def _texto(value, maximum):
    return (
        type(value) is str
        and 0 < len(value) <= maximum
        and value == value.strip()
        and "\r" not in value
        and "\n" not in value
    )


def _preco(value):
    return (
        type(value) is Decimal
        and value.is_finite()
        and value > Decimal("0")
        and value.as_tuple().exponent == -2
    )


def _inteiro_positivo(value):
    return type(value) is int and value > 0


def _oferta_publica(offer):
    code = offer.codigo
    name = offer.nome_publico
    vertical = offer.vertical
    model = offer.commercial_model
    subject = offer.subject_type
    state = offer.estado
    currency = offer.moeda
    price = offer.preco
    period = offer.billing_period
    unit = offer.usage_unit
    limit = offer.usage_limit
    mode = offer.checkout_mode

    if not (
        _texto(code, 120)
        and _CODIGO.fullmatch(code) is not None
        and _texto(name, 255)
        and type(vertical) is str
        and vertical in _VERTICAIS
        and type(model) is str
        and model in _MODELOS
        and type(subject) is str
        and subject in _SUJEITOS
        and type(state) is str
        and state == "published"
    ):
        raise ValueError

    if model == "negotiated":
        if (
            any(value is not None for value in (currency, price, period, unit, limit))
            or type(mode) is not str
            or mode != "proposal"
        ):
            raise ValueError
    else:
        if (
            type(currency) is not str
            or currency != "BRL"
            or not _preco(price)
            or type(mode) is not str
            or mode != "automatic"
        ):
            raise ValueError
        if model == "monthly":
            if period != "month" or unit is not None or limit is not None:
                raise ValueError
        elif (
            period is not None
            or not _texto(unit, 50)
            or not _inteiro_positivo(limit)
        ):
            raise ValueError

    return {
        "offer_code": code,
        "nome_publico": name,
        "vertical": vertical,
        "commercial_model": model,
        "subject_type": subject,
        "moeda": currency,
        "preco": None if price is None else format(price, ".2f"),
        "billing_period": period,
        "usage_unit": unit,
        "usage_limit": limit,
        "checkout_mode": mode,
    }


def criar_checkout_offer_catalog_router(
    *,
    catalog_service,
    current_user_dependency,
):
    listar = getattr(catalog_service, "listar_ofertas_publicadas", None)
    if not callable(listar) or not callable(current_user_dependency):
        raise _configuration_error()

    router = APIRouter()

    @router.get("/checkout/offers")
    def listar_ofertas(_usuario=Depends(current_user_dependency)):
        try:
            offers = catalog_service.listar_ofertas_publicadas()
            if type(offers) is not tuple:
                raise ValueError
            public = tuple(_oferta_publica(offer) for offer in offers)
            codes = tuple(item["offer_code"] for item in public)
            if len(codes) != len(set(codes)):
                raise ValueError
            return sorted(public, key=lambda item: item["offer_code"])
        except Exception:
            return Response(status_code=500, content=b"")

    return router
