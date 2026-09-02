"""Composicao raiz dos fluxos Mercado Pago."""

from app.services.checkout_offer_one_time_application import (
    CheckoutOfferOneTimeApplication,
)
from app.services.checkout_offer_one_time_dispatch import (
    CheckoutOfferOneTimeDispatcher,
)
from app.services.checkout_offer_order_composition import (
    CheckoutOfferOrderComposer,
)
from app.services.mercado_pago_checkout_offer_one_time import (
    MercadoPagoCheckoutOfferOneTimeGateway,
)
from app.services.mercado_pago_payment_client import MercadoPagoPaymentClient
from app.services.mercado_pago_preference_client import (
    MercadoPagoPreferenceClient,
)
from app.services.mercado_pago_runtime_config import (
    resolver_mercado_pago_runtime_config,
)
from app.services.mercado_pago_webhook_composition import (
    criar_mercado_pago_webhook_orchestrator,
)
from app.services.mercado_pago_webhook_hmac import (
    validar_mercado_pago_webhook_hmac,
)


class MercadoPagoComposition:
    """Composicao imutavel com representacao deliberadamente opaca."""

    __slots__ = (
        "_checkout_application",
        "_webhook_orchestrator",
        "_max_body_bytes",
    )

    def __init__(
        self,
        checkout_application,
        webhook_orchestrator,
        max_body_bytes,
    ):
        object.__setattr__(self, "_checkout_application", checkout_application)
        object.__setattr__(self, "_webhook_orchestrator", webhook_orchestrator)
        object.__setattr__(self, "_max_body_bytes", max_body_bytes)

    @property
    def checkout_application(self):
        return self._checkout_application

    @property
    def webhook_orchestrator(self):
        return self._webhook_orchestrator

    @property
    def max_body_bytes(self):
        return self._max_body_bytes

    def __setattr__(self, name, value):
        raise AttributeError("Mercado Pago composition is immutable")

    def __delattr__(self, name):
        raise AttributeError("Mercado Pago composition is immutable")

    def __repr__(self):
        return "<MercadoPagoComposition opaque>"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("Mercado Pago composition serialization is disabled")

    def __reduce_ex__(self, protocol):
        raise TypeError("Mercado Pago composition serialization is disabled")

    def __getstate__(self):
        raise TypeError("Mercado Pago composition serialization is disabled")


def compor_mercado_pago(
    *,
    values,
    session_factory,
    http_client,
) -> MercadoPagoComposition | None:
    """Resolve configuracao explicita e compoe os fluxos habilitados."""

    configuration = resolver_mercado_pago_runtime_config(values=values)
    if configuration is None:
        return None

    payment_client = MercadoPagoPaymentClient(
        http_client=http_client,
        access_token=configuration.access_token,
        timeout_seconds=configuration.timeout_seconds,
    )
    preference_client = MercadoPagoPreferenceClient(
        http_client=http_client,
        access_token=configuration.access_token,
        timeout_seconds=configuration.timeout_seconds,
    )
    gateway = MercadoPagoCheckoutOfferOneTimeGateway(
        preference_client,
        configuration.notification_url,
        dict(configuration.back_urls),
    )
    order_composer = CheckoutOfferOrderComposer(session_factory)
    dispatcher = CheckoutOfferOneTimeDispatcher(session_factory, gateway)
    checkout_application = CheckoutOfferOneTimeApplication(
        order_composer,
        dispatcher,
    )
    webhook_orchestrator = criar_mercado_pago_webhook_orchestrator(
        session_factory=session_factory,
        signature_validator=validar_mercado_pago_webhook_hmac,
        signature_secret=configuration.webhook_secret,
        payment_client=payment_client,
    )
    return MercadoPagoComposition(
        checkout_application,
        webhook_orchestrator,
        configuration.max_body_bytes,
    )


__all__ = ("MercadoPagoComposition", "compor_mercado_pago")
