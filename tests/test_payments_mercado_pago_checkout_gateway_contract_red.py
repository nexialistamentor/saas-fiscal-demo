"""Contrato RED offline do futuro gateway Mercado Pago Checkout Pro."""

from decimal import Decimal
from importlib import import_module

import pytest


class _ClientePreferenciasFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta = resposta
        self.erro = erro
        self.chamadas = []

    def criar_preferencia(self, *, payload, idempotency_key):
        self.chamadas.append(
            {"payload": payload, "idempotency_key": idempotency_key}
        )
        if self.erro is not None:
            raise self.erro
        return self.resposta


def test_mercado_pago_checkout_pro_gateway_contract_red():
    mercado_pago = import_module("app.services.mercado_pago_checkout")

    urls = {
        "notification_url": "https://fisco.example/webhooks/mercado-pago",
        "back_urls": {
            "success": "https://fisco.example/checkout/sucesso",
            "failure": "https://fisco.example/checkout/falha",
            "pending": "https://fisco.example/checkout/pendente",
        },
    }
    resposta_valida = {
        "provider_order_id": "mp-pref-123",
        "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect",
    }
    cliente = _ClientePreferenciasFalso(resposta=resposta_valida)
    gateway = mercado_pago.MercadoPagoCheckoutGateway(
        cliente_preferencias=cliente,
        notification_url=urls["notification_url"],
        back_urls=urls["back_urls"],
    )
    dados = {
        "ordem_id": 91,
        "user_id": 42,
        "empresa_id": 314,
        "plano_id": 7,
        "valor": Decimal("49.90"),
        "moeda": "BRL",
        "idempotency_key": "checkout-91",
    }

    configuracoes_invalidas = (
        {**urls, "notification_url": "http://fisco.example/webhook"},
        {**urls, "notification_url": "javascript:alert(1)"},
        {**urls, "notification_url": "/webhooks/mercado-pago"},
        {**urls, "notification_url": ""},
        {**urls, "notification_url": None},
        {**urls, "notification_url": 123},
        {
            **urls,
            "back_urls": {
                "success": "http://fisco.example/checkout/sucesso",
                "failure": urls["back_urls"]["failure"],
                "pending": urls["back_urls"]["pending"],
            },
        },
        {
            **urls,
            "back_urls": {
                "success": urls["back_urls"]["success"],
                "failure": "javascript:alert(1)",
                "pending": urls["back_urls"]["pending"],
            },
        },
        {
            **urls,
            "back_urls": {
                "success": urls["back_urls"]["success"],
                "failure": urls["back_urls"]["failure"],
                "pending": "/checkout/pendente",
            },
        },
        {
            **urls,
            "back_urls": {
                "success": urls["back_urls"]["success"],
                "failure": urls["back_urls"]["failure"],
                "pending": "",
            },
        },
        {
            **urls,
            "back_urls": {
                "success": urls["back_urls"]["success"],
                "failure": urls["back_urls"]["failure"],
                "pending": None,
            },
        },
        {**urls, "back_urls": None},
        {**urls, "back_urls": {"success": urls["back_urls"]["success"]}},
        {
            **urls,
            "back_urls": {
                **urls["back_urls"],
                "cancel": "https://fisco.example/checkout/cancelado",
            },
        },
    )
    for configuracao_invalida in configuracoes_invalidas:
        cliente_configuracao_invalida = _ClientePreferenciasFalso(
            resposta=resposta_valida
        )
        with pytest.raises(mercado_pago.MercadoPagoCheckoutError):
            mercado_pago.MercadoPagoCheckoutGateway(
                cliente_preferencias=cliente_configuracao_invalida,
                **configuracao_invalida,
            )
        assert cliente_configuracao_invalida.chamadas == []

    resultado = gateway.criar_cobranca(**dados)

    assert cliente.chamadas == [
        {
            "payload": {
                "external_reference": "91",
                "items": [
                    {
                        "id": "7",
                        "quantity": 1,
                        "unit_price": Decimal("49.90"),
                        "currency_id": "BRL",
                    }
                ],
                **urls,
            },
            "idempotency_key": "checkout-91",
        }
    ]
    assert resultado == resposta_valida
    assert set(resultado) == {"provider_order_id", "checkout_url"}

    payload_serializado = repr(cliente.chamadas[0]["payload"])
    for dado_proibido in (
        "user_id",
        "empresa_id",
        "idempotency_key",
        "token",
        "credencial",
        "42",
        "314",
        "checkout-91",
    ):
        assert dado_proibido not in payload_serializado

    casos_invalidos = (
        {"ordem_id": 0},
        {"ordem_id": True},
        {"ordem_id": False},
        {"user_id": 0},
        {"user_id": True},
        {"user_id": False},
        {"empresa_id": 0},
        {"empresa_id": True},
        {"empresa_id": False},
        {"plano_id": 0},
        {"plano_id": True},
        {"plano_id": False},
        {"valor": Decimal("0")},
        {"valor": Decimal("NaN")},
        {"valor": "49.90"},
        {"moeda": "USD"},
        {"idempotency_key": ""},
        {"idempotency_key": "   "},
    )
    for alteracao in casos_invalidos:
        cliente_invalido = _ClientePreferenciasFalso(resposta=resposta_valida)
        gateway_invalido = mercado_pago.MercadoPagoCheckoutGateway(
            cliente_preferencias=cliente_invalido,
            notification_url=urls["notification_url"],
            back_urls=urls["back_urls"],
        )
        with pytest.raises(mercado_pago.MercadoPagoCheckoutError) as capturada:
            gateway_invalido.criar_cobranca(**{**dados, **alteracao})
        assert cliente_invalido.chamadas == []
        assert "token" not in str(capturada.value).lower()
        assert "credencial" not in str(capturada.value).lower()

    respostas_invalidas = (
        None,
        {},
        {"provider_order_id": "", "checkout_url": resposta_valida["checkout_url"]},
        {"provider_order_id": "mp-pref-123", "checkout_url": "http://inseguro"},
        {"provider_order_id": "mp-pref-123", "checkout_url": "javascript:alert(1)"},
        {
            "provider_order_id": "mp-pref-123",
            "checkout_url": "https://pagamento-malicioso.example/checkout",
        },
        {
            "provider_order_id": "mp-pref-123",
            "checkout_url": "https://mercadopago.com.br.evil.example/checkout",
        },
    )
    for resposta_invalida in respostas_invalidas:
        cliente_invalido = _ClientePreferenciasFalso(resposta=resposta_invalida)
        gateway_invalido = mercado_pago.MercadoPagoCheckoutGateway(
            cliente_preferencias=cliente_invalido,
            notification_url=urls["notification_url"],
            back_urls=urls["back_urls"],
        )
        with pytest.raises(mercado_pago.MercadoPagoCheckoutError):
            gateway_invalido.criar_cobranca(**dados)

    resposta_dominio_raiz = {
        **resposta_valida,
        "checkout_url": "https://mercadopago.com.br/checkout/v1/redirect",
    }
    cliente_dominio_raiz = _ClientePreferenciasFalso(resposta=resposta_dominio_raiz)
    gateway_dominio_raiz = mercado_pago.MercadoPagoCheckoutGateway(
        cliente_preferencias=cliente_dominio_raiz,
        notification_url=urls["notification_url"],
        back_urls=urls["back_urls"],
    )
    assert gateway_dominio_raiz.criar_cobranca(**dados) == resposta_dominio_raiz

    resposta_com_segredos = {
        **resposta_valida,
        "payload": {"raw": True},
        "token": "provider-secret-token",
        "credencial": "provider-secret-credential",
        "resposta_completa": {"private": True},
    }
    cliente_segredos = _ClientePreferenciasFalso(resposta=resposta_com_segredos)
    gateway_segredos = mercado_pago.MercadoPagoCheckoutGateway(
        cliente_preferencias=cliente_segredos,
        notification_url=urls["notification_url"],
        back_urls=urls["back_urls"],
    )
    assert gateway_segredos.criar_cobranca(**dados) == resposta_valida

    segredo = "token-ultrassecreto-987"
    cliente_em_falha = _ClientePreferenciasFalso(
        erro=RuntimeError(f"credencial recusada: {segredo}")
    )
    gateway_em_falha = mercado_pago.MercadoPagoCheckoutGateway(
        cliente_preferencias=cliente_em_falha,
        notification_url=urls["notification_url"],
        back_urls=urls["back_urls"],
    )
    with pytest.raises(mercado_pago.MercadoPagoCheckoutError) as capturada:
        gateway_em_falha.criar_cobranca(**dados)
    mensagem_publica = str(capturada.value).lower()
    assert segredo not in mensagem_publica
    assert "token" not in mensagem_publica
    assert "credencial" not in mensagem_publica
