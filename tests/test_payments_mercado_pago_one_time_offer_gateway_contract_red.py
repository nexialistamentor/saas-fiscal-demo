"""Contrato RED offline do gateway Mercado Pago para ofertas one_time.

O primeiro ponto causal e a importacao direta do modulo futuro. O contrato
nao usa rede, SDK, credenciais, banco de dados ou catalogo.
"""

from decimal import Decimal
from importlib import import_module
from inspect import Parameter, signature

import pytest


CHECKOUT_URL = "https://www.mercadopago.com.br/checkout/v1/redirect"


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


def _assert_sanitizado(erro, modulo, *proibidos):
    assert type(erro) is modulo.MercadoPagoCheckoutOfferOneTimeError
    for representacao in (str(erro), repr(erro)):
        publica = representacao.lower()
        for marcador in (
            "token", "segredo", "secret", "payload", "credencial",
            "credential", "select ", "sql", "interno", "79.50", "79.5",
        ):
            assert marcador not in publica
        for proibido in proibidos:
            assert str(proibido).lower() not in publica


def test_mercado_pago_one_time_offer_gateway_contract_red():
    mercado_pago = import_module(
        "app.services.mercado_pago_checkout_offer_one_time"
    )

    assert issubclass(
        mercado_pago.MercadoPagoCheckoutOfferOneTimeError, Exception
    )
    parametros = signature(
        mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway.criar_cobranca
    ).parameters
    assert list(parametros) == [
        "self", "ordem_id", "user_id", "empresa_id", "offer_code",
        "valor", "moeda", "idempotency_key",
    ]
    assert all(
        parametro.kind is Parameter.POSITIONAL_OR_KEYWORD
        for parametro in parametros.values()
    )

    urls = {
        "notification_url": "https://fisco.example/webhooks/mercado-pago",
        "back_urls": {
            "success": "https://fisco.example/checkout/sucesso",
            "failure": "https://fisco.example/checkout/falha",
            "pending": "https://fisco.example/checkout/pendente",
        },
    }
    resposta_valida = {
        "id": "mp-pref-one-time-91",
        "init_point": CHECKOUT_URL,
    }
    dados = {
        "ordem_id": 91,
        "user_id": 41,
        "empresa_id": 301,
        "offer_code": "document-one-time-company",
        "valor": Decimal("79.50"),
        "moeda": "BRL",
        "idempotency_key": "offer-one-time-order-91",
    }

    cliente = _ClientePreferenciasFalso(resposta=resposta_valida)
    gateway = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
        cliente_preferencias=cliente, **urls
    )
    resultado = gateway.criar_cobranca(**dados)

    assert cliente.chamadas == [{
        "payload": {
            "external_reference": "91",
            "items": [{
                "id": "document-one-time-company",
                "title": "document-one-time-company",
                "quantity": 1,
                "unit_price": 79.5,
                "currency_id": "BRL",
            }],
            "notification_url": urls["notification_url"],
            "back_urls": urls["back_urls"],
        },
        "idempotency_key": "offer-one-time-order-91",
    }]
    payload = cliente.chamadas[0]["payload"]
    unit_price = payload["items"][0]["unit_price"]
    assert type(unit_price) is float
    assert Decimal(str(unit_price)) == dados["valor"]
    assert resultado == {
        "provider_order_id": "mp-pref-one-time-91",
        "checkout_url": CHECKOUT_URL,
    }
    assert set(resultado) == {"provider_order_id", "checkout_url"}

    payload_serializado = repr(payload)
    for ausente in (
        "plano_id", "user_id", "empresa_id", "idempotency_key", "token",
        "credencial", "41", "301", "offer-one-time-order-91",
    ):
        assert ausente not in payload_serializado

    # A API nao admite nomes/precos do browser, dados de catalogo, estado ou
    # campos que pertencem exclusivamente a resposta do provedor.
    for extra in (
        {"preco": Decimal("0.01")}, {"title": "Nome mutavel"},
        {"nome_publico": "Nome comercial"},
        {"capabilities": ("document.extract",)},
        {"commercial_model": "one_time"}, {"plano_id": 7},
        {"provider_order_id": "browser-provider"},
        {"checkout_url": "https://browser.example.invalid"},
        {"status": "paid"}, {"estado": "paid"},
    ):
        cliente_extra = _ClientePreferenciasFalso(resposta=resposta_valida)
        gateway_extra = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
            cliente_preferencias=cliente_extra, **urls
        )
        with pytest.raises(TypeError):
            gateway_extra.criar_cobranca(**dados, **extra)
        assert cliente_extra.chamadas == []

    configuracoes_invalidas = (
        {**urls, "notification_url": "http://fisco.example/webhook"},
        {**urls, "notification_url": "https://user@fisco.example/webhook"},
        {**urls, "notification_url": "https://fisco.example/webhook#frag"},
        {**urls, "notification_url": "https://fisco.example/webhook\r\nx"},
        {**urls, "notification_url": ""},
        {**urls, "notification_url": None},
        {**urls, "back_urls": None},
        {**urls, "back_urls": {"success": urls["back_urls"]["success"]}},
        {**urls, "back_urls": {**urls["back_urls"], "cancel": "https://fisco.example/cancel"}},
        {**urls, "back_urls": {**urls["back_urls"], "success": "http://fisco.example/sucesso"}},
        {**urls, "back_urls": {**urls["back_urls"], "failure": "https://user@fisco.example/falha"}},
        {**urls, "back_urls": {**urls["back_urls"], "pending": "https://fisco.example/pendente#frag"}},
        {**urls, "back_urls": {**urls["back_urls"], "pending": "https://fisco.example/pendente\nx"}},
    )
    for configuracao in configuracoes_invalidas:
        cliente_invalido = _ClientePreferenciasFalso(resposta=resposta_valida)
        with pytest.raises(
            mercado_pago.MercadoPagoCheckoutOfferOneTimeError
        ) as capturada:
            mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
                cliente_preferencias=cliente_invalido, **configuracao
            )
        _assert_sanitizado(capturada.value, mercado_pago)
        assert cliente_invalido.chamadas == []

    cliente_sem_porta = object()
    with pytest.raises(
        mercado_pago.MercadoPagoCheckoutOfferOneTimeError
    ) as capturada:
        mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
            cliente_preferencias=cliente_sem_porta, **urls
        )
    _assert_sanitizado(capturada.value, mercado_pago)

    casos_invalidos = (
        {"ordem_id": 0}, {"ordem_id": -1}, {"ordem_id": True},
        {"ordem_id": "91"}, {"user_id": 0}, {"user_id": -1},
        {"user_id": True}, {"user_id": "41"}, {"empresa_id": 0},
        {"empresa_id": -1}, {"empresa_id": True}, {"empresa_id": "301"},
        {"offer_code": ""}, {"offer_code": " document-one-time-company"},
        {"offer_code": "DOCUMENT-one-time-company"},
        {"offer_code": "document_one_time_company"},
        {"offer_code": "document"}, {"offer_code": 123},
        {"valor": 79.50}, {"valor": 79}, {"valor": True},
        {"valor": Decimal("NaN")}, {"valor": Decimal("Infinity")},
        {"valor": Decimal("-Infinity")}, {"valor": Decimal("0.00")},
        {"valor": Decimal("-0.01")}, {"valor": Decimal("79.5")},
        {"valor": Decimal("79.500")}, {"moeda": "brl"},
        {"moeda": "USD"}, {"moeda": None}, {"idempotency_key": ""},
        {"idempotency_key": "   "}, {"idempotency_key": " key"},
        {"idempotency_key": "key "}, {"idempotency_key": "key\r\nx"},
        {"idempotency_key": 91},
    )
    for alteracao in casos_invalidos:
        cliente_invalido = _ClientePreferenciasFalso(resposta=resposta_valida)
        gateway_invalido = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
            cliente_preferencias=cliente_invalido, **urls
        )
        with pytest.raises(
            mercado_pago.MercadoPagoCheckoutOfferOneTimeError
        ) as capturada:
            gateway_invalido.criar_cobranca(**{**dados, **alteracao})
        _assert_sanitizado(capturada.value, mercado_pago)
        assert cliente_invalido.chamadas == []

    respostas_invalidas = (
        None,
        [],
        {},
        {"id": "mp-pref-one-time-91"},
        {"init_point": CHECKOUT_URL},
        {"id": "", "init_point": CHECKOUT_URL},
        {"id": 91, "init_point": CHECKOUT_URL},
        {"id": "mp-pref\r\nx", "init_point": CHECKOUT_URL},
        {"id": "mp-pref-one-time-91", "init_point": ""},
        {"id": "mp-pref-one-time-91", "init_point": 91},
        {"id": "mp-pref-one-time-91", "init_point": "http://mercadopago.com.br/checkout"},
        {"id": "mp-pref-one-time-91", "init_point": "https://mercadopago.com.br.evil.example/checkout"},
        {"id": "mp-pref-one-time-91", "init_point": "https://evil-mercadopago.com.br/checkout"},
        {"id": "mp-pref-one-time-91", "init_point": "https://user@mercadopago.com.br/checkout"},
        {"id": "mp-pref-one-time-91", "init_point": "https://mercadopago.com.br/checkout#fragmento"},
        {"id": "mp-pref-one-time-91", "init_point": "https://mercadopago.com.br/checkout\r\nx"},
    )
    for resposta in respostas_invalidas:
        cliente_invalido = _ClientePreferenciasFalso(resposta=resposta)
        gateway_invalido = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
            cliente_preferencias=cliente_invalido, **urls
        )
        with pytest.raises(
            mercado_pago.MercadoPagoCheckoutOfferOneTimeError
        ) as capturada:
            gateway_invalido.criar_cobranca(**dados)
        _assert_sanitizado(capturada.value, mercado_pago, resposta)
        assert len(cliente_invalido.chamadas) == 1

    resposta_raiz = {
        "id": "mp-pref-root-91",
        "init_point": "https://mercadopago.com.br/checkout/v1/redirect",
    }
    cliente_raiz = _ClientePreferenciasFalso(resposta=resposta_raiz)
    gateway_raiz = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
        cliente_preferencias=cliente_raiz, **urls
    )
    assert gateway_raiz.criar_cobranca(**dados) == {
        "provider_order_id": resposta_raiz["id"],
        "checkout_url": resposta_raiz["init_point"],
    }

    resposta_com_segredos = {
        **resposta_valida,
        "token": "provider-secret-token",
        "payload": {"preco": "79.50"},
        "credencial": "provider-secret-credential",
    }
    cliente_segredos = _ClientePreferenciasFalso(resposta=resposta_com_segredos)
    gateway_segredos = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
        cliente_preferencias=cliente_segredos, **urls
    )
    assert gateway_segredos.criar_cobranca(**dados) == {
        "provider_order_id": resposta_valida["id"],
        "checkout_url": resposta_valida["init_point"],
    }

    segredo = (
        "SELECT token=ultrassecreto payload={'preco':'79.50'} "
        "credencial secret SQL interno"
    )
    cliente_falho = _ClientePreferenciasFalso(erro=RuntimeError(segredo))
    gateway_falho = mercado_pago.MercadoPagoCheckoutOfferOneTimeGateway(
        cliente_preferencias=cliente_falho, **urls
    )
    with pytest.raises(
        mercado_pago.MercadoPagoCheckoutOfferOneTimeError
    ) as capturada:
        gateway_falho.criar_cobranca(**dados)
    _assert_sanitizado(capturada.value, mercado_pago, segredo, resposta_valida)
    assert len(cliente_falho.chamadas) == 1
