"""Contrato RED da confirmação interna de pagamento já autenticado."""

from decimal import Decimal
from inspect import signature

import pytest

from app.services import checkout_core as checkout


CHECKOUT_URL = "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=trusted"


class _Catalogo:
    def obter_plano(self, plano_id):
        return {"id": plano_id, "preco": Decimal("49.90"), "moeda": "BRL"}


class _Repositorio:
    def __init__(self):
        self.ordens = []
        self.pagamentos = []


class _Gateway:
    def __init__(self):
        self.cobrancas = []
        self.cancelamentos = []

    def criar_cobranca(self, **dados):
        self.cobrancas.append(dados)
        return {
            "provider_order_id": f"provider-{dados['ordem_id']}",
            "checkout_url": CHECKOUT_URL,
        }

    def cancelar_cobranca(self, **dados):
        self.cancelamentos.append(dados)


class _Ativador:
    def __init__(self):
        self.ativacoes = []

    def ativar(self, **dados):
        self.ativacoes.append(dados)


class _VerificadorNaoUtilizavel:
    def verificar(self, *_args, **_kwargs):
        raise AssertionError("a confirmação interna não deve validar webhook")


def _core():
    repositorio = _Repositorio()
    gateway = _Gateway()
    ativador = _Ativador()
    core = checkout.CheckoutCore(
        catalogo=_Catalogo(),
        repositorio=repositorio,
        gateway=gateway,
        ativador=ativador,
        verificador_webhook=_VerificadorNaoUtilizavel(),
    )
    return core, repositorio, gateway, ativador


def _criar_ordem(core, sufixo):
    return core.iniciar_checkout(
        user_id=100 + sufixo,
        empresa_id=200 + sufixo,
        plano_id=7,
        idempotency_key=f"trusted-confirmation-{sufixo}",
    )


def _estado(repositorio, gateway, ativador):
    return (
        list(repositorio.ordens),
        [(ordem.status, ordem.__dict__.copy()) for ordem in repositorio.ordens],
        list(repositorio.pagamentos),
        list(gateway.cobrancas),
        list(gateway.cancelamentos),
        list(ativador.ativacoes),
    )


def _assert_sem_checkout_url(*registos):
    for registo in registos:
        assert not hasattr(registo, "checkout_url")
        assert "checkout_url" not in repr(registo)
        assert CHECKOUT_URL not in repr(registo)


def test_trusted_payment_confirmation_contract_red():
    core, repositorio, gateway, ativador = _core()
    confirmar = getattr(core, "confirmar_pagamento_autorizado", None)
    assert callable(confirmar), (
        "CheckoutCore deve implementar o método interno explícito "
        "confirmar_pagamento_autorizado(ordem_id, event_id)"
    )
    assert tuple(signature(confirmar).parameters) == ("ordem_id", "event_id")

    ordem = _criar_ordem(core, 1)
    for ordem_id, event_id in (
        (None, "event-valid"),
        (True, "event-valid"),
        (0, "event-valid"),
        (-1, "event-valid"),
        (ordem.id, None),
        (ordem.id, 1),
        (ordem.id, ""),
        (ordem.id, "   "),
        (ordem.id, "event\rforjado"),
        (ordem.id, "event\nforjado"),
    ):
        antes = _estado(repositorio, gateway, ativador)
        with pytest.raises(checkout.CheckoutError):
            confirmar(ordem_id, event_id)
        assert _estado(repositorio, gateway, ativador) == antes

    core_inexistente, repo_inexistente, gateway_inexistente, ativador_inexistente = (
        _core()
    )
    with pytest.raises(checkout.CheckoutError):
        core_inexistente.confirmar_pagamento_autorizado(999, "event-inexistente")
    assert repo_inexistente.ordens == []
    assert repo_inexistente.pagamentos == []
    assert ativador_inexistente.ativacoes == []
    assert gateway_inexistente.cobrancas == []
    with pytest.raises(checkout.CheckoutError):
        core_inexistente.obter_checkout_url(999, 1, 1)

    confirmada = confirmar(ordem.id, "event-paid-1")
    assert confirmada is ordem
    assert ordem.status == "paid"
    assert len(repositorio.pagamentos) == 1
    pagamento = repositorio.pagamentos[0]
    assert pagamento.ordem_id == ordem.id
    assert pagamento.event_id == "event-paid-1"
    assert pagamento.valor == ordem.valor
    assert pagamento.moeda == ordem.moeda
    assert len(ativador.ativacoes) == 1
    with pytest.raises(checkout.CheckoutError):
        core.obter_checkout_url(ordem.id, ordem.user_id, ordem.empresa_id)
    _assert_sem_checkout_url(ordem, pagamento)
    assert all("checkout_url" not in ativacao for ativacao in ativador.ativacoes)
    assert all(CHECKOUT_URL not in repr(ativacao) for ativacao in ativador.ativacoes)

    estado_confirmado = _estado(repositorio, gateway, ativador)
    assert confirmar(ordem.id, "event-paid-1") is ordem
    assert _estado(repositorio, gateway, ativador) == estado_confirmado

    outra_ordem = _criar_ordem(core, 2)
    antes_colisao = _estado(repositorio, gateway, ativador)
    with pytest.raises(checkout.CheckoutError):
        confirmar(outra_ordem.id, "event-paid-1")
    assert _estado(repositorio, gateway, ativador) == antes_colisao
    assert outra_ordem.status == "pending"

    cancelada = _criar_ordem(core, 3)
    core.cancelar_ordem(cancelada.id, cancelada.user_id, cancelada.empresa_id)
    antes_cancelada = _estado(repositorio, gateway, ativador)
    with pytest.raises(checkout.CheckoutError):
        confirmar(cancelada.id, "event-cancelled")
    assert _estado(repositorio, gateway, ativador) == antes_cancelada
    assert cancelada.status == "cancelled"
    with pytest.raises(checkout.CheckoutError):
        core.obter_checkout_url(
            cancelada.id,
            cancelada.user_id,
            cancelada.empresa_id,
        )

    _assert_sem_checkout_url(*repositorio.ordens, *repositorio.pagamentos)
    assert all("checkout_url" not in ativacao for ativacao in ativador.ativacoes)
