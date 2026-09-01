"""Contrato RED offline para roteamento duravel da confirmacao de pagamento."""

from decimal import Decimal
from inspect import signature

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session as SASession, sessionmaker
from sqlalchemy.pool import StaticPool


class _SessionRastreada(SASession):
    instancias = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fechada = False
        self.__class__.instancias.append(self)

    def close(self):
        self.fechada = True
        return super().close()


class _DelegateEspiao:
    def __init__(self, resposta=None, falha=None):
        self.resposta = resposta
        self.falha = falha
        self.chamadas = []

    def confirmar_pagamento_autorizado(
        self, ordem_id, notification_id, payment_id, valor, moeda
    ):
        assert all(sessao.fechada for sessao in _SessionRastreada.instancias)
        self.chamadas.append(
            (ordem_id, notification_id, payment_id, valor, moeda)
        )
        if self.falha is not None:
            raise self.falha
        return self.resposta


def _ambiente(models):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine, class_=_SessionRastreada, expire_on_commit=True
    )

    # Fase 1: dependencias soberanas, materializadas antes das ordens.
    with Session.begin() as db:
        db.add(models.Plano(
            id=7, nome="Plano legado", limite_cnpjs=1, limite_analises=1,
            preco=Decimal("29.90"), billing_type="monthly",
        ))
        db.add(models.User(
            id=41, email="routing-owner@example.invalid",
            hashed_password="hash-de-teste", plano_id=7,
        ))
        db.add(models.Empresa(
            id=301, razao_social="Empresa routing", user_id=41,
        ))
        db.add_all([
            models.CheckoutOffer(
                id=11, codigo="document-one-time-company",
                nome_publico="Documento avulso", vertical="document",
                commercial_model="one_time", subject_type="company",
                estado="published", moeda="BRL", preco=Decimal("79.50"),
                billing_period=None, usage_unit="document", usage_limit=7,
                contract_version=3,
            ),
            models.CheckoutOffer(
                id=12, codigo="tax-monthly-company",
                nome_publico="Fiscal mensal", vertical="tax",
                commercial_model="monthly", subject_type="company",
                estado="published", moeda="BRL", preco=Decimal("49.90"),
                billing_period="month", usage_unit=None, usage_limit=None,
                contract_version=2,
            ),
        ])
        db.flush()
        assert all(db.get(modelo, identidade) is not None for modelo, identidade in (
            (models.Plano, 7), (models.User, 41), (models.Empresa, 301),
            (models.CheckoutOffer, 11), (models.CheckoutOffer, 12),
        ))

    def oferta(ordem_id, offer_id, code, model, vertical, billing, unit, limit):
        ordem = models.OrdemCheckout(
            id=ordem_id, user_id=41, empresa_id=301, plano_id=None,
            offer_id=offer_id, offer_code=code, contract_version=3,
            vertical=vertical, commercial_model=model, subject_type="company",
            subject_id=301, valor=Decimal("79.50"), moeda="BRL",
            estado="pending", idempotency_key=f"routing-{ordem_id}",
            billing_period=billing, usage_unit=unit, usage_limit=limit,
        )
        if model == "one_time":
            ordem.capabilities = [
                models.OrdemCheckoutCapability(codigo="document.extract"),
                models.OrdemCheckoutCapability(codigo="document.validate"),
            ]
        elif model == "monthly":
            ordem.capabilities = [
                models.OrdemCheckoutCapability(codigo="tax.monitor"),
            ]
        return ordem

    # Fase 2: ordens validas primeiro; corrupcoes sao simuladas depois.
    with Session.begin() as db:
        db.add(models.OrdemCheckout(
            id=101, user_id=41, empresa_id=301, plano_id=7,
            valor=Decimal("29.90"), moeda="BRL", estado="pending",
            idempotency_key="routing-101",
        ))
        db.add(oferta(
            102, 11, "document-one-time-company", "one_time", "document",
            None, "document", 7,
        ))
        mensal = oferta(
            103, 12, "tax-monthly-company", "monthly", "tax",
            "month", None, None,
        )
        mensal.contract_version = 2
        db.add(mensal)
        for ordem_id in range(104, 112):
            db.add(oferta(
                ordem_id, 11, "document-one-time-company", "one_time",
                "document", None, "document", 7,
            ))

    corrupcoes = {
        104: "plano_id = 7",                         # plano + offer
        105: "offer_id = NULL, offer_code = NULL",  # ambos ausentes
        106: "commercial_model = 'negotiated'",
        107: "commercial_model = 'desconhecido'",
        108: "commercial_model = NULL",             # offer sem model
        109: "offer_code = ''",                     # identidade invalida
        110: "subject_id = NULL",                   # parcial
        111: "plano_id = 7, offer_id = NULL, "
             "commercial_model = 'monthly'",        # legado contaminado
    }
    with engine.begin() as connection:
        connection.execute(text("PRAGMA ignore_check_constraints=ON"))
        for ordem_id, atribuicoes in corrupcoes.items():
            connection.execute(text(
                f"UPDATE ordens_checkout SET {atribuicoes} WHERE id=:ordem_id"
            ), {"ordem_id": ordem_id})
        connection.execute(text("PRAGMA ignore_check_constraints=OFF"))

    _SessionRastreada.instancias = []
    return engine, Session


def _contagens(Session, models):
    with Session() as db:
        return tuple(db.scalar(select(func.count()).select_from(modelo)) for modelo in (
            models.OrdemCheckout, models.Pagamento, models.EventoPagamento,
            models.CheckoutOfferGrant, models.Entitlement,
        ))


def _assert_sanitizado(erro, classe, *proibidos):
    assert type(erro) is classe
    assert str(erro)
    for representacao in (str(erro), repr(erro)):
        conteudo = representacao.lower()
        for marcador in (
            "token", "segredo", "payload", "select", "insert", "update",
            "delete", "credencial", "valor", "moeda", "delegate",
            "legacy", "one_time", "notification", "payment",
        ):
            assert marcador not in conteudo
        for proibido in proibidos:
            assert str(proibido).lower() not in conteudo
    assert erro.__cause__ is None


def _preflight_fixture():
    from app import models

    engine, Session = _ambiente(models)
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    with Session() as db:
        ordens = {identidade: db.get(models.OrdemCheckout, identidade)
                  for identidade in range(101, 112)}
        assert all(ordens.values())
        capabilities = {
            identidade: tuple(capability.codigo for capability in ordem.capabilities)
            for identidade, ordem in ordens.items()
        }
        assert capabilities[101] == ()
        assert capabilities[102] == ("document.extract", "document.validate")
        assert capabilities[103] == ("tax.monitor",)
        assert all(
            capabilities[identidade] == ("document.extract", "document.validate")
            for identidade in range(104, 112)
        )
        assert (ordens[101].plano_id, ordens[101].offer_id,
                ordens[101].commercial_model) == (7, None, None)
        assert ordens[101].valor == Decimal("29.90")
        assert (ordens[102].plano_id, ordens[102].offer_id,
                ordens[102].offer_code, ordens[102].commercial_model) == (
                    None, 11, "document-one-time-company", "one_time"
                )
        assert ordens[102].valor == Decimal("79.50")
        assert (ordens[103].offer_id, ordens[103].commercial_model) == (12, "monthly")
        assert (ordens[104].plano_id, ordens[104].offer_id) == (7, 11)
        assert (ordens[105].plano_id, ordens[105].offer_id) == (None, None)
        assert ordens[106].commercial_model == "negotiated"
        assert ordens[107].commercial_model == "desconhecido"
        assert ordens[108].commercial_model is None
        assert ordens[109].offer_code == ""
        assert ordens[110].subject_id is None
        assert (ordens[111].plano_id, ordens[111].commercial_model) == (7, "monthly")
    assert _contagens(Session, models) == (11, 0, 0, 0, 0)
    return "PREFLIGHT PASS"


def test_payments_durable_webhook_confirmation_routing_contract_red():
    import app.services.checkout_durable_webhook_confirmation_routing as routing

    from app import models

    erro_publico = routing.CheckoutDurableWebhookConfirmationRoutingError
    metodo = routing.CheckoutDurableWebhookConfirmationRouter.confirmar_pagamento_autorizado
    assert list(signature(routing.CheckoutDurableWebhookConfirmationRouter).parameters) == [
        "session_factory", "legacy_confirmer", "one_time_confirmer",
    ]
    assert list(signature(metodo).parameters) == [
        "self", "ordem_id", "notification_id", "payment_id", "valor", "moeda",
    ]

    engine, Session = _ambiente(models)
    sql = []
    event.listen(
        engine, "before_cursor_execute",
        lambda _c, _u, statement, _p, _x, _m: sql.append(statement),
    )
    retorno_legacy = object()
    retorno_one_time = object()
    legacy = _DelegateEspiao(retorno_legacy)
    one_time = _DelegateEspiao(retorno_one_time)
    router = routing.CheckoutDurableWebhookConfirmationRouter(
        Session, legacy, one_time
    )
    valor_legacy = Decimal("29.90")
    argumentos_legacy = ("8128", "4719", valor_legacy, "BRL")
    valor_one_time = Decimal("79.50")
    argumentos_one_time = ("8129", "4720", valor_one_time, "BRL")
    antes = _contagens(Session, models)

    resposta = router.confirmar_pagamento_autorizado(101, *argumentos_legacy)
    assert resposta is retorno_legacy
    assert legacy.chamadas == [(101, *argumentos_legacy)]
    assert legacy.chamadas[0][3] is valor_legacy
    assert one_time.chamadas == []

    resposta = router.confirmar_pagamento_autorizado(102, *argumentos_one_time)
    assert resposta is retorno_one_time
    assert one_time.chamadas == [(102, *argumentos_one_time)]
    assert one_time.chamadas[0][3] is valor_one_time
    assert legacy.chamadas == [(101, *argumentos_legacy)]
    assert _contagens(Session, models) == antes

    sql_roteamento = tuple(sql)
    assert any(
        comando.lstrip().lower().startswith("select")
        and "ordens_checkout" in comando.lower()
        for comando in sql_roteamento
    )
    assert not any("checkout_offers" in comando.lower() for comando in sql_roteamento)
    assert not any(
        comando.lstrip().lower().startswith(("insert", "update", "delete"))
        for comando in sql_roteamento
    )

    chamadas_validas = (list(legacy.chamadas), list(one_time.chamadas))
    for ordem_id in (103, 104, 105, 106, 107, 108, 109, 110, 111, 999999):
        with pytest.raises(erro_publico) as capturada:
            router.confirmar_pagamento_autorizado(ordem_id, *argumentos_one_time)
        _assert_sanitizado(
            capturada.value, erro_publico, ordem_id, *argumentos_one_time
        )
        assert (legacy.chamadas, one_time.chamadas) == chamadas_validas
        assert _contagens(Session, models) == antes

    for ordem_id in (True, 101.0, "101", 0, -1, None):
        with pytest.raises(erro_publico):
            router.confirmar_pagamento_autorizado(ordem_id, *argumentos_one_time)
    assert (legacy.chamadas, one_time.chamadas) == chamadas_validas

    mensagem = None
    dependencias_invalidas = (
        (None, legacy, one_time),
        (42, legacy, one_time),
        (Session, object(), one_time),
        (Session, legacy, object()),
    )
    for dependencias in dependencias_invalidas:
        with pytest.raises(erro_publico) as capturada:
            routing.CheckoutDurableWebhookConfirmationRouter(*dependencias)
        _assert_sanitizado(capturada.value, erro_publico)
        mensagem = mensagem or str(capturada.value)
        assert str(capturada.value) == mensagem

    segredo = "token segredo payload SELECT credencial 9931"

    class _SessaoGetFalha:
        def get(self, *_args):
            raise RuntimeError(segredo)

        def close(self):
            pass

    class _SessaoCloseFalha:
        def get(self, *_args):
            return None

        def close(self):
            raise RuntimeError(segredo)

    falhas_sessao = (
        lambda: (_ for _ in ()).throw(RuntimeError(segredo)),
        lambda: _SessaoGetFalha(),
        lambda: _SessaoCloseFalha(),
    )
    for fabrica in falhas_sessao:
        antes_chamadas = (list(legacy.chamadas), list(one_time.chamadas))
        with pytest.raises(erro_publico) as capturada:
            routing.CheckoutDurableWebhookConfirmationRouter(
                fabrica, legacy, one_time
            ).confirmar_pagamento_autorizado(101, *argumentos_legacy)
        _assert_sanitizado(
            capturada.value, erro_publico, segredo, *argumentos_legacy
        )
        assert (legacy.chamadas, one_time.chamadas) == antes_chamadas

    casos_falha_delegate = (
        ("legacy", 101, argumentos_legacy, valor_legacy),
        ("one_time", 102, argumentos_one_time, valor_one_time),
    )
    for selecionado, ordem_id, argumentos, valor in casos_falha_delegate:
        falho = _DelegateEspiao(falha=RuntimeError(segredo + selecionado))
        candidato = routing.CheckoutDurableWebhookConfirmationRouter(
            Session,
            falho if selecionado == "legacy" else legacy,
            falho if selecionado == "one_time" else one_time,
        )
        with pytest.raises(erro_publico) as capturada:
            candidato.confirmar_pagamento_autorizado(ordem_id, *argumentos)
        _assert_sanitizado(capturada.value, erro_publico, segredo, selecionado)
        assert len(falho.chamadas) == 1
        assert falho.chamadas[0] == (ordem_id, *argumentos)
        assert falho.chamadas[0][3] is valor
        assert _contagens(Session, models) == antes
