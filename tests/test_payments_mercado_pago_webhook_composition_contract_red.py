"""Contrato RED offline da composicao interna do webhook Mercado Pago."""

import inspect
import os


class _ExternalDependencySentinel:
    def __init__(self, name):
        self.name = name

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"dependencia externa executada: {self.name}")

    def __getattr__(self, attribute):
        raise AssertionError(
            f"dependencia externa inspecionada: {self.name}.{attribute}"
        )

    def __str__(self):
        raise AssertionError(f"dependencia externa convertida: {self.name}")

    def __bytes__(self):
        raise AssertionError(f"dependencia externa convertida: {self.name}")


class _ForbiddenEnvironment(dict):
    def __getitem__(self, key):
        raise AssertionError("a composicao nao pode ler variaveis de ambiente")

    def get(self, key, default=None):
        raise AssertionError("a composicao nao pode ler variaveis de ambiente")


def test_payments_mercado_pago_webhook_composition_contract_red(monkeypatch):
    import app.services.mercado_pago_webhook_composition as composition

    parameters = inspect.signature(
        composition.criar_mercado_pago_webhook_orchestrator
    ).parameters
    assert list(parameters) == [
        "session_factory",
        "signature_validator",
        "signature_secret",
        "payment_client",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )

    session_factory = _ExternalDependencySentinel("session_factory")
    signature_validator = _ExternalDependencySentinel("signature_validator")
    signature_secret = _ExternalDependencySentinel("signature_secret")
    payment_client = _ExternalDependencySentinel("payment_client")

    construction_order = []
    instances = {}

    def constructor_double(name):
        def construct(*args, **kwargs):
            instance = object()
            construction_order.append((name, args, kwargs, instance))
            instances[name] = instance
            return instance

        return construct

    constructor_names = [
        "MercadoPagoWebhookSignatureVerifier",
        "MercadoPagoPaymentResolver",
        "CheckoutDurableWebhookConfirmer",
        "CheckoutOfferOneTimeConfirmer",
        "CheckoutDurableWebhookConfirmationRouter",
        "MercadoPagoWebhookOrchestrator",
    ]
    for name in constructor_names:
        monkeypatch.setattr(composition, name, constructor_double(name))

    def forbidden_getenv(*args, **kwargs):
        raise AssertionError("a composicao nao pode ler variaveis de ambiente")

    monkeypatch.setattr(os, "getenv", forbidden_getenv)
    monkeypatch.setattr(os, "environ", _ForbiddenEnvironment())

    result = composition.criar_mercado_pago_webhook_orchestrator(
        session_factory=session_factory,
        signature_validator=signature_validator,
        signature_secret=signature_secret,
        payment_client=payment_client,
    )

    assert [entry[0] for entry in construction_order] == constructor_names
    assert all(entry[2] == {} for entry in construction_order)
    assert construction_order[0][1] == (signature_validator, signature_secret)
    assert construction_order[1][1] == (payment_client,)
    assert construction_order[2][1] == (session_factory,)
    assert construction_order[3][1] == (session_factory,)
    assert construction_order[4][1] == (
        session_factory,
        instances["CheckoutDurableWebhookConfirmer"],
        instances["CheckoutOfferOneTimeConfirmer"],
    )
    assert construction_order[5][1] == (
        instances["MercadoPagoWebhookSignatureVerifier"],
        instances["MercadoPagoPaymentResolver"],
        instances["CheckoutDurableWebhookConfirmationRouter"],
    )
    assert result is instances["MercadoPagoWebhookOrchestrator"]
