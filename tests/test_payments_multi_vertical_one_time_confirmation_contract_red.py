"""Contrato RED offline da confirmacao atomica de oferta one_time.

O primeiro ponto causal deste unico node e a importacao direta do modulo
futuro. Nenhum fixture ou efeito de banco ocorre antes dessa importacao.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from inspect import Parameter, signature

import pytest
from sqlalchemy import create_engine, event, func, inspect as sa_inspect, select, text
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

    @event.listens_for(engine, "connect")
    def _ativar_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine, class_=_SessionRastreada, expire_on_commit=True
    )
    with Session.begin() as db:
        plano_legado = models.Plano(
            id=7,
            nome="Plano legado de controle",
            limite_cnpjs=1,
            limite_analises=1,
            preco=Decimal("29.90"),
            billing_type="monthly",
        )
        owner = models.User(
            id=41,
            email="one-time-owner@example.invalid",
            hashed_password="hash-de-teste",
        )
        outro = models.User(
            id=42,
            email="one-time-other@example.invalid",
            hashed_password="hash-de-teste",
        )
        empresa = models.Empresa(
            id=301, razao_social="Empresa one time", user_id=41
        )
        outra_empresa = models.Empresa(
            id=302, razao_social="Outra empresa", user_id=42
        )
        oferta = models.CheckoutOffer(
            id=7,
            codigo="document-one-time-company",
            nome_publico="Documentos avulsos",
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            estado="published",
            moeda="BRL",
            preco=Decimal("79.50"),
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
            contract_version=3,
        )
        oferta.capabilities = [
            models.CheckoutOfferCapability(codigo="document.extract"),
            models.CheckoutOfferCapability(codigo="document.validate"),
        ]
        ordem = models.OrdemCheckout(
            id=701,
            user_id=41,
            empresa_id=301,
            plano_id=None,
            offer_id=7,
            offer_code="document-one-time-company",
            contract_version=3,
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            subject_id=301,
            valor=Decimal("79.50"),
            moeda="BRL",
            estado="pending",
            idempotency_key="confirmation-order-701",
            provider_order_id="provider-order-701",
            checkout_url="https://checkout.example.invalid/order-701",
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
        )
        ordem.capabilities = [
            models.OrdemCheckoutCapability(codigo="document.extract"),
            models.OrdemCheckoutCapability(codigo="document.validate"),
        ]
        segunda = models.OrdemCheckout(
            id=702,
            user_id=42,
            empresa_id=302,
            plano_id=None,
            offer_id=7,
            offer_code="document-one-time-company",
            contract_version=3,
            vertical="document",
            commercial_model="one_time",
            subject_type="company",
            subject_id=302,
            valor=Decimal("79.50"),
            moeda="BRL",
            estado="pending",
            idempotency_key="confirmation-order-702",
            provider_order_id="provider-order-702",
            checkout_url="https://checkout.example.invalid/order-702",
            billing_period=None,
            usage_unit="document",
            usage_limit=7,
        )
        segunda.capabilities = [
            models.OrdemCheckoutCapability(codigo="document.extract"),
            models.OrdemCheckoutCapability(codigo="document.validate"),
        ]
        db.add_all([
            plano_legado,
            owner,
            outro,
            empresa,
            outra_empresa,
            oferta,
        ])
        db.flush()
        db.add_all([ordem, segunda])

    # O catalogo corrente deixa de representar o snapshot comprado.
    with Session.begin() as db:
        oferta = db.get(models.CheckoutOffer, 7)
        oferta.estado = "retired"
        oferta.preco = Decimal("999.99")
        oferta.usage_limit = 99
        oferta.capabilities[:] = [
            models.CheckoutOfferCapability(codigo="document.changed")
        ]
    _SessionRastreada.eventos = []
    return engine, Session


def _contagens(db, models):
    return {
        modelo.__name__: db.scalar(select(func.count()).select_from(modelo))
        for modelo in (
            models.EventoPagamento,
            models.Pagamento,
            models.CheckoutOfferGrant,
            models.CheckoutOfferGrantCapability,
            models.Entitlement,
        )
    }


def _snapshot_comercial(ordem):
    return (
        ordem.user_id,
        ordem.empresa_id,
        ordem.plano_id,
        ordem.offer_id,
        ordem.offer_code,
        ordem.contract_version,
        ordem.vertical,
        ordem.commercial_model,
        ordem.subject_type,
        ordem.subject_id,
        ordem.valor,
        ordem.moeda,
        ordem.billing_period,
        ordem.usage_unit,
        ordem.usage_limit,
        tuple(capability.codigo for capability in ordem.capabilities),
        ordem.provider_order_id,
        ordem.checkout_url,
    )


def _assert_sanitizado(erro, confirmation, *proibidos):
    assert type(erro) is confirmation.CheckoutOfferOneTimeConfirmationError
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in (
            "token", "segredo", "secret", "payload", "sql", "select ",
            "credencial", "credential", "interno", "valor", "moeda",
            "offer_code", "capabilities",
        ):
            assert marcador not in texto
        for proibido in proibidos:
            texto_proibido = str(proibido).lower()
            if texto_proibido:
                assert texto_proibido not in texto


def _assert_sessoes_fechadas():
    eventos = _SessionRastreada.eventos
    assert all(
        ("close", numero) in eventos
        for nome, numero in eventos
        if nome == "open"
    )


def _confirmar(confirmation, Session, ordem_id=701, notification_id="8128",
               payment_id="4719", valor=Decimal("79.50"), moeda="BRL"):
    return confirmation.CheckoutOfferOneTimeConfirmer(
        Session
    ).confirmar_pagamento_autorizado(
        ordem_id, notification_id, payment_id, valor, moeda
    )


def test_payments_multi_vertical_one_time_confirmation_contract_red():
    import app.services.checkout_offer_one_time_confirmation as confirmation

    from app import models

    assert issubclass(confirmation.CheckoutOfferOneTimeConfirmationError, Exception)
    assert list(signature(confirmation.CheckoutOfferOneTimeConfirmer).parameters) == [
        "session_factory"
    ]
    parametros = signature(
        confirmation.CheckoutOfferOneTimeConfirmer.confirmar_pagamento_autorizado
    ).parameters
    assert list(parametros) == [
        "self", "ordem_id", "notification_id", "payment_id", "valor", "moeda"
    ]
    assert all(parametro.kind is Parameter.POSITIONAL_OR_KEYWORD
               for parametro in parametros.values())

    engine, Session = _ambiente(models)
    comandos = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda _c, _u, statement, _p, _x, _m: comandos.append(statement),
    )
    with Session() as db:
        comercial_antes = _snapshot_comercial(db.get(models.OrdemCheckout, 701))

    resultado = _confirmar(confirmation, Session)
    assert sa_inspect(resultado, raiseerr=False) is None
    assert vars(resultado) == {
        "ordem_id": 701,
        "user_id": 41,
        "empresa_id": 301,
        "estado": "paid",
        "payment_id": "4719",
        "grant_id": resultado.grant_id,
        "usage_unit": "document",
        "usage_limit": 7,
        "usage_consumed": 0,
        "capabilities": ("document.extract", "document.validate"),
    }
    assert type(resultado.capabilities) is tuple
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        resultado.estado = "pending"
    str(resultado)
    repr(resultado)
    assert not any("checkout_offers" in comando.lower() for comando in comandos)
    _assert_sessoes_fechadas()

    with Session() as db:
        ordem = db.get(models.OrdemCheckout, 701)
        assert (ordem.estado, ordem.payment_id) == ("paid", "4719")
        assert _snapshot_comercial(ordem) == comercial_antes
        evento_pagamento = db.scalars(select(models.EventoPagamento)).one()
        pagamento = db.scalars(select(models.Pagamento)).one()
        grant = db.scalars(select(models.CheckoutOfferGrant)).one()
        assert (evento_pagamento.ordem_id, evento_pagamento.notification_id,
                evento_pagamento.payment_id) == (701, "8128", "4719")
        assert pagamento.ordem_checkout_id == 701
        assert pagamento.user_id == 41
        assert pagamento.plano_id is None
        assert pagamento.valor == Decimal("79.50")
        assert pagamento.mp_payment_id == "4719"
        assert pagamento.status == "approved"
        assert pagamento.confirmado_em is not None
        ordem_do_pagamento = db.get(
            models.OrdemCheckout,
            pagamento.ordem_checkout_id,
        )
        assert ordem_do_pagamento is not None
        assert ordem_do_pagamento.empresa_id == 301
        assert ordem_do_pagamento.moeda == "BRL"
        assert ordem_do_pagamento.id == ordem.id
        assert grant.ordem_id == 701
        assert (grant.usage_unit, grant.usage_limit, grant.usage_consumed,
                grant.estado) == ("document", 7, 0, "active")
        assert tuple(c.codigo for c in grant.capabilities) == (
            "document.extract", "document.validate"
        )
        assert all(not hasattr(c, "usage_limit") for c in grant.capabilities)
        assert all(not hasattr(c, "usage_consumed") for c in grant.capabilities)
        assert _contagens(db, models) == {
            "EventoPagamento": 1,
            "Pagamento": 1,
            "CheckoutOfferGrant": 1,
            "CheckoutOfferGrantCapability": 2,
            "Entitlement": 0,
        }
        user = db.get(models.User, 41)
        assert user.plano_id is None
        assert user.consulta_paga is False
        assert db.scalar(
            select(func.count()).select_from(models.RelatorioAnalise).where(
                models.RelatorioAnalise.pago.is_(True)
            )
        ) == 0

    # Retry por nova instancia/sessao devolve a mesma projecao sem duplicar.
    comandos.clear()
    repetido = _confirmar(confirmation, Session)
    assert repetido == resultado
    assert not any("checkout_offers" in comando.lower() for comando in comandos)
    with Session() as db:
        assert _contagens(db, models) == {
            "EventoPagamento": 1,
            "Pagamento": 1,
            "CheckoutOfferGrant": 1,
            "CheckoutOfferGrantCapability": 2,
            "Entitlement": 0,
        }
        assert db.scalars(select(models.CheckoutOfferGrant)).one().usage_consumed == 0

    # Colisoes e identidades nao canonicas falham fechadas.
    colisoes = (
        (701, "8128", "4720", Decimal("79.50"), "BRL"),
        (702, "8129", "4719", Decimal("79.50"), "BRL"),
        (999999, "8130", "4721", Decimal("79.50"), "BRL"),
    )
    identidades_invalidas = (
        (True, "8131", "4722", Decimal("79.50"), "BRL"),
        (0, "8131", "4722", Decimal("79.50"), "BRL"),
        (701.0, "8131", "4722", Decimal("79.50"), "BRL"),
        ("701", "8131", "4722", Decimal("79.50"), "BRL"),
        (702, True, "4722", Decimal("79.50"), "BRL"),
        (702, 8131, "4722", Decimal("79.50"), "BRL"),
        (702, "08131", "4722", Decimal("79.50"), "BRL"),
        (702, "8131\n", "4722", Decimal("79.50"), "BRL"),
        (702, "8131", True, Decimal("79.50"), "BRL"),
        (702, "8131", 4722, Decimal("79.50"), "BRL"),
        (702, "8131", "04722", Decimal("79.50"), "BRL"),
        (702, "8131", "4722 ", Decimal("79.50"), "BRL"),
    )
    for argumentos in colisoes + identidades_invalidas:
        with Session() as db:
            antes = _contagens(db, models)
            segunda_antes = tuple(
                getattr(db.get(models.OrdemCheckout, 702), campo)
                for campo in ("estado", "payment_id")
            )
        with pytest.raises(
            confirmation.CheckoutOfferOneTimeConfirmationError
        ) as capturada:
            _confirmar(confirmation, Session, *argumentos)
        _assert_sanitizado(capturada.value, confirmation, *argumentos)
        with Session() as db:
            assert _contagens(db, models) == antes
            segunda = db.get(models.OrdemCheckout, 702)
            assert (segunda.estado, segunda.payment_id) == segunda_antes

    monetarios_invalidos = (
        (Decimal("79.49"), "BRL"),
        (Decimal("79.51"), "BRL"),
        (Decimal("79.50"), "USD"),
        (Decimal("79.50"), "brl"),
        (True, "BRL"),
        (79, "BRL"),
        (79.50, "BRL"),
        ("79.50", "BRL"),
        (Decimal("0.00"), "BRL"),
        (Decimal("-0.01"), "BRL"),
        (Decimal("NaN"), "BRL"),
        (Decimal("Infinity"), "BRL"),
        (Decimal("79.5"), "BRL"),
        (Decimal("79.500"), "BRL"),
        (Decimal("79.501"), "BRL"),
        (Decimal("79.50"), ""),
        (Decimal("79.50"), None),
        (Decimal("79.50"), True),
        (Decimal("79.50"), 986),
    )
    for indice, (valor, moeda) in enumerate(monetarios_invalidos, start=8200):
        with Session() as db:
            antes = _contagens(db, models)
        with pytest.raises(
            confirmation.CheckoutOfferOneTimeConfirmationError
        ) as capturada:
            _confirmar(
                confirmation, Session, 702, str(indice), str(indice + 1000),
                valor, moeda,
            )
        _assert_sanitizado(capturada.value, confirmation, valor, moeda)
        with Session() as db:
            assert _contagens(db, models) == antes
            ordem = db.get(models.OrdemCheckout, 702)
            assert (ordem.estado, ordem.payment_id) == ("pending", None)

    # O contrato nao aceita qualquer autoridade comercial adicional.
    for extra in (
        {"user_id": 999}, {"empresa_id": 999}, {"offer_code": "browser"},
        {"capabilities": ("browser.injected",)}, {"usage_limit": 999},
        {"estado": "paid"},
    ):
        with pytest.raises(TypeError):
            confirmation.CheckoutOfferOneTimeConfirmer(
                Session
            ).confirmar_pagamento_autorizado(
                702, "8998", "8999", Decimal("79.50"), "BRL", **extra
            )

    # Corrupcoes persistidas que constraints atuais permitem parcialmente.
    casos_snapshot = {
        710: {"offer_id": None, "plano_id": 7},
        711: {"commercial_model": "monthly"},
        712: {"plano_id": 7},
        713: {"estado": "cancelled"},
        714: {"subject_type": "cpf"},
        715: {"subject_id": 999},
        716: {"user_id": 41},
        717: {"offer_code": ""},
        718: {"contract_version": 0},
        719: {"vertical": ""},
        720: {"usage_unit": " Document"},
        721: {"usage_limit": 0},
        722: {"provider_order_id": None},
        723: {"checkout_url": None},
    }
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("PRAGMA ignore_check_constraints=ON"))
        for ordem_id, mudancas in casos_snapshot.items():
            conn.execute(text(
                "INSERT INTO ordens_checkout "
                "(id,user_id,empresa_id,plano_id,offer_id,offer_code,contract_version,"
                "vertical,commercial_model,subject_type,subject_id,valor,moeda,estado,"
                "idempotency_key,provider_order_id,checkout_url,usage_unit,usage_limit) "
                "SELECT :id,user_id,empresa_id,plano_id,offer_id,offer_code,"
                "contract_version,vertical,commercial_model,subject_type,subject_id,"
                "valor,moeda,estado,:key,:provider,:url,usage_unit,usage_limit "
                "FROM ordens_checkout WHERE id=702"
            ), {
                "id": ordem_id,
                "key": f"corrupt-{ordem_id}",
                "provider": f"provider-{ordem_id}",
                "url": f"https://checkout.example.invalid/{ordem_id}",
            })
            for campo, valor in mudancas.items():
                conn.execute(text(
                    f"UPDATE ordens_checkout SET {campo}=:valor WHERE id=:id"
                ), {"valor": valor, "id": ordem_id})
            conn.execute(text(
                "INSERT INTO ordem_checkout_capabilities (ordem_id,codigo) "
                "VALUES (:id,'document.extract'),(:id,'document.validate')"
            ), {"id": ordem_id})
        # Capabilities vazias, duplicadas e invalidas (corrupcao historica).
        for ordem_id in (724, 725, 726):
            conn.execute(text(
                "INSERT INTO ordens_checkout "
                "(id,user_id,empresa_id,plano_id,offer_id,offer_code,contract_version,"
                "vertical,commercial_model,subject_type,subject_id,valor,moeda,estado,"
                "idempotency_key,provider_order_id,checkout_url,usage_unit,usage_limit) "
                "SELECT :id,user_id,empresa_id,plano_id,offer_id,offer_code,"
                "contract_version,vertical,commercial_model,subject_type,subject_id,"
                "valor,moeda,estado,:key,:provider,:url,usage_unit,usage_limit "
                "FROM ordens_checkout WHERE id=702"
            ), {"id": ordem_id, "key": f"cap-{ordem_id}",
                "provider": f"provider-{ordem_id}",
                "url": f"https://checkout.example.invalid/{ordem_id}"})
        conn.execute(text(
            "INSERT INTO ordem_checkout_capabilities (ordem_id,codigo) "
            "VALUES (725,'document.extract'),(725,'DOCUMENT.EXTRACT')"
        ))
        conn.execute(text(
            "INSERT INTO ordem_checkout_capabilities (ordem_id,codigo) "
            "VALUES (726,' Document.Invalid ')"
        ))
        conn.execute(text("PRAGMA ignore_check_constraints=OFF"))
        conn.execute(text("PRAGMA foreign_keys=ON"))

    for ordem_id in (*casos_snapshot, 724, 725, 726):
        with pytest.raises(confirmation.CheckoutOfferOneTimeConfirmationError):
            _confirmar(
                confirmation, Session, ordem_id, str(9000 + ordem_id),
                str(10000 + ordem_id),
            )
    with Session() as db:
        assert _contagens(db, models) == {
            "EventoPagamento": 1,
            "Pagamento": 1,
            "CheckoutOfferGrant": 1,
            "CheckoutOfferGrantCapability": 2,
            "Entitlement": 0,
        }

    # Falha interna na capability deve reverter toda a unidade atomica.
    segredo = "segredo-ultrassecreto-9931"

    def falhar_capability(_mapper, _connection, _target):
        raise RuntimeError(f"token payload SQL credencial interno {segredo}")

    event.listen(
        models.CheckoutOfferGrantCapability, "before_insert", falhar_capability
    )
    try:
        with pytest.raises(
            confirmation.CheckoutOfferOneTimeConfirmationError
        ) as capturada:
            _confirmar(confirmation, Session, 702, "9901", "9902")
        _assert_sanitizado(capturada.value, confirmation, segredo)
    finally:
        event.remove(
            models.CheckoutOfferGrantCapability, "before_insert", falhar_capability
        )
    _assert_sessoes_fechadas()
    with Session() as db:
        ordem = db.get(models.OrdemCheckout, 702)
        assert (ordem.estado, ordem.payment_id) == ("pending", None)
        assert db.scalar(select(func.count()).select_from(models.EventoPagamento).where(
            models.EventoPagamento.ordem_id == 702
        )) == 0
        assert db.scalar(select(func.count()).select_from(models.Pagamento).where(
            models.Pagamento.ordem_checkout_id == 702
        )) == 0
        assert db.scalar(select(func.count()).select_from(models.CheckoutOfferGrant).where(
            models.CheckoutOfferGrant.ordem_id == 702
        )) == 0
        assert db.scalar(
            select(func.count()).select_from(models.CheckoutOfferGrantCapability)
            .join(models.CheckoutOfferGrant)
            .where(models.CheckoutOfferGrant.ordem_id == 702)
        ) == 0
        assert db.scalar(select(func.count()).select_from(models.Entitlement)) == 0
        user = db.get(models.User, 42)
        assert user.plano_id is None
        assert user.consulta_paga is False
