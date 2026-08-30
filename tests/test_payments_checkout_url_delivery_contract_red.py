"""Contrato RED da entrega segura da checkout_url pelo CheckoutCore real."""

from decimal import Decimal

import pytest

from app.services import checkout_core as checkout


CHECKOUT_URL = "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=123"


class _Catalogo:
    def obter_plano(self, plano_id):
        return {"id": plano_id, "preco": Decimal("49.90"), "moeda": "BRL"}


class _Repositorio:
    def __init__(self):
        self.ordens = []
        self.pagamentos = []


class _GatewayMercadoPagoFalso:
    def __init__(self):
        self.cobrancas = []

    def criar_cobranca(self, **dados):
        self.cobrancas.append(dados)
        return {
            "provider_order_id": "mp-provider-order-123",
            "checkout_url": CHECKOUT_URL,
        }


class _Ativador:
    def __init__(self):
        self.ativacoes = []

    def ativar(self, **dados):
        self.ativacoes.append(dados)


class _VerificadorWebhookAutenticado:
    def verificar(self, _evento, _assinatura):
        return True


def _assert_checkout_url_ausente(registos):
    for registo in registos:
        assert not hasattr(registo, "checkout_url")
        assert CHECKOUT_URL not in repr(registo)


def test_checkout_url_delivery_contract_red():
    repositorio = _Repositorio()
    gateway = _GatewayMercadoPagoFalso()
    ativador = _Ativador()
    core = checkout.CheckoutCore(
        catalogo=_Catalogo(),
        repositorio=repositorio,
        gateway=gateway,
        ativador=ativador,
        verificador_webhook=_VerificadorWebhookAutenticado(),
    )

    dados_checkout = {
        "user_id": 42,
        "empresa_id": 314,
        "plano_id": 7,
        "idempotency_key": "checkout-url-delivery-1",
    }
    ordem = core.iniciar_checkout(**dados_checkout)

    _assert_checkout_url_ausente([ordem, *repositorio.ordens])
    assert repositorio.pagamentos == []
    assert ativador.ativacoes == []
    assert len(gateway.cobrancas) == 1

    obter_checkout_url = getattr(core, "obter_checkout_url", None)
    assert callable(obter_checkout_url), (
        "CheckoutCore deve disponibilizar obter_checkout_url(ordem_id, user_id, "
        "empresa_id)"
    )

    url = obter_checkout_url(
        ordem_id=ordem.id,
        user_id=42,
        empresa_id=314,
    )
    assert url == CHECKOUT_URL

    for identidade_divergente in (
        {"user_id": 99, "empresa_id": 314},
        {"user_id": 42, "empresa_id": 999},
    ):
        cobrancas_antes = list(gateway.cobrancas)
        ativacoes_antes = list(ativador.ativacoes)
        with pytest.raises(checkout.CheckoutError):
            obter_checkout_url(ordem_id=ordem.id, **identidade_divergente)
        assert gateway.cobrancas == cobrancas_antes
        assert ativador.ativacoes == ativacoes_antes

    mesma_ordem = core.iniciar_checkout(**dados_checkout)
    assert mesma_ordem is ordem
    assert len(gateway.cobrancas) == 1
    assert obter_checkout_url(
        ordem_id=mesma_ordem.id,
        user_id=42,
        empresa_id=314,
    ) == CHECKOUT_URL

    core.processar_webhook(
        {
            "event_id": "mp-event-paid-123",
            "provider_order_id": "mp-provider-order-123",
            "status": "paid",
        },
        assinatura="assinatura-autenticada",
    )

    with pytest.raises(checkout.CheckoutError):
        obter_checkout_url(
            ordem_id=ordem.id,
            user_id=42,
            empresa_id=314,
        )

    _assert_checkout_url_ausente([ordem, *repositorio.ordens])
    _assert_checkout_url_ausente(repositorio.pagamentos)
    assert len(ativador.ativacoes) == 1
    assert all("checkout_url" not in ativacao for ativacao in ativador.ativacoes)
    assert all(CHECKOUT_URL not in repr(ativacao) for ativacao in ativador.ativacoes)
    assert len(gateway.cobrancas) == 1
