"""Contrato RED do futuro núcleo seguro de checkout.

O teste usa adaptadores mínimos em memória, mas importa e exercita o núcleo real.
Enquanto esse núcleo não existir, o RED deve ser exclusivamente ModuleNotFoundError.
"""

from decimal import Decimal
from importlib import import_module
from inspect import signature

import pytest


class _CatalogoCanonico:
    def __init__(self):
        self.consultas = []

    def obter_plano(self, plano_id):
        self.consultas.append(plano_id)
        assert plano_id == 7
        return {"id": 7, "preco": Decimal("49.90"), "moeda": "BRL"}


class _RepositorioEmMemoria:
    def __init__(self):
        self.ordens = []
        self.pagamentos = []


class _GatewayEspiao:
    def __init__(self):
        self.cobrancas = []

    def criar_cobranca(self, **dados):
        self.cobrancas.append(dados)
        return {
            "provider_order_id": "provider-order-1",
            "checkout_url": "https://provider.invalid/1",
        }


class _AtivadorEspiao:
    def __init__(self):
        self.ativacoes = []

    def ativar(self, **dados):
        self.ativacoes.append(dados)


class _VerificadorWebhookFalso:
    def __init__(self):
        self.resultado = False
        self.verificacoes = []

    def verificar(self, evento, assinatura):
        self.verificacoes.append((evento, assinatura))
        return self.resultado


def test_checkout_security_contract_refined_red():
    checkout = import_module("app.services.checkout_core")

    catalogo = _CatalogoCanonico()
    repositorio = _RepositorioEmMemoria()
    gateway = _GatewayEspiao()
    ativador = _AtivadorEspiao()
    verificador = _VerificadorWebhookFalso()
    core = checkout.CheckoutCore(
        catalogo=catalogo,
        repositorio=repositorio,
        gateway=gateway,
        ativador=ativador,
        verificador_webhook=verificador,
    )

    parametros = signature(core.iniciar_checkout).parameters
    assert tuple(parametros) == (
        "user_id",
        "empresa_id",
        "plano_id",
        "idempotency_key",
    )

    with pytest.raises(TypeError):
        core.iniciar_checkout(
            user_id=42,
            empresa_id=314,
            plano_id=7,
            idempotency_key="checkout-42-314-7",
            preco=Decimal("0.01"),
            moeda="USD",
        )
    assert gateway.cobrancas == []
    assert repositorio.ordens == []

    ordem = core.iniciar_checkout(
        user_id=42,
        empresa_id=314,
        plano_id=7,
        idempotency_key="checkout-42-314-7",
    )

    assert ordem.user_id == 42
    assert ordem.empresa_id == 314
    assert ordem.plano_id == 7
    assert ordem.valor == Decimal("49.90")
    assert ordem.moeda == "BRL"
    assert catalogo.consultas == [7]
    assert gateway.cobrancas[0]["valor"] == Decimal("49.90")
    assert gateway.cobrancas[0]["moeda"] == "BRL"

    mesma_ordem = core.iniciar_checkout(
        user_id=42,
        empresa_id=314,
        plano_id=7,
        idempotency_key="checkout-42-314-7",
    )
    assert mesma_ordem is ordem
    assert len(repositorio.ordens) == 1
    assert len(gateway.cobrancas) == 1

    cobrancas_antes = list(gateway.cobrancas)
    ativacoes_antes = list(ativador.ativacoes)
    with pytest.raises(checkout.AcessoOrdemNegadoError):
        core.consultar_ordem(
            ordem_id=ordem.id,
            user_id=99,
            empresa_id=314,
        )
    assert gateway.cobrancas == cobrancas_antes
    assert ativador.ativacoes == ativacoes_antes

    with pytest.raises(checkout.AcessoOrdemNegadoError):
        core.cancelar_ordem(
            ordem_id=ordem.id,
            user_id=99,
            empresa_id=314,
        )
    assert gateway.cobrancas == cobrancas_antes
    assert ativador.ativacoes == ativacoes_antes

    core.processar_retorno(
        provider_order_id="provider-order-1",
        status="paid",
    )
    assert ordem.status != "paid"
    assert repositorio.pagamentos == []
    assert ativador.ativacoes == []

    evento = {
        "event_id": "event-1",
        "provider_order_id": "provider-order-1",
        "status": "paid",
    }
    with pytest.raises(checkout.WebhookNaoAutenticadoError):
        core.processar_webhook(evento, assinatura="assinatura-invalida")
    assert verificador.verificacoes == [(evento, "assinatura-invalida")]
    assert ordem.status != "paid"
    assert repositorio.pagamentos == []
    assert ativador.ativacoes == []

    verificador.resultado = True
    core.processar_webhook(evento, assinatura="assinatura-valida")
    core.processar_webhook(evento, assinatura="assinatura-valida")

    assert ordem.status == "paid"
    assert len(gateway.cobrancas) == 1
    assert len(repositorio.pagamentos) == 1
    assert len(ativador.ativacoes) == 1
