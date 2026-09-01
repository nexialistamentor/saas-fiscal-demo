"""Composicao interna do webhook Mercado Pago."""

from app.services.checkout_durable_webhook_confirmation import (
    CheckoutDurableWebhookConfirmer,
)
from app.services.checkout_durable_webhook_confirmation_routing import (
    CheckoutDurableWebhookConfirmationRouter,
)
from app.services.checkout_offer_one_time_confirmation import (
    CheckoutOfferOneTimeConfirmer,
)
from app.services.mercado_pago_payment_resolution import MercadoPagoPaymentResolver
from app.services.mercado_pago_webhook import MercadoPagoWebhookSignatureVerifier
from app.services.mercado_pago_webhook_orchestration import (
    MercadoPagoWebhookOrchestrator,
)


def criar_mercado_pago_webhook_orchestrator(
    *,
    session_factory,
    signature_validator,
    signature_secret,
    payment_client,
):
    signature_verifier = MercadoPagoWebhookSignatureVerifier(
        signature_validator,
        signature_secret,
    )
    payment_resolver = MercadoPagoPaymentResolver(payment_client)
    legacy_confirmer = CheckoutDurableWebhookConfirmer(session_factory)
    one_time_confirmer = CheckoutOfferOneTimeConfirmer(session_factory)
    confirmation_router = CheckoutDurableWebhookConfirmationRouter(
        session_factory,
        legacy_confirmer,
        one_time_confirmer,
    )
    return MercadoPagoWebhookOrchestrator(
        signature_verifier,
        payment_resolver,
        confirmation_router,
    )
