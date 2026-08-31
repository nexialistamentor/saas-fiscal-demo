"""Contrato RED offline do futuro resolvedor de pagamento Mercado Pago."""

from decimal import Decimal
from importlib import import_module

import pytest


class _ClientePagamentosFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta = resposta
        self.erro = erro
        self.chamadas = []

    def obter_pagamento(self, *, payment_id):
        self.chamadas.append({"payment_id": payment_id})
        if self.erro is not None:
            raise self.erro
        return self.resposta


def _assert_erro_sanitizado(erro, *dados_proibidos):
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in (
            "token",
            "secret",
            "segredo",
            "credencial",
            "payload",
            "sql",
            "interno",
            "transaction_amount",
            "currency_id",
        ):
            assert marcador not in texto
        for dado in dados_proibidos:
            assert str(dado).lower() not in texto


def _resolver(mercado_pago, resposta=None, erro=None):
    cliente = _ClientePagamentosFalso(resposta=resposta, erro=erro)
    resolvedor = mercado_pago.MercadoPagoPaymentResolver(
        cliente_pagamentos=cliente
    )
    return resolvedor, cliente


def test_mercado_pago_payment_resolution_contract_red(monkeypatch):
    mercado_pago = import_module(
        "app.services.mercado_pago_payment_resolution"
    )

    checkout_core = import_module("app.services.checkout_core")

    def _checkout_core_proibido(*_args, **_kwargs):
        raise AssertionError("o resolvedor nao pode chamar CheckoutCore")

    for nome in (
        "iniciar_checkout",
        "consultar_ordem",
        "cancelar_ordem",
        "processar_retorno",
        "processar_webhook",
        "confirmar_pagamento_autorizado",
    ):
        monkeypatch.setattr(
            checkout_core.CheckoutCore,
            nome,
            _checkout_core_proibido,
            raising=False,
        )

    for cliente_invalido in (None, object(), lambda: None):
        with pytest.raises(
            mercado_pago.MercadoPagoPaymentResolutionError
        ) as capturada:
            mercado_pago.MercadoPagoPaymentResolver(
                cliente_pagamentos=cliente_invalido
            )
        _assert_erro_sanitizado(capturada.value)

    resposta_aprovada = {
        "id": 4719,
        "external_reference": "91",
        "status": "approved",
        "transaction_amount": 49.90,
        "currency_id": "BRL",
        "token": "token-nao-confiavel",
        "payload": {"credencial": "privada"},
    }
    resolvedor, cliente = _resolver(mercado_pago, resposta_aprovada)
    assert resolvedor.resolver_pagamento("4719", "8128") == {
        "ordem_id": 91,
        "event_id": "8128",
        "valor": Decimal("49.90"),
        "moeda": "BRL",
    }
    assert cliente.chamadas == [{"payment_id": "4719"}]

    resposta_id_string = {**resposta_aprovada, "id": "4719"}
    resolvedor, cliente = _resolver(mercado_pago, resposta_id_string)
    assert resolvedor.resolver_pagamento("4719", "8129") == {
        "ordem_id": 91,
        "event_id": "8129",
        "valor": Decimal("49.90"),
        "moeda": "BRL",
    }
    assert cliente.chamadas == [{"payment_id": "4719"}]

    for valor in (
        "49.90",
        "49.900",
        "4.99E+1",
        "49.9",
        Decimal("49.90"),
        49,
    ):
        resolvedor, cliente = _resolver(
            mercado_pago,
            {**resposta_aprovada, "transaction_amount": valor},
        )
        resolucao = resolvedor.resolver_pagamento("4719", "8128")
        assert set(resolucao) == {"ordem_id", "event_id", "valor", "moeda"}
        assert resolucao == {
            "ordem_id": 91,
            "event_id": "8128",
            "valor": Decimal("49.90") if valor != 49 else Decimal("49.00"),
            "moeda": "BRL",
        }
        assert resolucao["valor"].as_tuple().exponent == -2
        assert cliente.chamadas == [{"payment_id": "4719"}]

    resolvedor, cliente = _resolver(
        mercado_pago,
        {**resposta_aprovada, "transaction_amount": "0.01"},
    )
    assert resolvedor.resolver_pagamento("4719", "8128") == {
        "ordem_id": 91,
        "event_id": "8128",
        "valor": Decimal("0.01"),
        "moeda": "BRL",
    }
    assert cliente.chamadas == [{"payment_id": "4719"}]

    for payment_id, notification_id in (
        (None, "8128"),
        (4719, "8128"),
        ("", "8128"),
        ("0", "8128"),
        ("-1", "8128"),
        ("01", "8128"),
        (" 4719", "8128"),
        ("4719 ", "8128"),
        ("47 19", "8128"),
        ("4719\r", "8128"),
        ("4719\n", "8128"),
        ("4719", None),
        ("4719", 8128),
        ("4719", ""),
        ("4719", "0"),
        ("4719", "-1"),
        ("4719", "08128"),
        ("4719", " 8128"),
        ("4719", "8128 "),
        ("4719", "81 28"),
        ("4719", "8128\r"),
        ("4719", "8128\n"),
    ):
        resolvedor, cliente = _resolver(mercado_pago, resposta_aprovada)
        with pytest.raises(mercado_pago.MercadoPagoPaymentResolutionError):
            resolvedor.resolver_pagamento(payment_id, notification_id)
        assert cliente.chamadas == []

    estados_nao_aprovados = (
        "pending",
        "authorized",
        "in_process",
        "in_mediation",
        "rejected",
        "cancelled",
        "refunded",
        "charged_back",
    )
    for status in estados_nao_aprovados:
        resolvedor, cliente = _resolver(
            mercado_pago,
            {"id": 4719, "external_reference": "91", "status": status},
        )
        assert resolvedor.resolver_pagamento("4719", "8128") is None
        assert cliente.chamadas == [{"payment_id": "4719"}]

    respostas_invalidas = (
        None,
        [],
        {},
        {**resposta_aprovada, "id": True},
        {**resposta_aprovada, "id": 0},
        {**resposta_aprovada, "id": "04719"},
        {**resposta_aprovada, "id": 4720},
        {**resposta_aprovada, "id": "4720"},
        {**resposta_aprovada, "external_reference": None},
        {**resposta_aprovada, "external_reference": 91},
        {**resposta_aprovada, "external_reference": ""},
        {**resposta_aprovada, "external_reference": "0"},
        {**resposta_aprovada, "external_reference": "-1"},
        {**resposta_aprovada, "external_reference": "091"},
        {**resposta_aprovada, "external_reference": "91.0"},
        {**resposta_aprovada, "external_reference": "user_id"},
        {**resposta_aprovada, "external_reference": "empresa_id"},
        {**resposta_aprovada, "external_reference": "ordem-arbitraria"},
        {key: value for key, value in resposta_aprovada.items() if key != "external_reference"},
        {
            **{key: value for key, value in resposta_aprovada.items() if key != "external_reference"},
            "user_id": "91",
            "empresa_id": "91",
        },
        {**resposta_aprovada, "status": "Approved"},
        {**resposta_aprovada, "status": "APPROVED"},
        {**resposta_aprovada, "status": "approved "},
        {**resposta_aprovada, "status": "paid"},
        {**resposta_aprovada, "status": "desconhecido"},
        {**resposta_aprovada, "status": None},
    )
    for resposta_invalida in respostas_invalidas:
        resolvedor, cliente = _resolver(mercado_pago, resposta_invalida)
        with pytest.raises(
            mercado_pago.MercadoPagoPaymentResolutionError
        ) as capturada:
            resolvedor.resolver_pagamento("4719", "8128")
        assert cliente.chamadas == [{"payment_id": "4719"}]
        _assert_erro_sanitizado(
            capturada.value,
            "token-nao-confiavel",
            "privada",
            "ordem-arbitraria",
        )

    campos_monetarios_invalidos = (
        {key: value for key, value in resposta_aprovada.items() if key != "transaction_amount"},
        {key: value for key, value in resposta_aprovada.items() if key != "currency_id"},
        {**resposta_aprovada, "transaction_amount": None},
        {**resposta_aprovada, "transaction_amount": True},
        {**resposta_aprovada, "transaction_amount": "valor-invalido"},
        {**resposta_aprovada, "transaction_amount": "NaN"},
        {**resposta_aprovada, "transaction_amount": "Infinity"},
        {**resposta_aprovada, "transaction_amount": "-Infinity"},
        {**resposta_aprovada, "transaction_amount": 0},
        {**resposta_aprovada, "transaction_amount": -1},
        {**resposta_aprovada, "transaction_amount": 49.901},
        {**resposta_aprovada, "transaction_amount": "49.901"},
        {**resposta_aprovada, "transaction_amount": Decimal("49.901")},
        {**resposta_aprovada, "currency_id": "brl"},
        {**resposta_aprovada, "currency_id": "USD"},
        {**resposta_aprovada, "currency_id": ""},
        {**resposta_aprovada, "currency_id": None},
        {**resposta_aprovada, "currency_id": True},
        {**resposta_aprovada, "currency_id": 1},
    )
    for resposta_invalida in campos_monetarios_invalidos:
        resolvedor, cliente = _resolver(mercado_pago, resposta_invalida)
        with pytest.raises(
            mercado_pago.MercadoPagoPaymentResolutionError
        ) as capturada:
            resolvedor.resolver_pagamento("4719", "8128")
        assert cliente.chamadas == [{"payment_id": "4719"}]
        _assert_erro_sanitizado(
            capturada.value,
            "49.90",
            "0.01",
            "USD",
            "token-nao-confiavel",
            "privada",
        )

    resolvedor, cliente = _resolver(
        mercado_pago,
        {
            **resposta_aprovada,
            "transaction_amount": "0.01",
            "currency_id": "USD",
        },
    )
    with pytest.raises(
        mercado_pago.MercadoPagoPaymentResolutionError
    ) as capturada:
        resolvedor.resolver_pagamento("4719", "8128")
    assert cliente.chamadas == [{"payment_id": "4719"}]
    _assert_erro_sanitizado(capturada.value, "0.01", "USD")

    detalhe_interno = "falha-interna-privada-9931"
    segredo = "segredo-ultrassecreto-8128"
    resolvedor, cliente = _resolver(
        mercado_pago,
        erro=RuntimeError(
            f"token credencial payload {segredo} {detalhe_interno}"
        ),
    )
    with pytest.raises(
        mercado_pago.MercadoPagoPaymentResolutionError
    ) as capturada:
        resolvedor.resolver_pagamento("4719", "8128")
    assert cliente.chamadas == [{"payment_id": "4719"}]
    _assert_erro_sanitizado(capturada.value, segredo, detalhe_interno)
