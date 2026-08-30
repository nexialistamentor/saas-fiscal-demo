"""Contrato RED offline da persistencia duravel do checkout.

O primeiro ponto causal deste contrato e a importacao do modulo de producao futuro.
Nao existe fallback, repositorio em memoria ou mock que o substitua.
"""

from decimal import Decimal
from importlib import import_module

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


def test_payments_durable_ledger_contract_red():
    durable = import_module("app.services.checkout_durable_ledger")
    models = import_module("app.models")

    engine = create_engine("sqlite:///:memory:")
    durable.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    # Ownership real: o ledger opera sobre identidades canónicas persistidas.
    with Session.begin() as db:
        db.add(
            models.Plano(
                id=7,
                nome="Plano ledger",
                limite_cnpjs=3,
                limite_analises=100,
                preco=Decimal("49.90"),
            )
        )
        db.add_all(
            [
                models.User(
                    id=user_id,
                    email=f"ledger-{user_id}@example.invalid",
                    hashed_password="hash-de-teste",
                    plano_id=7,
                )
                for user_id in (42, 43, 44)
            ]
        )
        db.add_all(
            [
                models.Empresa(id=314, razao_social="Empresa 42", user_id=42),
                models.Empresa(id=315, razao_social="Empresa 43", user_id=43),
                models.Empresa(id=316, razao_social="Empresa 44", user_id=44),
            ]
        )

    dados = dict(
        user_id=42,
        empresa_id=314,
        plano_id=7,
        valor=Decimal("49.90"),
        moeda="BRL",
        idempotency_key="checkout-durable-42-314-7",
    )

    # Um empresa_id existente não autoriza um utilizador que não seja o owner.
    with Session.begin() as db:
        ledger = durable.CheckoutDurableLedger(db)
        with pytest.raises(durable.CheckoutDurableLedgerError) as capturada:
            ledger.criar_ou_obter_ordem(
                **(
                    dados
                    | {
                        "empresa_id": 315,
                        "idempotency_key": "checkout-owner-mismatch-42-315",
                    }
                )
            )
        _assert_erro_publico_sanitizado(capturada.value)
        assert db.scalar(
            select(durable.OrdemCheckout).where(
                durable.OrdemCheckout.idempotency_key
                == "checkout-owner-mismatch-42-315"
            )
        ) is None

    with Session.begin() as db:
        ledger = durable.CheckoutDurableLedger(db)
        ordem = ledger.criar_ou_obter_ordem(**dados)
        ordem_id = ordem.id
        assert ordem.user_id == 42
        assert ordem.empresa_id == 314
        assert ordem.plano_id == 7
        assert ordem.valor == Decimal("49.90")
        assert ordem.moeda == "BRL"
        assert ordem.estado == "pending"
        assert ordem.idempotency_key == dados["idempotency_key"]
        assert ordem.provider_order_id is None

        ordem = ledger.registrar_preferencia(
            ordem_id=ordem_id,
            user_id=42,
            empresa_id=314,
            provider_order_id="provider-order-4719",
            checkout_url="https://provider.invalid/checkout/4719",
        )
        assert ordem.provider_order_id == "provider-order-4719"

    # Nova sessao/unidade de trabalho: idempotencia e URL nao dependem da instancia.
    with Session.begin() as db:
        ledger = durable.CheckoutDurableLedger(db)
        mesma = ledger.criar_ou_obter_ordem(**dados)
        assert mesma.id == ordem_id
        assert ledger.consultar_ordem(ordem_id, user_id=42, empresa_id=314).id == ordem_id
        assert ledger.obter_checkout_url(ordem_id, user_id=42, empresa_id=314) == (
            "https://provider.invalid/checkout/4719"
        )

        for divergencia in (
            {"user_id": 99},
            {"empresa_id": 999},
            {"plano_id": 8},
            {"valor": Decimal("0.01")},
            {"moeda": "USD"},
        ):
            with pytest.raises(durable.CheckoutDurableLedgerError) as capturada:
                ledger.criar_ou_obter_ordem(**(dados | divergencia))
            _assert_erro_publico_sanitizado(capturada.value)

        for identidade in (
            {"user_id": 99, "empresa_id": 314},
            {"user_id": 42, "empresa_id": 999},
        ):
            with pytest.raises(durable.CheckoutDurableLedgerError):
                ledger.consultar_ordem(ordem_id, **identidade)
            with pytest.raises(durable.CheckoutDurableLedgerError):
                ledger.obter_checkout_url(ordem_id, **identidade)
            with pytest.raises(durable.CheckoutDurableLedgerError):
                ledger.confirmar_pagamento_aprovado(
                    ordem_id=ordem_id,
                    notification_id="8128",
                    payment_id="4719",
                    **identidade,
                )

        outra = ledger.criar_ou_obter_ordem(
            user_id=43,
            empresa_id=315,
            plano_id=7,
            valor=Decimal("49.90"),
            moeda="BRL",
            idempotency_key="checkout-durable-43-315-7",
        )
        outra_id = outra.id
        with pytest.raises(durable.CheckoutDurableLedgerError):
            ledger.registrar_preferencia(
                ordem_id=outra_id,
                user_id=43,
                empresa_id=315,
                provider_order_id="provider-order-4719",
                checkout_url="https://provider.invalid/checkout/collision",
            )
        assert ledger.consultar_ordem(outra_id, user_id=43, empresa_id=315).provider_order_id is None

    with Session.begin() as db:
        ledger = durable.CheckoutDurableLedger(db)
        confirmado = ledger.confirmar_pagamento_aprovado(
            ordem_id=ordem_id,
            user_id=42,
            empresa_id=314,
            notification_id="8128",
            payment_id="4719",
        )
        assert confirmado.estado == "paid"
        assert confirmado.payment_id == "4719"

    def contagens(db):
        return (
            len(db.scalars(select(durable.RegistroFinanceiro)).all()),
            len(db.scalars(select(durable.Entitlement)).all()),
            len(db.scalars(select(durable.EventoPagamento)).all()),
        )

    with Session.begin() as db:
        assert contagens(db) == (1, 1, 1)
        entitlement = db.scalars(select(durable.Entitlement)).one()
        assert entitlement.ordem_id == ordem_id
        assert entitlement.user_id == 42
        assert entitlement.empresa_id == 314
        assert entitlement.plano_id == 7
        assert entitlement.estado == "active"

        ledger = durable.CheckoutDurableLedger(db)
        retry = ledger.confirmar_pagamento_aprovado(
            ordem_id=ordem_id,
            user_id=42,
            empresa_id=314,
            notification_id="8128",
            payment_id="4719",
        )
        assert retry.id == ordem_id
        assert contagens(db) == (1, 1, 1)

        # Notificações distintas do mesmo pagamento são eventos de auditoria
        # distintos, sem repetir os efeitos financeiros ou o entitlement.
        nova_notificacao = ledger.confirmar_pagamento_aprovado(
            ordem_id=ordem_id,
            user_id=42,
            empresa_id=314,
            notification_id="8130",
            payment_id="4719",
        )
        assert nova_notificacao.id == ordem_id
        assert contagens(db) == (1, 1, 2)
        assert {
            evento.notification_id
            for evento in db.scalars(
                select(durable.EventoPagamento).where(
                    durable.EventoPagamento.ordem_id == ordem_id,
                    durable.EventoPagamento.payment_id == "4719",
                )
            )
        } == {"8128", "8130"}

        retry_nova_notificacao = ledger.confirmar_pagamento_aprovado(
            ordem_id=ordem_id,
            user_id=42,
            empresa_id=314,
            notification_id="8130",
            payment_id="4719",
        )
        assert retry_nova_notificacao.id == ordem_id
        assert contagens(db) == (1, 1, 2)

        for colisao in (
            dict(ordem_id=outra_id, user_id=43, empresa_id=315,
                 notification_id="8128", payment_id="9999"),
            dict(ordem_id=outra_id, user_id=43, empresa_id=315,
                 notification_id="9999", payment_id="4719"),
        ):
            with pytest.raises(durable.CheckoutDurableLedgerError):
                ledger.confirmar_pagamento_aprovado(**colisao)
        assert contagens(db) == (1, 1, 2)

        # request_id e dado de transporte, nunca identidade publica do evento.
        with pytest.raises(TypeError):
            ledger.confirmar_pagamento_aprovado(
                ordem_id=outra_id,
                user_id=43,
                empresa_id=315,
                request_id="request-9931",
                payment_id="9999",
            )

    # Falha fisica no ultimo efeito deve reverter pagamento, entitlement e evento.
    with Session.begin() as db:
        ledger = durable.CheckoutDurableLedger(db)
        terceira = ledger.criar_ou_obter_ordem(
            user_id=44, empresa_id=316, plano_id=7,
            valor=Decimal("49.90"), moeda="BRL",
            idempotency_key="checkout-durable-atomic-44",
        )
        terceira_id = terceira.id
        ledger.registrar_preferencia(
            ordem_id=terceira_id, user_id=44, empresa_id=316,
            provider_order_id="provider-order-atomic",
            checkout_url="https://provider.invalid/checkout/atomic",
        )

    def falhar_entitlement(_mapper, _connection, _target):
        raise RuntimeError("token=segredo payload=interno")

    event.listen(durable.Entitlement, "before_insert", falhar_entitlement)
    try:
        with pytest.raises(durable.CheckoutDurableLedgerError) as capturada:
            with Session.begin() as db:
                durable.CheckoutDurableLedger(db).confirmar_pagamento_aprovado(
                    ordem_id=terceira_id, user_id=44, empresa_id=316,
                    notification_id="8129",
                    payment_id="4720",
                )
        _assert_erro_publico_sanitizado(capturada.value, "segredo", "interno")
    finally:
        event.remove(durable.Entitlement, "before_insert", falhar_entitlement)

    with Session.begin() as db:
        ordem_integra = db.get(durable.OrdemCheckout, terceira_id)
        assert ordem_integra.estado == "pending"
        assert ordem_integra.payment_id is None
        assert contagens(db) == (1, 1, 2)

        # O entitlement possui ciclo persistente próprio, sem pressupor aqui
        # qualquer implementação de refund ou chargeback.
        entitlement = db.scalars(select(durable.Entitlement)).one()
        entitlement.estado = "under_review"
        db.flush()
        assert db.get(durable.Entitlement, entitlement.id).estado == "under_review"
        entitlement.estado = "suspended"
        db.flush()
        assert db.get(durable.Entitlement, entitlement.id).estado == "suspended"

    with Session.begin() as db:
        entitlement = db.scalars(select(durable.Entitlement)).one()
        assert entitlement.estado == "suspended"
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                entitlement.estado = "estado-fora-do-contrato"
                db.flush()


def _assert_erro_publico_sanitizado(erro, *proibidos):
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in ("token", "payload", "segredo", "credencial", "interno"):
            assert marcador not in texto
        for proibido in proibidos:
            assert proibido.lower() not in texto
