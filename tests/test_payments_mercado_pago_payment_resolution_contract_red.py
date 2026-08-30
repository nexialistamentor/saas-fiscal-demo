"""Contrato RED offline do futuro resolvedor de pagamento Mercado Pago."""

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
        for marcador in ("token", "credencial", "payload", "interno"):
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
        "user_id": 42,
        "empresa_id": 314,
        "transaction_amount": "0.01",
        "currency_id": "USD",
        "token": "token-nao-confiavel",
        "payload": {"credencial": "privada"},
    }
    resolvedor, cliente = _resolver(mercado_pago, resposta_aprovada)
    assert resolvedor.resolver_pagamento("4719", "request-8128") == {
        "ordem_id": 91,
        "event_id": "request-8128",
    }
    assert cliente.chamadas == [{"payment_id": "4719"}]

    resposta_id_string = {**resposta_aprovada, "id": "4719"}
    resolvedor, cliente = _resolver(mercado_pago, resposta_id_string)
    assert resolvedor.resolver_pagamento("4719", "request-8129") == {
        "ordem_id": 91,
        "event_id": "request-8129",
    }
    assert cliente.chamadas == [{"payment_id": "4719"}]

    for data_id, request_id in (
        (None, "request-1"),
        (4719, "request-1"),
        ("", "request-1"),
        ("0", "request-1"),
        ("-1", "request-1"),
        ("01", "request-1"),
        (" 4719", "request-1"),
        ("4719 ", "request-1"),
        ("47 19", "request-1"),
        ("4719\r", "request-1"),
        ("4719\n", "request-1"),
        ("4719", None),
        ("4719", 8128),
        ("4719", ""),
        ("4719", " request-1"),
        ("4719", "request 1"),
        ("4719", "request-1\rforjado"),
        ("4719", "request-1\nforjado"),
    ):
        resolvedor, cliente = _resolver(mercado_pago, resposta_aprovada)
        with pytest.raises(mercado_pago.MercadoPagoPaymentResolutionError):
            resolvedor.resolver_pagamento(data_id, request_id)
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
            mercado_pago, {**resposta_aprovada, "status": status}
        )
        assert resolvedor.resolver_pagamento("4719", "request-known") is None
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
            resolvedor.resolver_pagamento("4719", "request-invalid")
        assert cliente.chamadas == [{"payment_id": "4719"}]
        _assert_erro_sanitizado(
            capturada.value,
            "token-nao-confiavel",
            "privada",
            "ordem-arbitraria",
        )

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
        resolvedor.resolver_pagamento("4719", "request-failure")
    assert cliente.chamadas == [{"payment_id": "4719"}]
    _assert_erro_sanitizado(capturada.value, segredo, detalhe_interno)
