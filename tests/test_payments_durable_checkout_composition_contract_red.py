"""Contrato RED offline da composicao sincrona e duravel do checkout.

O primeiro ponto causal e a importacao direta do modulo futuro. Nao existe
fallback, mock desse modulo, router, SDK, rede, credencial ou webhook.
"""

from decimal import Decimal
from importlib import import_module

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SASession, sessionmaker
from sqlalchemy.pool import StaticPool


CHECKOUT_URL = "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=4719"


class _CatalogoCanonico:
    def __init__(self, erro=None):
        self.erro = erro
        self.consultas = []

    def obter_plano(self, plano_id):
        self.consultas.append(plano_id)
        if self.erro is not None:
            raise self.erro
        return {"id": plano_id, "preco": Decimal("49.90"), "moeda": "BRL"}


class _SessionRastreada(SASession):
    eventos = []
    falhar_depois_do_commit_numero = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.numero = 1 + sum(evento[0] == "open" for evento in self.eventos)
        self.eventos.append(("open", self.numero))

    def commit(self):
        super().commit()
        self.eventos.append(("commit", self.numero))
        if self.falhar_depois_do_commit_numero == self.numero:
            raise RuntimeError("token payload segredo interno depois do commit")

    def rollback(self):
        self.eventos.append(("rollback", self.numero))
        return super().rollback()

    def close(self):
        self.eventos.append(("close", self.numero))
        return super().close()


class _GatewayDuravelFalso:
    """Preferencias logicas idempotentes, sem transporte externo."""

    def __init__(self, Session, models, *, falhar_antes=False, falhar_depois=False):
        self.Session = Session
        self.models = models
        self.falhar_antes = falhar_antes
        self.falhar_depois = falhar_depois
        self.chamadas = []
        self.preferencias = {}
        self.criacoes_fisicas = 0

    def criar_cobranca(self, **dados):
        with self.Session() as db:
            ordem = db.get(self.models.OrdemCheckout, dados["ordem_id"])
            assert ordem is not None
            assert ordem.estado == "pending"
            assert ordem.provider_order_id is None
            assert ordem.checkout_url is None
        self.chamadas.append(dados)
        if self.falhar_antes:
            raise RuntimeError("token payload segredo interno antes do provedor")
        resposta = self.preferencias.get(dados["idempotency_key"])
        if resposta is None:
            self.criacoes_fisicas += 1
            resposta = {
                "provider_order_id": f"mp-pref-{self.criacoes_fisicas}",
                "checkout_url": CHECKOUT_URL,
            }
            self.preferencias[dados["idempotency_key"]] = resposta
        if self.falhar_depois:
            self.falhar_depois = False
            raise RuntimeError("token payload segredo interno depois do provedor")
        return dict(resposta)


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    _SessionRastreada.eventos = []
    _SessionRastreada.falhar_depois_do_commit_numero = None
    Session = sessionmaker(
        bind=engine,
        class_=_SessionRastreada,
        expire_on_commit=False,
    )
    with Session.begin() as db:
        db.add(models.Plano(id=7, nome="Plano", limite_cnpjs=3,
                            limite_analises=100, preco=Decimal("49.90")))
        db.add(models.User(id=42, email="checkout@example.invalid",
                           hashed_password="hash", plano_id=7))
        db.add(models.Empresa(id=314, razao_social="Empresa", user_id=42))
    _SessionRastreada.eventos = []
    return Session


def _dados(**alteracoes):
    return {
        "user_id": 42,
        "empresa_id": 314,
        "plano_id": 7,
        "preco": Decimal("0.01"),
        "moeda": "USD",
        "idempotency_key": "checkout-durable-composition-42",
    } | alteracoes


def _ordem(Session, models):
    with Session() as db:
        return db.scalar(select(models.OrdemCheckout))


def _assert_pending_limpa(ordem):
    assert ordem is not None
    assert ordem.estado == "pending"
    assert ordem.provider_order_id is None
    assert ordem.checkout_url is None


def _assert_sanitizado(erro, *proibidos):
    assert type(erro).__name__ == "CheckoutDurableCheckoutCompositionError"
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in ("token", "payload", "segredo", "credencial", "interno"):
            assert marcador not in texto
        for proibido in proibidos:
            assert str(proibido).lower() not in texto


def test_payments_durable_checkout_composition_contract_red(monkeypatch):
    composition = import_module("app.services.checkout_durable_composition")
    durable = import_module("app.services.checkout_durable_ledger")
    models = import_module("app.models")

    erro_publico = composition.CheckoutDurableCheckoutCompositionError
    assert issubclass(erro_publico, Exception)

    # O ledger delimita operacoes; somente o compositor controla transacoes.
    def commit_proibido(_self):
        raise AssertionError("CheckoutDurableLedger nao pode executar commit")

    monkeypatch.setattr(durable.CheckoutDurableLedger, "commit", commit_proibido,
                        raising=False)

    Session = _ambiente(models)
    catalogo = _CatalogoCanonico()
    gateway = _GatewayDuravelFalso(Session, models)
    composer = composition.CheckoutDurableCheckoutComposer(
        session_factory=Session, catalogo=catalogo, gateway=gateway
    )
    entrega = composer.iniciar_checkout(**_dados())

    assert set(entrega) == {"ordem", "checkout_url"}
    assert entrega["checkout_url"] == CHECKOUT_URL
    ordem = entrega["ordem"]
    assert ordem.user_id == 42
    assert ordem.empresa_id == 314
    assert ordem.plano_id == 7
    assert ordem.valor == Decimal("49.90")
    assert ordem.moeda == "BRL"
    assert ordem.provider_order_id == "mp-pref-1"
    assert ordem.checkout_url == CHECKOUT_URL
    assert catalogo.consultas == [7]
    assert gateway.chamadas == [{
        "ordem_id": ordem.id,
        "user_id": 42,
        "empresa_id": 314,
        "plano_id": 7,
        "valor": Decimal("49.90"),
        "moeda": "BRL",
        "idempotency_key": "checkout-durable-composition-42",
    }]
    eventos = _SessionRastreada.eventos
    primeira_chamada_gateway = eventos.index(("open", 2))
    assert eventos.index(("commit", 1)) < primeira_chamada_gateway
    assert eventos.index(("close", 1)) < primeira_chamada_gateway
    assert eventos.index(("open", 3)) > primeira_chamada_gateway
    assert eventos.index(("commit", 3)) < eventos.index(("close", 3))

    eventos_antes = list(eventos)
    mesma_entrega = composer.iniciar_checkout(**_dados())
    assert mesma_entrega["ordem"].id == ordem.id
    assert mesma_entrega["checkout_url"] == CHECKOUT_URL
    assert len(gateway.chamadas) == 1
    assert len(_SessionRastreada.eventos) > len(eventos_antes)

    for divergencia in (
        {"user_id": 43}, {"empresa_id": 315}, {"plano_id": 8}
    ):
        chamadas_antes = list(gateway.chamadas)
        with pytest.raises(erro_publico) as capturada:
            composer.iniciar_checkout(**_dados(**divergencia))
        _assert_sanitizado(capturada.value)
        assert gateway.chamadas == chamadas_antes

    # Falhar dentro da chamada ao gateway preserva a fase A ja confirmada.
    Session = _ambiente(models)
    gateway = _GatewayDuravelFalso(Session, models, falhar_antes=True)
    composer = composition.CheckoutDurableCheckoutComposer(
        Session, _CatalogoCanonico(), gateway
    )
    with pytest.raises(erro_publico) as capturada:
        composer.iniciar_checkout(**_dados())
    _assert_sanitizado(capturada.value)
    _assert_pending_limpa(_ordem(Session, models))
    assert any(nome == "rollback" for nome, _ in _SessionRastreada.eventos)
    assert all(
        ("close", numero) in _SessionRastreada.eventos
        for nome, numero in _SessionRastreada.eventos if nome == "open"
    )

    # O provedor criou a preferencia, mas a resposta perdeu-se antes da fase B.
    Session = _ambiente(models)
    gateway = _GatewayDuravelFalso(Session, models, falhar_depois=True)
    composer = composition.CheckoutDurableCheckoutComposer(
        Session, _CatalogoCanonico(), gateway
    )
    with pytest.raises(erro_publico):
        composer.iniciar_checkout(**_dados())
    _assert_pending_limpa(_ordem(Session, models))
    recuperada = composer.iniciar_checkout(**_dados())
    assert recuperada["checkout_url"] == CHECKOUT_URL
    assert len(gateway.chamadas) == 2
    assert {c["idempotency_key"] for c in gateway.chamadas} == {
        "checkout-durable-composition-42"
    }
    assert gateway.criacoes_fisicas == 1

    # Queda depois do commit da fase B: o retry le exclusivamente o duravel.
    Session = _ambiente(models)
    gateway = _GatewayDuravelFalso(Session, models)
    composer = composition.CheckoutDurableCheckoutComposer(
        Session, _CatalogoCanonico(), gateway
    )
    _SessionRastreada.falhar_depois_do_commit_numero = 3
    with pytest.raises(erro_publico) as capturada:
        composer.iniciar_checkout(**_dados())
    _assert_sanitizado(capturada.value)
    persistida = _ordem(Session, models)
    assert persistida.provider_order_id == "mp-pref-1"
    assert persistida.checkout_url == CHECKOUT_URL
    chamadas_antes = list(gateway.chamadas)
    _SessionRastreada.falhar_depois_do_commit_numero = None
    entrega_retry = composer.iniciar_checkout(**_dados())
    assert entrega_retry["checkout_url"] == CHECKOUT_URL
    assert gateway.chamadas == chamadas_antes

    # Falha anterior a qualquer gateway nao vaza detalhes e fecha a sessao.
    Session = _ambiente(models)
    catalogo = _CatalogoCanonico(RuntimeError("token payload segredo interno"))
    gateway = _GatewayDuravelFalso(Session, models)
    composer = composition.CheckoutDurableCheckoutComposer(Session, catalogo, gateway)
    with pytest.raises(erro_publico) as capturada:
        composer.iniciar_checkout(**_dados())
    _assert_sanitizado(capturada.value)
    assert gateway.chamadas == []
    assert _ordem(Session, models) is None
    assert all(
        ("close", numero) in _SessionRastreada.eventos
        for nome, numero in _SessionRastreada.eventos if nome == "open"
    )
