"""Manage the explicit Mercado Pago runtime lifecycle."""

from app.services.mercado_pago_composition import compor_mercado_pago
from app.services.mercado_pago_runtime_config import (
    resolver_mercado_pago_runtime_config,
)


class MercadoPagoRuntimeActivation:
    """Own one Mercado Pago composition and its private HTTP client."""

    __slots__ = ("_composition", "_client", "_closed")

    def __init__(self, *, composition, client):
        self._composition = composition
        self._client = client
        self._closed = False

    @property
    def composition(self):
        return self._composition

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._client.close()

    def __repr__(self):
        return "<MercadoPagoRuntimeActivation opaque>"

    __str__ = __repr__


def ativar_mercado_pago(
    *,
    values,
    session_factory,
    http_client_factory,
) -> MercadoPagoRuntimeActivation | None:
    """Activate Mercado Pago from explicit values when it is enabled."""

    if resolver_mercado_pago_runtime_config(values=values) is None:
        return None

    client = http_client_factory()
    try:
        composition = compor_mercado_pago(
            values=values,
            session_factory=session_factory,
            http_client=client,
        )
        return MercadoPagoRuntimeActivation(
            composition=composition,
            client=client,
        )
    except BaseException:
        try:
            client.close()
        except BaseException:
            pass
        raise


__all__ = ("MercadoPagoRuntimeActivation", "ativar_mercado_pago")
