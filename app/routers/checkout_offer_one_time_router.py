"""Router autenticado para checkout one-time baseado em oferta."""

from ipaddress import ip_address
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

__all__ = (
    "CheckoutOfferOneTimeRouterConfigurationError",
    "criar_checkout_offer_one_time_router",
)


class CheckoutOfferOneTimeRouterConfigurationError(Exception):
    """Indica colaboradores ausentes ou incompatíveis."""


class _CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empresa_id: Annotated[StrictInt, Field(gt=0)]
    offer_code: Annotated[
        StrictStr,
        Field(
            max_length=120,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)+$",
        ),
    ]


def _configuration_error():
    return CheckoutOfferOneTimeRouterConfigurationError(
        "invalid checkout router configuration"
    )


def _empty_internal_response():
    return Response(status_code=500, content=b"")


def _valid_hostname(hostname):
    try:
        ip_address(hostname)
        return True
    except ValueError:
        pass

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if ascii_hostname.endswith("."):
        ascii_hostname = ascii_hostname[:-1]
    if not ascii_hostname or len(ascii_hostname) > 253:
        return False
    labels = ascii_hostname.split(".")
    return all(
        label
        and len(label) <= 63
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(character.isalnum() or character == "-" for character in label)
        for label in labels
    )


def _valid_checkout_url(value):
    if type(value) is not str or any(
        character.isspace() or ord(character) < 33 or ord(character) == 127
        for character in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
        username = parsed.username
        password = parsed.password
    except (UnicodeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and hostname is not None
        and _valid_hostname(hostname)
        and username is None
        and password is None
        and (port is None or 1 <= port <= 65535)
    )


def criar_checkout_offer_one_time_router(
    *,
    application_service,
    current_user_dependency,
):
    checkout = getattr(application_service, "iniciar_checkout", None)
    if not callable(checkout) or not callable(current_user_dependency):
        raise _configuration_error()

    router = APIRouter()

    @router.post("/checkout/one-time")
    def checkout_one_time(
        request: Request,
        body: _CheckoutRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=255,
                pattern=r"^[\x21-\x7e]+$",
            ),
        ],
        usuario=Depends(current_user_dependency),
    ):
        header_count = sum(
            1
            for name, _ in request.scope.get("headers", ())
            if name.lower() == b"idempotency-key"
        )
        if header_count != 1:
            return Response(status_code=422, content=b"")

        try:
            authenticated_user_id = usuario.id
            if type(authenticated_user_id) is not int or authenticated_user_id <= 0:
                return _empty_internal_response()
            result = application_service.iniciar_checkout(
                authenticated_user_id=authenticated_user_id,
                empresa_id=body.empresa_id,
                offer_code=body.offer_code,
                idempotency_key=idempotency_key,
            )
            if (
                type(result) is not dict
                or set(result) != {"checkout_url"}
                or not _valid_checkout_url(result["checkout_url"])
            ):
                return _empty_internal_response()
            return {"checkout_url": result["checkout_url"]}
        except Exception:
            return _empty_internal_response()

    return router
