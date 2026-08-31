"""Contrato RED offline da confirmacao duravel de webhook autenticado."""

from decimal import Decimal
from importlib import import_module
from inspect import signature

import pytest
from sqlalchemy import create_engine, event, inspect as sa_inspect, select
from sqlalchemy.orm import Session as SASession, sessionmaker
from sqlalchemy.pool import StaticPool


class _SessionRastreada(SASession):
    eventos = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.numero = 1 + sum(nome == "open" for nome, _ in self.eventos)
        self.eventos.append(("open", self.numero))

    def commit(self):
        self.eventos.append(("commit", self.numero))
        return super().commit()

    def rollback(self):
        self.eventos.append(("rollback", self.numero))
        return super().rollback()

    def close(self):
        self.eventos.append(("close", self.numero))
        return super().close()


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine,
        class_=_SessionRastreada,
        expire_on_commit=True,
    )
    with Session.begin() as db:
        db.add(models.Plano(
            id=7, nome="Plano", limite_cnpjs=3,
            limite_analises=100, preco=Decimal("49.90"),
        ))
        db.add_all([
            models.User(id=42, email="owner@example.invalid",
                        hashed_password="hash", plano_id=7),
            models.User(id=43, email="other@example.invalid",
                        hashed_password="hash", plano_id=7),
        ])
        db.add_all([
            models.Empresa(id=314, razao_social="Empresa owner", user_id=42),
            models.Empresa(id=315, razao_social="Empresa other", user_id=43),
        ])
        db.add_all([
            models.OrdemCheckout(
                id=91, user_id=42, empresa_id=314, plano_id=7,
                valor=Decimal("49.90"), moeda="BRL", estado="pending",
                idempotency_key="webhook-confirmation-91",
            ),
            models.OrdemCheckout(
                id=92, user_id=43, empresa_id=315, plano_id=7,
                valor=Decimal("49.90"), moeda="BRL", estado="pending",
                idempotency_key="webhook-confirmation-92",
            ),
        ])
    _SessionRastreada.eventos = []
    return Session


def _contagens(db, models):
    return tuple(len(db.scalars(select(modelo)).all()) for modelo in (
        models.Pagamento, models.EventoPagamento, models.Entitlement,
    ))


def _assert_sanitizado(erro, *proibidos):
    assert type(erro).__name__ == "CheckoutDurableWebhookConfirmationError"
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in ("token", "payload", "segredo", "credencial", "interno"):
            assert marcador not in texto
        for proibido in proibidos:
            assert str(proibido).lower() not in texto


def _assert_todas_fechadas():
    eventos = _SessionRastreada.eventos
    assert all(
        ("close", numero) in eventos
        for nome, numero in eventos if nome == "open"
    )


def test_payments_durable_webhook_confirmation_contract_red(monkeypatch):
    confirmation = import_module(
        "app.services.checkout_durable_webhook_confirmation"
    )
    durable = import_module("app.services.checkout_durable_ledger")
    models = import_module("app.models")

    metodo = confirmation.CheckoutDurableWebhookConfirmer.confirmar_pagamento_autorizado
    assert list(signature(confirmation.CheckoutDurableWebhookConfirmer).parameters) == [
        "session_factory"
    ]
    assert list(signature(metodo).parameters) == [
        "self", "ordem_id", "notification_id", "payment_id"
    ]

    chamadas = []
    confirmar_real = durable.CheckoutDurableLedger.confirmar_pagamento_aprovado

    def confirmar_espiado(self, *args, **kwargs):
        chamadas.append((args, kwargs))
        return confirmar_real(self, *args, **kwargs)

    monkeypatch.setattr(
        durable.CheckoutDurableLedger,
        "confirmar_pagamento_aprovado",
        confirmar_espiado,
    )

    Session = _ambiente(models)
    confirmer = confirmation.CheckoutDurableWebhookConfirmer(Session)
    resposta = confirmer.confirmar_pagamento_autorizado(91, "8128", "4719")
    assert chamadas == [((), {
        "ordem_id": 91,
        "user_id": 42,
        "empresa_id": 314,
        "notification_id": "8128",
        "payment_id": "4719",
    })]
    assert sa_inspect(resposta, raiseerr=False) is None
    str(resposta)
    repr(resposta)
    assert ("commit", 1) in _SessionRastreada.eventos
    assert _SessionRastreada.eventos.index(("commit", 1)) < (
        _SessionRastreada.eventos.index(("close", 1))
    )
    _assert_todas_fechadas()

    with Session() as db:
        ordem = db.get(models.OrdemCheckout, 91)
        assert (ordem.estado, ordem.payment_id) == ("paid", "4719")
        pagamento = db.scalars(select(models.Pagamento)).one()
        evento_pagamento = db.scalars(select(models.EventoPagamento)).one()
        entitlement = db.scalars(select(models.Entitlement)).one()
        assert pagamento.ordem_checkout_id == 91
        assert pagamento.user_id == 42
        assert evento_pagamento.ordem_id == 91
        assert entitlement.ordem_id == 91
        assert entitlement.user_id == 42
        assert entitlement.empresa_id == 314
        assert _contagens(db, models) == (1, 1, 1)

    # Nova instancia e nova sessao preservam a idempotencia duravel.
    confirmation.CheckoutDurableWebhookConfirmer(Session).confirmar_pagamento_autorizado(
        91, "8128", "4719"
    )
    with Session() as db:
        assert _contagens(db, models) == (1, 1, 1)

    erro_publico = confirmation.CheckoutDurableWebhookConfirmationError
    for argumentos in (
        (91, "8128", "4720"),       # notification_id com outro payment_id
        (92, "8129", "4719"),       # payment_id ligado a outra ordem
        (999, "8130", "4721"),      # ordem inexistente
    ):
        with pytest.raises(erro_publico) as capturada:
            confirmation.CheckoutDurableWebhookConfirmer(
                Session
            ).confirmar_pagamento_autorizado(*argumentos)
        _assert_sanitizado(capturada.value)
    _assert_todas_fechadas()

    chamadas_antes = list(chamadas)
    invalidos = (
        (True, "8131", "4722"),
        (91.0, "8131", "4722"),
        ("91", "8131", "4722"),
        (0, "8131", "4722"),
        (-1, "8131", "4722"),
        (92, True, "4722"),
        (92, 8131, "4722"),
        (92, "08131", "4722"),
        (92, "8131\n", "4722"),
        (92, "8131", True),
        (92, "8131", 4722),
        (92, "8131", "04722"),
        (92, "8131", "4722 "),
    )
    for argumentos in invalidos:
        with pytest.raises(erro_publico):
            confirmation.CheckoutDurableWebhookConfirmer(
                Session
            ).confirmar_pagamento_autorizado(*argumentos)
    assert chamadas == chamadas_antes

    for identidade in ("user_id", "empresa_id"):
        with pytest.raises(TypeError):
            confirmer.confirmar_pagamento_autorizado(
                92, "8131", "4722", **{identidade: 999}
            )

    segredo = "segredo-ultrassecreto-9931"

    def falhar_entitlement(_mapper, _connection, _target):
        raise RuntimeError(f"token payload credencial interno {segredo}")

    event.listen(models.Entitlement, "before_insert", falhar_entitlement)
    try:
        with pytest.raises(erro_publico) as capturada:
            confirmation.CheckoutDurableWebhookConfirmer(
                Session
            ).confirmar_pagamento_autorizado(92, "8131", "4722")
        _assert_sanitizado(capturada.value, segredo)
    finally:
        event.remove(models.Entitlement, "before_insert", falhar_entitlement)

    assert any(nome == "rollback" for nome, _ in _SessionRastreada.eventos)
    _assert_todas_fechadas()
    with Session() as db:
        ordem = db.get(models.OrdemCheckout, 92)
        assert (ordem.estado, ordem.payment_id) == ("pending", None)
        assert _contagens(db, models) == (1, 1, 1)
